"""Regression coverage for the public routing-contract resolver."""

import pytest

import clutch.execution as execution_module
from clutch import ExecutionRegistryError, Getriebe, resolve_execution_selector


NOW = "2026-08-30T04:30:00Z"


def resolve(selector: str, runner: str | None = None):
    return resolve_execution_selector(selector, runner=runner, resolved_at=NOW)


class _FakeMotor:
    def __init__(self, ready: bool):
        self._ready = ready

    def ist_verfuegbar(self, config=None):
        return self._ready


class _FakeMotorBlock:
    """Stands in for motorblock.MotorBlock so tests never spawn a real
    subprocess or make a real network/credential check."""

    def __init__(self, ready_by_provider: dict[str, bool]):
        self._ready_by_provider = ready_by_provider

    def motor_fuer(self, provider: str) -> _FakeMotor:
        if provider not in self._ready_by_provider:
            raise ValueError(provider)
        return _FakeMotor(self._ready_by_provider[provider])


@pytest.fixture()
def fake_motors(monkeypatch):
    def install(ready_by_provider: dict[str, bool]):
        monkeypatch.setattr(
            execution_module, "MotorBlock",
            lambda: _FakeMotorBlock(ready_by_provider),
        )

    return install


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
    # Bundled catalog data proves nothing beyond registry presence: the stages a
    # provider snapshot must supply stay unproven here. host_ready and
    # account_accessible are deliberately not asserted -- they are probed on the
    # executing host and therefore environment-dependent; the fake_motors tests
    # below pin that behaviour deterministically.
    assert result["availability"]["provider_api_listed"] is None
    assert result["availability"]["runner_compatible"] is True


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


def test_credential_provider_only_answers_account_accessible(fake_motors):
    fake_motors({"openai": True})

    result = resolve("openai-gpt-5.6-sol", runner="codex")

    assert result["availability"]["account_accessible"] is True
    assert result["availability"]["host_ready"] is None


def test_cli_provider_only_answers_host_ready(fake_motors):
    fake_motors({"anthropic": True, "claude-code": False})

    result = resolve("claude-code", runner="claude")

    # exact selector -> only its own provider (claude-code) is probed, not
    # the runner's sibling provider (anthropic).
    assert result["provider"] == "claude-code"
    assert result["availability"]["host_ready"] is False
    assert result["availability"]["account_accessible"] is None


def test_runner_selector_aggregates_across_its_providers(fake_motors):
    fake_motors({"anthropic": False, "claude-code": True})

    result = resolve("claude")

    # one ready provider in the runner's set is enough for host_ready=True.
    assert result["availability"]["host_ready"] is True
    assert result["availability"]["account_accessible"] is False


def test_unresolved_selector_never_probes_a_provider(fake_motors):
    fake_motors({})  # any motor_fuer() call would raise ValueError here

    result = resolve("model-that-does-not-exist")

    assert result["resolved"] is False
    assert result["availability"]["host_ready"] is None
    assert result["availability"]["account_accessible"] is None


def test_family_and_exact_selectors_agree_on_probed_readiness(fake_motors):
    """A snapshot that proves only the provider stages leaves the host-local
    ones to the probe. Both resolution paths must then reach the same verdict:
    a model claimable as an exact selector may not be silently dropped from its
    own family selector.
    """
    import json
    from pathlib import Path

    from clutch import ProviderCatalogSnapshot, apply_provider_catalog

    fixture = Path(__file__).parent / "fixtures" / "provider_catalogs" / "openai.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    # The adapter proved everything it could reach, but left the credential
    # axis open -- exactly the stage a local probe answers. (host_ready must
    # stay proven here: openai is a credential provider, so its Motor never
    # answers the host axis and nothing could ever become claimable.)
    data["entries"][0]["availability"]["account_accessible"] = None

    getriebe = Getriebe()
    apply_provider_catalog(getriebe, ProviderCatalogSnapshot.from_dict(data))
    fake_motors({"openai": True})

    exact = resolve_execution_selector(
        "openai-gpt-5.6-sol", runner="codex", registry=getriebe, resolved_at=NOW
    )
    family = resolve_execution_selector(
        "gpt5", runner="codex", registry=getriebe, resolved_at=NOW
    )

    assert exact["availability"]["account_accessible"] is True, "probe must answer"
    assert exact["claimable"] is True
    assert family["eligible_models"] == ["openai-gpt-5.6-sol"]
