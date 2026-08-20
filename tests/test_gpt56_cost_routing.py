from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from clutch.cli import main
from clutch.evaluation import EmpiricalRouter, EvalObservation, load_eval_profiles
from clutch.fahrer import Fahrer
from clutch.fahrtenbuch import FahrtEintrag, Fahrtenbuch
from clutch.gas_bremse import GasBremse
from clutch.getriebe import Getriebe
from clutch.kupplung import FahrtConfig
from clutch.motorblock import MotorErgebnis, OpenAIMotor
from clutch.pricing import UsageRecord, cost_for_gang


ALL_EFFORTS = ["none", "low", "medium", "high", "xhigh", "max"]


@pytest.fixture()
def getriebe():
    return Getriebe()


@pytest.mark.parametrize(
    ("name", "model_id", "input_rate", "cached_rate", "output_rate"),
    [
        ("openai-gpt-5.6-luna", "gpt-5.6-luna", 0.2, 0.02, 1.2),
        ("openai-gpt-5.6-terra", "gpt-5.6-terra", 2.0, 0.2, 12.0),
        ("openai-gpt-5.6-sol", "gpt-5.6-sol", 5.0, 0.5, 30.0),
    ],
)
def test_catalog_has_versioned_gpt56_facts(
    getriebe, name, model_id, input_rate, cached_rate, output_rate,
):
    gang = getriebe.gang(name)
    assert gang.model_id == model_id
    assert gang.efforts == ALL_EFFORTS
    assert gang.reasoning_modes == ["standard", "fast"]
    assert gang.pricing.input_per_million == input_rate
    assert gang.pricing.cached_input_per_million == cached_rate
    assert gang.pricing.output_per_million == output_rate
    assert gang.pricing.cache_write_multiplier == 1.25
    assert gang.pricing.long_context_threshold == 272_000
    assert gang.pricing.version == "openai-gpt-5.6-2026-07-30"
    assert gang.pricing.checked_at == "2026-08-20"
    assert gang.pricing.effective_at == "2026-07-30"
    assert gang.pricing.source_url.startswith("https://developers.openai.com/")
    assert not gang.pricing.is_stale(date(2026, 8, 20))
    assert gang.pricing.is_stale(date(2026, 10, 5))


def test_cost_mixed_cache_write_and_reasoning_exactly_once(getriebe):
    result = cost_for_gang(
        getriebe.gang("openai-gpt-5.6-terra"),
        UsageRecord(
            input_tokens=200_000,
            cached_input_tokens=20_000,
            cache_write_tokens=10_000,
            output_tokens=100_000,
            reasoning_tokens=80_000,
            data_status="observed",
        ),
        as_of=date(2026, 8, 20),
    )
    assert result.known
    assert result.uncached_input_tokens == 170_000
    assert result.input_usd == pytest.approx(0.34)
    assert result.cached_input_usd == pytest.approx(0.004)
    assert result.cache_write_usd == pytest.approx(0.025)
    assert result.output_usd == pytest.approx(1.2)
    assert result.total_usd == pytest.approx(1.569)
    assert result.reasoning_tokens == 80_000
    assert result.reasoning_tokens_billed_separately is False


def test_long_context_boundary_and_fast_tier(getriebe):
    gang = getriebe.gang("openai-gpt-5.6-sol")
    at_boundary = cost_for_gang(
        gang,
        UsageRecord(input_tokens=272_000, output_tokens=100_000, data_status="assumed"),
    )
    above = cost_for_gang(
        gang,
        UsageRecord(input_tokens=272_001, output_tokens=100_000, data_status="assumed"),
    )
    fast = cost_for_gang(
        gang,
        UsageRecord(
            input_tokens=272_001,
            output_tokens=100_000,
            tool_fees_usd=0.25,
            service_tier="fast",
            data_status="assumed",
        ),
    )
    assert at_boundary.long_context is False
    assert at_boundary.total_usd == pytest.approx(4.36)
    assert above.long_context is True
    assert above.total_usd == pytest.approx(7.22001)
    assert fast.total_usd == pytest.approx(14.69002)
    assert fast.tool_fees_usd == pytest.approx(0.25)


