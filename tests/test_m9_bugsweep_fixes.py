"""Regressionstests fuer die Phase-9-/bugsweep-Fixes (Sicherheit + Korrektheit)."""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.partner import zone_nummer
from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung, AGENTIC_CLI_PROVIDERS
from clutch.strecke import StreckenAnalyse
from clutch.prompt_library import PromptLibrary, PromptItem


def test_zone_nummer_failsafe_restriktiv():
    # Unbekannte Zone -> restriktivste (4 = nur Mensch), NICHT offenste (1)
    assert zone_nummer("gelb") == 4
    assert zone_nummer("unbekannt") == 4
    assert zone_nummer("green") == 1 and zone_nummer("red") == 4
    print("[OK] zone_nummer fail-safe restriktiv")


def test_untrusted_schliesst_agentische_cli_aus():
    g = Getriebe()
    k = Kupplung(g)
    # Erzwinge die Wahl eines agentischen CLI-Gangs via Override
    k.override("bundesstrasse", {"gang": "claude-code", "gas": 0.5, "muster": "einzelfahrt"})
    profil = StreckenAnalyse().analysiere("Fix den Bug in auth.py")
    # vertrauenswuerdig=True: darf claude-code sein
    vertraut = k.einlegen(profil, vertrauenswuerdig=True)
    # vertrauenswuerdig=False: KEIN agentischer CLI-Provider
    untrusted = k.einlegen(profil, vertrauenswuerdig=False)
    assert untrusted.gang.provider not in AGENTIC_CLI_PROVIDERS, \
        f"untrusted waehlte agentische CLI: {untrusted.gang.name}"
    print(f"[OK] untrusted schliesst agentische CLI aus (vertraut={vertraut.gang.name})")


def test_vision_warnung_wenn_kein_vision_modell():
    g = Getriebe()
    k = Kupplung(g)
    # Alle vision-faehigen Gaenge sperren -> Warnung im Grund, kein vision-Gang
    vision_gaenge = [x.name for x in g.filter(staerke="vision")]
    profil = StreckenAnalyse().analysiere("Beschreibe das Bild")
    config = k.einlegen(profil, zweck="vision", gesperrte_modelle=vision_gaenge)
    assert "vision" not in config.gang.staerken
    assert "kein vision-Modell" in config.entscheidungs_grund
    print("[OK] Vision-Warnung wenn kein Vision-Modell verfuegbar")


def test_prompt_suche_like_escape():
    with tempfile.TemporaryDirectory() as tmp:
        lib = PromptLibrary(db_path=Path(tmp) / "c.db")
        lib.upsert(PromptItem(id="", typ="prompt", name="Rabatt", content="50% sparen"))
        lib.upsert(PromptItem(id="", typ="prompt", name="Andere", content="nichts"))
        # "%" darf NICHT als Wildcard wirken -> nur der echte Treffer
        treffer = lib.liste(suche="50%")
        assert len(treffer) == 1 and treffer[0].name == "Rabatt"
        # "_" ebenfalls literal
        assert lib.liste(suche="x_y") == []
        print("[OK] LIKE-Escape in Prompt-Suche")


def test_import_promptboard_robust():
    with tempfile.TemporaryDirectory() as tmp:
        lib = PromptLibrary(db_path=Path(tmp) / "c.db")
        # Fehlende Datei -> 0, kein Crash
        assert lib.import_promptboard(Path(tmp) / "gibtsnicht.json") == 0
        # Kaputtes JSON -> 0, kein Crash
        kaputt = Path(tmp) / "kaputt.json"
        kaputt.write_text("{ das ist kein json", encoding="utf-8")
        assert lib.import_promptboard(kaputt) == 0
        # Gueltiges JSON -> importiert
        gut = Path(tmp) / "lib.json"
        gut.write_text(json.dumps({"items": [
            {"item_type": "PROMPT", "name": "A", "content": "x"},
        ]}), encoding="utf-8")
        assert lib.import_promptboard(gut) == 1
        print("[OK] import_promptboard robust")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
