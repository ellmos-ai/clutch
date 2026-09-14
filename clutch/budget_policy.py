"""Gemeinsame Budgetzonen-Policy fuer Routing und Systemstatus."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping


STANDARD_BUDGET_ZONEN = {
    "green": {"min_pct": 0, "max_pct": 30, "allowed_tiers": [1, 2, 3, 4, 5]},
    "yellow": {"min_pct": 30, "max_pct": 60, "allowed_tiers": [1, 2, 3]},
    "orange": {"min_pct": 60, "max_pct": 80, "allowed_tiers": [1, 2]},
    "red": {"min_pct": 80, "max_pct": 100, "allowed_tiers": []},
}


class BudgetErschoepftError(RuntimeError):
    """Die aktive Budgetzone erlaubt keinen LLM-Einsatz."""


def lade_fitness_kriterien(config_dir: Path) -> dict[str, Any]:
    """Laedt die dokumentierte Fitness-Konfiguration.

    ``fitness_criteria.json`` ist die einzige Konfigurationsquelle. Fehlt sie,
    greifen die eingebauten Defaults; eine vorhandene, aber strukturell
    ungueltige Datei wird nicht stillschweigend akzeptiert.
    """
    path = Path(config_dir) / "fitness_criteria.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("fitness_criteria.json muss ein JSON-Objekt enthalten")
    return data


def budget_zonen_aus_kriterien(
    criteria: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Liefert eine validierte Kopie der vier Budgetzonen."""
    raw = criteria.get("budget_zones")
    if raw is None:
        return deepcopy(STANDARD_BUDGET_ZONEN)
    if not isinstance(raw, Mapping):
        raise ValueError("budget_zones muss ein JSON-Objekt sein")

    zones: dict[str, dict[str, Any]] = {}
    for name in STANDARD_BUDGET_ZONEN:
        config = raw.get(name)
        if not isinstance(config, Mapping):
            raise ValueError(f"Budgetzone {name!r} fehlt oder ist ungueltig")
        tiers = config.get("allowed_tiers")
        min_pct = config.get("min_pct")
        max_pct = config.get("max_pct")
        if (
            not isinstance(tiers, list)
            or any(isinstance(tier, bool) or not isinstance(tier, int) for tier in tiers)
            or any(tier < 1 or tier > 5 for tier in tiers)
            or tiers != sorted(set(tiers))
        ):
            raise ValueError(f"allowed_tiers der Budgetzone {name!r} ist ungueltig")
        if (
            isinstance(min_pct, bool)
            or isinstance(max_pct, bool)
            or not isinstance(min_pct, (int, float))
            or not isinstance(max_pct, (int, float))
            or not 0 <= min_pct <= max_pct <= 100
        ):
            raise ValueError(f"Prozentgrenzen der Budgetzone {name!r} sind ungueltig")
        zones[name] = {
            "min_pct": min_pct,
            "max_pct": max_pct,
            "allowed_tiers": list(tiers),
        }
    return zones


def lade_budget_zonen(config_dir: Path) -> dict[str, dict[str, Any]]:
    """Laedt die Budgetzonen aus der kanonischen Fitness-Konfiguration."""
    return budget_zonen_aus_kriterien(lade_fitness_kriterien(config_dir))


def max_gang_fuer_zone(
    zones: Mapping[str, Mapping[str, Any]],
    zone: str,
) -> int:
    """Ermittelt den hoechsten erlaubten Gang; unbekannte Zonen bleiben kompatibel."""
    config = zones.get(zone)
    if config is None:
        return 5
    tiers = config.get("allowed_tiers", [1, 2, 3, 4, 5])
    return max(tiers) if tiers else 0
