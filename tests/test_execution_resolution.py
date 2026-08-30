"""Regression coverage for the public routing-contract resolver."""

import pytest

from clutch import ExecutionRegistryError, Getriebe, resolve_execution_selector


NOW = "2026-08-30T04:30:00Z"


def resolve(selector: str, runner: str | None = None):
    return resolve_execution_selector(selector, runner=runner, resolved_at=NOW)


def test_runner_alias_reuses_getriebe_models():
    result = resolve("gpt")

    assert result["requested_selector"] == "gpt"
    assert result["canonical_selector"] == "codex"
    assert result["selector_type"] == "runner"
    assert result["model_selection"] == "self"
    assert result["runner"] == "codex"
    assert result["resolved"] is True
    assert result["claimable"] is False
    assert result["eligible_models"] == []
    assert result["reason"] == "no-eligible-models"
    assert result["registry_fingerprint"].startswith("sha256:")
    assert result["resolved_at"] == NOW


def test_family_resolution_is_runner_compatible_and_deterministic():
    first = resolve("gpt5", runner="codex")
    second = resolve("gpt5", runner="codex")

    assert first["selector_type"] == "family"
    assert first["model_selection"] == "family"
    assert first["allowed_runners"] == ["codex"]
    assert first["claimable"] is False
    assert first["eligible_models"] == sorted(first["eligible_models"])
    assert first["eligible_models"] == []
    assert first["registry_fingerprint"] == second["registry_fingerprint"]


def test_exact_model_resolution_exposes_getriebe_identity():
    result = resolve("openai-gpt-5.6-sol", runner="codex")

    assert result["canonical_selector"] == "openai-gpt-5.6-sol"
    assert result["selector_type"] == "exact"
    assert result["model_selection"] == "exact"
    assert result["runner"] == "codex"
    assert result["provider"] == "openai"
    assert result["registry_name"] == "openai-gpt-5.6-sol"
    assert result["model_id"] == "gpt-5.6-sol"
    assert result["eligible_models"] == []
    assert result["claimable"] is False
    assert result["reason"] == "availability-unproven"
    assert result["availability"]["provider_documented"] is True
    assert result["availability"]["account_accessible"] is None
    assert result["availability"]["host_ready"] is None


def test_incompatible_runner_and_unknown_selector_are_distinguishable():
    incompatible = resolve("openai-gpt-5.6-sol", runner="claude")
    missing = resolve("model-that-does-not-exist", runner="codex")

    assert incompatible["resolved"] is True
    assert incompatible["claimable"] is False
    assert incompatible["reason"] == "runner-not-compatible"
    assert incompatible["eligible_models"] == []
    assert missing["resolved"] is False
    assert missing["claimable"] is False
    assert missing["reason"] == "selector-not-in-registry"
    assert missing["registry_fingerprint"].startswith("sha256:")


def test_empty_registry_is_an_outage_not_an_unknown_selector(tmp_path):
    empty_registry = Getriebe(config_dir=tmp_path)

    with pytest.raises(ExecutionRegistryError, match="contains no models"):
        resolve_execution_selector("codex", registry=empty_registry)
