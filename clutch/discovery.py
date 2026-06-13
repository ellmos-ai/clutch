"""Modell-Discovery -- automatisches Finden und Registrieren von LLM-Gängen.

Unterstützt:
  - Ollama-Instanzen (lokal oder remote) via GET /api/tags
  - OpenAI-kompatible Endpunkte via GET /models
  - Benutzerdefinierte Modelle aus einer Textdatei

Ein optionaler Remote-Ollama-Host kann über die Umgebungsvariable
CLUTCH_REMOTE_OLLAMA gesetzt werden (z.B. ein Host im eigenen VPN).
"""

from __future__ import annotations

import datetime
import logging
import os
import re
from pathlib import Path
from typing import Optional

from clutch.getriebe import Gang, Getriebe

logger = logging.getLogger("clutch.discovery")

# Optionaler Remote-Ollama-Host, konfigurierbar via Umgebungsvariable.
REMOTE_OLLAMA = os.environ.get("CLUTCH_REMOTE_OLLAMA", "")


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def gang_level_aus_groesse(groesse_str: str) -> int:
    """Leitet die Gang-Stufe (1–5) aus einer Parametergrößen-Angabe ab.

    Beispiele: "4b" → 2, "7B" → 2, "35b-a3b" → 3, "70B" → 4, "141b" → 5.
    Nimmt die erste Zahl im String; liefert 1 wenn keine Zahl gefunden.

    Schwellwerte:
      < 2B  → Gang 1
      < 8B  → Gang 2
      < 30B → Gang 3
      < 100B → Gang 4
      sonst → Gang 5
    """
    match = re.search(r"(\d+(?:\.\d+)?)", groesse_str or "")
    if not match:
        return 1
    wert = float(match.group(1))
    if wert < 2:
        return 1
    if wert < 8:
        return 2
    if wert < 30:
        return 3
    if wert < 100:
        return 4
    return 5


def _leistung_aus_gang(gang: int) -> str:
    """Gibt einen lesbaren Leistungsbegriff für eine Gang-Stufe zurück."""
    mapping = {1: "basis", 2: "basis", 3: "mittel", 4: "hoch", 5: "max"}
    return mapping.get(gang, "basis")


# ---------------------------------------------------------------------------
# Ollama-Discovery
# ---------------------------------------------------------------------------

def discover_ollama(base_url: str) -> list[Gang]:
    """Entdeckt alle lokal auf einem Ollama-Server laufenden Modelle.

    Ruft GET {base_url}/api/tags auf, parst models[].name und
    models[].details.parameter_size und erzeugt für jedes Modell einen Gang.

    Args:
        base_url: Basis-URL des Ollama-Servers, z.B. "http://localhost:11434".

    Returns:
        Liste von Gang-Objekten. Bei nicht erreichbarem Endpoint: leere Liste.
    """
    try:
        import requests  # lazy import -- kein hard-dependency auf Modulebene
        url = f"{base_url.rstrip('/')}/api/tags"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        daten = resp.json()
    except Exception as exc:
        logger.warning("Ollama-Discovery fehlgeschlagen (%s): %s", base_url, exc)
        return []

    gaenge: list[Gang] = []
    for modell in daten.get("models", []):
        name = modell.get("name", "")
        if not name:
            continue

        details = modell.get("details") or {}
        groesse_str = details.get("parameter_size", "")
        stufe = gang_level_aus_groesse(groesse_str)

        gang = Gang(
            name=name,
            provider="ollama",
            model_id=name,
            gang=stufe,
            leistung=_leistung_aus_gang(stufe),
            kosten_input_1k=0.0,
            kosten_output_1k=0.0,
            staerken=["unbewertet", "lokal"],
            schwaechen=[],
            endpoint=base_url,
        )
        gaenge.append(gang)

    return gaenge


# ---------------------------------------------------------------------------
# OpenAI-kompatibler Endpunkt
# ---------------------------------------------------------------------------

def discover_openai_kompatibel(base_url: str, api_key: str) -> list[str]:
    """Listet alle Modell-IDs eines OpenAI-kompatiblen Endpunkts auf.

    Ruft GET {base_url}/models mit Bearer-Authentifizierung auf und gibt
    data[].id zurück.

    Args:
        base_url: Basis-URL des Endpunkts (ohne abschließenden Slash).
        api_key:  Bearer-Token für den Authorization-Header.

    Returns:
        Liste von Modell-ID-Strings. Bei Fehler: leere Liste.
    """
    try:
        import requests
        url = f"{base_url.rstrip('/')}/models"
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        resp.raise_for_status()
        daten = resp.json()
        return [eintrag["id"] for eintrag in daten.get("data", []) if "id" in eintrag]
    except Exception as exc:
        logger.warning("OpenAI-Discovery fehlgeschlagen (%s): %s", base_url, exc)
        return []


# ---------------------------------------------------------------------------
# Benutzerdefinierte Modelle aus Textdatei
# ---------------------------------------------------------------------------

