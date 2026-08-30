"""Public execution-selector and provider-catalog evidence contract.

``Getriebe`` remains the only curated model registry. This module resolves
runner, family and exact selectors against it and accepts provider observations
through injected adapters. It performs no credential or network access itself.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from clutch.getriebe import Gang, Getriebe


AVAILABILITY_STAGES = (
    "provider_documented",
    "provider_api_listed",
    "account_accessible",
    "runner_compatible",
    "host_ready",
)
LIFECYCLES = {"ga", "preview", "limited", "deprecated", "retired", "unknown"}
PROVIDER_CATALOG_SCHEMA = "ellmos.clutch.provider-catalog.v1"
_ELIGIBLE_LIFECYCLES = {"ga", "preview", "limited"}


class ExecutionRegistryError(RuntimeError):
    """The execution registry could not provide a trustworthy resolution."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"


def normalize_selector_token(selector: str) -> str:
    """Normalize selector syntax without guessing its semantic identity."""
    if not isinstance(selector, str):
        raise TypeError("execution selector must be a string")
    token = selector.strip().casefold().replace("_", "-")
    if token.startswith("."):
        token = token[1:]
    if token.startswith("via-"):
        token = token[4:]
    return token


@dataclass(frozen=True)
class ModelAvailability:
    """Five independent evidence stages; ``None`` means unproven."""

    provider_documented: bool | None = None
    provider_api_listed: bool | None = None
    account_accessible: bool | None = None
    runner_compatible: bool | None = None
    host_ready: bool | None = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None) -> "ModelAvailability":
        values = values or {}
        unknown = set(values) - set(AVAILABILITY_STAGES)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"unknown availability stages: {names}")
        normalized: dict[str, bool | None] = {}
        for stage in AVAILABILITY_STAGES:
            value = values.get(stage)
            if value is not None and not isinstance(value, bool):
                raise ValueError(f"availability stage {stage} must be boolean or null")
            normalized[stage] = value
        return cls(**normalized)

    @property
    def claimable(self) -> bool:
        return all(getattr(self, stage) is True for stage in AVAILABILITY_STAGES)

    def to_dict(self) -> dict[str, bool | None]:
        return {stage: getattr(self, stage) for stage in AVAILABILITY_STAGES}


@dataclass(frozen=True)
class ExecutionResolution:
    requested_selector: str
    normalized_selector: str
    canonical_selector: str | None
    selector_type: str
    model_selection: str | None
    resolved: bool
    runner: str | None
    provider: str | None
    registry_name: str | None
    model_id: str | None
    allowed_runners: tuple[str, ...]
    eligible_models: tuple[str, ...]
    lifecycle: str
    catalog_source: str | None
    catalog_checked_at: str | None
    availability: ModelAvailability
    claimable: bool
    reason: str | None
    registry_fingerprint: str
    resolved_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_selector": self.requested_selector,
            "normalized_selector": self.normalized_selector,
            "canonical_selector": self.canonical_selector,
            "selector_type": self.selector_type,
            "model_selection": self.model_selection,
            "resolved": self.resolved,
            "runner": self.runner,
            "provider": self.provider,
            "registry_name": self.registry_name,
            "model_id": self.model_id,
            "allowed_runners": list(self.allowed_runners),
            "eligible_models": list(self.eligible_models),
            "lifecycle": self.lifecycle,
            "catalog_source": self.catalog_source,
            "catalog_checked_at": self.catalog_checked_at,
            "availability": self.availability.to_dict(),
            "claimable": self.claimable,
            "reason": self.reason,
            "registry_fingerprint": self.registry_fingerprint,
            "resolved_at": self.resolved_at,
        }


