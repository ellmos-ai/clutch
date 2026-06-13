"""Tests für M3 -- Modell-Discovery (discovery.py)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from clutch.getriebe import Gang, Getriebe
from clutch.discovery import (
    ModellDiscovery,
    discover_ollama,
    discover_openai_kompatibel,
    gang_level_aus_groesse,
    parse_custom_models,
)


# ---------------------------------------------------------------------------
# Hilfsfunktionen für Fake-Requests
# ---------------------------------------------------------------------------

def _fake_requests_get_factory(json_antwort: dict):
    """Erstellt ein SimpleNamespace-Requests-Modul, das bei .get() eine
    fixe JSON-Antwort liefert."""

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return json_antwort

    def fake_get(url, headers=None, timeout=None):
        return FakeResp()

    return SimpleNamespace(get=fake_get)


def _fake_requests_error_factory():
    """Erstellt ein SimpleNamespace-Requests-Modul, das immer eine Exception wirft."""

    def fake_get(url, headers=None, timeout=None):
        raise ConnectionError("Nicht erreichbar")

    return SimpleNamespace(get=fake_get)


# ---------------------------------------------------------------------------
# Tests: gang_level_aus_groesse
# ---------------------------------------------------------------------------

def test_gang_level_kleiner_2b():
    assert gang_level_aus_groesse("1b") == 1
    assert gang_level_aus_groesse("1.5B") == 1


def test_gang_level_kleiner_8b():
    assert gang_level_aus_groesse("4b") == 2
    assert gang_level_aus_groesse("7B") == 2


def test_gang_level_kleiner_30b():
    assert gang_level_aus_groesse("14B") == 3
    assert gang_level_aus_groesse("29b") == 3


def test_gang_level_kleiner_100b():
    assert gang_level_aus_groesse("70B") == 4
    assert gang_level_aus_groesse("72b") == 4
    # MoE-Notation: "35b-a3b" → erste Zahl ist 35 → Gang 4
    assert gang_level_aus_groesse("35b-a3b") == 4


def test_gang_level_groesser_gleich_100b():
    assert gang_level_aus_groesse("141b") == 5
    assert gang_level_aus_groesse("405B") == 5


def test_gang_level_kein_zahlenwert():
    # Kein Zahlenwert → Fallback Gang 1
    assert gang_level_aus_groesse("") == 1
    assert gang_level_aus_groesse("unbekannt") == 1
    assert gang_level_aus_groesse(None) == 1


# ---------------------------------------------------------------------------
# Tests: discover_ollama -- Parsing und korrekte Gang-Stufen
# ---------------------------------------------------------------------------

def test_discover_ollama_parsing(monkeypatch):
    """Ollama-Tags-Antwort wird korrekt in Gang-Objekte gemappt."""
    antwort = {
        "models": [
            {"name": "llama3.2:1b", "details": {"parameter_size": "1.2B"}},
            {"name": "mistral:7b", "details": {"parameter_size": "7B"}},
            {"name": "qwen2.5:32b", "details": {"parameter_size": "32B"}},
        ]
    }
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    gaenge = discover_ollama("http://localhost:11434")

    assert len(gaenge) == 3

    # Modell 1: 1.2B → Gang 1
    g1 = next(g for g in gaenge if g.name == "llama3.2:1b")
    assert g1.gang == 1
    assert g1.provider == "ollama"
    assert g1.kosten_input_1k == 0.0
    assert g1.kosten_output_1k == 0.0
    assert "lokal" in g1.staerken
    assert g1.endpoint == "http://localhost:11434"

    # Modell 2: 7B → Gang 2
    g2 = next(g for g in gaenge if g.name == "mistral:7b")
    assert g2.gang == 2

    # Modell 3: 32B → Gang 4 (>= 30B aber < 100B)
    g3 = next(g for g in gaenge if g.name == "qwen2.5:32b")
    assert g3.gang == 4


def test_discover_ollama_modell_id_gleich_name(monkeypatch):
    """model_id soll gleich name sein (Ollama-Konvention)."""
    antwort = {"models": [{"name": "phi3:mini", "details": {"parameter_size": "3.8B"}}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    gaenge = discover_ollama("http://localhost:11434")
    assert gaenge[0].model_id == "phi3:mini"


def test_discover_ollama_nicht_erreichbar(monkeypatch):
    """Bei nicht erreichbarem Host wird eine leere Liste zurückgegeben (kein Crash)."""
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_error_factory())

    gaenge = discover_ollama("http://nicht-erreichbar:11434")
    assert gaenge == []


def test_discover_ollama_leere_models_liste(monkeypatch):
    """Leere models-Liste → leere Ergebnisliste."""
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory({"models": []}))
    assert discover_ollama("http://localhost:11434") == []


def test_discover_ollama_fehlende_details(monkeypatch):
    """Fehlende details/parameter_size → Gang-Stufe 1 (Fallback)."""
    antwort = {"models": [{"name": "nodetails:latest"}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    gaenge = discover_ollama("http://localhost:11434")
    assert len(gaenge) == 1
    assert gaenge[0].gang == 1


# ---------------------------------------------------------------------------
# Tests: discover_openai_kompatibel
# ---------------------------------------------------------------------------

def test_discover_openai_kompatibel_gibt_ids_zurueck(monkeypatch):
    antwort = {"data": [{"id": "gpt-4o"}, {"id": "gpt-4o-mini"}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    ids = discover_openai_kompatibel("https://api.openai.com/v1", "sk-test")
    assert ids == ["gpt-4o", "gpt-4o-mini"]


def test_discover_openai_kompatibel_fehler(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_error_factory())
    assert discover_openai_kompatibel("http://nicht-da/v1", "key") == []


# ---------------------------------------------------------------------------
# Tests: parse_custom_models
# ---------------------------------------------------------------------------

BEISPIEL_CUSTOM = """\
name: mein-modell
provider: ollama
model_id: meins:7b
gang: 2
endpoint: http://localhost:11434
staerken: schnell, lokal

