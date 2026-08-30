"""Provider evidence and strict selector regression coverage."""

import json
from pathlib import Path

import pytest

from clutch import (
    AVAILABILITY_STAGES,
    LIFECYCLES,
    Gang,
    Getriebe,
    ModelAvailability,
    ProviderCatalogSnapshot,
    apply_provider_catalog,
    refresh_provider_catalog,
    resolve_execution_selector,
)
from clutch.cli import main


FIXTURES = Path(__file__).parent / "fixtures" / "provider_catalogs"


def _fixture(name: str) -> ProviderCatalogSnapshot:
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    return ProviderCatalogSnapshot.from_dict(data)


def _available() -> dict[str, bool]:
    return {stage: True for stage in AVAILABILITY_STAGES}


def test_availability_stages_are_independent_and_fail_closed():
    values = _available()
    values["account_accessible"] = False
    availability = ModelAvailability.from_mapping(values)

    assert tuple(availability.to_dict()) == AVAILABILITY_STAGES
    assert availability.provider_documented is True
    assert availability.account_accessible is False
    assert not availability.claimable


def test_unknown_availability_stage_is_rejected():
    with pytest.raises(ValueError, match="unknown availability"):
        ModelAvailability.from_mapping({"provider_documented": True, "combined": True})


def test_provider_fixtures_cover_required_lifecycles_and_provenance():
    snapshots = [_fixture(name) for name in ("anthropic", "google", "moonshot", "ollama", "openai")]
    lifecycles = {entry.lifecycle for snapshot in snapshots for entry in snapshot.entries}

    assert {"ga", "preview", "limited", "deprecated", "retired"} <= lifecycles
    assert lifecycles <= LIFECYCLES
    assert all(snapshot.source and snapshot.checked_at for snapshot in snapshots)
    assert all(snapshot.fingerprint.startswith("sha256:") for snapshot in snapshots)


def test_provider_refresh_reports_diff():
    previous = _fixture("openai")
    data = previous.to_dict()
    data["checked_at"] = "2026-08-23T00:00:00Z"
    data["entries"].append(
        {
            "registry_name": "provider-only-new-model",
            "model_id": "provider-only-new-model",
            "lifecycle": "preview",
            "source": data["source"],
            "checked_at": data["checked_at"],
            "availability": _available(),
            "runners": ["codex"],
        }
    )
    current = ProviderCatalogSnapshot.from_dict(data)

    class Adapter:
        provider = "openai"

        def fetch(self):
            return current

    result = refresh_provider_catalog(Adapter(), previous=previous)

    assert result.snapshot_accepted
    assert not result.retained_previous
    assert result.diff.added == ("provider-only-new-model",)


def test_provider_refresh_retains_proven_snapshot_and_hides_raw_failure():
    previous = _fixture("openai")

    class FailingAdapter:
        provider = "openai"

        def fetch(self):
            raise RuntimeError("credential-like raw-provider-detail")

    result = refresh_provider_catalog(FailingAdapter(), previous=previous)

    assert not result.snapshot_accepted
    assert result.retained_previous
    assert result.snapshot == previous
    assert result.error_code == "adapter-error:RuntimeError"
    assert "raw-provider-detail" not in json.dumps(result.to_dict())


def test_provider_refresh_hides_failure_while_reading_provider_identity():
    class FailingProviderPropertyAdapter:
        @property
        def provider(self):
            raise RuntimeError("credential-like raw detail")

        def fetch(self):
            raise AssertionError("fetch must not run")

    result = refresh_provider_catalog(FailingProviderPropertyAdapter())

    assert not result.snapshot_accepted
    assert result.provider == "unknown"
    assert result.error_code == "adapter-error:RuntimeError"
    assert "credential-like" not in json.dumps(result.to_dict())


def test_catalog_atomically_enriches_curated_model_and_family():
    getriebe = Getriebe()
    before = resolve_execution_selector(
        "openai-gpt-5.6-sol", runner="codex", registry=getriebe
    )

    result = apply_provider_catalog(getriebe, _fixture("openai"))
    exact = resolve_execution_selector(
        "openai-gpt-5.6-sol", runner="codex", registry=getriebe
    )
    family = resolve_execution_selector("gpt5", runner="codex", registry=getriebe)

    assert before["resolved"] and not before["claimable"]
    assert result.updated == ("openai-gpt-5.6-sol",)
    assert exact["resolved"] and exact["claimable"]
    assert exact["lifecycle"] == "ga"
    assert exact["catalog_checked_at"] == "2026-08-22T00:00:00Z"
    assert family["eligible_models"] == ["openai-gpt-5.6-sol"]
    assert family["claimable"]