def test_missing_usage_is_unknown_not_zero_cost(getriebe):
    result = cost_for_gang(
        getriebe.gang("openai-gpt-5.6-luna"),
        UsageRecord(data_status="unknown"),
    )
    assert not result.known
    assert result.total_usd is None
    assert result.data_status == "unknown"


def _config(getriebe, name="openai-gpt-5.6-terra", effort="high", **kwargs):
    return FahrtConfig(
        gang=getriebe.gang(name),
        gas=GasBremse().stellung(0.5),
        muster="einzelfahrt",
        effort=effort,
        **kwargs,
    )


@pytest.mark.parametrize("effort", ALL_EFFORTS)
def test_responses_payload_transports_requested_and_effective_effort(getriebe, effort):
    config = _config(getriebe, effort=effort)
    payload = OpenAIMotor(api_key="test")._build_payload(config, "test")
    assert payload["reasoning"]["effort"] == effort
    assert config.effort == effort
    assert config.effective_effort == effort


def test_max_delegate_never_leaks_to_api_without_delegate(getriebe):
    motor = OpenAIMotor(api_key="test")
    with pytest.raises(ValueError, match="is_delegate=True"):
        motor._build_payload(_config(getriebe, effort="max-delegate"), "test")

    delegated = _config(getriebe, effort="max-delegate", is_delegate=True)
    payload = motor._build_payload(delegated, "test")
    assert payload["reasoning"]["effort"] == "max"
    assert "max-delegate" not in json.dumps(payload)
    assert delegated.effective_effort == "max"


def test_responses_missing_usage_remains_unmetered(monkeypatch, getriebe):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": "gpt-5.6-terra", "output_text": "ok"}

    monkeypatch.setitem(
        sys.modules,
        "requests",
        SimpleNamespace(post=lambda *args, **kwargs: FakeResponse()),
    )
    result = OpenAIMotor(api_key="test").ausfuehren(_config(getriebe), "test")
    assert result.erfolg
    assert result.usage_status == "unknown"
    assert result.cost_usd is None
    assert result.cost_breakdown["known"] is False


def _observations(model, effort, qualities, costs, latencies, retry=0.0, task="coding_patch"):
    return [
        EvalObservation(
            task_class=task,
            eval_case=f"case-{index}",
            model_id=model,
            effort=effort,
            quality_score=quality,
            passed=quality >= 0.8,
            cost_usd=cost,
            latency_seconds=latency,
            retry_fallback_cost_usd=retry,
        )
        for index, (quality, cost, latency) in enumerate(zip(qualities, costs, latencies))
    ]


def test_empirical_router_quality_gate_expected_cost_and_pareto():
    rows = []
    rows += _observations("gpt-5.6-luna", "high", [0.7] * 5, [0.01] * 5, [2] * 5)
    rows += _observations("gpt-5.6-terra", "medium", [0.9] * 5, [0.10] * 5, [4] * 5, retry=0.02)
    rows += _observations("gpt-5.6-sol", "medium", [0.95] * 5, [0.50] * 5, [9] * 5)
    decision = EmpiricalRouter(min_samples=5).evaluate(
        "coding_patch",
        rows,
        min_quality=0.85,
        min_pass_rate=0.8,
        max_latency_seconds=10,
    )
    assert decision.status == "measured"
    assert decision.model_id == "gpt-5.6-terra"
    assert not decision.sol_required_by_evidence
    terra = next(c for c in decision.candidates if c.model_id == "gpt-5.6-terra")
    luna = next(c for c in decision.candidates if c.model_id == "gpt-5.6-luna")
    assert terra.expected_cost_per_success_usd == pytest.approx(0.12)
    assert terra.retry_fallback_cost_usd == pytest.approx(0.1)
    assert terra.on_pareto_frontier
    assert not luna.eligible


