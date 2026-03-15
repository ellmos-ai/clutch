"""Bordcomputer -- Health-Monitor mit Circuit-Breaker.

Ueberwacht den Systemzustand:
- Circuit-Breaker pro Modell (zu viele Fehler -> Modell sperren)
- Token-Explosions-Erkennung
- Overkill-Erkennung (zu viel gelesen, wenig geaendert)
- Budget-Zonen-Ueberwachung
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag


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

        config_dir = config_dir or Path(__file__).parent.parent / "config"
        schwellwerte = self._load_schwellwerte(config_dir)

        self.overkill_schwelle = schwellwerte.get("overkill_score", 5.0)
        self.token_explosion_faktor = schwellwerte.get("token_explosion_factor", 2.0)
        self.max_fehler_serie = schwellwerte.get("consecutive_failures", 3)
        self.fehler_pro_stunde_limit = schwellwerte.get("errors_per_hour_circuit_break", 5)

        self._budget_zonen = self._load_budget_zonen(config_dir)

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
        zone_config = self._budget_zonen.get(zone, {})
        tiers = zone_config.get("allowed_tiers", [1, 2, 3, 4, 5])
        return max(tiers) if tiers else 0

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

        if len(self._fehler_log[modell]) >= self.fehler_pro_stunde_limit:
            circuit.zustand = "open"
            circuit.geoeffnet_um = now
            warnungen.append(
                f"Circuit-Breaker OPEN fuer {modell}: "
                f"{len(self._fehler_log[modell])} Fehler/Stunde"
            )

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

    def _load_schwellwerte(self, config_dir: Path) -> dict:
        path = config_dir / "fitness.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("anomaly_thresholds", {})
        # Fallback: alte Config
        path2 = config_dir / "fitness_criteria.json"
        if path2.exists():
            with open(path2, encoding="utf-8") as f:
                return json.load(f).get("anomaly_thresholds", {})
        return {}

    def _load_budget_zonen(self, config_dir: Path) -> dict:
        for fname in ("fitness.json", "fitness_criteria.json"):
            path = config_dir / fname
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    if "budget_zones" in data:
                        return data["budget_zones"]
        return {
            "green":  {"min_pct": 0,  "max_pct": 30, "allowed_tiers": [1, 2, 3, 4, 5]},
            "yellow": {"min_pct": 30, "max_pct": 60, "allowed_tiers": [1, 2, 3]},
            "orange": {"min_pct": 60, "max_pct": 80, "allowed_tiers": [1, 2]},
            "red":    {"min_pct": 80, "max_pct": 100, "allowed_tiers": []},
        }
