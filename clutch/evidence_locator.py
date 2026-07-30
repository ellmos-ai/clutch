"""Datensparsamer Locator für lokale Clutch-Session-Evidence.

Der Locator projiziert ausschließlich eine opaque URI, Hash und lokale
Auflösungsdaten. Nachrichteninhalt und Datenbankpfad bleiben in Clutch.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any

from clutch.session_store import ChatMessage, SessionStore


class EvidenceLookupError(LookupError):
    """Basisklasse für fail-closed Evidence-Auflösung."""


class EvidenceNotFoundError(EvidenceLookupError):
    """Kein exakt passender lokaler Datensatz wurde gefunden."""


class AmbiguousEvidenceError(EvidenceLookupError):
    """Mehr als ein lokaler Datensatz erfüllt die Kriterien."""


class EvidenceIntegrityError(EvidenceLookupError):
    """Ein Locator passt nicht mehr zum lokal gespeicherten Datensatz."""


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PromptEvidenceLocator:
    """Cloud-sichere Projektion eines lokalen Clutch-Datensatzes."""

    schema: str
    provider: str
    source_uri: str
    content_hash: str
    captured_at: str
    locator: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """Serialisiert ausschließlich die sichere Projektion."""
        return asdict(self)


class ClutchEvidenceLocator:
    """Erzeugt und verifiziert Locator-Receipts für ``SessionStore``."""

    SCHEMA = "ellmos.prompt-evidence-locator.v1"
    PROVIDER = "clutch"

    def __init__(self, store: SessionStore) -> None:
        self._store = store

    def locate_one(
        self,
        *,
        message_id: str | None = None,
        session_id: str | None = None,
        role: str | None = None,
        captured_at: str | None = None,
    ) -> PromptEvidenceLocator:
        """Findet genau eine Nachricht oder verweigert die Projektion.

        ``message_id`` ist der bevorzugte, eindeutige Weg. Ohne ID ist eine
        lokale Suche nur innerhalb einer angegebenen Session zulässig. Null
        oder mehrere Treffer werden niemals heuristisch aufgelöst.
        """
        candidates: list[ChatMessage]
        if message_id:
            message = self._store.message(message_id)
            candidates = [message] if message else []
        elif session_id:
            candidates = self._store.verlauf(session_id)
        else:
            raise EvidenceNotFoundError(
                "message_id or session_id is required for local evidence lookup"
            )

        if session_id is not None:
            candidates = [item for item in candidates if item.session_id == session_id]
        if role is not None:
            candidates = [item for item in candidates if item.role == role]
        if captured_at is not None:
            candidates = [item for item in candidates if item.created_at == captured_at]

        if not candidates:
            raise EvidenceNotFoundError("no matching Clutch evidence")
        if len(candidates) != 1:
            raise AmbiguousEvidenceError(
                f"Clutch evidence lookup returned {len(candidates)} matches"
            )
        return self._project(candidates[0])

    def resolve_content(self, locator: PromptEvidenceLocator) -> str:
        """Löst Rohtext ausschließlich im lokalen Prozess auf.

        Vor der Rückgabe werden Schema, Provider, Session-Bindung, URI und
        Inhalts-Hash erneut geprüft. Fehler geben keinen Rohtext preis.
        """
        if locator.schema != self.SCHEMA or locator.provider != self.PROVIDER:
            raise EvidenceIntegrityError("unsupported evidence locator")
        if locator.locator.get("store") != "clutch-session-store":
            raise EvidenceIntegrityError("invalid evidence store binding")

        message_id = locator.locator.get("message_id", "")
        message = self._store.message(message_id)
        if message is None:
            raise EvidenceNotFoundError("referenced Clutch evidence is missing")

        expected = self._project(message)
        if expected != locator:
            raise EvidenceIntegrityError("Clutch evidence locator integrity check failed")
        return message.content

    def _project(self, message: ChatMessage) -> PromptEvidenceLocator:
        session_hash = _sha256(message.session_id)
        source_uri = (
            f"clutch-local://session-evidence/{session_hash}/{message.id}"
        )
        return PromptEvidenceLocator(
            schema=self.SCHEMA,
            provider=self.PROVIDER,
            source_uri=source_uri,
            content_hash=_sha256(message.content),
            captured_at=message.created_at,
            locator={
                "store": "clutch-session-store",
                "message_id": message.id,
                "session_id_hash": session_hash,
            },
        )