name: anderes-modell
provider: anthropic
model_id: claude-haiku-99
gang: 3
staerken: günstig, schnell
"""


def test_parse_custom_models_valide(tmp_path):
    """Valide Blöcke werden korrekt geparst."""
    datei = tmp_path / "custom_models.txt"
    datei.write_text(BEISPIEL_CUSTOM, encoding="utf-8")

    gaenge = parse_custom_models(datei)
    assert len(gaenge) == 2

    g1 = next(g for g in gaenge if g.name == "mein-modell")
    assert g1.provider == "ollama"
    assert g1.model_id == "meins:7b"
    assert g1.gang == 2
    assert g1.endpoint == "http://localhost:11434"
    assert "schnell" in g1.staerken
    assert "lokal" in g1.staerken

    g2 = next(g for g in gaenge if g.name == "anderes-modell")
    assert g2.provider == "anthropic"
    assert g2.gang == 3
    assert "günstig" in g2.staerken


def test_parse_custom_models_fehlerhafter_block_wird_uebersprungen(tmp_path):
    """Blöcke ohne Pflichtfelder werden übersprungen; valide Blöcke bleiben."""
    inhalt = """\
provider: ollama
model_id: irgendwas

name: guter-block
provider: ollama
model_id: gut:3b
gang: 2
"""
    datei = tmp_path / "custom_models.txt"
    datei.write_text(inhalt, encoding="utf-8")

    gaenge = parse_custom_models(datei)
    assert len(gaenge) == 1
    assert gaenge[0].name == "guter-block"


def test_parse_custom_models_datei_nicht_vorhanden(tmp_path):
    """Nicht vorhandene Datei → leere Liste, kein Crash."""
    gaenge = parse_custom_models(tmp_path / "nicht_vorhanden.txt")
    assert gaenge == []


def test_parse_custom_models_warnt_bei_fehlendem_pflichtfeld(tmp_path, caplog):
    """Bei fehlendem Pflichtfeld wird eine Warnung geloggt."""
    import logging

    inhalt = """\
