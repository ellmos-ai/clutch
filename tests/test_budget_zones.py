"""Vertragstests fuer die gemeinsame Budgetzonen-Policy."""

from __future__ import annotations

import json

import pytest

from clutch import BudgetErschoepftError
from clutch.bordcomputer import Bordcomputer
from clutch.fahrtenbuch import Fahrtenbuch
from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung
from clutch.strecke import StreckenAnalyse


STANDARD_ZONES = {
    "green": {"min_pct": 0, "max_pct": 30, "allowed_tiers": [1, 2, 3, 4, 5]},
    "yellow": {"min_pct": 30, "max_pct": 60, "allowed_tiers": [1, 2, 3]},
    "orange": {"min_pct": 60, "max_pct": 80, "allowed_tiers": [1, 2]},
    "red": {"min_pct": 80, "max_pct": 100, "allowed_tiers": []},
}


def _write_policy(config_dir, zones):
    config_dir.mkdir()
    (config_dir / "fitness_criteria.json").write_text(
        json.dumps({"anomaly_thresholds": {}, "budget_zones": zones}),
        encoding="utf-8",
    )


def _profil():
    return StreckenAnalyse().analysiere(
        "Entwirf eine komplexe Architektur fuer mehrere gekoppelte Systeme"
    )


def test_paketpolicy_entspricht_dokumentiertem_budgetvertrag(tmp_path):
    bordcomputer = Bordcomputer(Fahrtenbuch(db_path=tmp_path / "fahrten.db"))

    assert {
        zone: bordcomputer.max_gang_fuer_zone(zone)
        for zone in ("green", "yellow", "orange", "red")
    } == {"green": 5, "yellow": 3, "orange": 2, "red": 0}


def test_json_policy_steuert_bordcomputer_und_kupplung(tmp_path):
    zones = {name: dict(config) for name, config in STANDARD_ZONES.items()}
    zones["orange"]["allowed_tiers"] = [1]
    config_dir = tmp_path / "config"
    _write_policy(config_dir, zones)

    bordcomputer = Bordcomputer(
        Fahrtenbuch(db_path=tmp_path / "fahrten.db"),
        config_dir=config_dir,
    )
    kupplung = Kupplung(Getriebe(), config_dir=config_dir)
    kupplung.set_erkundungsrate(0)

    assert bordcomputer.max_gang_fuer_zone("orange") == 1
    assert kupplung.einlegen(_profil(), budget_zone="orange").gang.gang == 1


def test_undokumentierte_fitness_json_wird_ignoriert(tmp_path):
    config_dir = tmp_path / "config"
    _write_policy(config_dir, STANDARD_ZONES)
    (config_dir / "fitness.json").write_text(
        json.dumps(
            {
                "anomaly_thresholds": {"overkill_score": 999},
                "budget_zones": {
                    **STANDARD_ZONES,
                    "orange": {
                        "min_pct": 60,
                        "max_pct": 80,
                        "allowed_tiers": [1],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    bordcomputer = Bordcomputer(
        Fahrtenbuch(db_path=tmp_path / "fahrten.db"),
        config_dir=config_dir,
    )

    assert bordcomputer.overkill_schwelle == 5.0
    assert bordcomputer.max_gang_fuer_zone("orange") == 2


def test_rote_budgetzone_verhindert_routing():
    kupplung = Kupplung(Getriebe())
    kupplung.set_erkundungsrate(0)

    with pytest.raises(BudgetErschoepftError, match="(?i)budget.*(rot|red)"):
        kupplung.einlegen(_profil(), budget_zone="red")