class ExecutionRegistry:
    """Resolve public selectors against one :class:`Getriebe` instance."""

    def __init__(self, getriebe: Getriebe):
        self.getriebe = getriebe
        config = getriebe.execution_registry_config()
        self.schema = config.get("schema", "ellmos.clutch.execution-registry.v1")
        self.aliases = {
            normalize_selector_token(key): normalize_selector_token(value)
            for key, value in config.get("aliases", {}).items()
        }
        self.profiles = {
            normalize_selector_token(key): value
            for key, value in config.get("profiles", {}).items()
        }

    def fingerprint(self) -> str:
        """Hash every registry fact and policy that affects resolution."""
        models = []
        for gang in sorted(self.getriebe.alle_gaenge(), key=lambda item: item.name):
            models.append(
                {
                    "name": gang.name,
                    "provider": gang.provider,
                    "model_id": gang.model_id,
                    "gang": gang.gang,
                    "leistung": gang.leistung,
                    "efforts": list(gang.efforts),
                    "reasoning_modes": list(gang.reasoning_modes),
                    "lifecycle": gang.lifecycle,
                    "availability": ModelAvailability.from_mapping(
                        gang.availability
                    ).to_dict(),
                    "runners": sorted(gang.runners),
                    "catalog_source": gang.catalog_source,
                    "catalog_checked_at": gang.catalog_checked_at,
                }
            )
        return _sha256(
            {
                "schema": self.schema,
                "aliases": self.aliases,
                "profiles": self.profiles,
                "models": models,
            }
        )

    def normalize_runner(self, runner: str) -> str | None:
        token = normalize_selector_token(runner)
        canonical = self.aliases.get(token, token)
        profile = self.profiles.get(canonical)
        if profile and profile.get("kind") == "runner":
            return normalize_selector_token(str(profile.get("runner", canonical)))
        known = {
            normalize_selector_token(str(profile.get("runner", "")))
            for profile in self.profiles.values()
            if profile.get("runner")
        }
        return canonical if canonical in known else None

    def resolve(
        self,
        selector: str,
        runner: str | None = None,
        *,
        resolved_at: str | None = None,
    ) -> ExecutionResolution:
        if not isinstance(selector, str):
            raise TypeError("execution selector must be a string")
        if runner is not None and not isinstance(runner, str):
            raise TypeError("execution runner must be a string or None")
        if not self.getriebe.alle_gaenge():
            raise ExecutionRegistryError("Clutch execution registry contains no models")

        requested = selector.strip()
        normalized = normalize_selector_token(selector)
        fingerprint = self.fingerprint()
        timestamp = resolved_at or _utc_now()
        requested_runner = self.normalize_runner(runner) if runner else None
        if runner and requested_runner is None:
            return self._unresolved(
                requested, normalized, "unknown-runner", fingerprint, timestamp
            )

        if normalized == "self":
            if requested_runner is None:
                return self._unresolved(
                    requested,
                    normalized,
                    "runner-required-for-self",
                    fingerprint,
                    timestamp,
                    selector_type="self",
                    model_selection="self",
                )
            return self._resolve_profile(
                requested,
                normalized,
                requested_runner,
                self.profiles.get(requested_runner, {}),
                fingerprint,
                timestamp,
                selector_type="self",
            )

        canonical = self.aliases.get(normalized, normalized)
        profile = self.profiles.get(canonical)
        if profile:
            profile_runner = self.normalize_runner(str(profile.get("runner", canonical)))
            if requested_runner and profile_runner != requested_runner:
                return self._unresolved(
                    requested,
                    normalized,
                    "runner-selector-conflict",
                    fingerprint,
                    timestamp,
                )
            return self._resolve_profile(
                requested,
                normalized,
                canonical,
                profile,
                fingerprint,
                timestamp,
            )

        matches_by_name: dict[str, Gang] = {}
        for gang in self.getriebe.alle_gaenge():
            if (
                normalize_selector_token(gang.name) == canonical
                or normalize_selector_token(gang.model_id) == canonical
            ):
                matches_by_name[gang.name] = gang
        matches = list(matches_by_name.values())
        if len(matches) > 1 and requested_runner:
            compatible = [gang for gang in matches if requested_runner in gang.runners]
            if compatible:
                matches = compatible
        if len(matches) > 1:
            return self._unresolved(
                requested,
                normalized,
                "ambiguous-exact-selector",
                fingerprint,
                timestamp,
            )
        if not matches:
            return self._unresolved(
                requested,
                normalized,
                "selector-not-in-registry",
                fingerprint,
                timestamp,
            )

        gang = matches[0]
        availability = ModelAvailability.from_mapping(gang.availability)
        allowed_runners = tuple(sorted(set(gang.runners)))
        runner_compatible = requested_runner is None or requested_runner in allowed_runners
        if not runner_compatible:
            evidence = availability.to_dict()
            evidence["runner_compatible"] = False
            availability = ModelAvailability.from_mapping(evidence)
        lifecycle_eligible = gang.lifecycle in _ELIGIBLE_LIFECYCLES
        claimable = (
            availability.claimable
            and bool(allowed_runners)
            and runner_compatible
            and lifecycle_eligible
        )
        if not runner_compatible:
            reason = "runner-not-compatible"
        elif not allowed_runners:
            reason = "runner-evidence-missing"
        elif not lifecycle_eligible:
            reason = "lifecycle-not-eligible"
        elif not availability.claimable:
            reason = "availability-unproven"
        else:
            reason = None
        selected_runner = requested_runner
        if selected_runner is None and len(allowed_runners) == 1:
            selected_runner = allowed_runners[0]
        return ExecutionResolution(
            requested_selector=requested,
            normalized_selector=normalized,
            canonical_selector=gang.name,
            selector_type="exact",
            model_selection="exact",
            resolved=True,
            runner=selected_runner,
            provider=gang.provider,
            registry_name=gang.name,
            model_id=gang.model_id,
            allowed_runners=allowed_runners,
            eligible_models=(gang.name,) if claimable else (),
            lifecycle=gang.lifecycle,
            catalog_source=gang.catalog_source,
            catalog_checked_at=gang.catalog_checked_at,
            availability=availability,
            claimable=claimable,
            reason=reason,
            registry_fingerprint=fingerprint,
            resolved_at=timestamp,
        )

    def _resolve_profile(
        self,
        requested: str,
        normalized: str,
        canonical: str,
        profile: Mapping[str, Any],
        fingerprint: str,
        resolved_at: str,
        selector_type: str | None = None,
    ) -> ExecutionResolution:
        kind = profile.get("kind")
        runner = self.normalize_runner(str(profile.get("runner", canonical)))
        if kind not in {"runner", "family"} or runner is None:
            return self._unresolved(
                requested,
                normalized,
                "invalid-registry-profile",
                fingerprint,
                resolved_at,
            )
        candidates = []
        for gang in self.getriebe.alle_gaenge():
            if not self._profile_matches(profile, gang):
                continue
            availability = ModelAvailability.from_mapping(gang.availability)
            if (
                availability.claimable
                and runner in gang.runners
                and gang.lifecycle in _ELIGIBLE_LIFECYCLES
            ):
                candidates.append(gang.name)
        resolved_type = selector_type or str(kind)
        return ExecutionResolution(
            requested_selector=requested,
            normalized_selector=normalized,
            canonical_selector=canonical,
            selector_type=resolved_type,
            model_selection="family" if kind == "family" else "self",
            resolved=True,
            runner=runner,
            provider=profile.get("provider"),
            registry_name=None,
            model_id=None,
            allowed_runners=(runner,),
            eligible_models=tuple(sorted(candidates)),
            lifecycle="profile",
            catalog_source=None,
            catalog_checked_at=None,
            availability=ModelAvailability(),
            claimable=bool(candidates),
            reason=None if candidates else "no-eligible-models",
            registry_fingerprint=fingerprint,
            resolved_at=resolved_at,
        )

    @staticmethod
    def _profile_matches(profile: Mapping[str, Any], gang: Gang) -> bool:
        providers = profile.get("providers")
        if providers is not None and gang.provider not in providers:
            return False
        provider = profile.get("provider")
        if provider is not None and gang.provider != provider:
            return False
        prefix = profile.get("model_id_prefix")
        return prefix is None or gang.model_id.startswith(str(prefix))

    @staticmethod
    def _unresolved(
        requested: str,
        normalized: str,
        reason: str,
        fingerprint: str,
        resolved_at: str,
        *,
        selector_type: str = "unresolved",
        model_selection: str | None = None,
    ) -> ExecutionResolution:
        return ExecutionResolution(
            requested_selector=requested,
            normalized_selector=normalized,
            canonical_selector=None,
            selector_type=selector_type,
            model_selection=model_selection,
            resolved=False,
            runner=None,
            provider=None,
            registry_name=None,
            model_id=None,
            allowed_runners=(),
            eligible_models=(),
            lifecycle="unknown",
            catalog_source=None,
            catalog_checked_at=None,
            availability=ModelAvailability(),
            claimable=False,
            reason=reason,
            registry_fingerprint=fingerprint,
            resolved_at=resolved_at,
        )


