"""Prompt-Bibliothek -- SQLite-basierter Speicher für Prompts und verwandte Einträge.

Unterstützte Typen: prompt, skill, workflow, rolle, agent.
Recycling-Vorlage: PromptBoard src/models.py + src/storage.py (LibraryItem-Modell).
DB: ~/.clutch/clutch.db, Tabelle `prompts`.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

# Erlaubte Typen (analog zu PromptBoard ItemType, aber lowercase)
_ERLAUBTE_TYPEN = {"prompt", "skill", "workflow", "rolle", "agent"}


def _jetzt_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalisiere_typ(wert: str) -> str:
    """Mappt eingehende Typ-Strings auf die internen lowercase-Werte.

    Für den PromptBoard-Import werden Großschreibungen (PROMPT, SKILL, …)
    und Synonyme (ROLE → rolle) akzeptiert.
    """
    wert = wert.strip().lower()
    if wert == "role":
        wert = "rolle"
    return wert if wert in _ERLAUBTE_TYPEN else "prompt"


@dataclass
class PromptItem:
    """Ein Eintrag in der Prompt-Bibliothek."""

    id: str
    typ: str = "prompt"          # prompt | skill | workflow | rolle | agent
    name: str = ""
    content: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""
    created_at: str = field(default_factory=_jetzt_iso)
    updated_at: str = field(default_factory=_jetzt_iso)

    def __post_init__(self) -> None:
        self.typ = _normalisiere_typ(self.typ)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prompts (
    id          TEXT PRIMARY KEY,
    typ         TEXT NOT NULL DEFAULT 'prompt',
    name        TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    category    TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '[]',
    source      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prompts_typ ON prompts(typ);
CREATE INDEX IF NOT EXISTS idx_prompts_name ON prompts(name COLLATE NOCASE);
"""


# ---------------------------------------------------------------------------
# PromptLibrary
# ---------------------------------------------------------------------------

class PromptLibrary:
    """SQLite-basierte Prompt-Bibliothek.

    Standard-Pfad: ~/.clutch/clutch.db (teilt sich die DB mit dem Fahrtenbuch,
    sofern der Nutzer denselben Pfad verwendet; CREATE TABLE IF NOT EXISTS
    garantiert Idempotenz).
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        if db_path is None:
            db_path = Path.home() / ".clutch" / "clutch.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Internes Verbindungs-Handling
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Hilfsmethoden
    # ------------------------------------------------------------------

    @staticmethod
    def _row_zu_item(row: sqlite3.Row) -> PromptItem:
        tags_raw = row["tags"]
        try:
            tags = json.loads(tags_raw) if tags_raw else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        return PromptItem(
            id=row["id"],
            typ=row["typ"],
            name=row["name"],
            content=row["content"],
            category=row["category"],
            tags=tags,
            source=row["source"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def upsert(self, item: PromptItem) -> PromptItem:
        """Eintrag einfügen oder aktualisieren.

        Wenn item.id leer ist, wird eine neue UUID vergeben.
        updated_at wird immer auf den aktuellen Zeitstempel gesetzt.
        """
        if not item.id:
            item.id = uuid4().hex
        item.updated_at = _jetzt_iso()

        tags_json = json.dumps(item.tags, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO prompts
                   (id, typ, name, content, category, tags, source, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       typ        = excluded.typ,
                       name       = excluded.name,
                       content    = excluded.content,
                       category   = excluded.category,
                       tags       = excluded.tags,
                       source     = excluded.source,
                       updated_at = excluded.updated_at""",
                (
                    item.id, item.typ, item.name, item.content,
                    item.category, tags_json, item.source,
                    item.created_at, item.updated_at,
                ),
            )
        return item

    def get(self, id: str) -> Optional[PromptItem]:
        """Einzelnen Eintrag per ID laden. None wenn nicht gefunden."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM prompts WHERE id = ?", (id,)
            ).fetchone()
        return self._row_zu_item(row) if row else None

    def liste(
        self,
        typ: Optional[str] = None,
        tag: Optional[str] = None,
        suche: Optional[str] = None,
    ) -> list[PromptItem]:
        """Einträge auflisten mit optionalen Filtern.

        Args:
            typ:    Exakter Typ-Filter (prompt/skill/workflow/rolle/agent).
            tag:    Nur Einträge zurückgeben, deren tags-Liste diesen Tag enthält.
            suche:  Case-insensitive Suche in name und content.
        """
        query = "SELECT * FROM prompts WHERE 1=1"
        params: list = []

        if typ is not None:
            query += " AND typ = ?"
            params.append(_normalisiere_typ(typ))

        if suche is not None:
            # LIKE-Metazeichen escapen, sonst werden % und _ als Wildcards gewertet.
            query += " AND (name LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"
            sicher = suche.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            muster = f"%{sicher}%"
            params.extend([muster, muster])

        query += " ORDER BY updated_at DESC"

        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()

        ergebnisse = [self._row_zu_item(r) for r in rows]

        # Tag-Filter nachgelagert (Tags liegen als JSON-Array in der DB)
        if tag is not None:
            tag_lower = tag.casefold()
            ergebnisse = [
                item for item in ergebnisse
                if any(t.casefold() == tag_lower for t in item.tags)
            ]

        return ergebnisse

    def loesche(self, id: str) -> bool:
        """Eintrag löschen. Gibt True zurück wenn ein Eintrag entfernt wurde."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM prompts WHERE id = ?", (id,))
            return cursor.rowcount > 0

    def copy_text(self, id: str) -> str:
        """Content eines Eintrags zurückgeben (für Copy-in-Chat).

        Gibt leeren String zurück wenn der Eintrag nicht existiert.
        """
        item = self.get(id)
        return item.content if item else ""

    def import_promptboard(self, json_pfad: Path) -> int:
        """PromptBoard library.json importieren.

        Mappt item_type (PROMPT/SKILL/WORKFLOW/ROLLE/AGENT) auf typ (lowercase).
        Namenskollisionen erzeugen einen neuen Eintrag — bestehende werden NICHT
        überschrieben (jede Collision = eigener Eintrag mit neuer ID).

        Args:
            json_pfad: Pfad zur PromptBoard library.json.

        Returns:
            Anzahl erfolgreich importierter Einträge.
        """
        json_pfad = Path(json_pfad)
        if not json_pfad.exists():
            return 0
        try:
            daten = json.loads(json_pfad.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return 0
        if not isinstance(daten, dict):
            return 0
        items_roh = daten.get("items", [])

        importiert = 0
        for eintrag in items_roh:
            item_type_roh = eintrag.get("item_type", "PROMPT")
            typ = _normalisiere_typ(item_type_roh)

            tags_roh = eintrag.get("tags", [])
            if isinstance(tags_roh, str):
                tags_roh = [t.strip() for t in tags_roh.split(",") if t.strip()]

            neues_item = PromptItem(
                id=uuid4().hex,          # immer neue ID → keine Überschreibung
                typ=typ,
                name=eintrag.get("name", ""),
                content=eintrag.get("content", ""),
                category=eintrag.get("category", ""),
                tags=tags_roh,
                source=eintrag.get("source", ""),
                created_at=eintrag.get("created_at", _jetzt_iso()),
                updated_at=eintrag.get("updated_at", _jetzt_iso()),
            )
            self.upsert(neues_item)
            importiert += 1

        return importiert
