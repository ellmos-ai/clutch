"""Public execution-selector and provider-catalog contract tests.

All provider evidence is fixture-backed.  These tests never call a provider,
inspect credentials, or infer host readiness from an upstream model list.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from clutch import resolve_execution_selector
from clutch.cli import main
from clutch.execution_registry import (
    AVAILABILITY_STAGES,
    ModelAvailability,
    ProviderCatalogSnapshot,
    refresh_provider_catalog,
)
from clutch.getriebe import Gang, Getriebe


FIXTURES = Path(__file__).parent / "fixtures" / "provider_catalogs"


def _all_available(*, host_ready: bool = True) -> dict[str, bool]:
    return {
        "provider_documented": True,
        "provider_api_listed": True,
        "account_accessible": True,
        "runner_compatible": True,
        "host_ready": host_ready,
    }


def _enable(getriebe: Getriebe, name: str, *runners: str, host_ready: bool = True) -> None:
    gang = getriebe.gang(name)
    assert gang is not None
    gang.availability = _all_available(host_ready=host_ready)
    gang.runners = list(runners)
    gang.lifecycle = "ga"


def test_runner_alias_normalizes_without_duplicating_model_catalog():
    getriebe = Getriebe()
    _enable(getriebe, "openai-gpt-5.6-sol", "codex")

    result = resolve_execution_selector(".via-gpt", getriebe=getriebe)

    assert result.resolved
    assert result.selector_type == "runner"
    assert result.model_selection == "self"
    assert result.normalized_selector == "gpt"
    assert result.canonical_selector == "codex"
    assert result.runner == "codex"
    assert result.eligible_models == ("openai-gpt-5.6-sol",)
    assert result.claimable


def test_explicit_self_uses_the_normalized_runner():
    getriebe = Getriebe()
    _enable(getriebe, "claude-fable", "claude")

    result = resolve_execution_selector("self", runner="claude", getriebe=getriebe)

    assert result.resolved
    assert result.selector_type == "self"
    assert result.model_selection == "self"
    assert result.canonical_selector == "claude"
    assert result.runner == "claude"
    assert result.eligible_models == ("claude-fable",)


def test_self_without_runner_is_fail_closed():
    result = resolve_execution_selector("self", getriebe=Getriebe())

    assert not result.resolved
    assert result.reason == "runner-required-for-self"
    assert not result.claimable


def test_family_profile_selects_only_fully_available_candidates():
    getriebe = Getriebe()
    _enable(getriebe, "openai-gpt-5.6-sol", "codex")
    _enable(getriebe, "openai-gpt-5.6-terra", "codex", host_ready=False)

    result = resolve_execution_selector("gpt5", getriebe=getriebe)

    assert result.resolved
    assert result.selector_type == "family"
    assert result.model_selection == "family"
    assert result.canonical_selector == "openai-gpt-5"
    assert result.runner == "codex"
    assert result.eligible_models == ("openai-gpt-5.6-sol",)
    assert result.claimable


def test_exact_name_and_model_id_resolve_to_the_same_registry_entry():
    getriebe = Getriebe()
    _enable(getriebe, "openai-gpt-5.6-sol", "codex")

    by_name = resolve_execution_selector("openai-gpt-5.6-sol", getriebe=getriebe)
    by_id = resolve_execution_selector("gpt-5.6-sol", runner="codex", getriebe=getriebe)

    assert by_name.selector_type == by_id.selector_type == "exact"
    assert by_name.registry_name == by_id.registry_name == "openai-gpt-5.6-sol"
    assert by_name.model_id == by_id.model_id == "gpt-5.6-sol"
    assert by_name.catalog_source == "https://developers.openai.com/api/docs/models/gpt-5.6-sol"
    assert by_name.claimable and by_id.claimable


def test_unknown_exact_model_is_never_silently_substituted():
    result = resolve_execution_selector("claude-opus-5", runner="claude", getriebe=Getriebe())

    assert not result.resolved
    assert result.selector_type == "unresolved"
    assert result.reason == "selector-not-in-registry"
    assert result.registry_name is None
    assert result.model_id is None
    assert result.eligible_models == ()
    assert not result.claimable


def test_curated_registry_refresh_can_add_opus_5_as_its_own_exact_profile():
    getriebe = Getriebe()
    before = resolve_execution_selector("claude-opus-5", runner="claude", getriebe=getriebe)
    getriebe.registriere_gang(
        Gang(
            name="claude-opus-5",
            provider="anthropic",
            model_id="claude-opus-5",
            gang=5,
            leistung="max",
            kosten_input_1k=0,
            kosten_output_1k=0,
            lifecycle="ga",
            availability=_all_available(),
            runners=["claude"],
            catalog_source="https://platform.claude.com/docs/en/api/models/list",
            catalog_checked_at="2026-08-23T00:00:00Z",
        )
    )
    after = resolve_execution_selector("claude-opus-5", runner="claude", getriebe=getriebe)

    assert not before.resolved
    assert after.resolved and after.claimable
    assert after.registry_name == after.model_id == "claude-opus-5"
    assert getriebe.gang("claude-opus").model_id == "claude-opus-4-6"


def test_ambiguous_exact_model_id_requires_runner_disambiguation():
    getriebe = Getriebe()
    for name, provider, runner in (
        ("direct-same", "anthropic", "claude"),
        ("bridge-same", "agy", "agy"),
    ):
        gang = Gang(
            name=name,
            provider=provider,
            model_id="same-model-id",
            gang=3,
            leistung="hoch",
            kosten_input_1k=0,
            kosten_output_1k=0,
            lifecycle="ga",
            availability=_all_available(),
            runners=[runner],
        )
        getriebe.registriere_gang(gang)

    ambiguous = resolve_execution_selector("same-model-id", getriebe=getriebe)
    exact = resolve_execution_selector("same-model-id", runner="agy", getriebe=getriebe)

    assert not ambiguous.resolved
    assert ambiguous.reason == "ambiguous-exact-selector"
    assert exact.resolved
    assert exact.registry_name == "bridge-same"


def test_availability_stages_are_independent_and_fail_closed():
    values = {
        "provider_documented": True,
        "provider_api_listed": True,
        "account_accessible": False,
        "runner_compatible": True,
        "host_ready": True,
    }
    availability = ModelAvailability.from_mapping(values)

    assert tuple(availability.to_dict()) == AVAILABILITY_STAGES
    assert availability.provider_documented is True
    assert availability.account_accessible is False
    assert availability.host_ready is True
    assert not availability.claimable


def test_upstream_presence_does_not_imply_local_host_readiness():
    getriebe = Getriebe()
    _enable(getriebe, "ollama-qwen3", "ollama", host_ready=False)

    result = resolve_execution_selector("ollama-qwen3", runner="ollama", getriebe=getriebe)

    assert result.resolved
    assert result.availability.provider_documented is True
    assert result.availability.runner_compatible is True
    assert result.availability.host_ready is False
    assert not result.claimable


def test_registry_fingerprint_is_stable_and_changes_with_registry_content():
    first = Getriebe()
    second = Getriebe()

    before = first.registry_fingerprint()
    assert before == second.registry_fingerprint()
    assert before.startswith("sha256:")

    second.registriere_gang(
        Gang(
            name="fixture-new-model",
            provider="fixture",
            model_id="fixture-new-model-v1",
            gang=1,
            leistung="basis",
            kosten_input_1k=0,
            kosten_output_1k=0,
        )
    )
    assert second.registry_fingerprint() != before


@pytest.mark.parametrize(
    ("provider", "expected_lifecycle", "host_ready"),
    [
        ("anthropic", "limited", False),
        ("openai", "ga", True),
        ("google", "preview", False),
        ("moonshot", "retired", False),
        ("ollama", "ga", False),
    ],
)
def test_provider_catalog_fixtures_keep_lifecycle_and_availability_separate(
    provider: str,
    expected_lifecycle: str,
    host_ready: bool,
):
    snapshot = ProviderCatalogSnapshot.from_dict(
        json.loads((FIXTURES / f"{provider}.json").read_text(encoding="utf-8"))
    )

    assert snapshot.provider == provider
    entry = next(entry for entry in snapshot.entries if entry.lifecycle == expected_lifecycle)
    assert entry.availability.host_ready is host_ready
    assert snapshot.fingerprint.startswith("sha256:")


def test_provider_fixtures_cover_required_lifecycle_boundaries():
    lifecycles = set()
    for fixture in FIXTURES.glob("*.json"):
        snapshot = ProviderCatalogSnapshot.from_dict(
            json.loads(fixture.read_text(encoding="utf-8"))
        )
        lifecycles.update(entry.lifecycle for entry in snapshot.entries)

    assert {"ga", "preview", "limited", "deprecated", "retired"} <= lifecycles


def test_provider_refresh_reports_diff_without_provider_call_in_core():
    previous = ProviderCatalogSnapshot.from_dict(
        json.loads((FIXTURES / "anthropic.json").read_text(encoding="utf-8"))
    )
    updated_data = previous.to_dict()
    updated_data["checked_at"] = "2026-08-23T00:00:00Z"
    updated_data["entries"].append(
        {
            "registry_name": "claude-opus-5",
            "model_id": "claude-opus-5",
            "lifecycle": "ga",
            "source": "https://platform.claude.com/docs/en/api/models/list",
            "checked_at": "2026-08-23T00:00:00Z",
            "availability": _all_available(host_ready=False),
            "runners": ["claude"],
        }
    )
    updated = ProviderCatalogSnapshot.from_dict(updated_data)

    class FixtureAdapter:
        provider = "anthropic"

        def fetch(self):
            return updated

    result = refresh_provider_catalog(FixtureAdapter(), previous=previous)

    assert result.applied
    assert not result.retained_previous
    assert result.diff.added == ("claude-opus-5",)
    assert result.diff.removed == ()
    assert result.snapshot == updated


def test_provider_refresh_failure_retains_last_proven_snapshot_and_hides_error_text():
    previous = ProviderCatalogSnapshot.from_dict(
        json.loads((FIXTURES / "openai.json").read_text(encoding="utf-8"))
    )

    class FailingAdapter:
        provider = "openai"

        def fetch(self):
            raise RuntimeError("raw-provider-detail-should-never-escape")

    result = refresh_provider_catalog(FailingAdapter(), previous=previous)

    assert not result.applied
    assert result.retained_previous
    assert result.snapshot == previous
    assert result.error_code == "adapter-error:RuntimeError"
    assert "raw-provider-detail" not in json.dumps(result.to_dict())


def test_cli_resolve_is_machine_readable_and_unresolved_returns_three(capsys):
    ok = main(["resolve", "gpt", "--json"])
    output = json.loads(capsys.readouterr().out)
    missing = main(["resolve", "claude-opus-5", "--runner", "claude", "--json"])
    missing_output = json.loads(capsys.readouterr().out)

    assert ok == 0
    assert output["canonical_selector"] == "codex"
    assert output["registry_fingerprint"].startswith("sha256:")
    assert missing == 3
    assert missing_output["reason"] == "selector-not-in-registry"


def test_models_json_exposes_all_availability_stages(capsys):
    assert main(["models", "--json", "--no-discovery"]) == 0
    models = json.loads(capsys.readouterr().out)

    assert tuple(models[0]["availability"]) == AVAILABILITY_STAGES
    assert "lifecycle" in models[0]
    assert "runners" in models[0]
