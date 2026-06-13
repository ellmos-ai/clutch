"""Partner -- Cross-Agent-Delegation mit Budget-Zonen.

Portiert und an clutch angepasst aus BACHs Partner-Handler
(hub/partner.py + delegation/complexity_scorer.get_partner_recommendation).

Ein "Partner" ist ein Delegations-Ziel jenseits der reinen Provider-APIs:
- external_ai: anderer Agent/CLI (Codex, agy/Gemini-CLI, Kimi-CLI, ...)
- local_ai:   lokales Modell (Ollama lokal/remote)
- human:      Eskalation an den Menschen (Budget-Zone 4)

Delegations-Zonen koppeln das Budget an die erlaubte Partner-Klasse:
  Zone 1 (0-30%):  alles erlaubt
  Zone 2 (30-60%): nur guenstige Partner (kein teures external_ai-Premium)
  Zone 3 (60-80%): nur lokale AI / guenstig
  Zone 4 (80-100%): nur Mensch (keine bezahlte AI mehr)

Zero-Dependency (nur stdlib).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


PartnerTyp = str  # "external_ai" | "local_ai" | "human"
CostTier = str    # "low" | "medium" | "high" | "free"


@dataclass
class Partner:
    name: str
    typ: PartnerTyp = "external_ai"
    cost_tier: CostTier = "medium"
    endpoint: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)
    success_rate: float = 1.0
    priority: int = 50
    verfuegbar: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "typ": self.typ,
            "cost_tier": self.cost_tier,
            "endpoint": self.endpoint,
            "capabilities": list(self.capabilities),
            "success_rate": self.success_rate,
            "priority": self.priority,
            "verfuegbar": self.verfuegbar,
        }


# Budget-Zone (1-4) -> erlaubte Partner-Typen + max. Cost-Tier
DELEGATION_ZONEN = {
    1: {"typen": {"external_ai", "local_ai", "human"}, "max_cost": {"low", "medium", "high", "free"}},
    2: {"typen": {"external_ai", "local_ai", "human"}, "max_cost": {"low", "medium", "free"}},
    3: {"typen": {"local_ai", "human"}, "max_cost": {"low", "free"}},
    4: {"typen": {"human"}, "max_cost": {"free"}},
}

_ZONE_NAME_TO_NR = {"green": 1, "yellow": 2, "orange": 3, "red": 4}


def zone_nummer(zone: str | int) -> int:
    """Normalisiert Zonen-Bezeichnung (green/.. oder 1-4) auf 1-4.

    Fail-safe: unbekannte Werte werden zur restriktivsten Zone (4 = nur Mensch),
    NICHT zur offensten -- ein Tippfehler darf keine Budget-Eskalation umgehen.
    """
    if isinstance(zone, int):
        return max(1, min(4, zone))
    return _ZONE_NAME_TO_NR.get(str(zone).lower(), 4)


class PartnerRegistry:
    """Verwaltet Partner und empfiehlt Delegations-Ziele nach Zone/Zweck."""

    def __init__(self, partner: Optional[list[Partner]] = None):
        self._partner: dict[str, Partner] = {}
        for p in (partner or self._defaults()):
            self._partner[p.name] = p

    @staticmethod
    def _defaults() -> list[Partner]:
        # Default-Partner spiegeln die real verfuegbaren Delegationswege.
        return [
            Partner("codex", "external_ai", "medium", capabilities=["code", "review"], priority=60),
            Partner("agy", "external_ai", "low", capabilities=["research", "vision"], priority=55),
            Partner("kimi-cli", "external_ai", "low", capabilities=["code", "agent"], priority=50),
            Partner("ollama-local", "local_ai", "free", endpoint="http://localhost:11434",
                    capabilities=["code", "bulk"], priority=40),
            Partner("human", "human", "free", capabilities=["entscheidung", "freigabe"], priority=10),
        ]

    def add(self, partner: Partner) -> None:
        self._partner[partner.name] = partner

    def get(self, name: str) -> Optional[Partner]:
        return self._partner.get(name)

    def alle(self) -> list[Partner]:
        return list(self._partner.values())

    def verfuegbare(self) -> list[Partner]:
        return [p for p in self._partner.values() if p.verfuegbar]

    def erlaubt_in_zone(self, partner: Partner, zone: str | int) -> bool:
        z = DELEGATION_ZONEN[zone_nummer(zone)]
        return partner.typ in z["typen"] and partner.cost_tier in z["max_cost"]

    def empfehle(
        self,
        zone: str | int = 1,
        zweck: Optional[str] = None,
    ) -> Optional[Partner]:
        """Empfiehlt den besten erlaubten Partner fuer Zone (+ optional Zweck).

        Auswahl: nur verfuegbare + zonen-erlaubte Partner; bevorzugt
        Capability-Match zum Zweck, dann hoechste priority * success_rate.
        In Zone 4 bleibt nur der Mensch -- bewusste Eskalation.
        """
        kandidaten = [
            p for p in self.verfuegbare() if self.erlaubt_in_zone(p, zone)
        ]
        if not kandidaten:
            return None

        def schluessel(p: Partner) -> tuple:
            cap_match = 1 if (zweck and zweck in p.capabilities) else 0
            return (cap_match, p.priority * p.success_rate)

        return max(kandidaten, key=schluessel)
