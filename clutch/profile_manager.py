"""Profil-Manager — verwaltet user/zweck/toolset-Profile in clutch.db.

Drei Profil-Scopes (pro Chat überschreibbar):

``user``-Payload (Identität/Defaults):
    {
        "name": str,           # Anzeigename des Nutzers
        "default_profil": str  # Name des Standard-Routing-Profils (zweck-scope)
    }

``zweck``-Payload (Routing-Profil, Kosten-vs-Zweck-Gewichtung):
    {
        "kosten_gewicht":    float,      # 0.0 = nur Zweck zählt, 1.0 = nur Kosten zählen
        "erlaubte_gaenge":   list[str],  # leere Liste = alle erlaubt
        "max_gang":          int,        # maximale Gangstufe (0 = unbegrenzt)
        "tages_limit_usd":   float       # tägliches Budget in USD (0.0 = kein Limit)
    }

``toolset``-Payload (erlaubte Tools + Systemprompt-Toggle):
    {
        "erlaubte_tools":       list[str],  # leere Liste = alle erlaubt
        "tool_infos":           dict,        # {tool_name: beschreibung/metadaten}
        "mitgesendete_prompts": list[str],   # Prompt-IDs aus der Prompt-Bibliothek
        "system_prompt_on":     bool         # CLUTCH.md-Systemprompt an/aus
    }
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import time


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class Profil:
    """Ein gespeichertes Profil (user, zweck oder toolset)."""

    name: str
    scope: str          # "user" | "zweck" | "toolset"
    payload: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        erlaubte_scopes = {"user", "zweck", "toolset"}
        if self.scope not in erlaubte_scopes:
            raise ValueError(
                f"Ungültiger Scope '{self.scope}'. Erlaubt: {erlaubte_scopes}"
            )


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    name       TEXT NOT NULL,
    scope      TEXT NOT NULL CHECK(scope IN ('user', 'zweck', 'toolset')),
    payload    TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (name, scope)
);

CREATE TABLE IF NOT EXISTS active_profiles (
    scope TEXT PRIMARY KEY CHECK(scope IN ('user', 'zweck', 'toolset')),
    name  TEXT NOT NULL
);
"""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ProfileManager:
    """Verwaltet user/zweck/toolset-Profile in clutch.db.

    Parameter
    ---------
    db_path:
        Pfad zur SQLite-Datenbank. Standard: ``~/.clutch/clutch.db``.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".clutch" / "clutch.db"
        self.db_path: Path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Interne Hilfsmethoden
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        """Öffnet eine Verbindung, committet am Ende und schließt sie immer."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Erstellt Tabellen, falls noch nicht vorhanden (idempotent)."""
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @staticmethod
    def _row_zu_profil(row: sqlite3.Row) -> Profil:
        return Profil(
            name=row["name"],
            scope=row["scope"],
            payload=json.loads(row["payload"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def speichere(self, profil: Profil) -> Profil:
        """Speichert oder aktualisiert ein Profil. Setzt ``updated_at`` auf jetzt.

        Gibt das gespeicherte Profil (mit aktuellem ``updated_at``) zurück.
        """
        profil.updated_at = time.time()
        if profil.created_at == 0.0:
            profil.created_at = profil.updated_at

        payload_json = json.dumps(profil.payload, ensure_ascii=False)

        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO profiles (name, scope, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name, scope) DO UPDATE SET
                    payload    = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (
                    profil.name,
                    profil.scope,
                    payload_json,
                    profil.created_at,
                    profil.updated_at,
                ),
            )
        return profil

    def lade(self, name: str, scope: str) -> Optional[Profil]:
        """Lädt ein Profil. Gibt ``None`` zurück, wenn es nicht existiert."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM profiles WHERE name = ? AND scope = ?",
                (name, scope),
            ).fetchone()
        return self._row_zu_profil(row) if row else None

    def liste(self, scope: Optional[str] = None) -> list[Profil]:
        """Gibt alle Profile zurück, optional gefiltert nach Scope."""
        with self._conn() as conn:
            if scope is not None:
                rows = conn.execute(
                    "SELECT * FROM profiles WHERE scope = ? ORDER BY name",
                    (scope,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM profiles ORDER BY scope, name"
                ).fetchall()
        return [self._row_zu_profil(r) for r in rows]

    def loesche(self, name: str, scope: str) -> bool:
        """Löscht ein Profil. Gibt ``True`` zurück, wenn ein Eintrag entfernt wurde."""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM profiles WHERE name = ? AND scope = ?",
                (name, scope),
            )
            return cursor.rowcount > 0

    # ------------------------------------------------------------------
    # Aktives Profil je Scope
    # ------------------------------------------------------------------

    def aktives_setzen(self, scope: str, name: str) -> None:
        """Setzt das aktive Profil für einen Scope (persistiert in DB)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO active_profiles (scope, name) VALUES (?, ?)
                ON CONFLICT(scope) DO UPDATE SET name = excluded.name
                """,
                (scope, name),
            )

    def aktives(self, scope: str) -> Optional[str]:
        """Gibt den Namen des aktuell aktiven Profils für einen Scope zurück.

        Gibt ``None`` zurück, wenn kein aktives Profil gesetzt ist.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT name FROM active_profiles WHERE scope = ?",
                (scope,),
            ).fetchone()
        return row["name"] if row else None

    # ------------------------------------------------------------------
    # Toolset-Hilfsmethoden
    # ------------------------------------------------------------------

    def system_prompt_an(self, toolset_name: str) -> bool:
        """Liest ``system_prompt_on`` aus dem angegebenen Toolset-Profil.

        Gibt ``True`` zurück (Standardverhalten), wenn:
        - das Profil nicht existiert,
        - der Key ``system_prompt_on`` fehlt.
        """
        profil = self.lade(toolset_name, "toolset")
        if profil is None:
            return True
        return bool(profil.payload.get("system_prompt_on", True))

    def set_system_prompt(self, toolset_name: str, an: bool) -> None:
        """Setzt ``system_prompt_on`` im Toolset-Profil.

        Legt das Profil an, wenn es noch nicht existiert.
        """
        profil = self.lade(toolset_name, "toolset")
        if profil is None:
            profil = Profil(name=toolset_name, scope="toolset", payload={})
        profil.payload["system_prompt_on"] = an
        self.speichere(profil)

    # ------------------------------------------------------------------
    # Factory: nicht-persistierte Default-Profile
    # ------------------------------------------------------------------

    @staticmethod
    def default_profil(scope: str) -> Profil:
        """Gibt ein nicht-persistiertes Profil mit sinnvollen Defaults zurück.

        Das Profil wird NICHT in der Datenbank gespeichert — es dient als
        Vorlage. Zum Speichern: ``manager.speichere(manager.default_profil(scope))``.
        """
        if scope == "user":
            payload: dict = {
                "name": "",
                "default_profil": "standard",
            }
        elif scope == "zweck":
            payload = {
                "kosten_gewicht": 0.5,
                "erlaubte_gaenge": [],
                "max_gang": 0,
                "tages_limit_usd": 0.0,
            }
        elif scope == "toolset":
            payload = {
                "erlaubte_tools": [],
                "tool_infos": {},
                "mitgesendete_prompts": [],
                "system_prompt_on": True,
            }
        else:
            raise ValueError(f"Ungültiger Scope '{scope}'")

        return Profil(name="standard", scope=scope, payload=payload)