def resolve_execution_selector(
    selector: str,
    runner: str | None = None,
    *,
    registry: Getriebe | None = None,
    getriebe: Getriebe | None = None,
    resolved_at: str | None = None,
) -> dict[str, Any]:
    """Resolve without executing a model and return a stable JSON-ready mapping.

    ``getriebe`` is accepted as a compatibility alias for the unreleased v0.5
    contract. Supplying both registry keywords is an error.
    """
    if registry is not None and getriebe is not None:
        raise TypeError("pass either registry or getriebe, not both")
    if registry is not None:
        model_registry = registry
    elif getriebe is not None:
        model_registry = getriebe
    else:
        model_registry = Getriebe()
    result = ExecutionRegistry(model_registry).resolve(
        selector, runner=runner, resolved_at=resolved_at
    )
    return result.to_dict()


@dataclass(frozen=True)
class ProviderCatalogEntry:
    provider: str
    registry_name: str
    model_id: str
    lifecycle: str
    source: str
    checked_at: str
    availability: ModelAvailability
    runners: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, provider: str, data: Mapping[str, Any]) -> "ProviderCatalogEntry":
        lifecycle = data.get("lifecycle", "unknown")
        if lifecycle not in LIFECYCLES:
            raise ValueError(f"invalid lifecycle: {lifecycle}")
        required = ("registry_name", "model_id", "source", "checked_at")
        if any(not data.get(field) for field in required):
            raise ValueError("provider catalog entry is missing required evidence")
        raw_runners = data.get("runners", [])
        if not isinstance(raw_runners, (list, tuple)):
            raise ValueError("provider catalog runners must be a list of strings")
        runners = []
        for runner in raw_runners:
            if not isinstance(runner, str) or not normalize_selector_token(runner):
                raise ValueError("provider catalog runners must contain non-empty strings")
            runners.append(normalize_selector_token(runner))
        if len(runners) != len(set(runners)):
            raise ValueError("provider catalog runners must be unique")
        return cls(
            provider=provider,
            registry_name=str(data["registry_name"]),
            model_id=str(data["model_id"]),
            lifecycle=str(lifecycle),
            source=str(data["source"]),
            checked_at=str(data["checked_at"]),
            availability=ModelAvailability.from_mapping(data.get("availability")),
            runners=tuple(sorted(runners)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_name": self.registry_name,
            "model_id": self.model_id,
            "lifecycle": self.lifecycle,
            "source": self.source,
            "checked_at": self.checked_at,
            "availability": self.availability.to_dict(),
            "runners": list(self.runners),
        }


@dataclass(frozen=True)
class ProviderCatalogSnapshot:
    provider: str
    source: str
    checked_at: str
    entries: tuple[ProviderCatalogEntry, ...]
    schema: str = PROVIDER_CATALOG_SCHEMA

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProviderCatalogSnapshot":
        if data.get("schema") != PROVIDER_CATALOG_SCHEMA:
            raise ValueError("unsupported provider catalog schema")
        provider = str(data.get("provider", "")).strip()
        source = str(data.get("source", "")).strip()
        checked_at = str(data.get("checked_at", "")).strip()
        if not provider or not source or not checked_at:
            raise ValueError("provider catalog snapshot is missing provenance")
        raw_entries = data.get("entries", [])
        if not isinstance(raw_entries, (list, tuple)):
            raise ValueError("provider catalog entries must be a list")
        if not all(isinstance(entry, Mapping) for entry in raw_entries):
            raise ValueError("provider catalog entries must be objects")
        entries = tuple(
            sorted(
                (ProviderCatalogEntry.from_dict(provider, entry) for entry in raw_entries),
                key=lambda entry: entry.registry_name,
            )
        )
        names = [entry.registry_name for entry in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate provider catalog registry_name")
        return cls(provider=provider, source=source, checked_at=checked_at, entries=entries)

    @property
    def fingerprint(self) -> str:
        return _sha256(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "provider": self.provider,
            "source": self.source,
            "checked_at": self.checked_at,
            "entries": [entry.to_dict() for entry in self.entries],
        }


class ProviderCatalogAdapter(Protocol):
    """Injected adapter boundary; implementations own all provider I/O."""

    provider: str

    def fetch(self) -> ProviderCatalogSnapshot:
        """Return one validated, evidence-bearing snapshot."""


@dataclass(frozen=True)
class ProviderCatalogDiff:
    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "added": list(self.added),
            "removed": list(self.removed),
            "changed": list(self.changed),
        }


@dataclass(frozen=True)
class ProviderRefreshResult:
    provider: str
    snapshot_accepted: bool
    retained_previous: bool
    snapshot: ProviderCatalogSnapshot | None
    diff: ProviderCatalogDiff
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "snapshot_accepted": self.snapshot_accepted,
            "retained_previous": self.retained_previous,
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "snapshot_fingerprint": self.snapshot.fingerprint if self.snapshot else None,
            "diff": self.diff.to_dict(),
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class ProviderCatalogApplyResult:
    """Result of enriching existing curated gears with runtime evidence."""

    provider: str
    applied: bool
    updated: tuple[str, ...] = ()
    skipped_unregistered: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "applied": self.applied,
            "updated": list(self.updated),
            "skipped_unregistered": list(self.skipped_unregistered),
        }


