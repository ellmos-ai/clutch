"""Tests für den datensparsamen Clutch Evidence-Locator."""

from dataclasses import replace

import pytest

from clutch.evidence_locator import (
    AmbiguousEvidenceError,
    ClutchEvidenceLocator,
    EvidenceIntegrityError,
    EvidenceNotFoundError,
)
from clutch.session_store import SessionStore


@pytest.fixture
def store(tmp_path):
    return SessionStore(tmp_path / "clutch.db")


def test_locator_contains_uri_hash_and_no_raw_text(store):
    session = store.neue_session()
    message = store.add_message(session.id, "user", "privater Rohprompt")

    receipt = ClutchEvidenceLocator(store).locate_one(message_id=message.id)
    projection = receipt.to_dict()

    assert projection["source_uri"].startswith("clutch-local://session-evidence/")
    assert len(projection["content_hash"]) == 64
    assert projection["locator"]["message_id"] == message.id
    assert session.id not in repr(projection)
    assert "privater Rohprompt" not in repr(projection)
    assert str(store.db_path) not in repr(projection)


def test_locator_resolves_content_only_after_integrity_check(store):
    session = store.neue_session()
    message = store.add_message(session.id, "user", "nur lokal")
    adapter = ClutchEvidenceLocator(store)

    receipt = adapter.locate_one(message_id=message.id)

    assert adapter.resolve_content(receipt) == "nur lokal"


def test_missing_evidence_fails_closed(store):
    with pytest.raises(EvidenceNotFoundError):
        ClutchEvidenceLocator(store).locate_one(message_id="missing")


def test_ambiguous_evidence_fails_closed(store):
    session = store.neue_session()
    store.add_message(session.id, "user", "eins")
    store.add_message(session.id, "user", "zwei")

    with pytest.raises(AmbiguousEvidenceError):
        ClutchEvidenceLocator(store).locate_one(
            session_id=session.id,
            role="user",
        )


def test_tampered_hash_fails_closed_without_raw_text_in_error(store):
    session = store.neue_session()
    message = store.add_message(session.id, "user", "streng privat")
    adapter = ClutchEvidenceLocator(store)
    receipt = adapter.locate_one(message_id=message.id)
    tampered = replace(receipt, content_hash="0" * 64)

    with pytest.raises(EvidenceIntegrityError) as error:
        adapter.resolve_content(tampered)

    assert "streng privat" not in str(error.value)
