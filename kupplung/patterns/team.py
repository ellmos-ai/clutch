"""Team-Fahrt -- Parallele spezialisierte Ausfuehrung.

Mehrere Fahrer fahren parallel, jeder mit eigenem Gang.
Ergebnisse werden zusammengefuehrt.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable

from kupplung.kupplung import FahrtConfig


@dataclass
class TeamMitglied:
    name: str
    config: FahrtConfig
    handler: Callable[[Any], Any]
    spezialisierung: str = ""


@dataclass
class TeamErgebnis:
    erfolg: bool
    ergebnisse: dict[str, Any] = field(default_factory=dict)
    fehler: dict[str, str] = field(default_factory=dict)
    latenz: float = 0.0
    fertig: int = 0
    gesamt: int = 0


class TeamFahrt:
    """Parallele Ausfuehrung mit spezialisierten Mitgliedern."""

    def __init__(self, max_parallel: int = 5):
        self.mitglieder: list[TeamMitglied] = []
        self.max_parallel = max_parallel

    def mitglied(self, m: TeamMitglied) -> "TeamFahrt":
        self.mitglieder.append(m)
        return self

    def fahren(self, kontext: Any = None) -> TeamErgebnis:
        result = TeamErgebnis(erfolg=True, gesamt=len(self.mitglieder))
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            futures = {
                pool.submit(m.handler, kontext): m for m in self.mitglieder
            }
            for future in as_completed(futures):
                m = futures[future]
                try:
                    result.ergebnisse[m.name] = future.result(timeout=120)
                    result.fertig += 1
                except Exception as e:
                    result.fehler[m.name] = str(e)
                    result.erfolg = False

        result.latenz = time.time() - t0
        return result
