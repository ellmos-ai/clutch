"""Tests für M4 -- CLI-Ansteuerbarkeit (clutch.cli).

Strategie: Kein Netzwerk, kein LLM. Alle Tests laufen offline.
- route + models: Engine-intern, zero-dependency auf Provider-Keys
- config: roundtrip mit temporärem HOME (USERPROFILE auf Windows)
- one-shot/run: NICHT live getestet (würde Netzwerk brauchen);
  Provider-Unavailability-Pfad über monkeypatch abgedeckt.
"""

import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from clutch.cli import main, _lade_config, _speichere_config, _config_pfad


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------

class TestRoute:
    def test_route_json_exit_0(self, capsys):
        rc = main(["route", "Fix den Bug in auth.py", "--json"])
        assert rc == 0

    def test_route_json_enthaelt_pflichtfelder(self, capsys):
        main(["route", "Fix den Bug in auth.py", "--json"])
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        assert "gang" in daten, "Feld 'gang' fehlt"
        assert "zweck" in daten, "Feld 'zweck' fehlt"
        assert "score" in daten, "Feld 'score' fehlt"
        assert "provider" in daten, "Feld 'provider' fehlt"
        assert "gas" in daten, "Feld 'gas' fehlt"
        assert "muster" in daten, "Feld 'muster' fehlt"

    def test_route_text_exit_0(self, capsys):
        rc = main(["route", "Erkläre mir Quantenmechanik"])
        assert rc == 0

    def test_route_text_ausgabe_nicht_leer(self, capsys):
        main(["route", "Schreibe einen Sortieralgorithmus"])
        captured = capsys.readouterr()
        assert len(captured.out.strip()) > 0

    def test_route_score_in_range(self, capsys):
        main(["route", "Hallo", "--json"])
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        assert 0 <= daten["score"] <= 100

    def test_route_zweck_erkannt(self, capsys):
        main(["route", "Implementiere einen Quicksort-Algorithmus in Python", "--json"])
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        # Coding-Prompt sollte 'coding' oder 'general' liefern, nie None
        assert daten["zweck"] is not None
        assert isinstance(daten["zweck"], str)


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------

class TestModels:
    def test_models_json_nicht_leer(self, capsys):
        rc = main(["models", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        liste = json.loads(captured.out)
        assert isinstance(liste, list)
        assert len(liste) > 0, "Gänge-Liste ist leer"

    def test_models_json_enthaelt_pflichtfelder(self, capsys):
        main(["models", "--json"])
        captured = capsys.readouterr()
        liste = json.loads(captured.out)
        first = liste[0]
        assert "name" in first
        assert "provider" in first
        assert "gang_stufe" in first

    def test_models_text_exit_0(self, capsys):
        rc = main(["models"])
        assert rc == 0

    def test_models_text_ausgabe_nicht_leer(self, capsys):
        main(["models"])
        captured = capsys.readouterr()
        assert len(captured.out.strip()) > 0


# ---------------------------------------------------------------------------
# config (roundtrip mit temporärem HOME)
# ---------------------------------------------------------------------------

class TestConfig:
    def test_config_set_und_lesen(self, tmp_path, monkeypatch, capsys):
        """Setzt einen Wert und liest ihn wieder — isoliert in tmp HOME."""
        monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows
        monkeypatch.setenv("HOME", str(tmp_path))         # POSIX-Fallback

        rc_set = main(["config", "test_schluessel", "test_wert"])
        assert rc_set == 0
        capsys.readouterr()  # stdout des Set-Aufrufs verwerfen

        # Lesen zurück mit --json
        main(["config", "test_schluessel", "--json"])
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        assert daten.get("test_schluessel") == "test_wert"

    def test_config_lesen_unbekannter_key(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path))

        rc = main(["config", "nicht_vorhanden", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        assert daten.get("nicht_vorhanden") is None

    def test_config_mehrere_keys(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("USERPROFILE", str(tmp_path))
        monkeypatch.setenv("HOME", str(tmp_path))

        main(["config", "key_a", "wert_a"])
        main(["config", "key_b", "wert_b"])
        capsys.readouterr()  # Set-Ausgaben verwerfen

        main(["config", "key_a", "--json"])
        captured = capsys.readouterr()
        assert json.loads(captured.out)["key_a"] == "wert_a"

        main(["config", "key_b", "--json"])
        captured = capsys.readouterr()
        assert json.loads(captured.out)["key_b"] == "wert_b"


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_stats_exit_0(self, capsys):
        rc = main(["stats"])
        assert rc == 0

    def test_stats_json_hat_schluessel(self, capsys):
        rc = main(["stats", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        daten = json.loads(captured.out)
        assert "bordcomputer" in daten
        assert "tankuhr" in daten


# ---------------------------------------------------------------------------
# One-shot / run: Provider-Unavailability (kein Netzwerk)
# ---------------------------------------------------------------------------

class TestRunProviderUnavailable:
    """Testet den Fallback wenn kein Motor verfügbar ist."""

    def test_run_kein_motor_gibt_exit_2(self, capsys, monkeypatch):
        """Wenn alle Motoren unavailable sind, soll Exit 2 zurückkommen."""
        from clutch import motorblock as mb

        # Alle Motoren als unavailable patchen
        original_init = mb.MotorBlock.__init__

        class MockBlock(mb.MotorBlock):
            def verfuegbare_motoren(self):
                return {name: False for name in super().verfuegbare_motoren()}

        monkeypatch.setattr(mb, "MotorBlock", MockBlock)

        rc = main(["run", "Hallo Welt"])
        # Exit 2 = kein Provider verfügbar
        assert rc == 2

    def test_route_laeuft_ohne_provider(self, capsys):
        """route ist dry-run und braucht keinen Provider."""
        rc = main(["route", "Teste die Verbindung", "--json"])
        assert rc == 0


# ---------------------------------------------------------------------------
# Positionales Prompt (direkter Aufruf ohne Subcommand)
# ---------------------------------------------------------------------------

class TestPositionalPrompt:
    def test_kein_prompt_zeigt_hilfe(self, capsys):
        rc = main([])
        assert rc == 0
        captured = capsys.readouterr()
        assert "clutch" in captured.out.lower() or len(captured.out) > 0


# ---------------------------------------------------------------------------
# Smoke: Import + main erreichbar
# ---------------------------------------------------------------------------

def test_import_main():
    from clutch.cli import main as cli_main
    assert callable(cli_main)
