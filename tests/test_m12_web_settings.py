"""Tests für M6+ -- Web-Settings (Credentials/Config-Endpunkte).

Werte von API-Keys dürfen NIE über die API zurückgegeben werden.
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient
from clutch.chat_runtime import ChatRuntime
from clutch.motorblock import MotorErgebnis


def _handler(config, task):
    return MotorErgebnis(text="WEBOK", input_tokens=1, output_tokens=1,
                         model_id=config.model_id, provider=config.provider)


def _client(tmp, monkeypatch):
    # Home auf tmp -> CredentialStore + cli-config schreiben nach tmp, nicht echtes ~/.clutch
    monkeypatch.setenv("USERPROFILE", tmp)
    monkeypatch.setenv("HOME", tmp)
    db = Path(tmp) / "clutch.db"
    rt = ChatRuntime(db_path=db, handler=_handler)
    from clutch.webapp import create_app
    return TestClient(create_app(db_path=db, runtime=rt),
                      base_url="http://127.0.0.1")


def test_credentials_set_list_delete_und_kein_wert_leak(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        c = _client(tmp, monkeypatch)

        # Leer am Anfang (kein Store-Key)
        r = c.get("/api/credentials")
        assert r.status_code == 200
        assert all(k.get("im_store") is False for k in r.json()["keys"]) or r.json()["keys"] == []

        # Setzen
        r = c.post("/api/credentials", json={"name": "MOONSHOT_API_KEY", "value": "sk-streng-geheim"})
        assert r.status_code == 200 and r.json()["ok"] is True

        # Listen -> Name da, WERT nirgends im Response-Body
        r = c.get("/api/credentials")
        body = r.text
        assert "MOONSHOT_API_KEY" in body
        assert "sk-streng-geheim" not in body, "API-Key-WERT darf nie über die API auftauchen!"
        eintrag = [k for k in r.json()["keys"] if k["name"] == "MOONSHOT_API_KEY"][0]
        assert eintrag["im_store"] is True

        # Löschen
        r = c.delete("/api/credentials/MOONSHOT_API_KEY")
        assert r.status_code == 200 and r.json()["entfernt"] is True

        r = c.get("/api/credentials")
        assert "sk-streng-geheim" not in r.text
        print("[OK] Credentials set/list/delete ohne Wert-Leak")


def test_credentials_set_validierung(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        c = _client(tmp, monkeypatch)
        assert c.post("/api/credentials", json={"name": "", "value": "x"}).status_code == 422
        assert c.post("/api/credentials", json={"name": "X", "value": ""}).status_code == 422
        print("[OK] Credentials-Validierung")


def test_config_roundtrip(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        c = _client(tmp, monkeypatch)
        assert c.post("/api/config", json={"key": "default_provider", "value": "anthropic"}).status_code == 200
        r = c.get("/api/config")
        assert r.status_code == 200 and r.json().get("default_provider") == "anthropic"
        assert c.post("/api/config", json={"key": ""}).status_code == 422
        print("[OK] Config-Roundtrip")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
