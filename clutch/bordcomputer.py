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

from clutch.availability import AvailabilityStore, provider_failure_reason
from clutch.budget_policy import (
    budget_zonen_aus_kriterien,
    lade_fitness_kriterien,
    max_gang_fuer_zone,
)
from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag


@dataclass
class SystemStatus:
    gesund: bool = True
    warnungen: list[str] = field(default_factory=list)
    gesperrte_modelle: list[str] = field(default_factory=list)
    budget_zone: str = "green"
    verfuegbarkeit: dict[str, dict] = field(default_factory=dict)


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
        availability_path: Optional[Path] = None,
        token_budget_path: Optional[Path] = None,
        sparmodus_path: Optional[Path] = None,
        model_provider: Optional[dict[str, str]] = None,
    ):
        self.buch = fahrtenbuch
        self._circuits: dict[str, CircuitState] = {}
        self._fehler_log: dict[str, list[float]] = defaultdict(list)
        self._model_provider = dict(model_provider or {})
        self.availability = AvailabilityStore(
            path=availability_path,
            token_budget_path=token_budget_path,
            sparmodus_path=sparmodus_path,
        )

        config_dir = config_dir or Path(__file__).parent / "config"
        fitness_kriterien = lade_fitness_kriterien(config_dir)
        schwellwerte = fitness_kriterien.get("anomaly_thresholds", {})

        self.overkill_schwelle = schwellwerte.get("overkill_score", 5.0)
        self.token_explosion_faktor = schwellwerte.get("token_explosion_factor", 2.0)
        self.max_fehler_serie = schwellwerte.get("consecutive_failures", 3)
        self.fehler_pro_stunde_limit = schwellwerte.get("errors_per_hour_circuit_break", 5)

        self._budget_zonen = budget_zonen_aus_kriterien(fitness_kriterien)
        self._sync_circuits()

    def pruefe(self, budget_verbraucht_pct: float = 0.0) -> SystemStatus:
        status = SystemStatus()
        now = time.time()
        self.availability.refresh_external(now=now)
        self._sync_circuits()

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
                if now - circuit.geoeffnet_um > circuit.abkuehlzeit:
                    circuit.zustand = "half_open"
                    self._save_circuit(modell)
                    status.warnungen.append(f"{modell}: Testphase (half-open)")
                    status.verfuegbarkeit[modell] = {
                        "available": True,
                        "state": "half_open",
                        "until": None,
                        "resets_at": None,
                        "reason": "Circuit-Testphase",
                        "source": "circuit",
                    }
                else:
                    status.gesperrte_modelle.append(modell)
                    status.warnungen.append(f"{modell}: GESPERRT (Circuit open)")
                    status.verfuegbarkeit[modell] = {
                        "available": False,
                        "state": "open",
                        "until": circuit.geoeffnet_um + circuit.abkuehlzeit,
                        "resets_at": None,
                        "reason": "Circuit open",
                        "source": "circuit",
                    }

        # Provider-Kontingente (token_budget/notaus/429 etc.) gelten fuer alle
        # bekannten Gaenge des Providers und werden pro pruefe()-Aufruf neu gelesen.
        provider_blocks = self.availability.active_provider_blocks(now=now)
        for modell, provider in self._model_provider.items():
            blocks = provider_blocks.get(provider, [])
            if not blocks:
                status.verfuegbarkeit.setdefault(modell, {
                    "available": modell not in status.gesperrte_modelle,
                    "state": "available",
                    "until": None,
                    "resets_at": None,
                    "reason": None,
                    "source": None,
                })
                continue
            block = max(blocks, key=lambda item: float(item.get("until") or float("inf")))
            if modell not in status.gesperrte_modelle:
                status.gesperrte_modelle.append(modell)
            status.verfuegbarkeit[modell] = {
                "available": False,
                "state": "blocked",
                "until": block.get("until"),
                "resets_at": block.get("resets_at"),
                "reason": block.get("reason"),
                "source": block.get("source"),
            }
            status.warnungen.append(f"{modell}: GESPERRT ({block.get('reason')})")

        # Anomalien aus DB
        for anomalie in self.buch.anomalien(stunden=1):
            status.warnungen.append(
                f"Anomalie: {anomalie['strecken_typ']} / {anomalie['gang']} -- "
                f"{anomalie['fehler']} Fehler"
            )

        status.gesperrte_modelle = sorted(set(status.gesperrte_modelle))
        if status.gesperrte_modelle:
            status.gesund = status.gesund and len(status.gesperrte_modelle) < 3

        return status

    def fahrt_auswerten(
        self,
        eintrag: FahrtEintrag,
        fehlertext: Optional[str] = None,
        output_text: Optional[str] = None,
    ) -> list[str]:
        """Wertet eine abgeschlossene Fahrt aus. Gibt Warnungen zurueck."""
        warnungen = []
        self._sync_circuits()

        if not eintrag.erfolg:
            warnungen.extend(self._fehler_verarbeiten(eintrag))
        else:
            self._erfolg_verarbeiten(eintrag)

        provider_reason = provider_failure_reason(eintrag.provider, fehlertext, output_text)
        if provider_reason:
            self.availability.record_provider_failure(eintrag.provider, provider_reason)
            warnungen.append(f"Kontingentsperre fuer {eintrag.provider}: {provider_reason}")

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
        self.availability.refresh_external()
        self._sync_circuits()
        circuit = self._circuits.get(modell)
        if circuit and circuit.zustand == "open":
            return False
        provider = self._model_provider.get(modell)
        return provider not in self.availability.active_provider_blocks()

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

        self._save_circuit(modell)

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
            self._save_circuit(modell)

    def _sync_circuits(self) -> None:
        persisted = self.availability.circuits()
        self._circuits = {}
        self._fehler_log = defaultdict(list)
        for modell, raw in persisted.items():
            if not isinstance(raw, dict):
                continue
            self._circuits[modell] = CircuitState(
                modell=modell,
                zustand=str(raw.get("state", "closed")),
                fehler_zaehler=int(raw.get("failure_count", 0) or 0),
                letzter_fehler=float(raw.get("last_failure", 0.0) or 0.0),
                geoeffnet_um=float(raw.get("opened_at", 0.0) or 0.0),
                abkuehlzeit=float(raw.get("cooldown_seconds", 300.0) or 300.0),
            )
            timestamps = raw.get("error_timestamps", [])
            if isinstance(timestamps, list):
                self._fehler_log[modell] = [float(value) for value in timestamps if isinstance(value, (int, float))]

    def _save_circuit(self, modell: str) -> None:
        circuit = self._circuits[modell]
        self.availability.save_circuit(
            modell,
            {
                "state": circuit.zustand,
                "failure_count": circuit.fehler_zaehler,
                "last_failure": circuit.letzter_fehler,
                "opened_at": circuit.geoeffnet_um,
                "cooldown_seconds": circuit.abkuehlzeit,
                "until": (
                    circuit.geoeffnet_um + circuit.abkuehlzeit
                    if circuit.zustand == "open" else None
                ),
                "error_timestamps": self._fehler_log.get(modell, []),
            },
        )

    def _budget_zone(self, verbraucht_pct: float) -> str:
        for name, cfg in sorted(
            self._budget_zonen.items(),
            key=lambda x: x[1].get("max_pct", 100),
        ):
            if verbraucht_pct <= cfg.get("max_pct", 100):
                return name
        return "red"
