"""Opaque, cloud-sicherer Locator für lokale Clutch-Session-Evidence."""

from __future__ import annotations

import hashlib
import re
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


_LOCATOR_ID = re.compile(r"^loc-[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PromptEvidenceLocator:
    """Projektion mit festem Scheme sowie ausschließlich opaque ID und Hash."""

    schema: str
    provider_code: str
    locator_id: str
    source_uri: str
    content_hash: str

    def __post_init__(self) -> None:
        if self.schema != "ellmos.prompt-evidence-locator.v2":
            raise EvidenceIntegrityError("unsupported evidence locator schema")
        if self.provider_code != "clutch":
            raise EvidenceIntegrityError("unsupported evidence provider")
        if not _LOCATOR_ID.fullmatch(self.locator_id):
            raise EvidenceIntegrityError("invalid opaque locator ID")
        if self.source_uri != f"clutch-local://evidence/{self.locator_id}":
            raise EvidenceIntegrityError("invalid fixed-scheme evidence URI")
        if not _SHA256.fullmatch(self.content_hash):
            raise EvidenceIntegrityError("invalid evidence content hash")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ClutchEvidenceLocator:
    """Erzeugt eine opaque Projektion und hält die Auflösung im lokalen Store."""

    SCHEMA = "ellmos.prompt-evidence-locator.v2"
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
        """Findet genau eine Nachricht oder verweigert die Projektion."""
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
        return self._project_and_bind(candidates[0])

    def resolve_content(self, locator: PromptEvidenceLocator) -> str:
        """Löst Rohtext nach erneuter ID-, URI- und Hash-Prüfung lokal auf."""
        locator.__post_init__()
        resolved = self._store.evidence_message(locator.locator_id)
        if resolved is None:
            raise EvidenceNotFoundError("referenced Clutch evidence is missing")
        message, bound_hash = resolved
        if bound_hash != locator.content_hash or _sha256(message.content) != bound_hash:
            raise EvidenceIntegrityError("Clutch evidence locator integrity check failed")
        return message.content

    def _project_and_bind(self, message: ChatMessage) -> PromptEvidenceLocator:
        content_hash = _sha256(message.content)
        identity = "\n".join((message.session_id, message.id, content_hash))
        locator_id = f"loc-{_sha256(identity)}"
        self._store.bind_evidence_locator(locator_id, message.id, content_hash)
        return PromptEvidenceLocator(
            schema=self.SCHEMA,
            provider_code=self.PROVIDER,
            locator_id=locator_id,
            source_uri=f"clutch-local://evidence/{locator_id}",
            content_hash=content_hash,
        )
