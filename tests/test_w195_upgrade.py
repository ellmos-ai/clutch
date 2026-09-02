"""Regressionstests fuer W195: U1 Verfuegbarkeit, U2 Overlay, U3 Routingwuensche."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from clutch.availability import AvailabilityStore, _exclusive_file_lock
from clutch.bordcomputer import Bordcomputer
from clutch.cli import main
from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag
from clutch.fahrer import Fahrer
from clutch.getriebe import Gang, Getriebe
from clutch.kupplung import Kupplung
from clutch.strecke import StreckenAnalyse
from clutch.user_overrides import lade_user_overrides, speichere_user_overrides


def _entry(index: int, success: bool = False, provider: str = "google") -> FahrtEintrag:
    return FahrtEintrag(
        fahrt_id=f"fahrt-{index}",
        strecken_typ="bundesstrasse",
        gang="gemini-pro",
        provider=provider,
        gas=0.7,
        muster="einzelfahrt",
        erfolg=success,
    )


def test_u1_circuit_persistiert_zwischen_prozessen(tmp_path):
    availability = tmp_path / "availability.json"
    buch = Fahrtenbuch(tmp_path / "clutch.db")
    first = Bordcomputer(
        buch,
        availability_path=availability,
        model_provider={"gemini-pro": "google"},
    )
    for index in range(3):
        first.fahrt_auswerten(_entry(index))

    second = Bordcomputer(
        buch,
        availability_path=availability,
        model_provider={"gemini-pro": "google"},
    )
    status = second.pruefe()
    assert "gemini-pro" in status.gesperrte_modelle
    persisted = json.loads(availability.read_text(encoding="utf-8"))
    circuit = persisted["circuits"]["gemini-pro"]
    assert circuit["state"] == "open"
    assert circuit["until"] > circuit["opened_at"]
    circuit["opened_at"] = time.time() - 400
    circuit["until"] = circuit["opened_at"] + circuit["cooldown_seconds"]
    availability.write_text(json.dumps(persisted), encoding="utf-8")
    third = Bordcomputer(
        buch,
        availability_path=availability,
        model_provider={"gemini-pro": "google"},
    )
    half_open = third.pruefe().verfuegbarkeit["gemini-pro"]
    assert half_open["state"] == "half_open"
    assert json.loads(availability.read_text(encoding="utf-8"))["circuits"]["gemini-pro"]["state"] == "half_open"

    race_path = tmp_path / "race-availability.json"
    race_store = AvailabilityStore(race_path)
    script = (
        "import sys; from pathlib import Path; "
        "from clutch.availability import AvailabilityStore; "
        "AvailabilityStore(Path(sys.argv[1])).record_provider_failure('openai', '429')"
    )
    with _exclusive_file_lock(race_store.lock_path):
        process = subprocess.Popen([sys.executable, "-c", script, str(race_path)])
        time.sleep(0.2)
        assert process.poll() is None
    process.wait(timeout=5)
    assert process.returncode == 0
    assert "openai" in race_store.read()["provider_blocks"]


def test_u1_token_budget_rot_sperrt_anthropic_bis_reset(tmp_path):
    now = time.time()
    token_budget = tmp_path / "token_budget.json"
    token_budget.write_text(json.dumps({
        "written_at": now,
        "five_hour": {"used_percentage": 95, "resets_at": now + 1800},
        "seven_day": {"used_percentage": 20, "resets_at": now + 86400},
    }), encoding="utf-8")
    sparmodus = tmp_path / "sparmodus.json"
    sparmodus.write_text('{"mode":"off"}', encoding="utf-8")
    bc = Bordcomputer(
        Fahrtenbuch(tmp_path / "clutch.db"),
        availability_path=tmp_path / "availability.json",
        token_budget_path=token_budget,
        sparmodus_path=sparmodus,
        model_provider={"claude-sonnet": "anthropic", "gemini-pro": "google"},
    )

    status = bc.pruefe()
    assert "claude-sonnet" in status.gesperrte_modelle
    assert "gemini-pro" not in status.gesperrte_modelle
    detail = status.verfuegbarkeit["claude-sonnet"]
    assert detail["source"] == "token_budget"
    assert detail["until"] == now + 1800
    assert detail["resets_at"] == now + 1800

    token_budget.unlink()
    second = Bordcomputer(
        Fahrtenbuch(tmp_path / "second.db"),
        availability_path=tmp_path / "availability.json",
        token_budget_path=token_budget,
        sparmodus_path=sparmodus,
        model_provider={"claude-sonnet": "anthropic"},
    )
    assert "claude-sonnet" in second.pruefe().gesperrte_modelle


def test_u1_sieben_tage_rot_sperrt_bis_zum_sieben_tage_reset(tmp_path):
    now = time.time()
    token_budget = tmp_path / "token_budget.json"
    token_budget.write_text(json.dumps({
        "written_at": now,
        "five_hour": {"used_percentage": 10, "resets_at": now + 1800},
        "seven_day": {"used_percentage": 94, "resets_at": now + 7200},
    }), encoding="utf-8")
    bc = Bordcomputer(
        Fahrtenbuch(tmp_path / "clutch.db"),
        availability_path=tmp_path / "availability.json",
        token_budget_path=token_budget,
        sparmodus_path=tmp_path / "missing-sparmodus.json",
        model_provider={"claude-sonnet": "anthropic"},
    )
    detail = bc.pruefe().verfuegbarkeit["claude-sonnet"]
    assert detail["until"] == now + 7200
    assert "7d" in detail["reason"]


def test_u1_stale_token_budget_ist_keine_sperrquelle(tmp_path):
    now = time.time()
    token_budget = tmp_path / "token_budget.json"
    token_budget.write_text(json.dumps({
        "written_at": now - 7200,
        "five_hour": {"used_percentage": 99, "resets_at": now + 1800},
    }), encoding="utf-8")
    bc = Bordcomputer(
        Fahrtenbuch(tmp_path / "clutch.db"),
        availability_path=tmp_path / "availability.json",
        token_budget_path=token_budget,
        sparmodus_path=tmp_path / "missing-sparmodus.json",
        model_provider={"claude-sonnet": "anthropic"},
    )
    assert "claude-sonnet" not in bc.pruefe().gesperrte_modelle


def test_u1_notaus_und_provider_fehler_werden_persistiert(tmp_path):
    sparmodus = tmp_path / "sparmodus.json"
    sparmodus.write_text('{"mode":"notaus","resets_at":"2030-01-01T00:00:00Z"}', encoding="utf-8")
    availability = tmp_path / "availability.json"
    bc = Bordcomputer(
        Fahrtenbuch(tmp_path / "clutch.db"),
        availability_path=availability,
        token_budget_path=tmp_path / "missing-budget.json",
        sparmodus_path=sparmodus,
        model_provider={"claude-sonnet": "anthropic", "openai-codex": "openai"},
    )
    assert "claude-sonnet" in bc.pruefe().gesperrte_modelle
    warnings = bc.fahrt_auswerten(
        _entry(1, provider="openai"),
        fehlertext="HTTP 429 rate-limit reached",
    )
    assert any("Kontingentsperre" in warning for warning in warnings)
    assert "openai-codex" in bc.pruefe().gesperrte_modelle

    sparmodus.write_text('{"mode":"notaus"}', encoding="utf-8")
    bc.pruefe()
    notaus = json.loads(availability.read_text(encoding="utf-8"))["provider_blocks"]["anthropic"]["sparmodus"]
    assert notaus["until"] is not None


def test_u1_agy_exit_null_ohne_ausgabe_setzt_provider_sperre(tmp_path):
    bc = Bordcomputer(
        Fahrtenbuch(tmp_path / "clutch.db"),
        availability_path=tmp_path / "availability.json",
        token_budget_path=tmp_path / "missing-budget.json",
        sparmodus_path=tmp_path / "missing-sparmodus.json",
        model_provider={"agy-gemini": "agy"},
    )
    entry = _entry(1, success=True, provider="agy")
    bc.fahrt_auswerten(entry, output_text="")
    detail = bc.pruefe().verfuegbarkeit["agy-gemini"]
    assert detail["source"] == "provider_error"
    assert "Exit 0 ohne Ausgabe" in detail["reason"]

    corrupt = tmp_path / "corrupt-availability.json"
    corrupt.write_text("{kaputt", encoding="utf-8")
    before = corrupt.read_bytes()
    with pytest.raises(ValueError, match="Ungueltige Verfuegbarkeitsdatei"):
        AvailabilityStore(corrupt).record_provider_failure("openai", "429")
    assert corrupt.read_bytes() == before


def test_u2_overlay_deaktiviert_alias_begrenzt_gang_und_kosten(tmp_path):
    overlay = tmp_path / "user_overrides.json"
    speichere_user_overrides({
        "disabled_models": ["sonnet"],
        "preferred_models": ["codex"],
        "preferred_providers": ["openai"],
        "model_max_gang": {"openai-codex": 3},
        "aliases": {"sonnet": "claude-sonnet", "codex": "openai-codex"},
        "model_cost_override": {
            "ollama-kimi-k2": {"kosten_input_1k": 0.001, "kosten_output_1k": 0.004},
            "cloud-custom": {"kosten_input_1k": 0.002, "kosten_output_1k": 0.006},
        },
    }, overlay)

    getriebe = Getriebe(overrides_path=overlay)
    assert getriebe.gang("sonnet") is None
    assert getriebe.gang("sonnet", einschliesslich_deaktiviert=True).name == "claude-sonnet"
    assert getriebe.gang("codex").gang == 3
    assert getriebe.gang("ollama-kimi-k2").kosten_output_1k == 0.004
    assert getriebe.preferred_models == ["openai-codex"]
    assert getriebe.preferred_providers == ["openai"]
    discovered = Gang("cloud-custom", "ollama", "custom:cloud", 4, "hoch", 0, 0)
    getriebe.registriere_gang(discovered)
    assert discovered.kosten_output_1k == 0.006
    kupplung = Kupplung(getriebe)
    kupplung.set_erkundungsrate(0)
    config = kupplung.einlegen(StreckenAnalyse().analysiere("smoke"))
    assert config.gang.name == "openai-codex"
    with pytest.raises(RuntimeError, match="kein verfuegbarer Gang"):
        kupplung.einlegen(StreckenAnalyse().analysiere("smoke"), budget_zone="red")


def test_u2_cli_disable_enable_und_prefer_schreibt_nur_clutch_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLUTCH_HOME", str(tmp_path / "clutch-home"))
    assert main(["models", "disable", "claude-sonnet", "--json"]) == 0
    capsys.readouterr()
    assert "claude-sonnet" in lade_user_overrides()["disabled_models"]
    assert main(["config", "prefer", "codex", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["preferred"] == "openai-codex"
    assert main(["config", "prefer", "openai", "--json"]) == 0
    provider_result = json.loads(capsys.readouterr().out)
    assert provider_result["kind"] == "provider"
    assert main(["models", "enable", "claude-sonnet", "--json"]) == 0
    capsys.readouterr()
    assert "claude-sonnet" not in lade_user_overrides()["disabled_models"]
    overlay = tmp_path / "clutch-home" / "user_overrides.json"
    overlay.write_text("{kaputt", encoding="utf-8")
    before = overlay.read_bytes()
    assert main(["models", "disable", "gemini-pro", "--json"]) == 1
    capsys.readouterr()
    assert overlay.read_bytes() == before


def test_u3_api_praeferenz_ausschluss_und_alternativen(tmp_path):
    fahrer = Fahrer(
        db_path=tmp_path / "clutch.db",
        overrides_path=tmp_path / "missing-overrides.json",
        availability_path=tmp_path / "availability.json",
        token_budget_path=tmp_path / "missing-budget.json",
        sparmodus_path=tmp_path / "missing-sparmodus.json",
    )
    fahrer.kupplungs_mechanik.set_erkundungsrate(0)
    profil = fahrer.strecke_analysieren("smoke")
    config = fahrer.kuppeln(
        profil,
        zweck="general",
        ausschluss=["claude-sonnet"],
        praeferenz=["codex"],
        effort_override="high",
    )
    assert config.gang.name == "openai-codex"
    assert "claude-sonnet" not in config.alternativen
    assert len(config.alternativen) == 2
    assert config.effort == "high"
    assert config.to_dict()["alternativen"] == config.alternativen

    excluded = fahrer.getriebe.gang("claude-sonnet", einschliesslich_deaktiviert=True)
    fahrer.fahrschule.empirisch_routen = lambda _: SimpleNamespace(
        model_id=excluded.model_id,
        effort="xhigh",
        status="measured",
        reason="test",
    )
    result = fahrer.fahren(
        "smoke",
        handler=lambda _config, _task: "ok",
        kontext={
            "task_class": "coding",
            "ausschluss": ["claude-sonnet"],
            "praeferenz": ["codex"],
        },
    )
    assert result.config.gang.name == "openai-codex"
    assert "claude-sonnet" not in result.config.alternativen

    allowed_empirical = fahrer.getriebe.gang("gemini-pro")
    fahrer.fahrschule.empirisch_routen = lambda _: SimpleNamespace(
        model_id=allowed_empirical.model_id,
        effort="xhigh",
        status="measured",
        reason="test",
    )
    explicit = fahrer.fahren(
        "smoke",
        handler=lambda _config, _task: "ok",
        kontext={"task_class": "coding", "praeferenz": ["codex"]},
    )
    assert explicit.config.gang.name == "openai-codex"


def test_u3_cli_flags_und_route_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLUTCH_HOME", str(tmp_path / "clutch-home"))
    db = tmp_path / "clutch.db"
    rc = main([
        "route", "smoke", "--prefer", "codex", "--exclude", "claude-sonnet", "gemini-pro",
        "--zweck", "coding", "--effort", "xhigh", "--db", str(db), "--json",
    ])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["gang"] == "openai-codex"
    assert data["zweck"] == "coding"
    assert data["effort"] == "xhigh"
    assert len(data["alternativen"]) == 2
    assert "claude-sonnet" not in data["alternativen"]
    assert "gemini-pro" not in data["alternativen"]


def test_u1_models_status_json_enthaelt_sperrgrund(tmp_path, monkeypatch, capsys):
    clutch_dir = tmp_path / "clutch-home"
    clutch_dir.mkdir()
    (clutch_dir / "user_overrides.json").write_text(
        '{"disabled_models":["claude-sonnet"]}', encoding="utf-8"
    )
    monkeypatch.setenv("CLUTCH_HOME", str(clutch_dir))
    assert main(["models", "--status", "--no-discovery", "--json"]) == 0
    models = json.loads(capsys.readouterr().out)
    sonnet = next(model for model in models if model["name"] == "claude-sonnet")
    assert sonnet["availability"] == "disabled"
    assert sonnet["availability_reason"] == "user_overrides.disabled_models"
