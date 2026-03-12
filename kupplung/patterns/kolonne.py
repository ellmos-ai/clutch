"""Kolonne -- Sequentielles Fahrt-Muster (Chain).

Fahrzeuge fahren hintereinander. Output von Fahrzeug N
ist Input fuer Fahrzeug N+1. Jedes kann einen anderen Gang nutzen.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from kupplung.kupplung import FahrtConfig


@dataclass
class KolonnenSchritt:
    name: str
    config: FahrtConfig
    handler: Callable[[Any], Any]


@dataclass
class KolonnenErgebnis:
    erfolg: bool
    schritte_fertig: int
    schritte_gesamt: int
    outputs: list[Any] = field(default_factory=list)
    fehler: list[str] = field(default_factory=list)
    latenz: float = 0.0


class Kolonne:
    """Sequentielle Ausfuehrung -- jeder Schritt kann anderen Gang nutzen."""

    def __init__(self):
        self.schritte: list[KolonnenSchritt] = []

    def schritt(self, s: KolonnenSchritt) -> "Kolonne":
        self.schritte.append(s)
        return self

    def fahren(self, start_input: Any = None) -> KolonnenErgebnis:
        result = KolonnenErgebnis(
            erfolg=True, schritte_fertig=0, schritte_gesamt=len(self.schritte),
        )
        aktuell = start_input
        t0 = time.time()

        for i, s in enumerate(self.schritte):
            try:
                aktuell = s.handler(aktuell)
                result.outputs.append(aktuell)
                result.schritte_fertig = i + 1
            except Exception as e:
                result.erfolg = False
                result.fehler.append(f"Schritt {i} ({s.name}): {e}")
                break

        result.latenz = time.time() - t0
        return result
