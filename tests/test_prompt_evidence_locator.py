"""Tests für den opaque Clutch Evidence-Locator."""

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


def test_projection_contains_only_fixed_uri_opaque_id_and_hash(store):
    session = store.neue_session()
    message = store.add_message(session.id, "user", "privater Rohprompt")

    receipt = ClutchEvidenceLocator(store).locate_one(message_id=message.id)
    projection = receipt.to_dict()

    assert set(projection) == {
        "schema",
        "provider_code",
        "locator_id",
        "source_uri",
        "content_hash",
    }
    assert projection["source_uri"] == (
        f"clutch-local://evidence/{projection['locator_id']}"
    )
    assert session.id not in repr(projection)
    assert message.id not in repr(projection)
    assert "privater Rohprompt" not in repr(projection)
    assert str(store.db_path) not in repr(projection)
    assert "?" not in projection["source_uri"]
    assert "#" not in projection["source_uri"]


def test_locator_binding_resolves_content_only_locally(store):
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


def test_tampered_hash_or_uri_fails_closed(store):
    session = store.neue_session()
    message = store.add_message(session.id, "user", "streng privat")
    adapter = ClutchEvidenceLocator(store)
    receipt = adapter.locate_one(message_id=message.id)
    with pytest.raises(EvidenceIntegrityError):
        adapter.resolve_content(replace(receipt, content_hash="0" * 64))
    with pytest.raises(EvidenceIntegrityError):
        replace(receipt, source_uri=receipt.source_uri + "?session=raw")
