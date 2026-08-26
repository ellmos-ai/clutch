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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from clutch.pricing import PricingSpec, UsageRecord, cost_for_gang


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

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent / "config"
        self._gaenge: dict[str, Gang] = {}
        self._provider: dict[str, ProviderInfo] = {}
        self._fahrer_optionen: dict = {}
        self._execution_registry: dict = {}
        self._load()

    def _load(self) -> None:
        path = self.config_dir / "getriebe.json"
        if not path.exists():
            return

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        self._execution_registry = data.get("execution_registry", {})
        provider_evidence = self._execution_registry.get("provider_evidence", {})

        # Gaenge laden
        for name, cfg in data.get("gaenge", {}).items():
            pricing = PricingSpec.from_dict(cfg["pricing"]) if cfg.get("pricing") else None
            evidence = provider_evidence.get(cfg.get("provider", "unknown"), {})
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
    def execution_registry_config(self) -> dict:
        """Return an isolated copy of the public selector-profile contract."""
        return deepcopy(self._execution_registry)

    def registry_fingerprint(self) -> str:
        """Fingerprint model identities, evidence, aliases, and profiles."""
        from clutch.execution_registry import ExecutionRegistry

        return ExecutionRegistry(self).fingerprint()

    def resolve_execution_selector(self, selector: str, runner: Optional[str] = None):
        """Resolve a public runner/self/family/exact execution selector."""
        from clutch.execution_registry import ExecutionRegistry

        return ExecutionRegistry(self).resolve(selector, runner=runner)

    def apply_provider_catalog(self, snapshot):
        """Overlay validated provider evidence onto existing curated gears."""
        from clutch.execution_registry import apply_provider_catalog

        return apply_provider_catalog(self, snapshot)

    def gang(self, name: str) -> Optional[Gang]:
        """Gibt einen Gang nach Name zurueck."""
        return self._gaenge.get(name)

    def alle_gaenge(self) -> list[Gang]:
        """Alle registrierten Gaenge, sortiert nach Gang-Nummer."""
        return sorted(self._gaenge.values(), key=lambda g: g.gang)

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
        result = list(self._gaenge.values())

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

        candidates = [g for g in self._gaenge.values()
                      if g.gang < current.gang]
        if not candidates:
            return None
        return max(candidates, key=lambda g: g.gang)

    def naechster_gang_hoch(self, aktuell: str) -> Optional[Gang]:
        """Findet den naechsthoeheren Gang (Upshift)."""
        current = self.gang(aktuell)
        if not current:
            return None

        candidates = [g for g in self._gaenge.values()
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
        self._gaenge[gang.name] = gang

    def entferne_gang(self, name: str) -> bool:
        """Entfernt einen Gang."""
        if name in self._gaenge:
            del self._gaenge[name]
            return True
        return False

    def __len__(self) -> int:
        return len(self._gaenge)

    def __repr__(self) -> str:
        gaenge = ", ".join(f"{g.name}(G{g.gang})" for g in self.alle_gaenge())
        return f"Getriebe[{gaenge}]"