def test_empirical_router_cold_start_has_no_fabricated_score():
    decision = EmpiricalRouter(min_samples=5).evaluate(
        "bulk_transformation",
        [],
        min_quality=0.8,
        min_pass_rate=0.9,
    )
    assert decision.status == "cold_start"
    assert decision.model_id == "gpt-5.6-luna"
    assert decision.candidates == ()
    profiles = load_eval_profiles()
    assert profiles["data_status"] == "evaluation-plan-not-measurement"
    assert "intelligence" not in json.dumps(profiles).lower()


def test_fahrer_applies_explicit_task_class_cold_start(tmp_path):
    fahrer = Fahrer(db_path=tmp_path / "clutch.db")
    result = fahrer.fahren(
        "Transformiere die Datensätze",
        handler=lambda config, task: MotorErgebnis(
            text="ok", model_id=config.model_id, provider=config.provider,
        ),
        kontext={"task_class": "bulk_transformation"},
    )
    assert result.config.model_id == "gpt-5.6-luna"
    assert result.config.effort == "medium"
    assert "empirical:cold_start" in result.config.entscheidungs_grund


def test_sqlite_migration_and_usage_cost_persistence(tmp_path):
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE fahrten (fahrt_id TEXT PRIMARY KEY, strecken_typ TEXT NOT NULL, "
        "gang TEXT NOT NULL, provider TEXT NOT NULL, gas REAL, muster TEXT NOT NULL, "
        "total_tokens INTEGER, thinking_tokens INTEGER, tool_calls INTEGER, files_read INTEGER, "
        "files_changed INTEGER, latenz_sekunden REAL, erfolg INTEGER, wiederholungen INTEGER, "
        "user_korrekturen INTEGER, fehler_anzahl INTEGER, ist_erkundung INTEGER, "
        "entscheidungs_grund TEXT, timestamp REAL NOT NULL)"
    )
    conn.commit()
    conn.close()

    buch = Fahrtenbuch(db_path)
    buch.eintragen(FahrtEintrag(
        fahrt_id="f-1",
        strecken_typ="testfahrt",
        gang="openai-gpt-5.6-terra",
        provider="openai",
        gas=0.5,
        muster="einzelfahrt",
        model_id="gpt-5.6-terra",
        requested_effort="high",
        effective_effort="high",
        mode="standard",
        service_tier="default",
        task_class="coding_patch",
        eval_case="coding_unit_fix",
        input_tokens=100,
        cached_input_tokens=20,
        cache_write_tokens=10,
        output_tokens=30,
        reasoning_tokens=5,
        usage_status="observed",
        price_version="openai-gpt-5.6-2026-07-30",
        cost_usd=0.001,
    ))
    assert buch.eval_label_setzen("f-1", 0.9, True)
    row = buch.eval_daten("coding_patch")[0]
    assert row["requested_effort"] == "high"
    assert row["reasoning_tokens"] == 5
    assert row["cost_usd"] == pytest.approx(0.001)


def test_cli_cost_json_uses_versioned_source(capsys):
    rc = main([
        "cost", "--model", "gpt-5.6-luna", "--input", "100000",
        "--output", "0", "--json",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_usd"] == pytest.approx(0.02)
    assert data["data_status"] == "assumed"
    assert data["pricing_version"] == "openai-gpt-5.6-2026-07-30"


def test_generated_price_graphic_is_explicitly_non_eval_and_dated():
    svg = (Path(__file__).parents[1] / "docs" / "gpt56_price_facts.svg").read_text(encoding="utf-8")
    assert "data status: official price facts" in svg
    assert "not a performance evaluation" in svg
    assert "effective: 2026-07-30" in svg
    assert "checked: 2026-08-20" in svg
    assert "confidence: source-verified tariff" in svg
    assert "empirical quality sample: n/a" in svg


def test_historical_images_are_unverified_without_private_paths():
    root = Path(__file__).parents[1]
    docs = (root / "docs" / "GPT56_COST_ROUTING.md").read_text(encoding="utf-8")
    assert "unverified historical input" in docs
    assert "2649c2caa1b9cc041db97c9edd2734d1ada7c5e9a4f98ade04d112781e40366c" in docs
    assert "6450f373a9e1ec9b842cd2a6fce4cdcdffa4d6496fb46c0f5bea1fa47bd8bd8c" in docs