def apply_provider_catalog(
    getriebe: Getriebe,
    snapshot: ProviderCatalogSnapshot,
) -> ProviderCatalogApplyResult:
    """Atomically enrich curated gears; never add provider-discovered models."""
    if not isinstance(snapshot, ProviderCatalogSnapshot):
        raise TypeError("snapshot must be ProviderCatalogSnapshot")

    updates: list[tuple[Gang, ProviderCatalogEntry]] = []
    skipped: list[str] = []
    for entry in snapshot.entries:
        gang = getriebe.gang(entry.registry_name, einschliesslich_deaktiviert=True)
        if gang is None:
            skipped.append(entry.registry_name)
            continue
        if gang.provider != snapshot.provider or gang.model_id != entry.model_id:
            raise ValueError(f"provider catalog identity mismatch: {entry.registry_name}")
        updates.append((gang, entry))

    for gang, entry in updates:
        gang.lifecycle = entry.lifecycle
        gang.catalog_source = entry.source
        gang.catalog_checked_at = entry.checked_at
        gang.availability = entry.availability.to_dict()
        gang.runners = list(entry.runners)

    return ProviderCatalogApplyResult(
        provider=snapshot.provider,
        applied=True,
        updated=tuple(entry.registry_name for _, entry in updates),
        skipped_unregistered=tuple(skipped),
    )


