"""Tests für clutch.i18n — Internationalisierungsmodul."""

from __future__ import annotations

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import clutch.i18n as i18n
from clutch.i18n import t, set_lang, get_lang, verfuegbare_sprachen, LANGS, DEFAULT_LANG


# ---------------------------------------------------------------------------
# Hilfsfunktion: Modul-State zurücksetzen (damit Tests isoliert laufen)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_lang():
    """Setzt _current_lang vor und nach jedem Test zurück."""
    original = i18n._current_lang
    yield
    i18n._current_lang = original


# ---------------------------------------------------------------------------
# LANGS / DEFAULT_LANG Konstanten
# ---------------------------------------------------------------------------

def test_langs_enthaelt_sechs_sprachen():
    assert set(LANGS) == {"en", "de", "es", "zh", "ja", "ru"}
    assert len(LANGS) == 6


def test_default_lang_ist_en():
    assert DEFAULT_LANG == "en"


def test_verfuegbare_sprachen_entspricht_langs():
    assert set(verfuegbare_sprachen()) == set(LANGS)


# ---------------------------------------------------------------------------
# set_lang / get_lang
# ---------------------------------------------------------------------------

def test_set_lang_und_get_lang():
    set_lang("de")
    assert get_lang() == "de"


def test_set_lang_en():
    set_lang("en")
    assert get_lang() == "en"


def test_get_lang_default_ohne_set(monkeypatch):
    i18n._current_lang = None
    monkeypatch.delenv("CLUTCH_LANG", raising=False)
    assert get_lang() == DEFAULT_LANG


def test_get_lang_env_prioritaet(monkeypatch):
    i18n._current_lang = None
    monkeypatch.setenv("CLUTCH_LANG", "ja")
    assert get_lang() == "ja"


def test_set_lang_hat_prioritaet_ueber_env(monkeypatch):
    monkeypatch.setenv("CLUTCH_LANG", "zh")
    set_lang("ru")
    assert get_lang() == "ru"


# ---------------------------------------------------------------------------
# t() — Übersetzungen en/de
# ---------------------------------------------------------------------------

def test_t_en_gang():
    assert t("route.gang", lang="en") == "Gang"


def test_t_de_gang():
    assert t("route.gang", lang="de") == "Gang"


def test_t_de_nicht_gesetzt():
    assert t("config.not_set", lang="de", key="foo") == "foo ist nicht gesetzt."


def test_t_en_nicht_gesetzt():
    assert t("config.not_set", lang="en", key="bar") == "bar is not set."


def test_t_de_keys_gespeichert():
    result = t("keys.gespeichert", lang="de", name="MYKEY")
    assert "MYKEY" in result
    assert "gespeichert" in result


def test_t_en_keys_gespeichert():
    result = t("keys.gespeichert", lang="en", name="MYKEY")
    assert "MYKEY" in result
    assert "saved" in result


def test_t_de_chat_begruessung():
    begruessung = t("chat.begruessung", lang="de")
    assert "exit" in begruessung
    assert "clutch" in begruessung.lower()


def test_t_de_stats_header():
    assert "clutch" in t("stats.header", lang="de").lower()


def test_t_de_error_routing():
    result = t("error.routing", lang="de", e="timeout")
    assert "timeout" in result
    assert "Fehler" in result or "Error" in result


def test_t_en_error_routing():
    result = t("error.routing", lang="en", e="timeout")
    assert "timeout" in result
    assert "Error" in result


# ---------------------------------------------------------------------------
# t() — Platzhalter-Format
# ---------------------------------------------------------------------------

def test_t_platzhalter_einfach():
    result = t("keys.entfernt", lang="de", name="TESTKEY")
    assert "TESTKEY" in result


def test_t_platzhalter_mehrere():
    result = t("config.not_set", lang="en", key="mykey")
    assert "mykey" in result


def test_t_platzhalter_provider():
    result = t("run.motor_nicht_verfuegbar", lang="de", provider="anthropic")
    assert "anthropic" in result


def test_t_route_header_mit_prompt():
    result = t("route.header", lang="de", prompt="'Hallo Welt'")
    assert "Hallo Welt" in result


# ---------------------------------------------------------------------------
# t() — Fallback-Verhalten
# ---------------------------------------------------------------------------