provider: ollama
model_id: kein-name:7b
gang: 2
"""
    datei = tmp_path / "custom_models.txt"
    datei.write_text(inhalt, encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger="clutch.discovery"):
        gaenge = parse_custom_models(datei)

    assert gaenge == []
    assert any("Pflichtfelder" in rec.message or "übersprungen" in rec.message
               for rec in caplog.records)


# ---------------------------------------------------------------------------
# Tests: ModellDiscovery.entdecke_und_registriere
# ---------------------------------------------------------------------------

def _leeres_getriebe() -> Getriebe:
    """Getriebe ohne vorgeladene Config-Datei."""
    g = Getriebe.__new__(Getriebe)
    g._gaenge = {}
    g._provider = {}
    g._fahrer_optionen = {}
    return g


def test_entdecke_registriert_neue_gaenge(monkeypatch):
    """Neu entdeckte Gänge werden in das Getriebe eingetragen."""
    antwort = {"models": [{"name": "phi3:mini", "details": {"parameter_size": "3.8B"}}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    getriebe = _leeres_getriebe()
    discovery = ModellDiscovery()
    bericht = discovery.entdecke_und_registriere(getriebe, ollama_hosts=["http://localhost:11434"])

    assert "phi3:mini" in bericht["neu"]
    assert getriebe.gang("phi3:mini") is not None


def test_entdecke_ueberschreibt_nicht_bestehende(monkeypatch):
    """Bereits vorhandene Gänge werden NICHT überschrieben."""
    antwort = {"models": [{"name": "phi3:mini", "details": {"parameter_size": "70B"}}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    getriebe = _leeres_getriebe()
    # Vorhandenen Gang mit Gang-Stufe 2 eintragen
    vorhandener = Gang(
        name="phi3:mini",
        provider="ollama",
        model_id="phi3:mini",
        gang=2,
        leistung="basis",
        kosten_input_1k=0,
        kosten_output_1k=0,
    )
    getriebe.registriere_gang(vorhandener)

    discovery = ModellDiscovery()
    bericht = discovery.entdecke_und_registriere(getriebe, ollama_hosts=["http://localhost:11434"])

    # Der vorhandene Gang darf NICHT überschrieben werden (Gang-Stufe bleibt 2)
    assert "phi3:mini" in bericht["uebersprungen"]
    assert "phi3:mini" not in bericht["neu"]
    assert getriebe.gang("phi3:mini").gang == 2


def test_entdecke_metadaten_neu(monkeypatch):
    """Für neue Gänge werden Metadaten (discovered_at) gesetzt."""
    antwort = {"models": [{"name": "llama3:8b", "details": {"parameter_size": "8B"}}]}
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_get_factory(antwort))

    getriebe = _leeres_getriebe()
    discovery = ModellDiscovery()
    discovery.entdecke_und_registriere(getriebe, ollama_hosts=["http://localhost:11434"])

    assert "llama3:8b" in discovery.metadaten
    meta = discovery.metadaten["llama3:8b"]
    assert "discovered_at" in meta
    assert "last_verified" in meta
    # ISO-Format: enthält mindestens "T" als Trennzeichen
    assert "T" in meta["discovered_at"]


def test_entdecke_mit_custom_pfad(tmp_path, monkeypatch):
    """Custom-Modelle aus Datei werden ebenfalls registriert."""
    # Kein Ollama-Host → keine Netzwerkanfragen nötig
    datei = tmp_path / "custom.txt"
    datei.write_text(
        "name: lokal-test\nprovider: ollama\nmodel_id: lokal:3b\ngang: 2\n",
        encoding="utf-8",
    )

    getriebe = _leeres_getriebe()
    discovery = ModellDiscovery()
    bericht = discovery.entdecke_und_registriere(
        getriebe, ollama_hosts=[], custom_pfad=datei
    )

    assert "lokal-test" in bericht["neu"]
    assert getriebe.gang("lokal-test") is not None


def test_entdecke_host_nicht_erreichbar(monkeypatch):
    """Nicht erreichbarer Host → leerer Bericht, kein Crash."""
    monkeypatch.setitem(sys.modules, "requests", _fake_requests_error_factory())

    getriebe = _leeres_getriebe()
    discovery = ModellDiscovery()
    bericht = discovery.entdecke_und_registriere(
        getriebe, ollama_hosts=["http://nicht-da:11434"]
    )

    assert bericht["neu"] == []
    assert bericht["uebersprungen"] == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
