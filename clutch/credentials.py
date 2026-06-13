"""Credentials -- lokaler API-Key-Speicher mit Env-Vorrang.

Loest Keys bei Bedarf auf, ohne sie staendig als Umgebungsvariable setzen zu
muessen. Aufloesungs-Reihenfolge (erste nicht-leere gewinnt):

  1. Umgebungsvariable (z.B. MOONSHOT_API_KEY)            -- hoechste Prioritaet
  2. clutch-Store  ~/.clutch/credentials.json            -- via `clutch keys set`
  3. BACH-kompatible Datei ~/.credentials/<name.lower()> -- Interop mit BACH

Keys werden NICHT verschluesselt (zero-dependency, wie ~/.npmrc / ~/.netrc).
Die Datei wird best-effort auf Nutzer-Lese-/Schreibrechte (0600) beschraenkt.
Env-Variablen bleiben der empfohlene Weg fuer CI/Server.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Optional


def _store_pfad() -> Path:
    return Path.home() / ".clutch" / "credentials.json"


class CredentialStore:
    """Liest/schreibt API-Keys in ~/.clutch/credentials.json."""

    def __init__(self, pfad: Optional[Path] = None):
        self.pfad = Path(pfad) if pfad else _store_pfad()

    def _laden(self) -> dict:
        if not self.pfad.exists():
            return {}
        try:
            data = json.loads(self.pfad.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _speichern(self, data: dict) -> None:
        self.pfad.parent.mkdir(parents=True, exist_ok=True)
        self.pfad.write_text(json.dumps(data, indent=2), encoding="utf-8")
        # Best-effort Rechte einschraenken (nur Eigentuemer lesen/schreiben).
        try:
            os.chmod(self.pfad, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass  # Windows / FS ohne POSIX-Rechte -- ignorieren

    def get(self, name: str) -> Optional[str]:
        wert = self._laden().get(name)
        return wert or None

    def set(self, name: str, wert: str) -> None:
        data = self._laden()
        data[name] = wert
        self._speichern(data)

    def remove(self, name: str) -> bool:
        data = self._laden()
        if name in data:
            del data[name]
            self._speichern(data)
            return True
        return False

    def namen(self) -> list[str]:
        """Nur die Key-Namen (NIEMALS die Werte) -- fuer Anzeige."""
        return sorted(self._laden().keys())


def _bach_kompat_datei(env_var: str) -> Optional[str]:
    """Liest einen Key aus BACHs ~/.credentials/<name.lower()> (Interop)."""
    pfad = Path.home() / ".credentials" / env_var.lower()
    try:
        if pfad.exists():
            wert = pfad.read_text(encoding="utf-8").strip()
            return wert or None
    except OSError:
        pass
    return None


def get_api_key(env_var: str, store: Optional[CredentialStore] = None) -> str:
    """Loest einen API-Key auf: Env -> clutch-Store -> BACH-Datei -> ''."""
    aus_env = os.environ.get(env_var)
    if aus_env:
        return aus_env
    store = store or CredentialStore()
    aus_store = store.get(env_var)
    if aus_store:
        return aus_store
    aus_bach = _bach_kompat_datei(env_var)
    if aus_bach:
        return aus_bach
    return ""
