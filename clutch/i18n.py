"""i18n — Internationalisierung für clutch CLI.

Unterstützte Sprachen: en, de, es, zh, ja, ru.
Locale-Dateien liegen in clutch/locales/<lang>.json (paket-relativ).

Nutzung:
    from clutch.i18n import t, set_lang, get_lang

    set_lang("de")
    print(t("route.gang"))                    # "Gang"
    print(t("route.score", score=42))         # "Score:     42/100"
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

LANGS: list[str] = ["en", "de", "es", "zh", "ja", "ru"]
DEFAULT_LANG: str = "en"

_LOCALES_DIR: Path = Path(__file__).parent / "locales"

# ---------------------------------------------------------------------------
# Interner State
# ---------------------------------------------------------------------------

_current_lang: str | None = None          # explizit per set_lang() gesetzt
_cache: dict[str, dict[str, str]] = {}    # lang -> Wörterbuch


# ---------------------------------------------------------------------------
# Kern-API
# ---------------------------------------------------------------------------

def verfuegbare_sprachen() -> list[str]:
    """Gibt die Liste der unterstützten Sprach-Codes zurück."""
    return list(LANGS)


def set_lang(lang: str) -> None:
    """Setzt die aktuelle Sprache (Modul-State)."""
    global _current_lang
    _current_lang = lang


def get_lang() -> str:
    """Gibt die aktuell aktive Sprache zurück.

    Priorität: set_lang() > Env CLUTCH_LANG > DEFAULT_LANG.
    """
    if _current_lang is not None:
        return _current_lang
    env = os.environ.get("CLUTCH_LANG", "").strip()
    if env:
        return env
    return DEFAULT_LANG


def _lade_locale(lang: str) -> dict[str, str]:
    """Lädt und cached locales/<lang>.json. Gibt {} bei Fehler zurück."""
    if lang in _cache:
        return _cache[lang]
    pfad = _LOCALES_DIR / f"{lang}.json"
    try:
        with open(pfad, encoding="utf-8") as f:
            daten: dict[str, str] = json.load(f)
        _cache[lang] = daten
        return daten
    except Exception:
        _cache[lang] = {}
        return {}


def t(msg_key: str, lang: Optional[str] = None, **kwargs: object) -> str:
    """Gibt den übersetzten String für *msg_key* zurück.

    Priorität der Sprach-Auflösung:
      1. Explizites *lang*-Argument
      2. get_lang() (Modul-State oder CLUTCH_LANG-Env)
      3. DEFAULT_LANG ("en")

    Fallback-Kette: gewählte Sprache → "en" → *msg_key* selbst.
    Platzhalter: `{name}` werden via .format(**kwargs) befüllt.

    Hinweis: Der erste Parameter heißt *msg_key* (nicht *key*), damit
    Aufrufer `key=...` als Platzhalter-Argument übergeben können.
    """
    aufgeloeste_sprache = lang if lang is not None else get_lang()

    # Versuche gewählte Sprache
    locale = _lade_locale(aufgeloeste_sprache)
    wert = locale.get(msg_key)

    # Fallback: Englisch
    if wert is None and aufgeloeste_sprache != DEFAULT_LANG:
        en_locale = _lade_locale(DEFAULT_LANG)
        wert = en_locale.get(msg_key)

    # Letzter Fallback: msg_key selbst
    if wert is None:
        wert = msg_key

    # Platzhalter einsetzen
    if kwargs:
        try:
            wert = wert.format(**kwargs)
        except (KeyError, ValueError):
            pass  # Unformattierten Wert zurückgeben

    return wert
