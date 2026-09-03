"""Public execution-selector resolution for cross-system routing contracts.

``Getriebe`` remains the single source of concrete model records.  This
module adds the missing contract layer that classifies a selector as a runner,
family, exact model, or alias and returns a deterministic registry
fingerprint.  It probes credential and host readiness on the executing host
(T-20260902-665621838, via the same ``Motor.ist_verfuegbar()`` checks
``motorblock`` already trusts) rather than leaving them permanently ``None`` --
a ``required`` execution binding depends on both being confirmed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from clutch.getriebe import Gang, Getriebe
from clutch.motorblock import MotorBlock


class ExecutionRegistryError(RuntimeError):
    """The execution registry could not provide a trustworthy resolution."""


_POLICY_VERSION = 1

# User-facing shorthand.  Aliases are resolved before selector classification.
_ALIASES = {
    "gpt": "codex",
}

# A runner is an execution surface, while a provider describes a model record.
# Every provider is assigned to exactly one runner so exact-model bindings stay
# deterministic even when the caller does not supply a runner.
_RUNNER_PROVIDERS = {
    "agy": frozenset({"agy"}),
    "claude": frozenset({"anthropic", "claude-code"}),
    "clutch": frozenset({"google", "ollama"}),
    "codex": frozenset({"openai"}),
    "kimi": frozenset({"kimi-api", "kimi-cli", "kimi-code"}),
}

# Family selectors intentionally precede exact-name lookup: ``claude-opus``
# and ``claude-sonnet`` are stable families even though today's registry also
# contains same-named concrete records.
_FAMILY_POLICIES = {
    "claude-opus": {
        "runner": "claude",
        "providers": frozenset({"anthropic"}),
        "model_token": "claude-opus",
    },
    "claude-sonnet": {
        "runner": "claude",
        "providers": frozenset({"anthropic"}),
        "model_token": "claude-sonnet",
    },
    "gpt5": {
        "runner": "codex",
        "providers": frozenset({"openai"}),
        "model_token": "gpt-5",
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _runner_for(gang: Gang) -> str | None:
    matches = [runner for runner, providers in _RUNNER_PROVIDERS.items() if gang.provider in providers]
    if len(matches) > 1:
        raise ExecutionRegistryError(f"provider {gang.provider!r} maps to multiple execution runners")
    return matches[0] if matches else None


def _registry_fingerprint(registry: Getriebe) -> str:
    """Hash only the registry facts and policy that affect selector resolution."""
    models = [
        {"name": gang.name, "provider": gang.provider, "model_id": gang.model_id}
        for gang in registry.alle_gaenge()
    ]
    families = {
        name: {
            "runner": policy["runner"],
            "providers": sorted(policy["providers"]),
            "model_token": policy["model_token"],
        }
        for name, policy in _FAMILY_POLICIES.items()
    }
    payload = {
        "policy_version": _POLICY_VERSION,
        "aliases": _ALIASES,
        "runner_providers": {
            runner: sorted(providers) for runner, providers in _RUNNER_PROVIDERS.items()
        },
        "families": families,
        "models": sorted(models, key=lambda item: item["name"]),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


# Providers whose Motor.ist_verfuegbar() checks a credential (API key
# presence) rather than a local binary/endpoint. Every provider named in
# _RUNNER_PROVIDERS has a Motor in motorblock.MotorBlock; this set just
# decides which readiness axis its check result answers -- the axis it
# does NOT answer stays None (not checked), never guessed as unavailable.
_CREDENTIAL_PROVIDERS = frozenset({"anthropic", "google", "openai", "kimi-api"})


def _probe_provider(provider: str) -> tuple[bool | None, bool | None]:
    """(host_ready, account_accessible) for one provider's Motor.

    Reuses the readiness checks the execution layer already trusts (CLI
    ``--version`` probes, local Ollama ``/api/tags``, credential lookups)
    instead of re-implementing them here.
    """
    try:
        motor = MotorBlock().motor_fuer(provider)
    except ValueError:
        return None, None
    # ponytail: probes live on every call (subprocess/network for CLI and
    # Ollama motors) -- fine at binding time, not a per-token hot path. Add
    # a short-TTL cache here if that assumption stops holding.
    ready = motor.ist_verfuegbar()
    if provider in _CREDENTIAL_PROVIDERS:
        return None, ready
    return ready, None


def _aggregate_readiness(providers: frozenset[str]) -> tuple[bool | None, bool | None]:
    """Combines per-provider readiness for a selector that may resolve to
    several providers (a runner or family selector). None stays None unless
    at least one provider in the set actually answered that axis; among
    those that did, one working provider is enough."""
    host_results: list[bool] = []
    account_results: list[bool] = []
    for provider in providers:
        host, account = _probe_provider(provider)
        if host is not None:
            host_results.append(host)
        if account is not None:
            account_results.append(account)
    host_ready = any(host_results) if host_results else None
    account_accessible = any(account_results) if account_results else None
    return host_ready, account_accessible


def _availability(
    *, registered: bool, compatible: bool | None,
    host_ready: bool | None = None, account_accessible: bool | None = None,
) -> dict[str, bool | None]:
    return {
        "registry_loaded": True,
        "selector_registered": registered,
        "provider_documented": registered,
        "provider_api_listed": registered,
        "account_accessible": account_accessible,
        "runner_compatible": compatible,
        "host_ready": host_ready,
    }


def _family_models(registry: Getriebe, canonical: str) -> list[Gang]:
    policy = _FAMILY_POLICIES[canonical]
    token = str(policy["model_token"])
    providers = policy["providers"]
    return [
        gang for gang in registry.alle_gaenge()
        if gang.provider in providers and token in gang.model_id.casefold()
    ]


def resolve_execution_selector(
    selector: str,
    *,
    runner: str | None = None,
    registry: Getriebe | None = None,
    resolved_at: str | None = None,
) -> dict[str, Any]:
    """Resolve a runner, family, exact model, or alias against ``Getriebe``.

    ``resolved`` answers whether the selector exists.  ``claimable`` also
    requires a compatible runner and at least one eligible concrete model.
    ``availability.host_ready``/``account_accessible`` are probed per
    candidate provider and stay ``None`` only where no Motor answered that
    axis -- never inferred from registry presence alone.
    """
    if not isinstance(selector, str):
        raise TypeError("execution selector must be a string")
    if runner is not None and not isinstance(runner, str):
        raise TypeError("execution runner must be a string or None")

    model_registry = registry if registry is not None else Getriebe()
    if not model_registry.alle_gaenge():
        raise ExecutionRegistryError("Clutch execution registry contains no models")

    requested = selector.strip()
    normalized = requested.casefold()
    canonical = _ALIASES.get(normalized, normalized)
    requested_runner = runner.strip().casefold() if runner else None
    fingerprint = _registry_fingerprint(model_registry)
    timestamp = resolved_at or _utc_now()

    selector_type: str
    model_selection: str
    selected_runner: str
    provider: str | None = None
    registry_name: str | None = None
    model_id: str | None = None
    provider_candidates: frozenset[str]

    if canonical in _RUNNER_PROVIDERS:
        selector_type = "runner"
        model_selection = "self"
        selected_runner = canonical
        provider_candidates = _RUNNER_PROVIDERS[selected_runner]
        models = [
            gang for gang in model_registry.alle_gaenge()
            if gang.provider in provider_candidates
        ]
    elif canonical in _FAMILY_POLICIES:
        selector_type = "family"
        model_selection = "family"
        selected_runner = str(_FAMILY_POLICIES[canonical]["runner"])
        provider_candidates = frozenset(_FAMILY_POLICIES[canonical]["providers"])
        models = _family_models(model_registry, canonical)
    else:
        exact_by_name = {gang.name.casefold(): gang for gang in model_registry.alle_gaenge()}
        exact = exact_by_name.get(canonical)
        if exact is None:
            return {
                "requested_selector": requested,
                "canonical_selector": None,
                "selector_type": "unresolved",
                "model_selection": None,
                "resolved": False,
                "claimable": False,
                "runner": None,
                "provider": None,
                "registry_name": None,
                "model_id": None,
                "allowed_runners": [],
                "eligible_models": [],
                "availability": _availability(registered=False, compatible=None),
                "reason": "selector-not-in-registry",
                "registry_fingerprint": fingerprint,
                "resolved_at": timestamp,
            }
        selected_runner = _runner_for(exact) or ""
        if not selected_runner:
            raise ExecutionRegistryError(
                f"model {exact.name!r} uses provider {exact.provider!r} without an execution runner"
            )
        selector_type = "exact"
        model_selection = "exact"
        canonical = exact.name
        models = [exact]
        provider = exact.provider
        provider_candidates = frozenset({provider})
        registry_name = exact.name
        model_id = exact.model_id

    compatible = requested_runner in {None, selected_runner}
    eligible_models = sorted(gang.name for gang in models) if compatible else []
    claimable = compatible and bool(eligible_models)
    if not compatible:
        reason = "runner-not-compatible"
    elif not eligible_models:
        reason = "selector-has-no-eligible-models"
    else:
        reason = None
    host_ready, account_accessible = _aggregate_readiness(provider_candidates)

    return {
        "requested_selector": requested,
        "canonical_selector": canonical,
        "selector_type": selector_type,
        "model_selection": model_selection,
        "resolved": True,
        "claimable": claimable,
        "runner": selected_runner,
        "provider": provider,
        "registry_name": registry_name,
        "model_id": model_id,
        "allowed_runners": [selected_runner],
        "eligible_models": eligible_models,
        "availability": _availability(
            registered=True, compatible=compatible,
            host_ready=host_ready, account_accessible=account_accessible,
        ),
        "reason": reason,
        "registry_fingerprint": fingerprint,
        "resolved_at": timestamp,
    }


__all__ = ["ExecutionRegistryError", "resolve_execution_selector"]
