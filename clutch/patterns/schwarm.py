"""Schwarm -- Massiv parallele Ausfuehrung fuer Mikrotasks.

Viele guenstige Worker verarbeiten unabhaengige Tasks.
Ein Aggregator fuehrt die Ergebnisse zusammen.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class SchwarmAufgabe:
    aufgaben_id: str
    payload: Any


@dataclass
class SchwarmErgebnis:
    erfolg: bool
    ergebnisse: dict[str, Any] = field(default_factory=dict)
    fehler: dict[str, str] = field(default_factory=dict)
    latenz: float = 0.0
    fertig: int = 0
    gesamt: int = 0
    aggregiert: Any = None


class Schwarm:
    """Massiv parallele Ausfuehrung mit Aggregation."""

    def __init__(
        self,
        worker: Callable[[Any], Any],
        aggregator: Optional[Callable[[dict[str, Any]], Any]] = None,
        max_parallel: int = 10,
        timeout: float = 60.0,
    ):
        self.worker = worker
        self.aggregator = aggregator
        self.max_parallel = max_parallel
        self.timeout = timeout

    def ausfuehren(self, aufgaben: list[SchwarmAufgabe]) -> SchwarmErgebnis:
        result = SchwarmErgebnis(erfolg=True, gesamt=len(aufgaben))
        t0 = time.time()

        with ThreadPoolExecutor(max_workers=self.max_parallel) as pool:
            futures = {
                pool.submit(self.worker, a.payload): a for a in aufgaben
            }
            for future in as_completed(futures):
                a = futures[future]
                try:
                    result.ergebnisse[a.aufgaben_id] = future.result(timeout=self.timeout)
                    result.fertig += 1
                except Exception as e:
                    result.fehler[a.aufgaben_id] = str(e)

        if self.aggregator and result.ergebnisse:
            try:
                result.aggregiert = self.aggregator(result.ergebnisse)
            except Exception as e:
                result.fehler["_aggregator"] = str(e)

        result.erfolg = len(result.fehler) == 0
        result.latenz = time.time() - t0
        return result
