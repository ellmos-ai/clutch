"""Getriebe -- Provider-neutrale Modell-Registry.

Das Getriebe verwaltet alle verfuegbaren Gaenge (Modelle)
ueber alle Provider hinweg: Anthropic, Google, Ollama, etc.

Jeder Gang hat eine Nummer (1-5), Kosten, Staerken/Schwaechen.
Das Getriebe ist neutral -- es weiss nicht wer faehrt (Fahrer),
es stellt nur die Gaenge bereit.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Optional

from clutch.pricing import PricingSpec, UsageRecord, cost_for_gang
from clutch.user_overrides import lade_user_overrides


@dataclass
class Gang:
    """Ein Gang = ein konkretes Modell eines Providers."""
    name: str                    # z.B. "claude-sonnet", "gemini-flash"
    provider: str                # "anthropic", "google", "ollama"
    model_id: str                # API model ID
    gang: int                    # 1-5 (1=niedrigster, 5=hoechster)
    leistung: str                # "basis", "mittel", "hoch", "max"
    kosten_input_1k: float       # USD pro 1K Input-Tokens
    kosten_output_1k: float      # USD pro 1K Output-Tokens
    staerken: list[str] = field(default_factory=list)
    schwaechen: list[str] = field(default_factory=list)
    max_context: int = 200000
    endpoint: Optional[str] = None  # Fuer lokale Modelle
    efforts: list[str] = field(default_factory=list)
    reasoning_modes: list[str] = field(default_factory=list)
    catalog_checked_at: Optional[str] = None
    catalog_source: Optional[str] = None
    quantization: Optional[str] = None
    pricing: Optional[PricingSpec] = None
    lifecycle: str = "unknown"
    availability: dict[str, Optional[bool]] = field(default_factory=dict)
    runners: list[str] = field(default_factory=list)

    @property
    def ist_lokal(self) -> bool:
        return self.provider == "ollama"

    @property
    def ist_kostenlos(self) -> bool:
        return self.kosten_input_1k == 0 and self.kosten_output_1k == 0

    def kosten_schaetzen(self, tokens: int, input_anteil: float = 0.3) -> float:
        """Schaetzt Kosten fuer eine gegebene Token-Menge."""
        inp = int(tokens * input_anteil)
        out = tokens - inp
        ergebnis = cost_for_gang(
            self,
            UsageRecord(
                input_tokens=inp,
                cached_input_tokens=0,
                cache_write_tokens=0,
                output_tokens=out,
                reasoning_tokens=0,
                data_status="assumed",
            ),
        )
        return float(ergebnis.total_usd or 0.0)


@dataclass
class ProviderInfo:
    name: str
    typ: str              # "api" | "lokal"
    auth_env_var: Optional[str] = None
    basis_url: Optional[str] = None


class Getriebe:
    """Verwaltet alle verfuegbaren Gaenge (Modelle) aller Provider.

    Nutzung:
        getriebe = Getriebe()
        gang = getriebe.gang("claude-sonnet")
        alle_guenstigen = getriebe.filter(max_gang=2)
        lokale = getriebe.filter(provider="ollama")
    """

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        overrides_path: Optional[Path] = None,
    ):
        self.config_dir = config_dir or Path(__file__).parent / "config"
        self.overrides_path = overrides_path
        self._gaenge: dict[str, Gang] = {}
        self._provider: dict[str, ProviderInfo] = {}
        self._fahrer_optionen: dict = {}
        self._disabled_models: set[str] = set()
        self._preferred_models: list[str] = []
        self._preferred_providers: list[str] = []
        self._role_preferred_models: dict[str, list[str]] = {}
        self._role_profile_path: Optional[str] = None
        self._aliases: dict[str, str] = {}
        self._model_max_gang: dict[str, object] = {}
        self._model_cost_overrides: dict[str, object] = {}
        self._execution_registry: dict = {}
        self._load()

    def _load(self) -> None:
        path = self.config_dir / "getriebe.json"
        if not path.exists():
            return

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self._execution_registry = deepcopy(data.get("execution_registry", {}))
        provider_evidence = self._execution_registry.get("provider_evidence", {})

        # Gaenge laden
        for name, cfg in data.get("gaenge", {}).items():
            evidence = provider_evidence.get(cfg.get("provider", "unknown"), {})
            pricing = PricingSpec.from_dict(cfg["pricing"]) if cfg.get("pricing") else None
            self._gaenge[name] = Gang(
                name=name,
                provider=cfg.get("provider", "unknown"),
                model_id=cfg.get("model_id", name),
                gang=cfg.get("gang", 1),
                leistung=cfg.get("leistung", "basis"),
                kosten_input_1k=cfg.get(
                    "kosten_input_1k",
                    pricing.input_per_million / 1000 if pricing else 0,
                ),
                kosten_output_1k=cfg.get(
                    "kosten_output_1k",
                    pricing.output_per_million / 1000 if pricing else 0,
                ),
                staerken=cfg.get("staerken", []),
                schwaechen=cfg.get("schwaechen", []),
                max_context=cfg.get("max_context", 200000),
                endpoint=cfg.get("endpoint"),
                efforts=cfg.get("efforts", []),
                reasoning_modes=cfg.get("reasoning_modes", []),
                catalog_checked_at=cfg.get(
                    "catalog_checked_at", evidence.get("catalog_checked_at")
                ),
                catalog_source=cfg.get("catalog_source", evidence.get("catalog_source")),
                quantization=cfg.get("quantization"),
                pricing=pricing,
                lifecycle=cfg.get("lifecycle", evidence.get("lifecycle", "unknown")),
                availability=deepcopy(
                    cfg.get("availability", evidence.get("availability", {}))
                ),
                runners=list(cfg.get("runners", evidence.get("runners", []))),
            )

        # Provider laden
        for name, cfg in data.get("provider", {}).items():
            self._provider[name] = ProviderInfo(
                name=name,
                typ=cfg.get("typ", "api"),
                auth_env_var=cfg.get("auth"),
                basis_url=cfg.get("basis_url"),
            )

        self._fahrer_optionen = data.get("fahrer_optionen", {})
        self._apply_user_overrides()

    def execution_registry_config(self) -> dict:
        """Return an isolated copy of the public selector-profile contract."""
        return deepcopy(self._execution_registry)

    def registry_fingerprint(self) -> str:
        """Fingerprint all facts that influence execution resolution."""
        from clutch.execution import ExecutionRegistry

        return ExecutionRegistry(self).fingerprint()

    def resolve_execution_selector(self, selector: str, runner: Optional[str] = None):
        """Resolve a runner, self, family or exact execution selector."""
        from clutch.execution import resolve_execution_selector

        return resolve_execution_selector(selector, runner=runner, registry=self)

    def apply_provider_catalog(self, snapshot):
        """Overlay validated provider evidence onto curated gears."""
        from clutch.execution import apply_provider_catalog

        return apply_provider_catalog(self, snapshot)

    def _apply_user_overrides(self) -> None:
        overrides = lade_user_overrides(self.overrides_path)
        self._aliases = {
            str(alias).strip(): str(target).strip()
            for alias, target in overrides.get("aliases", {}).items()
            if str(alias).strip() and str(target).strip()
        }
        self._disabled_models = {
            self._aliases.get(name, name)
            for name in overrides.get("disabled_models", [])
        }
        self._preferred_models = [
            self._aliases.get(name, name)
            for name in overrides.get("preferred_models", [])
        ]
        self._preferred_providers = list(overrides.get("preferred_providers", []))
        self._role_preferred_models = overrides.get("role_preferred_models", {})
        self._role_profile_path = overrides.get("role_profile_path")
        self._model_max_gang = {
            self._aliases.get(name, name): value
            for name, value in overrides.get("model_max_gang", {}).items()
        }
        self._model_cost_overrides = {
            self._aliases.get(name, name): value
            for name, value in overrides.get("model_cost_override", {}).items()
        }
        for gang in self._gaenge.values():
            self._apply_gang_overrides(gang)

    def _apply_gang_overrides(self, gang: Gang) -> None:
        model_max_gang = getattr(self, "_model_max_gang", {})
        if gang.name in model_max_gang:
            value = model_max_gang[gang.name]
            try:
                maximum = max(1, min(5, int(value)))
            except (TypeError, ValueError):
                maximum = gang.gang
            if gang.gang > maximum:
                gang.gang = maximum

        override = getattr(self, "_model_cost_overrides", {}).get(gang.name)
        if isinstance(override, dict):
            input_1k = override.get("kosten_input_1k", override.get("input_per_1k"))
            output_1k = override.get("kosten_output_1k", override.get("output_per_1k"))
            input_million = override.get("input_per_million")
            output_million = override.get("output_per_million")
            try:
                if input_million is not None:
                    input_1k = float(input_million) / 1000
                if output_million is not None:
                    output_1k = float(output_million) / 1000
                if input_1k is not None:
                    gang.kosten_input_1k = float(input_1k)
                if output_1k is not None:
                    gang.kosten_output_1k = float(output_1k)
            except (TypeError, ValueError):
                return
            if gang.pricing is not None:
                gang.pricing = replace(
                    gang.pricing,
                    input_per_million=gang.kosten_input_1k * 1000,
                    output_per_million=gang.kosten_output_1k * 1000,
                    version=f"{gang.pricing.version}+user-override",
                    source_url="user_overrides.json",
                )

    def resolve_name(self, name: str) -> str:
        """Loest Nutzer-Aliase auf; unbekannte Namen bleiben unveraendert."""
        return getattr(self, "_aliases", {}).get(name, name)

    def gang(self, name: str, einschliesslich_deaktiviert: bool = False) -> Optional[Gang]:
        """Gibt einen Gang nach Name zurueck."""
        canonical = self.resolve_name(name)
        if not einschliesslich_deaktiviert and canonical in getattr(self, "_disabled_models", set()):
            return None
        return self._gaenge.get(canonical)

    def alle_gaenge(self, einschliesslich_deaktiviert: bool = False) -> list[Gang]:
        """Alle registrierten Gaenge, sortiert nach Gang-Nummer."""
        values = self._gaenge.values()
        if not einschliesslich_deaktiviert:
            disabled = getattr(self, "_disabled_models", set())
            values = (g for g in values if g.name not in disabled)
        return sorted(values, key=lambda g: g.gang)

    def ist_deaktiviert(self, name: str) -> bool:
        return self.resolve_name(name) in getattr(self, "_disabled_models", set())

    @property
    def preferred_models(self) -> list[str]:
        return list(getattr(self, "_preferred_models", []))

    @property
    def preferred_providers(self) -> list[str]:
        return list(getattr(self, "_preferred_providers", []))

    def role_preferred_models(self, role: str) -> list[str]:
        """Return a strictly configured role preference, never a guessed model."""
        if role not in {"thinker", "worker", "draft", "reviewer", "escalation"}:
            raise ValueError(f"unknown routing role: {role}")
        configured = self._role_preferred_models
        if self._role_profile_path:
            if configured:
                raise ValueError("role profile and manual role preferences are mutually exclusive")
            configured = self._load_role_profile()
        models = configured.get(role)
        if not models:
            raise ValueError(f"no model preference configured for role: {role}")
        for name in models:
            if self.gang(name, einschliesslich_deaktiviert=True) is None:
                raise ValueError(f"unknown model for role {role}: {name}")
        return list(models)

    def _load_role_profile(self) -> dict[str, list[str]]:
        """Read an explicitly selected private model-strategy profile for role routing."""
        path = Path(self._role_profile_path or "")
        if not path.is_absolute() or not path.is_file():
            raise ValueError("role profile must be an existing absolute file")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("role profile is unreadable or invalid JSON") from error
        if not isinstance(data, dict) or data.get("schema_version") != "1.0.0":
            raise ValueError("unsupported role profile schema")
        entries = data.get("models")
        if not isinstance(entries, list) or not entries:
            raise ValueError("role profile needs a nonempty models list")
        known_roles = {"thinker", "worker", "draft", "reviewer", "escalation"}
        by_role: dict[str, list[str]] = {}
        seen: set[str] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("invalid role profile model entry")
            name, provider, roles = entry.get("id"), entry.get("provider"), entry.get("roles")
            if not isinstance(name, str) or not name or name in seen:
                raise ValueError("invalid or duplicate role profile model ID")
            seen.add(name)
            gang = self._gaenge.get(name)
            if gang is None or gang.provider != provider:
                raise ValueError(f"unregistered model or provider in role profile: {name}")
            if entry.get("verified") is not True or entry.get("deprecated") is not False:
                raise ValueError(f"unverified or deprecated role profile model: {name}")
            if not isinstance(roles, list) or not roles or any(
                not isinstance(item, str) or item not in known_roles for item in roles
            ) or len(set(roles)) != len(roles):
                raise ValueError(f"invalid roles in role profile model: {name}")
            for item in roles:
                by_role.setdefault(item, []).append(name)
        return by_role

    @property
    def aliases(self) -> dict[str, str]:
        return dict(getattr(self, "_aliases", {}))

    def passende_praeferenz(self, token: str) -> tuple[str, list[Gang]]:
        """Loest eine Aufrufpraeferenz als Gang, Provider oder eindeutigen Kurznamen auf."""
        canonical = self.resolve_name(token)
        exact = self.gang(canonical)
        if exact is not None:
            return "model", [exact]
        provider_matches = [g for g in self.alle_gaenge() if g.provider == token]
        if provider_matches:
            return "provider", provider_matches
        model_id_matches = [g for g in self.alle_gaenge() if g.model_id == token]
        if model_id_matches:
            return "model", model_id_matches
        short = token.lower().strip()
        name_matches = [
            g for g in self.alle_gaenge()
            if short and short in g.name.lower().replace("_", "-").split("-")
        ]
        return ("model", name_matches) if len(name_matches) == 1 else ("unknown", [])

    def filter(
        self,
        provider: Optional[str] = None,
        max_gang: Optional[int] = None,
        min_gang: Optional[int] = None,
        nur_lokal: bool = False,
        nur_kostenlos: bool = False,
        staerke: Optional[str] = None,
    ) -> list[Gang]:
        """Filtert Gaenge nach Kriterien."""
        result = self.alle_gaenge()

        if provider:
            result = [g for g in result if g.provider == provider]
        if max_gang is not None:
            result = [g for g in result if g.gang <= max_gang]
        if min_gang is not None:
            result = [g for g in result if g.gang >= min_gang]
        if nur_lokal:
            result = [g for g in result if g.ist_lokal]
        if nur_kostenlos:
            result = [g for g in result if g.ist_kostenlos]
        if staerke:
            result = [g for g in result if staerke in g.staerken]

        return sorted(result, key=lambda g: g.gang)

    def naechster_gang_runter(self, aktuell: str) -> Optional[Gang]:
        """Findet den naechstniedrigeren Gang (Downshift)."""
        current = self.gang(aktuell)
        if not current:
            return None

        candidates = [g for g in self.alle_gaenge()
                      if g.gang < current.gang]
        if not candidates:
            return None
        return max(candidates, key=lambda g: g.gang)

    def naechster_gang_hoch(self, aktuell: str) -> Optional[Gang]:
        """Findet den naechsthoeheren Gang (Upshift)."""
        current = self.gang(aktuell)
        if not current:
            return None

        candidates = [g for g in self.alle_gaenge()
                      if g.gang > current.gang]
        if not candidates:
            return None
        return min(candidates, key=lambda g: g.gang)

    def standard_fahrer(self) -> Optional[Gang]:
        """Das Standard-Modell fuer den Fahrer (Orchestrator)."""
        name = self._fahrer_optionen.get("standard", "claude-opus")
        return self.gang(name)

    def fahrer_alternativen(self) -> list[Gang]:
        """Alternative Fahrer-Modelle."""
        names = self._fahrer_optionen.get("alternativen", [])
        return [g for name in names if (g := self.gang(name))]

    def provider_info(self, name: str) -> Optional[ProviderInfo]:
        return self._provider.get(name)

    def registriere_gang(self, gang: Gang) -> None:
        """Registriert einen neuen Gang zur Laufzeit."""
        self._apply_gang_overrides(gang)
        self._gaenge[gang.name] = gang

    def entferne_gang(self, name: str) -> bool:
        """Entfernt einen Gang."""
        if name in self._gaenge:
            del self._gaenge[name]
            return True
        return False

    def __len__(self) -> int:
        return len(self.alle_gaenge())

    def __repr__(self) -> str:
        gaenge = ", ".join(f"{g.name}(G{g.gang})" for g in self.alle_gaenge())
        return f"Getriebe[{gaenge}]"
