"""Tests fuer den lokalen Credential-Store + keys-CLI."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.credentials import CredentialStore, get_api_key
from clutch import cli


def test_store_set_get_remove():
    with tempfile.TemporaryDirectory() as tmp:
        store = CredentialStore(pfad=Path(tmp) / "credentials.json")
        assert store.get("X") is None
        store.set("X", "geheim")
        assert store.get("X") == "geheim"
        assert store.remove("X") is True
        assert store.get("X") is None
        assert store.remove("X") is False
        print("[OK] Store set/get/remove")


def test_store_namen_ohne_werte():
    with tempfile.TemporaryDirectory() as tmp:
        store = CredentialStore(pfad=Path(tmp) / "c.json")
        store.set("MOONSHOT_API_KEY", "sk-geheim-1")
        store.set("ANTHROPIC_API_KEY", "sk-geheim-2")
        namen = store.namen()
        assert namen == ["ANTHROPIC_API_KEY", "MOONSHOT_API_KEY"]
        # Werte tauchen in der Namensliste NICHT auf
        assert all("sk-" not in n for n in namen)
        print("[OK] namen() zeigt keine Werte")


def test_get_api_key_env_vorrang(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = CredentialStore(pfad=Path(tmp) / "c.json")
        store.set("MOONSHOT_API_KEY", "aus-store")
        monkeypatch.setenv("MOONSHOT_API_KEY", "aus-env")
        assert get_api_key("MOONSHOT_API_KEY", store=store) == "aus-env"
        print("[OK] Env hat Vorrang")


def test_get_api_key_store_fallback(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = CredentialStore(pfad=Path(tmp) / "c.json")
        store.set("MOONSHOT_API_KEY", "aus-store")
        monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
        assert get_api_key("MOONSHOT_API_KEY", store=store) == "aus-store"
        print("[OK] Store-Fallback")


def test_get_api_key_leer_wenn_nichts(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        store = CredentialStore(pfad=Path(tmp) / "c.json")
        monkeypatch.delenv("NIXKEY", raising=False)
        # bach-kompat Datei existiert fuer NIXKEY sicher nicht
        assert get_api_key("NIXKEY", store=store) == ""
        print("[OK] leer wenn nichts gefunden")


def test_keys_cli_set_list_remove(monkeypatch, capsys):
    with tempfile.TemporaryDirectory() as tmp:
        # Home auf tmp umbiegen, damit CredentialStore() nach tmp schreibt
        monkeypatch.setenv("USERPROFILE", tmp)
        monkeypatch.setenv("HOME", tmp)

        assert cli.main(["keys", "set", "TESTKEY", "sk-supergeheim"]) == 0
        capsys.readouterr()

        assert cli.main(["keys", "list"]) == 0
        out = capsys.readouterr().out
        assert "TESTKEY" in out
        # Der Wert darf NIE in der Ausgabe erscheinen
        assert "sk-supergeheim" not in out

        assert cli.main(["keys", "remove", "TESTKEY"]) == 0
        capsys.readouterr()  # "TESTKEY entfernt."-Meldung verwerfen
        assert cli.main(["keys", "list"]) == 0
        out2 = capsys.readouterr().out
        assert "TESTKEY" not in out2
        print("[OK] keys-CLI set/list/remove (Wert nie sichtbar)")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
