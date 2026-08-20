"""Tankuhr -- Budget-Tracking mit Zonen-System.

Trackt Verbrauch in USD ueber alle Provider hinweg.
Bestimmt die aktuelle Budget-Zone (Gruen bis Rot).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from clutch.getriebe import Gang
from clutch.pricing import UsageRecord, cost_for_gang


@dataclass
class TankStand:
    """Aktueller Budget-Stand."""
    kosten_heute_usd: float = 0.0
    kosten_monat_usd: float = 0.0
    fahrten_heute: int = 0
    fahrten_monat: int = 0
    tages_limit_usd: float = 50.0
    monats_limit_usd: float = 500.0
    tages_verbrauch_pct: float = 0.0
    monats_verbrauch_pct: float = 0.0
    zone: str = "green"
    zone_nachricht: str = ""
    unmetered_fahrten_heute: int = 0
    unmetered_fahrten_monat: int = 0


class Tankuhr:
    """Trackt Kosten ueber alle Provider."""

    def __init__(self, config_dir: Optional[Path] = None, buch=None):
        config_dir = config_dir or Path(__file__).parent / "config"
        config = self._load_config(config_dir)

        self.tages_limit = config.get("tages_limit_usd", 50.0)
        self.monats_limit = config.get("monats_limit_usd", 500.0)

        self.buch = buch
        self._kosten_log: list[tuple[float, Optional[float], str]] = []

    def tanken(self, gang: Gang, input_tokens: int, output_tokens: int) -> float:
        """Zeichnet Verbrauch auf. Gibt Kosten in USD zurueck."""
        breakdown = cost_for_gang(
            gang,
            UsageRecord(
                input_tokens=input_tokens,
                cached_input_tokens=0,
                cache_write_tokens=0,
                output_tokens=output_tokens,
                reasoning_tokens=0,
                data_status="observed",
            ),
        )
        cost = float(breakdown.total_usd or 0.0)
        self.tanken_kosten(gang.provider, cost)
        return cost

    def tanken_kosten(self, provider: str, cost_usd: Optional[float]) -> None:
        """Zeichnet ein zentrales Kostenergebnis auf; None bleibt ungemessen."""
        self._kosten_log.append((time.time(), cost_usd, provider))
        self._cleanup()

    def stand(self) -> TankStand:
        now = time.time()
        day_start = self._tagesanfang(now)
        month_start = self._monatsanfang(now)

        if self.buch is not None:
            heute = self.buch.kosten_uebersicht(day_start)
            monat = self.buch.kosten_uebersicht(month_start)
            kosten_heute = heute["kosten_usd"]
            kosten_monat = monat["kosten_usd"]
            fahrten_heute = heute["fahrten"]
            fahrten_monat = monat["fahrten"]
            unmetered_heute = heute["unmetered_fahrten"]
            unmetered_monat = monat["unmetered_fahrten"]
        else:
            kosten_heute = sum(c for t, c, _ in self._kosten_log if t >= day_start and c is not None)
            kosten_monat = sum(c for t, c, _ in self._kosten_log if t >= month_start and c is not None)
            fahrten_heute = sum(1 for t, _, _ in self._kosten_log if t >= day_start)
            fahrten_monat = sum(1 for t, _, _ in self._kosten_log if t >= month_start)
            unmetered_heute = sum(1 for t, c, _ in self._kosten_log if t >= day_start and c is None)
            unmetered_monat = sum(1 for t, c, _ in self._kosten_log if t >= month_start and c is None)

        tages_pct = (kosten_heute / self.tages_limit * 100) if self.tages_limit > 0 else 0
        monats_pct = (kosten_monat / self.monats_limit * 100) if self.monats_limit > 0 else 0
        used_pct = max(tages_pct, monats_pct)

        zone = self._zone(used_pct)
        nachrichten = {
            "green": "Tank voll -- alle Gaenge verfuegbar",
            "yellow": "Tank halb -- nur guenstige Gaenge",
            "orange": "Tank fast leer -- nur Haiku/lokal",
            "red": "Tank leer -- kein LLM-Einsatz",
        }

        return TankStand(
            kosten_heute_usd=round(kosten_heute, 4),
            kosten_monat_usd=round(kosten_monat, 4),
            fahrten_heute=fahrten_heute,
            fahrten_monat=fahrten_monat,
            tages_limit_usd=self.tages_limit,
            monats_limit_usd=self.monats_limit,
            tages_verbrauch_pct=round(tages_pct, 1),
            monats_verbrauch_pct=round(monats_pct, 1),
            zone=zone,
            zone_nachricht=nachrichten.get(zone, ""),
            unmetered_fahrten_heute=unmetered_heute,
            unmetered_fahrten_monat=unmetered_monat,
        )

    def zone(self) -> str:
        return self.stand().zone

    def verbrauch_pct(self) -> float:
        s = self.stand()
        return max(s.tages_verbrauch_pct, s.monats_verbrauch_pct)

    def kosten_schaetzen(self, gang: Gang, tokens: int) -> float:
        return gang.kosten_schaetzen(tokens)

    def _zone(self, pct: float) -> str:
        if pct < 30:
            return "green"
        elif pct < 60:
            return "yellow"
        elif pct < 80:
            return "orange"
        return "red"

    def _cleanup(self):
        now = time.time()
        month_start = self._monatsanfang(now)
        self._kosten_log = [(t, c, p) for t, c, p in self._kosten_log if t >= month_start]

    @staticmethod
    def _tagesanfang(ts: float) -> float:
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    @staticmethod
    def _monatsanfang(ts: float) -> float:
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp()

    def _load_config(self, config_dir: Path) -> dict:
        path = config_dir / "kupplung.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("tankuhr", {})
        return {}