def refresh_provider_catalog(
    adapter: ProviderCatalogAdapter,
    *,
    previous: ProviderCatalogSnapshot | None = None,
) -> ProviderRefreshResult:
    """Refresh through an injected adapter and retain proven state on failure."""
    provider = previous.provider if previous is not None else "unknown"
    try:
        provider = str(getattr(adapter, "provider", "unknown"))
        if previous is not None and previous.provider != provider:
            return ProviderRefreshResult(
                provider=provider,
                snapshot_accepted=False,
                retained_previous=False,
                snapshot=None,
                diff=ProviderCatalogDiff(),
                error_code="invalid-previous-provider",
            )
        snapshot = adapter.fetch()
        if not isinstance(snapshot, ProviderCatalogSnapshot):
            raise TypeError("adapter must return ProviderCatalogSnapshot")
        if snapshot.provider != provider:
            raise ValueError("adapter/provider mismatch")
        return ProviderRefreshResult(
            provider=provider,
            snapshot_accepted=True,
            retained_previous=False,
            snapshot=snapshot,
            diff=_catalog_diff(previous, snapshot),
        )
    except Exception as exc:  # adapter boundary must fail closed
        return ProviderRefreshResult(
            provider=provider,
            snapshot_accepted=False,
            retained_previous=previous is not None,
            snapshot=previous,
            diff=ProviderCatalogDiff(),
            error_code=f"adapter-error:{type(exc).__name__}",
        )


def _catalog_diff(
    previous: ProviderCatalogSnapshot | None,
    current: ProviderCatalogSnapshot,
) -> ProviderCatalogDiff:
    old = (
        {entry.registry_name: entry.to_dict() for entry in previous.entries}
        if previous
        else {}
    )
    new = {entry.registry_name: entry.to_dict() for entry in current.entries}
    return ProviderCatalogDiff(
        added=tuple(sorted(set(new) - set(old))),
        removed=tuple(sorted(set(old) - set(new))),
        changed=tuple(
            sorted(name for name in set(old) & set(new) if old[name] != new[name])
        ),
    )


__all__ = [
    "AVAILABILITY_STAGES",
    "LIFECYCLES",
    "PROVIDER_CATALOG_SCHEMA",
    "ExecutionRegistry",
    "ExecutionRegistryError",
    "ExecutionResolution",
    "ModelAvailability",
    "ProviderCatalogAdapter",
    "ProviderCatalogApplyResult",
    "ProviderCatalogDiff",
    "ProviderCatalogEntry",
    "ProviderCatalogSnapshot",
    "ProviderRefreshResult",
    "apply_provider_catalog",
    "normalize_selector_token",
    "refresh_provider_catalog",
    "resolve_execution_selector",
]
