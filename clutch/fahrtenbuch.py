"""Fahrtenbuch -- SQLite-basierter Metrik-Speicher.

Zeichnet jede Fahrt (Task-Ausfuehrung) auf:
- Welcher Gang (Modell) wurde genutzt
- Wie viel Gas (Reasoning-Level)
- Streckentyp, Provider, Tokens, Latenz, Erfolg
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class FahrtEintrag:
    """Ein Eintrag im Fahrtenbuch."""
    fahrt_id: str
    strecken_typ: str
    gang: str                 # Modell-Name
    provider: str             # anthropic, google, ollama
    gas: float                # 0.0 - 1.0
    muster: str               # einzelfahrt, kolonne, team, schwarm
    total_tokens: int = 0
    thinking_tokens: int = 0
    tool_calls: int = 0
    files_read: int = 0
    files_changed: int = 0
    latenz_sekunden: float = 0.0
    erfolg: bool = True
    wiederholungen: int = 0
    user_korrekturen: int = 0
    fehler_anzahl: int = 0
    ist_erkundung: bool = False
    entscheidungs_grund: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class FahrtStatistik:
    """Aggregierte Statistiken fuer eine Gang x Strecke Kombination."""
    strecken_typ: str
    gang: str
    provider: str
    gas_durchschnitt: float
    gesamt_fahrten: int
    erfolgsrate: float
    avg_tokens: float
    avg_latenz: float
    avg_wiederholungen: float
    avg_korrekturen: float
    effizienz: float
    stichproben: int


_SCHEMA = """
CREATE TABLE IF NOT EXISTS fahrten (
    fahrt_id TEXT PRIMARY KEY,
    strecken_typ TEXT NOT NULL,
    gang TEXT NOT NULL,
    provider TEXT NOT NULL,
    gas REAL DEFAULT 0.5,
    muster TEXT NOT NULL,
    total_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    tool_calls INTEGER DEFAULT 0,
    files_read INTEGER DEFAULT 0,
    files_changed INTEGER DEFAULT 0,
    latenz_sekunden REAL DEFAULT 0.0,
    erfolg INTEGER DEFAULT 1,
    wiederholungen INTEGER DEFAULT 0,
    user_korrekturen INTEGER DEFAULT 0,
    fehler_anzahl INTEGER DEFAULT 0,
    ist_erkundung INTEGER DEFAULT 0,
    entscheidungs_grund TEXT DEFAULT '',
    timestamp REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strecken_typ ON fahrten(strecken_typ);
CREATE INDEX IF NOT EXISTS idx_gang_provider ON fahrten(gang, provider);
CREATE INDEX IF NOT EXISTS idx_timestamp ON fahrten(timestamp);

CREATE TABLE IF NOT EXISTS routing_policy (
    strecken_typ TEXT PRIMARY KEY,
    gang TEXT NOT NULL,
    provider TEXT NOT NULL,
    gas REAL NOT NULL,
    muster TEXT NOT NULL,
    fitness_score REAL DEFAULT 0.0,
    stichproben INTEGER DEFAULT 0,
    aktualisiert REAL NOT NULL
);
"""


class Fahrtenbuch:
    """SQLite-basiertes Fahrtenbuch."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "data" / "clutch.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def eintragen(self, eintrag: FahrtEintrag) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO fahrten
                (fahrt_id, strecken_typ, gang, provider, gas, muster,
                 total_tokens, thinking_tokens, tool_calls, files_read,
                 files_changed, latenz_sekunden, erfolg, wiederholungen,
                 user_korrekturen, fehler_anzahl, ist_erkundung,
                 entscheidungs_grund, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    eintrag.fahrt_id, eintrag.strecken_typ, eintrag.gang,
                    eintrag.provider, eintrag.gas, eintrag.muster,
                    eintrag.total_tokens, eintrag.thinking_tokens,
                    eintrag.tool_calls, eintrag.files_read,
                    eintrag.files_changed, eintrag.latenz_sekunden,
                    int(eintrag.erfolg), eintrag.wiederholungen,
                    eintrag.user_korrekturen, eintrag.fehler_anzahl,
                    int(eintrag.ist_erkundung), eintrag.entscheidungs_grund,
                    eintrag.timestamp,
                ),
            )

    def statistik(
        self,
        strecken_typ: str,
        gang: Optional[str] = None,
        max_alter_tage: int = 30,
    ) -> Optional[FahrtStatistik]:
        cutoff = time.time() - (max_alter_tage * 86400)
        query = """
            SELECT
                strecken_typ, gang, provider,
                AVG(gas) as gas_durchschnitt,
                COUNT(*) as gesamt_fahrten,
                AVG(CASE WHEN erfolg THEN 1.0 ELSE 0.0 END) as erfolgsrate,
                AVG(total_tokens) as avg_tokens,
                AVG(latenz_sekunden) as avg_latenz,
                AVG(wiederholungen) as avg_wiederholungen,
                AVG(user_korrekturen) as avg_korrekturen,
                COUNT(*) as stichproben
            FROM fahrten
            WHERE strecken_typ = ? AND timestamp > ?
        """
        params: list = [strecken_typ, cutoff]
        if gang:
            query += " AND gang = ?"
            params.append(gang)
        query += " GROUP BY strecken_typ, gang"

        with self._conn() as conn:
            row = conn.execute(query, params).fetchone()

        if not row or row["gesamt_fahrten"] == 0:
            return None

        avg_tokens = row["avg_tokens"] or 1
        return FahrtStatistik(
            strecken_typ=row["strecken_typ"],
            gang=row["gang"] or "",
            provider=row["provider"] or "",
            gas_durchschnitt=row["gas_durchschnitt"] or 0.5,
            gesamt_fahrten=row["gesamt_fahrten"],
            erfolgsrate=row["erfolgsrate"],
            avg_tokens=avg_tokens,
            avg_latenz=row["avg_latenz"] or 0.0,
            avg_wiederholungen=row["avg_wiederholungen"] or 0.0,
            avg_korrekturen=row["avg_korrekturen"] or 0.0,
            effizienz=(row["erfolgsrate"] / avg_tokens) * 1000,
            stichproben=row["stichproben"],
        )

    def alle_statistiken(self, strecken_typ: str, max_alter_tage: int = 30) -> list[FahrtStatistik]:
        cutoff = time.time() - (max_alter_tage * 86400)
        query = """
            SELECT
                strecken_typ, gang, provider,
                AVG(gas) as gas_durchschnitt,
                COUNT(*) as gesamt_fahrten,
                AVG(CASE WHEN erfolg THEN 1.0 ELSE 0.0 END) as erfolgsrate,
                AVG(total_tokens) as avg_tokens,
                AVG(latenz_sekunden) as avg_latenz,
                AVG(wiederholungen) as avg_wiederholungen,
                AVG(user_korrekturen) as avg_korrekturen,
                COUNT(*) as stichproben
            FROM fahrten
            WHERE strecken_typ = ? AND timestamp > ?
            GROUP BY strecken_typ, gang, provider
            HAVING COUNT(*) >= 3
            ORDER BY erfolgsrate DESC, avg_tokens ASC
        """
        results = []
        with self._conn() as conn:
            for row in conn.execute(query, [strecken_typ, cutoff]):
                avg_tokens = row["avg_tokens"] or 1
                results.append(FahrtStatistik(
                    strecken_typ=row["strecken_typ"],
                    gang=row["gang"],
                    provider=row["provider"],
                    gas_durchschnitt=row["gas_durchschnitt"] or 0.5,
                    gesamt_fahrten=row["gesamt_fahrten"],
                    erfolgsrate=row["erfolgsrate"],
                    avg_tokens=avg_tokens,
                    avg_latenz=row["avg_latenz"] or 0.0,
                    avg_wiederholungen=row["avg_wiederholungen"] or 0.0,
                    avg_korrekturen=row["avg_korrekturen"] or 0.0,
                    effizienz=(row["erfolgsrate"] / avg_tokens) * 1000,
                    stichproben=row["stichproben"],
                ))
        return results

    def gesamte_fahrten(self) -> int:
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM fahrten").fetchone()
            return row["cnt"] if row else 0

    def policy_speichern(self, strecken_typ: str, gang: str, provider: str,
                         gas: float, muster: str, fitness: float, stichproben: int) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO routing_policy
                (strecken_typ, gang, provider, gas, muster, fitness_score,
                 stichproben, aktualisiert)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (strecken_typ, gang, provider, gas, muster, fitness, stichproben, time.time()),
            )

    def policy_laden(self, strecken_typ: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM routing_policy WHERE strecken_typ = ?", (strecken_typ,)
            ).fetchone()
            return dict(row) if row else None

    def anomalien(self, stunden: int = 1) -> list[dict]:
        cutoff = time.time() - (stunden * 3600)
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT strecken_typ, gang, provider,
                    COUNT(*) as fahrten,
                    SUM(CASE WHEN NOT erfolg THEN 1 ELSE 0 END) as fehler,
                    AVG(total_tokens) as avg_tokens,
                    MAX(total_tokens) as max_tokens
                FROM fahrten
                WHERE timestamp > ?
                GROUP BY strecken_typ, gang, provider
                HAVING fehler > 2 OR max_tokens > avg_tokens * 3""",
                (cutoff,),
            ).fetchall()
            return [dict(r) for r in rows]
