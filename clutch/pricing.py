"""Versionierte Preis- und Usage-Berechnung fuer clutch.

Alle Kostenpfade (CLI, Tacho, Tankuhr und API-JSON) verwenden diese Funktionen.
Reasoning-Tokens sind laut OpenAI Bestandteil der Output-Tokens und werden
deshalb nur als beobachtete Teilmenge ausgewiesen, niemals erneut berechnet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional


VALID_DATA_STATUS = {"observed", "assumed", "unknown"}


@dataclass(frozen=True)
class PricingSpec:
    """Versionierter Tarif eines Modells, Preise jeweils pro Million Tokens."""

    version: str
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float
    source_url: str
    checked_at: str
    effective_at: str
    cache_write_multiplier: float = 1.25
    long_context_threshold: int = 272_000
    long_input_multiplier: float = 2.0
    long_output_multiplier: float = 1.5
    stale_after_days: int = 45
    service_tier_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "default": 1.0,
            "standard": 1.0,
            "auto": 1.0,
            "fast": 2.0,
            "priority": 2.0,
        }
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PricingSpec":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def is_stale(self, as_of: Optional[date] = None) -> bool:
        """Signalisiert, ob die letzte Quellenpruefung abgelaufen ist."""
        checked = date.fromisoformat(self.checked_at)
        return (as_of or date.today()) > checked + timedelta(days=self.stale_after_days)


@dataclass(frozen=True)
class UsageRecord:
    """Normalisierte Usage eines Aufrufs.

    ``input_tokens`` ist der vom Provider gemeldete gesamte Input. Cached- und
    Cache-Write-Tokens sind darin enthalten und werden fuer die Preisberechnung
    herausgerechnet. Ohne Provider-Usage bleibt der Status ``unknown``.
    """

    input_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    tool_fees_usd: float = 0.0
    service_tier: str = "default"
    data_status: str = "unknown"

    def __post_init__(self) -> None:
        if self.data_status not in VALID_DATA_STATUS:
            raise ValueError(f"ungueltiger data_status: {self.data_status}")
        for name in (
            "input_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "output_tokens",
            "reasoning_tokens",
        ):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} darf nicht negativ sein")
        if self.tool_fees_usd < 0:
            raise ValueError("tool_fees_usd darf nicht negativ sein")


@dataclass(frozen=True)
class CostBreakdown:
    """Nachvollziehbares Ergebnis der zentralen Kostenberechnung."""

    known: bool
    data_status: str
    total_usd: Optional[float]
    input_usd: Optional[float]
    cached_input_usd: Optional[float]
    cache_write_usd: Optional[float]
    output_usd: Optional[float]
    tool_fees_usd: Optional[float]
    input_tokens: Optional[int]
    uncached_input_tokens: Optional[int]
    cached_input_tokens: Optional[int]
    cache_write_tokens: Optional[int]
    output_tokens: Optional[int]
    reasoning_tokens: Optional[int]
    reasoning_tokens_billed_separately: bool
    long_context: Optional[bool]
    service_tier: str
    service_tier_multiplier: Optional[float]
    pricing_version: str
    pricing_source_url: str
    pricing_checked_at: str
    pricing_effective_at: str
    pricing_stale: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.000000000001")))


def calculate_cost(
    pricing: PricingSpec,
    usage: UsageRecord,
    *,
    as_of: Optional[date] = None,
) -> CostBreakdown:
    """Berechnet Kosten; unbekannte Usage wird nicht still als Null verbucht."""
    base = {
        "known": False,
        "data_status": usage.data_status,
        "total_usd": None,
        "input_usd": None,
        "cached_input_usd": None,
        "cache_write_usd": None,
        "output_usd": None,
        "tool_fees_usd": None,
        "input_tokens": usage.input_tokens,
        "uncached_input_tokens": None,
        "cached_input_tokens": usage.cached_input_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.reasoning_tokens,
        "reasoning_tokens_billed_separately": False,
        "long_context": None,
        "service_tier": usage.service_tier,
        "service_tier_multiplier": None,
        "pricing_version": pricing.version,
        "pricing_source_url": pricing.source_url,
        "pricing_checked_at": pricing.checked_at,
        "pricing_effective_at": pricing.effective_at,
        "pricing_stale": pricing.is_stale(as_of),
    }
    if usage.data_status == "unknown" or usage.input_tokens is None or usage.output_tokens is None:
        return CostBreakdown(**base)

    cached = usage.cached_input_tokens or 0
    cache_write = usage.cache_write_tokens or 0
    if cached + cache_write > usage.input_tokens:
        raise ValueError("cached_input_tokens + cache_write_tokens ueberschreiten input_tokens")
    if usage.reasoning_tokens is not None and usage.reasoning_tokens > usage.output_tokens:
        raise ValueError("reasoning_tokens muessen in output_tokens enthalten sein")

    if usage.service_tier not in pricing.service_tier_multipliers:
        raise ValueError(f"unbekannter service_tier: {usage.service_tier}")
    tier_multiplier = Decimal(str(pricing.service_tier_multipliers[usage.service_tier]))
    long_context = usage.input_tokens > pricing.long_context_threshold
    input_multiplier = Decimal(str(pricing.long_input_multiplier if long_context else 1.0))
    output_multiplier = Decimal(str(pricing.long_output_multiplier if long_context else 1.0))
    per_million = Decimal("1000000")

    uncached = usage.input_tokens - cached - cache_write
    input_cost = (
        Decimal(uncached)
        * Decimal(str(pricing.input_per_million))
        * input_multiplier
        / per_million
    )
    cached_cost = (
        Decimal(cached)
        * Decimal(str(pricing.cached_input_per_million))
        * input_multiplier
        / per_million
    )
    cache_write_cost = (
        Decimal(cache_write)
        * Decimal(str(pricing.input_per_million))
        * Decimal(str(pricing.cache_write_multiplier))
        * input_multiplier
        / per_million
    )
    output_cost = (
        Decimal(usage.output_tokens)
        * Decimal(str(pricing.output_per_million))
        * output_multiplier
        / per_million
    )
    tool_cost = Decimal(str(usage.tool_fees_usd))

    # Der Service-Tier-Multiplikator gilt fuer Modell-Tokens; Tool-Gebuehren
    # werden separat gemeldet und nicht ohne eigene Quelle vervielfacht.
    input_cost *= tier_multiplier
    cached_cost *= tier_multiplier
    cache_write_cost *= tier_multiplier
    output_cost *= tier_multiplier
    total = input_cost + cached_cost + cache_write_cost + output_cost + tool_cost

    return CostBreakdown(
        **{
            **base,
            "known": True,
            "total_usd": _money(total),
            "input_usd": _money(input_cost),
            "cached_input_usd": _money(cached_cost),
            "cache_write_usd": _money(cache_write_cost),
            "output_usd": _money(output_cost),
            "tool_fees_usd": _money(tool_cost),
            "uncached_input_tokens": uncached,
            "long_context": long_context,
            "service_tier_multiplier": float(tier_multiplier),
        }
    )


def cost_for_gang(gang: Any, usage: UsageRecord, *, as_of: Optional[date] = None) -> CostBreakdown:
    """Berechnet ueber die Gang-SSOT; Legacy-Gaenge werden explizit abgeleitet."""
    pricing = getattr(gang, "pricing", None)
    if pricing is None:
        pricing = PricingSpec(
            version=f"legacy-{gang.name}",
            input_per_million=float(gang.kosten_input_1k) * 1000,
            cached_input_per_million=float(gang.kosten_input_1k) * 1000,
            output_per_million=float(gang.kosten_output_1k) * 1000,
            source_url=getattr(gang, "catalog_source", None) or "local-catalog",
            checked_at=getattr(gang, "catalog_checked_at", None) or date.today().isoformat(),
            effective_at=getattr(gang, "catalog_checked_at", None) or date.today().isoformat(),
            cache_write_multiplier=1.0,
            long_context_threshold=10**18,
            long_input_multiplier=1.0,
            long_output_multiplier=1.0,
            service_tier_multipliers={"default": 1.0, "standard": 1.0, "auto": 1.0},
        )
    return calculate_cost(pricing, usage, as_of=as_of)
