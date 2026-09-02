"""Update-feste Nutzer-Overrides fuer den gebuendelten Modellkatalog."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Optional


DEFAULT_OVERRIDES: dict[str, Any] = {
    "disabled_models": [],
    "preferred_models": [],
    "preferred_providers": [],
    "model_max_gang": {},
    "aliases": {},
    "model_cost_override": {},
}


def clutch_home() -> Path:
    """Runtime-Verzeichnis; CLUTCH_HOME ermoeglicht isolierte Tests/Deployments."""
    override = os.environ.get("CLUTCH_HOME")
    return Path(override).expanduser() if override else Path.home() / ".clutch"


def user_overrides_path() -> Path:
    return clutch_home() / "user_overrides.json"


def _normalisiere_liste(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip() and item.strip() not in result:
            result.append(item.strip())
    return result


def normalisiere_overrides(data: Any) -> dict[str, Any]:
    """Validiert bekannte Felder und verwirft unbekannte Daten nicht."""
    source = data if isinstance(data, dict) else {}
    result = dict(source)
    result["disabled_models"] = _normalisiere_liste(source.get("disabled_models"))
    result["preferred_models"] = _normalisiere_liste(source.get("preferred_models"))
    result["preferred_providers"] = _normalisiere_liste(source.get("preferred_providers"))
    for key in ("model_max_gang", "aliases", "model_cost_override"):
        result[key] = source.get(key) if isinstance(source.get(key), dict) else {}
    return result


def lade_user_overrides(path: Optional[Path] = None) -> dict[str, Any]:
    path = Path(path) if path is not None else user_overrides_path()
    if not path.exists():
        return normalisiere_overrides({})
    try:
        with path.open("r", encoding="utf-8") as handle:
            return normalisiere_overrides(json.load(handle))
    except (OSError, json.JSONDecodeError):
        # Eine kaputte Nutzerdatei wird nie ueberschrieben oder als leer gespeichert.
        return normalisiere_overrides({})


def _lade_mutierbar(path: Optional[Path]) -> dict[str, Any]:
    target = Path(path) if path is not None else user_overrides_path()
    if not target.exists():
        return normalisiere_overrides({})
    try:
        with target.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Nutzer-Overlay ist unlesbar und wird nicht ueberschrieben: {target}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Nutzer-Overlay muss ein JSON-Objekt sein: {target}")
    return normalisiere_overrides(value)


def speichere_user_overrides(data: dict[str, Any], path: Optional[Path] = None) -> Path:
    """Schreibt atomar mit restriktiven Rechten; nur fuer explizite CLI-Mutationen."""
    path = Path(path) if path is not None else user_overrides_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except OSError:
        pass
    text = json.dumps(normalisiere_overrides(data), ensure_ascii=False, indent=2) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        try:
            os.chmod(tmp_name, 0o600)
        except OSError:
            pass
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_name, path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path


def setze_modell_aktiv(name: str, aktiv: bool, path: Optional[Path] = None) -> dict[str, Any]:
    data = _lade_mutierbar(path)
    disabled = data["disabled_models"]
    if aktiv:
        data["disabled_models"] = [item for item in disabled if item != name]
    elif name not in disabled:
        disabled.append(name)
    speichere_user_overrides(data, path)
    return data


def setze_praeferenz(name: str, provider: bool, path: Optional[Path] = None) -> dict[str, Any]:
    data = _lade_mutierbar(path)
    key = "preferred_providers" if provider else "preferred_models"
    values = [item for item in data[key] if item != name]
    data[key] = [name, *values]
    speichere_user_overrides(data, path)
    return data
