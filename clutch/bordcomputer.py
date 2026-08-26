"""Bordcomputer -- Health-Monitor mit Circuit-Breaker.

Ueberwacht den Systemzustand:
- Circuit-Breaker pro Modell (zu viele Fehler -> Modell sperren)
- Token-Explosions-Erkennung
- Overkill-Erkennung (zu viel gelesen, wenig geaendert)
- Budget-Zonen-Ueberwachung
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag
from clutch.budget_policy import (
    budget_zonen_aus_kriterien,
    lade_fitness_kriterien,
    max_gang_fuer_zone,
)


@dataclass
class SystemStatus:
    gesund: bool = True
    warnungen: list[str] = field(default_factory=list)
    gesperrte_modelle: list[str] = field(default_factory=list)
    budget_zone: str = "green"


@dataclass
class CircuitState:
    modell: str
    zustand: str = "closed"  # closed | open | half_open
    fehler_zaehler: int = 0
    letzter_fehler: float = 0.0
    geoeffnet_um: float = 0.0
    abkuehlzeit: float = 300.0  # 5 Minuten


class Bordcomputer:
    """Ueberwacht die System-Gesundheit."""

    def __init__(
        self,
        fahrtenbuch: Fahrtenbuch,
        config_dir: Optional[Path] = None,
    ):
        self.buch = fahrtenbuch
        self._circuits: dict[str, CircuitState] = {}
        self._fehler_log: dict[str, list[float]] = defaultdict(list)

        config_dir = config_dir or Path(__file__).parent / "config"
        fitness_kriterien = lade_fitness_kriterien(config_dir)
        schwellwerte = fitness_kriterien.get("anomaly_thresholds", {})

        self.overkill_schwelle = schwellwerte.get("overkill_score", 5.0)
        self.token_explosion_faktor = schwellwerte.get("token_explosion_factor", 2.0)
        self.max_fehler_serie = schwellwerte.get("consecutive_failures", 3)
        self.fehler_pro_stunde_limit = schwellwerte.get("errors_per_hour_circuit_break", 5)

        self._budget_zonen = budget_zonen_aus_kriterien(fitness_kriterien)

    def pruefe(self, budget_verbraucht_pct: float = 0.0) -> SystemStatus:
        status = SystemStatus()

        # Budget-Zone
        status.budget_zone = self._budget_zone(budget_verbraucht_pct)
        if status.budget_zone == "red":
            status.warnungen.append("TANKUHR ROT: Kein LLM-Einsatz erlaubt")
            status.gesund = False
        elif status.budget_zone == "orange":
            status.warnungen.append("TANKUHR ORANGE: Nur guenstige Modelle erlaubt")

        # Circuit-Breaker
        for modell, circuit in self._circuits.items():
            if circuit.zustand == "open":
                if time.time() - circuit.geoeffnet_um > circuit.abkuehlzeit:
                    circuit.zustand = "half_open"
                    status.warnungen.append(f"{modell}: Testphase (half-open)")
                else:
                    status.gesperrte_modelle.append(modell)
                    status.warnungen.append(f"{modell}: GESPERRT (Circuit open)")

        # Anomalien aus DB
        for anomalie in self.buch.anomalien(stunden=1):
            status.warnungen.append(
                f"Anomalie: {anomalie['strecken_typ']} / {anomalie['gang']} -- "
                f"{anomalie['fehler']} Fehler"
            )

        if status.gesperrte_modelle:
            status.gesund = len(status.gesperrte_modelle) < 3

        return status

    def fahrt_auswerten(self, eintrag: FahrtEintrag) -> list[str]:
        """Wertet eine abgeschlossene Fahrt aus. Gibt Warnungen zurueck."""
        warnungen = []

        if not eintrag.erfolg:
            warnungen.extend(self._fehler_verarbeiten(eintrag))
        else:
            self._erfolg_verarbeiten(eintrag)

        # Token-Explosion
        stats = self.buch.statistik(eintrag.strecken_typ, eintrag.gang)
        if stats and stats.avg_tokens > 0:
            if eintrag.total_tokens > stats.avg_tokens * self.token_explosion_faktor:
                warnungen.append(
                    f"Token-Explosion: {eintrag.total_tokens} > "
                    f"{self.token_explosion_faktor}x Baseline ({stats.avg_tokens:.0f})"
                )

        # Overkill
        if eintrag.files_changed > 0:
            overkill = eintrag.files_read / eintrag.files_changed
            if overkill > self.overkill_schwelle:
                warnungen.append(
                    f"Overkill: {eintrag.files_read} gelesen / "
                    f"{eintrag.files_changed} geaendert = {overkill:.1f}"
                )

        return warnungen

    def modell_verfuegbar(self, modell: str) -> bool:
        circuit = self._circuits.get(modell)
        if not circuit:
            return True
        return circuit.zustand != "open"

    def max_gang_fuer_zone(self, zone: str) -> int:
        return max_gang_fuer_zone(self._budget_zonen, zone)

    # --- Private ---

    def _fehler_verarbeiten(self, eintrag: FahrtEintrag) -> list[str]:
        warnungen = []
        modell = eintrag.gang

        if modell not in self._circuits:
            self._circuits[modell] = CircuitState(modell=modell)

        circuit = self._circuits[modell]
        circuit.fehler_zaehler += 1
        circuit.letzter_fehler = time.time()

        now = time.time()
        self._fehler_log[modell].append(now)
        cutoff = now - 3600
        self._fehler_log[modell] = [t for t in self._fehler_log[modell] if t > cutoff]

        # Zwei Ausloeser: Fehler in Folge (consecutive_failures) ODER
        # Fehler pro Stunde. Der Serien-Ausloeser greift auch bei niedriger
        # Anfragefrequenz, wenn ein Modell komplett ausfaellt, aber unter dem
        # Stundenlimit bleibt. fehler_zaehler wird bei Erfolg zurueckgesetzt
        # (siehe _erfolg_verarbeiten) und zaehlt daher Fehler in Folge.
        anzahl_stunde = len(self._fehler_log[modell])
        ausloeser = None
        if circuit.fehler_zaehler >= self.max_fehler_serie:
            ausloeser = f"{circuit.fehler_zaehler} Fehler in Folge"
        elif anzahl_stunde >= self.fehler_pro_stunde_limit:
            ausloeser = f"{anzahl_stunde} Fehler/Stunde"

        if ausloeser and circuit.zustand != "open":
            circuit.zustand = "open"
            circuit.geoeffnet_um = now
            warnungen.append(f"Circuit-Breaker OPEN fuer {modell}: {ausloeser}")

        return warnungen

    def _erfolg_verarbeiten(self, eintrag: FahrtEintrag) -> None:
        modell = eintrag.gang
        if modell in self._circuits:
            circuit = self._circuits[modell]
            if circuit.zustand == "half_open":
                circuit.zustand = "closed"
                circuit.fehler_zaehler = 0
            elif circuit.zustand == "closed":
                circuit.fehler_zaehler = 0

    def _budget_zone(self, verbraucht_pct: float) -> str:
        for name, cfg in sorted(
            self._budget_zonen.items(),
            key=lambda x: x[1].get("max_pct", 100),
        ):
            if verbraucht_pct <= cfg.get("max_pct", 100):
                return name
        return "red"
