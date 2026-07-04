"""Tests für M6 -- Web-App (FastAPI-Endpunkte).

FastAPI und httpx sind optionale Dependencies -- fehlen sie, werden alle
Tests übersprungen (pytest.importorskip).

Fake-Handler injiziert ein MotorErgebnis(text="WEBOK", ...) damit keine
echten LLM-Aufrufe stattfinden.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# Optionale Dependencies -- Tests überspringen wenn nicht installiert
fastapi = pytest.importorskip("fastapi")
httpx   = pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from clutch.chat_runtime import ChatRuntime
from clutch.motorblock import MotorErgebnis


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _fake_handler(antwort: str = "WEBOK"):
    """Gibt einen Handler zurück, der immer ein festes MotorErgebnis liefert."""

    def handler(config, task):
        return MotorErgebnis(
            text=antwort,
            input_tokens=1,
            output_tokens=1,
            model_id=config.model_id,
            provider=config.provider,
        )

    return handler


def _make_client(tmp_dir: str) -> TestClient:
    """Erstellt einen TestClient mit injizierter Fake-Runtime."""
    db_path = Path(tmp_dir) / "clutch.db"
    handler = _fake_handler()
    rt = ChatRuntime(db_path=db_path, handler=handler)

    from clutch.webapp import create_app
    app = create_app(db_path=db_path, runtime=rt)
    # base_url 127.0.0.1 -> Host-Header passt zur TrustedHostMiddleware.
    return TestClient(app, base_url="http://127.0.0.1")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_index_liefert_html():
    """GET / gibt Status 200 und HTML zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/")
        assert antwort.status_code == 200
        # Entweder echtes HTML oder Fallback -- beides ist HTML
        ct = antwort.headers.get("content-type", "")
        assert "html" in ct.lower()


def test_chat_neue_session():
    """POST /api/chat ohne session_id legt neue Session an und liefert 'WEBOK'."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.post("/api/chat", json={"text": "Hallo"})
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["text"] == "WEBOK"
        assert "session_id" in daten
        assert daten["session_id"]        # nicht leer
        assert daten["erfolg"] is True


def test_chat_fortfuehren():
    """POST /api/chat mit bestehender session_id führt Sitzung fort."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)

        # Erste Nachricht (neue Session)
        erste = client.post("/api/chat", json={"text": "Erste Nachricht"}).json()
        sid = erste["session_id"]

        # Zweite Nachricht (gleiche Session)
        zweite = client.post("/api/chat", json={"session_id": sid, "text": "Zweite Nachricht"})
        assert zweite.status_code == 200
        daten = zweite.json()
        assert daten["session_id"] == sid
        assert daten["text"] == "WEBOK"


def test_chat_mit_bild():
    """POST /api/chat mit hat_bild=true wird korrekt weitergeleitet."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.post("/api/chat", json={"text": "Was siehst du?", "hat_bild": True})
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["text"] == "WEBOK"


def test_sessions_liste():
    """GET /api/sessions gibt eine Liste zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)

        # Zunächst leer
        antwort = client.get("/api/sessions")
        assert antwort.status_code == 200
        assert isinstance(antwort.json(), list)

        # Nach Chat -- mindestens eine Session
        client.post("/api/chat", json={"text": "Test"})
        antwort = client.get("/api/sessions")
        daten = antwort.json()
        assert len(daten) >= 1
        erste_session = daten[0]
        assert "id" in erste_session
        assert "created_at" in erste_session


def test_session_verlauf():
    """GET /api/sessions/{id} gibt Session mit Verlauf zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)

        # Session anlegen
        chat_antwort = client.post("/api/chat", json={"text": "Frage"}).json()
        sid = chat_antwort["session_id"]

        antwort = client.get(f"/api/sessions/{sid}")
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["id"] == sid
        assert "nachrichten" in daten
        nachrichten = daten["nachrichten"]
        assert len(nachrichten) == 2   # user + assistant
        rollen = [m["role"] for m in nachrichten]
        assert "user" in rollen
        assert "assistant" in rollen


def test_session_nicht_gefunden():
    """GET /api/sessions/{unbekannte_id} gibt 404 zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/api/sessions/nichtexistent")
        assert antwort.status_code == 404


def test_models_nicht_leer():
    """GET /api/models gibt eine nicht-leere Liste zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/api/models")
        assert antwort.status_code == 200
        gaenge = antwort.json()
        assert isinstance(gaenge, list)
        assert len(gaenge) > 0
        # Struktur prüfen
        erster = gaenge[0]
        assert "name" in erster
        assert "provider" in erster
        assert "gang" in erster


def test_profiles_liste():
    """GET /api/profiles gibt eine Liste zurück (initial leer)."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/api/profiles")
        assert antwort.status_code == 200
        assert isinstance(antwort.json(), list)


def test_profiles_speichern_und_lesen():
    """POST /api/profiles + GET /api/profiles?scope= funktionieren korrekt."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)

        nutzlast = {
            "name": "test-profil",
            "scope": "user",
            "payload": {"name": "Lukas"},
        }
        antwort = client.post("/api/profiles", json=nutzlast)
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["name"] == "test-profil"

        # Per GET abrufen
        antwort = client.get("/api/profiles?scope=user")
        profile = antwort.json()
        namen = [p["name"] for p in profile]
        assert "test-profil" in namen


def test_profiles_ungültiger_scope():
    """POST /api/profiles mit ungültigem Scope gibt 400 zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.post("/api/profiles", json={
            "name": "test",
            "scope": "ungültig",
            "payload": {},
        })
        assert antwort.status_code == 400


def test_prompts_liste():
    """GET /api/prompts gibt eine Liste zurück (initial leer)."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/api/prompts")
        assert antwort.status_code == 200
        assert isinstance(antwort.json(), list)


def test_prompts_suche():
    """GET /api/prompts?suche= filtert Ergebnisse."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        antwort = client.get("/api/prompts?suche=irgendwas")
        assert antwort.status_code == 200
        assert isinstance(antwort.json(), list)


def test_stats_enthält_sessions():
    """GET /api/stats gibt ein dict mit 'sessions'-Schlüssel zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)

        # Zunächst ohne Sessions
        antwort = client.get("/api/stats")
        assert antwort.status_code == 200
        daten = antwort.json()
        assert "sessions" in daten
        assert isinstance(daten["sessions"], int)

        # Nach einem Chat-Aufruf steigt der Zähler
        client.post("/api/chat", json={"text": "Test"})
        antwort = client.get("/api/stats")
        daten = antwort.json()
        assert daten["sessions"] >= 1


def test_upload_endpunkt():
    """POST /api/upload nimmt eine Datei entgegen und gibt hat_bild zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        client = _make_client(tmp)
        # Kleines Dummy-Bild als Bytes hochladen
        fake_bild = b"\xff\xd8\xff\xe0test"  # minimale JPEG-Signatur
        antwort = client.post(
            "/api/upload",
            files={"datei": ("test.jpg", fake_bild, "image/jpeg")},
        )
        assert antwort.status_code == 200
        daten = antwort.json()
        assert daten["hat_bild"] is True
        assert "name" in daten


def test_webapp_importierbar_ohne_fastapi():
    """webapp.py ist importierbar -- create_app/serve werfen ImportError wenn FastAPI fehlt.

    Dieser Test prüft nur, dass das Modul importierbar ist (nicht, dass FastAPI fehlt,
    denn in dieser Test-Suite ist FastAPI ja vorhanden -- sonst wären die Tests geskippt).
    """
    from clutch import webapp  # noqa: F401
    assert hasattr(webapp, "create_app")
    assert hasattr(webapp, "serve")