def test_catalog_apply_skips_unknown_models_without_curating_them():
    getriebe = Getriebe()
    data = _fixture("openai").to_dict()
    data["entries"][0]["registry_name"] = "provider-only-model"
    data["entries"][0]["model_id"] = "provider-only-model"

    result = apply_provider_catalog(getriebe, ProviderCatalogSnapshot.from_dict(data))

    assert result.applied
    assert result.updated == ()
    assert result.skipped_unregistered == ("provider-only-model",)
    assert getriebe.gang("provider-only-model") is None


def test_catalog_apply_rejects_identity_mismatch_without_partial_mutation():
    getriebe = Getriebe()
    gang = getriebe.gang("openai-gpt-5.6-sol")
    assert gang is not None
    original = (gang.lifecycle, gang.availability.copy(), list(gang.runners))
    data = _fixture("openai").to_dict()
    data["entries"][0]["model_id"] = "different-model-id"

    with pytest.raises(ValueError, match="identity mismatch"):
        apply_provider_catalog(getriebe, ProviderCatalogSnapshot.from_dict(data))

    assert (gang.lifecycle, gang.availability, gang.runners) == original


def test_upstream_listing_does_not_imply_host_readiness():
    getriebe = Getriebe()
    apply_provider_catalog(getriebe, _fixture("ollama"))

    result = resolve_execution_selector("ollama-qwen3", runner="ollama", registry=getriebe)

    assert result["resolved"]
    assert result["availability"]["provider_api_listed"] is True
    assert result["availability"]["host_ready"] is False
    assert not result["claimable"]


def test_exact_model_id_ambiguity_requires_runner_disambiguation():
    getriebe = Getriebe()
    ambiguous = resolve_execution_selector("gemini-3.5-flash", registry=getriebe)
    exact = resolve_execution_selector(
        "gemini-3.5-flash", runner="agy", registry=getriebe
    )

    assert not ambiguous["resolved"]
    assert ambiguous["reason"] == "ambiguous-exact-selector"
    assert exact["resolved"]
    assert exact["registry_name"] == "agy-gemini-3.5-flash"


def test_cross_namespace_exact_collision_is_not_silently_resolved():
    getriebe = Getriebe()
    for name, model_id in (
        ("collision-token", "different-model-id"),
        ("different-registry-name", "collision-token"),
    ):
        getriebe.registriere_gang(
            Gang(
                name=name,
                provider="openai",
                model_id=model_id,
                gang=3,
                leistung="hoch",
                kosten_input_1k=0,
                kosten_output_1k=0,
                lifecycle="ga",
                availability=_available(),
                runners=["codex"],
            )
        )

    result = resolve_execution_selector("collision-token", runner="codex", registry=getriebe)

    assert not result["resolved"]
    assert result["reason"] == "ambiguous-exact-selector"


def test_unregistered_opus_5_stays_unresolved_until_curated_as_itself():
    getriebe = Getriebe()
    before = resolve_execution_selector("claude-opus-5", runner="claude", registry=getriebe)
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
            availability=_available(),
            runners=["claude"],
            catalog_source="https://platform.claude.com/docs/en/api/models/list",
            catalog_checked_at="2026-08-23T00:00:00Z",
        )
    )
    after = resolve_execution_selector("claude-opus-5", runner="claude", registry=getriebe)

    assert not before["resolved"]
    assert after["resolved"] and after["claimable"]
    assert after["registry_name"] == after["model_id"] == "claude-opus-5"
    assert getriebe.gang("claude-opus").model_id == "claude-opus-4-6"


def test_registry_fingerprint_changes_when_evidence_changes():
    getriebe = Getriebe()
    before = getriebe.registry_fingerprint()
    apply_provider_catalog(getriebe, _fixture("openai"))

    assert getriebe.registry_fingerprint() != before


def test_cli_resolve_is_machine_readable_and_can_require_claimable(capsys):
    assert main(["resolve", "gpt", "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    missing = main(["resolve", "claude-opus-5", "--runner", "claude", "--json"])
    missing_output = json.loads(capsys.readouterr().out)
    unavailable = main(["resolve", "gpt", "--require-claimable", "--json"])
    unavailable_output = json.loads(capsys.readouterr().out)

    assert output["canonical_selector"] == "codex"
    assert output["registry_fingerprint"].startswith("sha256:")
    assert missing == 3
    assert missing_output["reason"] == "selector-not-in-registry"
    assert unavailable == 4
    assert unavailable_output["resolved"] and not unavailable_output["claimable"]


def test_models_json_exposes_catalog_evidence_without_runtime_probe(capsys):
    assert main(["models", "--json", "--no-discovery"]) == 0
    models = json.loads(capsys.readouterr().out)

    assert tuple(models[0]["execution_availability"]) == AVAILABILITY_STAGES
    assert "lifecycle" in models[0]
    assert "runners" in models[0]