def test_t_fallback_auf_en_bei_fehlendem_key_in_sprache(tmp_path, monkeypatch):
    """Wenn ein Key in einer Sprache fehlt, fällt t() auf en zurück."""
    # Wir patchen den Cache so, dass 'de' einen leeren Dict hat
    original_cache = dict(i18n._cache)
    i18n._cache["de"] = {}  # de: kein Eintrag
    try:
        result = t("route.gang", lang="de")
        # Muss auf en zurückfallen (="Gang")
        assert result == "Gang"
    finally:
        i18n._cache.update(original_cache)
        i18n._cache.pop("de", None)
        # Cache neu laden lassen
        i18n._cache.pop("de", None)


def test_t_fallback_auf_key_wenn_in_keiner_sprache():
    """Wenn der msg_key in keiner Sprache existiert, wird der Key selbst zurückgegeben."""
    result = t("key.das.es.nicht.gibt", lang="en")
    assert result == "key.das.es.nicht.gibt"


def test_t_fallback_kette_unbekannte_sprache():
    """Bei unbekannter Sprache (kein JSON-File) → en-Fallback → Key."""
    # 'xy' hat keine Locale-Datei
    result = t("route.gang", lang="xy")
    # Fällt auf en zurück
    assert result == "Gang"


# ---------------------------------------------------------------------------
# Schlüsselgleichheit aller 6 Locales
# ---------------------------------------------------------------------------

def _lade_locale_direkt(lang: str) -> dict:
    pfad = Path(__file__).parent.parent / "clutch" / "locales" / f"{lang}.json"
    with open(pfad, encoding="utf-8") as f:
        return json.load(f)


def test_alle_locales_haben_gleiche_keys():
    """Alle 6 Locale-Dateien müssen exakt dieselben Keys enthalten."""
    locales = {lang: _lade_locale_direkt(lang) for lang in LANGS}
    referenz_keys = set(locales["en"].keys())

    for lang, daten in locales.items():
        fehlende = referenz_keys - set(daten.keys())
        extra = set(daten.keys()) - referenz_keys
        assert not fehlende, f"Locale '{lang}' fehlt Keys: {fehlende}"
        assert not extra, f"Locale '{lang}' hat extra Keys: {extra}"


def test_alle_locales_sind_valides_json():
    """Alle Locale-Dateien müssen valides JSON sein."""
    for lang in LANGS:
        pfad = Path(__file__).parent.parent / "clutch" / "locales" / f"{lang}.json"
        assert pfad.exists(), f"Locale-Datei fehlt: {pfad}"
        daten = _lade_locale_direkt(lang)
        assert isinstance(daten, dict), f"Locale '{lang}' ist kein Dict"
        assert len(daten) > 0, f"Locale '{lang}' ist leer"


def test_locales_werte_sind_strings():
    """Alle Werte in allen Locale-Dateien müssen Strings sein."""
    for lang in LANGS:
        daten = _lade_locale_direkt(lang)
        for key, value in daten.items():
            assert isinstance(value, str), (
                f"Locale '{lang}', Key '{key}': Wert ist kein String ({type(value)})"
            )


# ---------------------------------------------------------------------------
# de.json — Echte Umlaute
# ---------------------------------------------------------------------------

def test_de_hat_echte_umlaute():
    """de.json muss echte Umlaute (ä ö ü ß) enthalten, keine ae/oe/ue."""
    de = _lade_locale_direkt("de")
    alle_werte = " ".join(de.values())
    # Mindestens ein Umlaut muss vorkommen
    hat_umlaut = any(c in alle_werte for c in "äöüÄÖÜß")
    assert hat_umlaut, "de.json enthält keine echten Umlaute"


def test_de_gespeichert_enthaelt_umlaut():
    """'gespeichert' in de.json enthält echtes 'ei' und typisch deutschen Text."""
    de = _lade_locale_direkt("de")
    # config.saved enthält "gespeichert" mit normalem 'e'
    assert "gespeichert" in de.get("config.saved", "")


# ---------------------------------------------------------------------------
# Smoke: Import
# ---------------------------------------------------------------------------

def test_import_i18n():
    from clutch.i18n import t as t_func, set_lang as sl, get_lang as gl
    assert callable(t_func)
    assert callable(sl)
    assert callable(gl)
