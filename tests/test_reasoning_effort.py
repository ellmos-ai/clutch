"""Reasoning-Effort ist orthogonal zu Modell/Gas und pro Aufruf überschreibbar."""

import json

import pytest

from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung
from clutch.strecke import StreckenProfil, StreckenTyp, Tempo


def _profil(typ: StreckenTyp) -> StreckenProfil:
    return StreckenProfil(
        typ=typ,
        tempo=Tempo.NORMAL,
        schwierigkeit=0.5,
    )


def test_effort_kommt_aus_der_task_klasse():
    kupplung = Kupplung(Getriebe())

    routine = kupplung.einlegen(_profil(StreckenTyp.FELDWEG))
    review = kupplung.einlegen(_profil(StreckenTyp.PRUEFSTRECKE))

    assert routine.effort == "high"
    assert review.effort == "max-delegate"
    assert review.to_dict()["effort"] == "max-delegate"


def test_effort_override_gilt_nur_fuer_den_aufruf():
    kupplung = Kupplung(Getriebe())
    profil = _profil(StreckenTyp.LANDSTRASSE)

    assert kupplung.einlegen(profil).effort == "xhigh"
    assert kupplung.einlegen(profil, effort_override="HIGH").effort == "high"
    assert kupplung.einlegen(profil).effort == "xhigh"


def test_effort_bleibt_fuer_alte_configs_optional(tmp_path):
    (tmp_path / "strecken.json").write_text(
        json.dumps({
            "strecken": {
                "feldweg": {
                    "gang": "claude-haiku",
                    "gas": 0.3,
                    "muster": "einzelfahrt",
                }
            },
            "standard": {
                "gang": "claude-sonnet",
                "gas": 0.5,
                "muster": "einzelfahrt",
            },
            "erkundungsrate": 0,
        }),
        encoding="utf-8",
    )
    kupplung = Kupplung(Getriebe(), config_dir=tmp_path)

    assert kupplung.einlegen(_profil(StreckenTyp.FELDWEG)).effort is None


def test_ungueltiger_effort_wird_nicht_still_akzeptiert():
    kupplung = Kupplung(Getriebe())

    with pytest.raises(ValueError, match="ungueltiger effort"):
        kupplung.einlegen(
            _profil(StreckenTyp.LANDSTRASSE),
            effort_override="ultracode",
        )
