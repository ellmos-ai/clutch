"""Fahrschule -- Lern- und Anpassungslogik (Evolution Loop).

Analysiert gesammelte Fahrten und passt die Routing-Policy an.
Epsilon-Greedy Exploration + Fitness-Scoring + Decay.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from clutch.fahrtenbuch import Fahrtenbuch, FahrtStatistik
from clutch.kupplung import Kupplung


@dataclass
class FitnessErgebnis:
    gesamt: float
    effizienz: float
    qualitaet: float
    speed: float
    zuverlaessigkeit: float



class FitnessBewerter:
    """Bewertet die Fitness einer Gang x Gas Kombination."""

    def __init__(self, gewichte: Optional[dict] = None):
        self.gewichte = gewichte or {
            "effizienz": 0.30,
            "qualitaet": 0.35,
            "speed": 0.20,
            "zuverlaessigkeit": 0.15,
        }

    def bewerten(
        self,
        stats: FahrtStatistik,
        baseline_tokens: float = 5000,
        baseline_latenz: float = 30.0,
    ) -> FitnessErgebnis:
        eff = self._effizienz(stats, baseline_tokens)
        qual = self._qualitaet(stats)
        spd = self._speed(stats, baseline_latenz)
        zuv = self._zuverlaessigkeit(stats)

        gesamt = (
            eff * self.gewichte["effizienz"]
            + qual * self.gewichte["qualitaet"]
            + spd * self.gewichte["speed"]
            + zuv * self.gewichte["zuverlaessigkeit"]
        )

        return FitnessErgebnis(
            gesamt=round(gesamt, 4),
            effizienz=round(eff, 4),
            qualitaet=round(qual, 4),
            speed=round(spd, 4),
            zuverlaessigkeit=round(zuv, 4),
        )

    def _effizienz(self, stats: FahrtStatistik, baseline: float) -> float:
        if stats.avg_tokens <= 0:
            return 1.0
        ratio = baseline / stats.avg_tokens
        return self._sigmoid(ratio)

    def _qualitaet(self, stats: FahrtStatistik) -> float:
        base = stats.erfolgsrate
        korrektur_abzug = min(0.3, stats.avg_korrekturen * 0.1)
        return max(0.0, base - korrektur_abzug)

    def _speed(self, stats: FahrtStatistik, baseline: float) -> float:
        if stats.avg_latenz <= 0:
            return 1.0
        return self._sigmoid(baseline / stats.avg_latenz, steepness=2.0)

    def _zuverlaessigkeit(self, stats: FahrtStatistik) -> float:
        retry_abzug = min(0.4, stats.avg_wiederholungen * 0.1)
        fehler_rate = 1.0 - stats.erfolgsrate
        return max(0.0, 1.0 - retry_abzug - fehler_rate * 0.5)

    @staticmethod
    def _sigmoid(x: float, midpoint: float = 1.0, steepness: float = 3.0) -> float:
        try:
            return 1.0 / (1.0 + math.exp(-steepness * (x - midpoint)))
        except OverflowError:
            return 0.0 if x < midpoint else 1.0


class Fahrschule:
    """Lernt aus Fahrten und optimiert die Kupplung."""

    def __init__(
        self,
        buch: Fahrtenbuch,
        kupplung: Kupplung,
        config_dir: Optional[Path] = None,
    ):
        self.buch = buch
        self.kupplung = kupplung
        self.bewerter = FitnessBewerter()

        config_dir = config_dir or Path(__file__).parent.parent / "config"
        config = self._load_config(config_dir)

        self.min_fahrten = config.get("min_fahrten_phase1", 200)
        self.erkundungsrate = config.get("erkundungsrate", 0.10)
        self.erkundungs_decay = config.get("erkundungs_decay", 0.995)
        self.min_erkundung = config.get("min_erkundungsrate", 0.02)
        self.max_alter_tage = config.get("decay_max_alter_tage", 30)

    def trainieren(self) -> dict:
        """Fuehrt einen Trainingszyklus durch."""
        total = self.buch.gesamte_fahrten()
        ergebnis = {
            "phase": "sammeln" if total < self.min_fahrten else "optimieren",
            "gesamte_fahrten": total,
            "updates": [],
            "erkundungsrate": self.erkundungsrate,
        }

        if total < self.min_fahrten:
            ergebnis["nachricht"] = (
                f"Sammelphase: {total}/{self.min_fahrten} Fahrten. "
                "Noch keine Policy-Updates."
            )
            return ergebnis

        # Alle Streckentypen evaluieren
        strecken_config = self.kupplung._strecken_config.get("strecken", {})
        for strecken_typ in strecken_config:
            update = self._strecke_evaluieren(strecken_typ)
            if update:
                ergebnis["updates"].append(update)

        self._erkundung_decay()
        ergebnis["erkundungsrate"] = self.erkundungsrate

        return ergebnis

    def _strecke_evaluieren(self, strecken_typ: str) -> Optional[dict]:
        alle_stats = self.buch.alle_statistiken(strecken_typ, self.max_alter_tage)
        if not alle_stats:
            return None

        bewertet = []
        for stats in alle_stats:
            if stats.stichproben < 3:
                continue
            fitness = self.bewerter.bewerten(stats)
            bewertet.append((stats, fitness))

        if not bewertet:
            return None

        bewertet.sort(key=lambda x: x[1].gesamt, reverse=True)
        beste_stats, beste_fitness = bewertet[0]

        # Nur updaten bei signifikanter Verbesserung (>5%)
        aktuelle_policy = self.buch.policy_laden(strecken_typ)
        if aktuelle_policy:
            if beste_fitness.gesamt <= aktuelle_policy.get("fitness_score", 0) * 1.05:
                return None

        self.buch.policy_speichern(
            strecken_typ=strecken_typ,
            gang=beste_stats.gang,
            provider=beste_stats.provider,
            gas=beste_stats.gas_durchschnitt,
            muster="einzelfahrt",
            fitness=beste_fitness.gesamt,
            stichproben=beste_stats.stichproben,
        )

        self.kupplung.override(strecken_typ, {
            "gang": beste_stats.gang,
            "gas": beste_stats.gas_durchschnitt,
        })

        return {
            "strecke": strecken_typ,
            "neuer_gang": beste_stats.gang,
            "neuer_provider": beste_stats.provider,
            "fitness": beste_fitness.gesamt,
            "stichproben": beste_stats.stichproben,
        }

    def _erkundung_decay(self) -> None:
        self.erkundungsrate = max(
            self.min_erkundung,
            self.erkundungsrate * self.erkundungs_decay,
        )
        self.kupplung.set_erkundungsrate(self.erkundungsrate)

    def _load_config(self, config_dir: Path) -> dict:
        path = config_dir / "kupplung.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("fahrschule", {})
        return {}