def parse_custom_models(pfad: Path) -> list[Gang]:
    """Parst eine einfache Textdatei mit benutzerdefinierten Modellblöcken.

    Format:
        Blöcke werden durch Leerzeilen getrennt. Jede Zeile hat die Form
        ``key: value``. Unterstützte Schlüssel:

        - name       (Pflichtfeld)
        - provider   (Pflichtfeld)
        - model_id   (Pflichtfeld)
        - gang       (Ganzzahl 1–5)
        - endpoint   (URL, optional)
        - staerken   (kommaseparierte Liste, optional)

    Fehlerhafte Blöcke werden übersprungen; eine Warnung wird geloggt.

    Args:
        pfad: Pfad zur Konfigurationsdatei.

    Returns:
        Liste erfolgreich geparster Gang-Objekte.
    """
    if not pfad.exists():
        logger.warning("custom_models-Datei nicht gefunden: %s", pfad)
        return []

    inhalt = pfad.read_text(encoding="utf-8")
    bloecke = re.split(r"\n{2,}", inhalt.strip())

    gaenge: list[Gang] = []
    for i, block in enumerate(bloecke):
        block = block.strip()
        if not block:
            continue

        cfg: dict[str, str] = {}
        for zeile in block.splitlines():
            zeile = zeile.strip()
            if not zeile or ":" not in zeile:
                continue
            schluessel, _, wert = zeile.partition(":")
            cfg[schluessel.strip().lower()] = wert.strip()

        # Pflichtfelder prüfen
        fehlend = [f for f in ("name", "provider", "model_id") if f not in cfg]
        if fehlend:
            logger.warning(
                "Modellblock %d übersprungen — Pflichtfelder fehlen: %s", i + 1, fehlend
            )
            continue

        # Gang-Stufe
        try:
            stufe = int(cfg.get("gang", "1"))
            if stufe < 1 or stufe > 5:
                raise ValueError(f"Ungültige Gang-Stufe: {stufe}")
        except (ValueError, TypeError) as exc:
            logger.warning("Modellblock %d übersprungen — ungültige gang-Angabe: %s", i + 1, exc)
            continue

        # Stärken
        staerken_raw = cfg.get("staerken", "")
        staerken = [s.strip() for s in staerken_raw.split(",") if s.strip()] if staerken_raw else []

        try:
            gang = Gang(
                name=cfg["name"],
                provider=cfg["provider"],
                model_id=cfg["model_id"],
                gang=stufe,
                leistung=_leistung_aus_gang(stufe),
                kosten_input_1k=0.0,
                kosten_output_1k=0.0,
                staerken=staerken,
                schwaechen=[],
                endpoint=cfg.get("endpoint"),
            )
            gaenge.append(gang)
        except Exception as exc:
            logger.warning("Modellblock %d übersprungen — Fehler beim Erstellen: %s", i + 1, exc)

    return gaenge


# ---------------------------------------------------------------------------
# ModellDiscovery-Klasse
# ---------------------------------------------------------------------------

class ModellDiscovery:
    """Orchestriert die Modell-Entdeckung und Registrierung im Getriebe.

    Hält Metadaten (Zeitstempel) für entdeckte Gänge in ``self.metadaten``.
    Das Gang-Objekt selbst bleibt unverändert.

    Beispiel::

        from clutch.getriebe import Getriebe
        from clutch.discovery import ModellDiscovery

        getriebe = Getriebe()
        discovery = ModellDiscovery()
        bericht = discovery.entdecke_und_registriere(getriebe)
        print(bericht)  # {"neu": [...], "uebersprungen": [...]}
    """

    def __init__(self):
        # name → {"discovered_at": iso-str, "last_verified": iso-str}
        self.metadaten: dict[str, dict[str, str]] = {}

    def entdecke_und_registriere(
        self,
        getriebe: Getriebe,
        ollama_hosts: Optional[list[str]] = None,
        custom_pfad: Optional[Path] = None,
    ) -> dict:
        """Entdeckt Modelle und registriert neue Gänge im Getriebe.

        Bestehende Gänge (nach Name) werden NICHT überschrieben.

        Args:
            getriebe:      Die Getriebe-Instanz, in der neue Gänge registriert werden.
            ollama_hosts:  Liste von Ollama-Basis-URLs.
                           Standard: ["http://localhost:11434"]
            custom_pfad:   Optionaler Pfad zur custom_models.txt.

        Returns:
            dict mit den Schlüsseln "neu" (Liste neuer Namen) und
            "uebersprungen" (bereits vorhandene Namen).
        """
        if ollama_hosts is None:
            ollama_hosts = ["http://localhost:11434"]

        kandidaten: list[Gang] = []

        # Ollama-Hosts abfragen
        for host in ollama_hosts:
            kandidaten.extend(discover_ollama(host))

        # Benutzerdefinierte Modelle laden
        if custom_pfad is not None:
            kandidaten.extend(parse_custom_models(custom_pfad))

        neu: list[str] = []
        uebersprungen: list[str] = []
        jetzt = datetime.datetime.now().isoformat()

        for gang in kandidaten:
            if getriebe.gang(gang.name) is not None:
                # Bereits vorhanden -- Zeitstempel aktualisieren, aber nicht überschreiben
                if gang.name in self.metadaten:
                    self.metadaten[gang.name]["last_verified"] = jetzt
                uebersprungen.append(gang.name)
            else:
                getriebe.registriere_gang(gang)
                self.metadaten[gang.name] = {
                    "discovered_at": jetzt,
                    "last_verified": jetzt,
                }
                neu.append(gang.name)

        logger.info(
            "Discovery abgeschlossen: %d neu registriert, %d übersprungen.",
            len(neu),
            len(uebersprungen),
        )
        return {"neu": neu, "uebersprungen": uebersprungen}
