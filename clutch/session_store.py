"""Session-Store -- SQLite-basierte Persistenz für Chat-Sitzungen und Verläufe.

Speichert Sitzungen (ChatSession) und deren Nachrichten (ChatMessage) in
clutch.db unter ~/.clutch/. Keine externen Abhängigkeiten (nur stdlib).
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


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _jetzt() -> str:
    """ISO-8601-Zeitstempel (UTC) ohne Mikrosekunden."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Datenklassen
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    """Eine einzelne Nachricht innerhalb einer Sitzung."""
    id: str
    session_id: str
    role: str                        # "user", "assistant", "system", …
    content: str
    attachments: list[str]           # Dateiname oder Pfad-Liste
    tokens: int
    model: str
    latenz: float                    # Antwortzeit in Sekunden
    created_at: str                  # ISO-8601


@dataclass
class ChatSession:
    """Metadaten einer Chat-Sitzung."""
    id: str
    titel: str
    profil: Optional[str]            # Profil-ID oder None
    model_override: Optional[str]    # Modell-Überschreibung oder None
    system_prompt_on: bool
    created_at: str                  # ISO-8601
    updated_at: str                  # ISO-8601


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_sessions (
    id               TEXT PRIMARY KEY,
    titel            TEXT NOT NULL DEFAULT '',
    profil           TEXT,
    model_override   TEXT,
    system_prompt_on INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL DEFAULT '',
    attachments TEXT NOT NULL DEFAULT '[]',
    tokens      INTEGER NOT NULL DEFAULT 0,
    model       TEXT NOT NULL DEFAULT '',
    latenz      REAL NOT NULL DEFAULT 0.0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session_id
    ON chat_messages(session_id);

CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
    ON chat_sessions(updated_at DESC);
"""


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class SessionStore:
    """Persistenter Speicher für Chat-Sitzungen und Nachrichten."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".clutch" / "clutch.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Interne Helfer
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # Sitzungs-Operationen
    # ------------------------------------------------------------------

    def neue_session(
        self,
        titel: str = "",
        profil: Optional[str] = None,
        model_override: Optional[str] = None,
        system_prompt_on: bool = True,
    ) -> ChatSession:
        """Legt eine neue Sitzung an und gibt sie zurück."""
        jetzt = _jetzt()
        sitzung = ChatSession(
            id=uuid4().hex,
            titel=titel,
            profil=profil,
            model_override=model_override,
            system_prompt_on=system_prompt_on,
            created_at=jetzt,
            updated_at=jetzt,
        )
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO chat_sessions
                   (id, titel, profil, model_override, system_prompt_on,
                    created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    sitzung.id,
                    sitzung.titel,
                    sitzung.profil,
                    sitzung.model_override,
                    int(sitzung.system_prompt_on),
                    sitzung.created_at,
                    sitzung.updated_at,
                ),
            )
        return sitzung

    def session(self, session_id: str) -> Optional[ChatSession]:
        """Gibt die Sitzung zurück oder None, wenn sie nicht existiert."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return _row_zu_session(row) if row else None

    def sessions(self, limit: int = 50) -> list[ChatSession]:
        """Gibt Sitzungen zurück, neueste zuerst."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_zu_session(r) for r in rows]

    def loesche(self, session_id: str) -> bool:
        """Löscht Sitzung und alle zugehörigen Nachrichten. Gibt True zurück, wenn gefunden."""
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM chat_sessions WHERE id = ?", (session_id,)
            )
            return cur.rowcount > 0

    def set_system_prompt(self, session_id: str, an: bool) -> None:
        """Setzt den system_prompt_on-Status der Sitzung."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE chat_sessions SET system_prompt_on = ?, updated_at = ? WHERE id = ?",
                (int(an), _jetzt(), session_id),
            )

    # ------------------------------------------------------------------
    # Nachrichten-Operationen
    # ------------------------------------------------------------------

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: Optional[list[str]] = None,
        tokens: int = 0,
        model: str = "",
        latenz: float = 0.0,
    ) -> ChatMessage:
        """Hängt eine Nachricht an die Sitzung an und aktualisiert updated_at."""
        nachricht = ChatMessage(
            id=uuid4().hex,
            session_id=session_id,
            role=role,
            content=content,
            attachments=attachments or [],
            tokens=tokens,
            model=model,
            latenz=latenz,
            created_at=_jetzt(),
        )
        jetzt = _jetzt()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO chat_messages
                   (id, session_id, role, content, attachments,
                    tokens, model, latenz, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    nachricht.id,
                    nachricht.session_id,
                    nachricht.role,
                    nachricht.content,
                    json.dumps(nachricht.attachments, ensure_ascii=False),
                    nachricht.tokens,
                    nachricht.model,
                    nachricht.latenz,
                    nachricht.created_at,
                ),
            )
            conn.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (jetzt, session_id),
            )
        return nachricht

    def verlauf(self, session_id: str) -> list[ChatMessage]:
        """Gibt alle Nachrichten der Sitzung chronologisch zurück."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT * FROM chat_messages
                   WHERE session_id = ?
                   ORDER BY created_at ASC""",
                (session_id,),
            ).fetchall()
        return [_row_zu_message(r) for r in rows]


# ---------------------------------------------------------------------------
# Interne Konverter
# ---------------------------------------------------------------------------

def _row_zu_session(row: sqlite3.Row) -> ChatSession:
    return ChatSession(
        id=row["id"],
        titel=row["titel"],
        profil=row["profil"],
        model_override=row["model_override"],
        system_prompt_on=bool(row["system_prompt_on"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_zu_message(row: sqlite3.Row) -> ChatMessage:
    try:
        attachments = json.loads(row["attachments"] or "[]")
    except (json.JSONDecodeError, TypeError):
        attachments = []
    return ChatMessage(
        id=row["id"],
        session_id=row["session_id"],
        role=row["role"],
        content=row["content"],
        attachments=attachments,
        tokens=row["tokens"],
        model=row["model"],
        latenz=row["latenz"],
        created_at=row["created_at"],
    )
