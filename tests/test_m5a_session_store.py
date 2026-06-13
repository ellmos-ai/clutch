"""Tests für M5a -- Session- + Chatverlauf-Persistenz (clutch.session_store).

Strategie: Alles in-memory via temporärem Verzeichnis. Kein Netzwerk, kein LLM.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from clutch.session_store import SessionStore, ChatSession, ChatMessage


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    """SessionStore mit frischer Datenbank im temporären Verzeichnis."""
    return SessionStore(db_path=tmp_path / "test.db")


# ---------------------------------------------------------------------------
# Session anlegen + wiederfinden
# ---------------------------------------------------------------------------

class TestSessionCRUD:
    def test_neue_session_gibt_session_zurück(self, store):
        s = store.neue_session(titel="Erster Test")
        assert isinstance(s, ChatSession)
        assert s.titel == "Erster Test"
        assert len(s.id) == 32           # uuid4().hex = 32 Zeichen

    def test_session_wiederfinden(self, store):
        s = store.neue_session(titel="Wiederholungstest", profil="dev")
        geladen = store.session(s.id)
        assert geladen is not None
        assert geladen.id == s.id
        assert geladen.titel == "Wiederholungstest"
        assert geladen.profil == "dev"

    def test_session_nicht_vorhanden(self, store):
        assert store.session("nichtvorhanden") is None

    def test_neue_session_defaults(self, store):
        s = store.neue_session()
        assert s.titel == ""
        assert s.profil is None
        assert s.model_override is None
        assert s.system_prompt_on is True

    def test_neue_session_model_override(self, store):
        s = store.neue_session(model_override="claude-opus-4")
        geladen = store.session(s.id)
        assert geladen.model_override == "claude-opus-4"


# ---------------------------------------------------------------------------
# Messages anhängen + Verlauf + Attachments
# ---------------------------------------------------------------------------

class TestMessages:
    def test_message_anhängen_und_verlauf(self, store):
        s = store.neue_session()
        m1 = store.add_message(s.id, "user", "Hallo!")
        m2 = store.add_message(s.id, "assistant", "Ich bin bereit.")

        verlauf = store.verlauf(s.id)
        assert len(verlauf) == 2
        assert verlauf[0].role == "user"
        assert verlauf[0].content == "Hallo!"
        assert verlauf[1].role == "assistant"

    def test_verlauf_chronologisch(self, store):
        s = store.neue_session()
        for i in range(5):
            store.add_message(s.id, "user", f"Nachricht {i}")

        verlauf = store.verlauf(s.id)
        inhalte = [m.content for m in verlauf]
        assert inhalte == [f"Nachricht {i}" for i in range(5)]

    def test_attachments_roundtrip(self, store):
        s = store.neue_session()
        dateien = ["bild.png", "dokument.pdf", "notiz.txt"]
        m = store.add_message(
            s.id, "user", "Dateien angehängt",
            attachments=dateien, tokens=42, model="claude-sonnet-4-6", latenz=1.23
        )

        verlauf = store.verlauf(s.id)
        assert len(verlauf) == 1
        wieder = verlauf[0]
        assert wieder.attachments == dateien
        assert wieder.tokens == 42
        assert wieder.model == "claude-sonnet-4-6"
        assert abs(wieder.latenz - 1.23) < 1e-9

    def test_leere_attachments(self, store):
        s = store.neue_session()
        store.add_message(s.id, "user", "Kein Anhang")
        verlauf = store.verlauf(s.id)
        assert verlauf[0].attachments == []

    def test_verlauf_leere_session(self, store):
        s = store.neue_session()
        assert store.verlauf(s.id) == []

    def test_add_message_aktualisiert_updated_at(self, store):
        s = store.neue_session()
        updated_vorher = s.updated_at
        store.add_message(s.id, "user", "Hallo")
        geladen = store.session(s.id)
        # updated_at darf gleich oder neuer sein (Zeitauflösung 1 Sekunde)
        assert geladen.updated_at >= updated_vorher


# ---------------------------------------------------------------------------
# sessions() Reihenfolge
# ---------------------------------------------------------------------------

class TestSessionsListe:
    def test_sessions_neueste_zuerst(self, store):
        s1 = store.neue_session(titel="Erste")
        s2 = store.neue_session(titel="Zweite")
        s3 = store.neue_session(titel="Dritte")
        # Message anhängen aktualisiert updated_at von s1 → schiebt s1 nach vorn
        store.add_message(s1.id, "user", "Ping")

        liste = store.sessions()
        assert liste[0].id == s1.id    # s1 hat neuestes updated_at
        assert liste[-1].titel in {"Zweite", "Dritte"}

    def test_sessions_limit(self, store):
        for i in range(10):
            store.neue_session(titel=f"Sitzung {i}")
        assert len(store.sessions(limit=5)) == 5

    def test_sessions_leer(self, store):
        assert store.sessions() == []


# ---------------------------------------------------------------------------
# loesche() -- Session + Messages
# ---------------------------------------------------------------------------

class TestLoesche:
    def test_loesche_entfernt_session(self, store):
        s = store.neue_session()
        assert store.loesche(s.id) is True
        assert store.session(s.id) is None

    def test_loesche_entfernt_messages(self, store):
        s = store.neue_session()
        store.add_message(s.id, "user", "Wird gelöscht")
        store.add_message(s.id, "assistant", "Ebenfalls weg")
        store.loesche(s.id)
        # Verlauf einer gelöschten Session = leer (FK ON DELETE CASCADE)
        assert store.verlauf(s.id) == []

    def test_loesche_nicht_vorhanden(self, store):
        assert store.loesche("gibtsNicht") is False

    def test_loesche_lässt_andere_sessions_intakt(self, store):
        s1 = store.neue_session(titel="Bleibt")
        s2 = store.neue_session(titel="Wird gelöscht")
        store.add_message(s1.id, "user", "Ich bleibe")
        store.loesche(s2.id)

        assert store.session(s1.id) is not None
        assert len(store.verlauf(s1.id)) == 1


# ---------------------------------------------------------------------------
# set_system_prompt
# ---------------------------------------------------------------------------

class TestSystemPromptToggle:
    def test_set_system_prompt_aus(self, store):
        s = store.neue_session(system_prompt_on=True)
        store.set_system_prompt(s.id, an=False)
        geladen = store.session(s.id)
        assert geladen.system_prompt_on is False

    def test_set_system_prompt_an(self, store):
        s = store.neue_session(system_prompt_on=False)
        store.set_system_prompt(s.id, an=True)
        geladen = store.session(s.id)
        assert geladen.system_prompt_on is True

    def test_set_system_prompt_toggle_mehrfach(self, store):
        s = store.neue_session()
        for erwartung in [False, True, False, True]:
            store.set_system_prompt(s.id, an=erwartung)
            assert store.session(s.id).system_prompt_on is erwartung


# ---------------------------------------------------------------------------
# Idempotenz: Schema kann mehrfach initialisiert werden
# ---------------------------------------------------------------------------

class TestIdempotenz:
    def test_doppelte_initialisierung(self, tmp_path):
        db = tmp_path / "idempotenz.db"
        store1 = SessionStore(db_path=db)
        s = store1.neue_session(titel="Persistent")
        # Zweite Instanz öffnet dieselbe DB -- kein Fehler, kein Datenverlust
        store2 = SessionStore(db_path=db)
        assert store2.session(s.id) is not None
        assert store2.session(s.id).titel == "Persistent"
