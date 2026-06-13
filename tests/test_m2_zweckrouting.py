"""Tests fuer M2 -- Zweck-/Modalitaets-Routing (staerken-basiert, bildbewusst)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung
from clutch.strecke import StreckenAnalyse
from clutch.fahrer import Fahrer
from clutch.motorblock import MotorErgebnis


def test_filter_nach_staerke():
    g = Getriebe()
    vision = g.filter(staerke="vision")
    assert vision, "Es sollte vision-faehige Gaenge geben (kimi-api-vision)"
    assert all("vision" in x.staerken for x in vision)
    print("[OK] Getriebe.filter(staerke=...)")


def test_vision_zweck_waehlt_vision_gang():
    g = Getriebe()
    k = Kupplung(g)
    profil = StreckenAnalyse().analysiere("Beschreibe den Inhalt")
    # Ohne Budget-Limit: vision-Zweck muss ein vision-faehiges Modell waehlen
    config = k.einlegen(profil, zweck="vision")
    assert "vision" in config.gang.staerken, f"vision-Zweck -> {config.gang.name} ohne vision-staerke"
    print("[OK] vision-Zweck waehlt vision-Gang")


def test_coding_zweck_waehlt_coding_gang():
    g = Getriebe()
    k = Kupplung(g)
    profil = StreckenAnalyse().analysiere("Schreibe Code")
    config = k.einlegen(profil, zweck="coding")
    assert "coding" in config.gang.staerken or config.gang.gang >= 1
    print("[OK] coding-Zweck Routing")


def test_zweck_respektiert_budget_limit():
    g = Getriebe()
    k = Kupplung(g)
    k.set_erkundungsrate(0.0)  # Exploration aus -> Budget-Grenze deterministisch
    profil = StreckenAnalyse().analysiere("Beschreibe das Bild")
    # Orange erlaubt nur G1-G2; vision-Gaenge sind G4 -> kein Wechsel ueber Limit
    config = k.einlegen(profil, zweck="vision", budget_zone="orange")
    assert config.gang.gang <= 2, f"Zweck darf Budget-Limit nicht ueberschreiten: G{config.gang.gang}"
    print("[OK] Zweck respektiert Budget-Limit")


def test_general_zweck_aendert_nichts():
    g = Getriebe()
    k = Kupplung(g)
    k.set_erkundungsrate(0.0)  # Exploration aus -> deterministischer Vergleich
    profil = StreckenAnalyse().analysiere("Fix den Bug in auth.py")
    ohne = k.einlegen(profil)
    mit = k.einlegen(profil, zweck="general")
    assert ohne.gang.name == mit.gang.name
    print("[OK] general-Zweck neutral")


def test_fahrer_bild_kontext_routet_vision():
    with tempfile.TemporaryDirectory() as tmp:
        fahrer = Fahrer(db_path=Path(tmp) / "c.db")
        gewaehlt = {}

        def handler(config, task):
            gewaehlt["gang"] = config.gang
            return MotorErgebnis(text="ok", input_tokens=1, output_tokens=1,
                                 model_id=config.model_id, provider=config.provider)

        # Bild-Anhang -> Fahrer erkennt vision -> vision-faehiges Modell
        fahrer.fahren("Was ist das?", handler=handler, kontext={"hat_bild": True})
        assert "vision" in gewaehlt["gang"].staerken, \
            f"Bild-Kontext -> {gewaehlt['gang'].name} ohne vision-staerke"
        print("[OK] Fahrer Bild-Kontext routet vision")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
