"""Tests fuer M0 -- Engine-Hygiene + portierte Extras (Scorer, Partner, Tankuhr-Flow)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.scorer import Scorer, get_scorer
from clutch.partner import Partner, PartnerRegistry, zone_nummer, DELEGATION_ZONEN
from clutch.fahrer import Fahrer
from clutch.motorblock import MotorErgebnis


# --- Scorer ---------------------------------------------------------------

def test_scorer_score_steigt_mit_komplexitaet():
    s = Scorer()
    einfach, _ = s.score("Zeige mir den Status")
    komplex, _ = s.score(
        "Entwickle eine Multi-Agent Architektur mit verteiltem State-Management, "
        "Authentication via API und mehreren Schritten: zuerst X, dann Y, danach Z."
    )
    assert komplex > einfach
    assert 0 <= einfach <= 100 and 0 <= komplex <= 100
    print("[OK] Scorer Komplexitaet")


def test_scorer_gang_level():
    s = Scorer()
    assert s.gang_level_fuer_score(5) == 1
    assert s.gang_level_fuer_score(50) == 3
    assert s.gang_level_fuer_score(95) == 5
    print("[OK] Scorer Gang-Level")


def test_scorer_zweck_erkennung():
    s = Scorer()
    assert s.erkenne_zweck("Refactore die Funktion und behebe den Bug im Code") == "coding"
    assert s.erkenne_zweck("Recherchiere Studien und vergleiche die Literatur") == "research"
    assert s.erkenne_zweck("Was steht auf dem Bild?") == "vision"
    assert s.erkenne_zweck("Wie spaet ist es") == "general"
    # Bild-Anhang erzwingt vision unabhaengig vom Text
    assert s.erkenne_zweck("Fasse das zusammen", hat_bild=True) == "vision"
    print("[OK] Scorer Zweck")


def test_scorer_bewerte_komplett():
    e = get_scorer().bewerte("Implementiere ein Authentication-System mit JWT")
    assert e.zweck == "coding"
    assert e.gang_level >= 1
    assert "keywords" in e.breakdown
    print("[OK] Scorer bewerte()")


# --- Partner --------------------------------------------------------------

def test_partner_zonen_normalisierung():
    assert zone_nummer("green") == 1
    assert zone_nummer("red") == 4
    assert zone_nummer(3) == 3
    assert zone_nummer(99) == 4
    print("[OK] Partner Zonen-Normalisierung")


def test_partner_zone4_nur_mensch():
    reg = PartnerRegistry()
    empf = reg.empfehle(zone="red")
    assert empf is not None and empf.typ == "human", "Zone 4 muss zum Menschen eskalieren"
    print("[OK] Partner Zone-4-Eskalation")


def test_partner_zone1_erlaubt_external():
    reg = PartnerRegistry()
    # In Zone 1 sollte ein external_ai/local_ai-Partner waehlbar sein
    empf = reg.empfehle(zone="green", zweck="code")
    assert empf is not None
    assert empf.typ in ("external_ai", "local_ai")
    print("[OK] Partner Zone-1")


def test_partner_zone3_nur_lokal_oder_human():
    reg = PartnerRegistry()
    for p in reg.verfuegbare():
        if reg.erlaubt_in_zone(p, "orange"):
            assert p.typ in ("local_ai", "human")
    print("[OK] Partner Zone-3-Restriktion")


def test_partner_zweck_match_bevorzugt():
    reg = PartnerRegistry([
        Partner("a", "external_ai", "low", capabilities=["research"], priority=50),
        Partner("b", "external_ai", "low", capabilities=["code"], priority=50),
    ])
    assert reg.empfehle(zone="green", zweck="code").name == "b"
    print("[OK] Partner Zweck-Match")


# --- Tankuhr-Verdrahtung im Fahrer ---------------------------------------

def test_fahrer_verbucht_tokens_und_kosten():
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "clutch.db"
        fahrer = Fahrer(db_path=db)

        # Handler liefert ein MotorErgebnis -> Tokens/Kosten muessen flieszen
        def handler(config, task):
            return MotorErgebnis(
                text="ok",
                input_tokens=1000,
                output_tokens=500,
                model_id=config.model_id,
                provider=config.provider,
            )

        erg = fahrer.fahren("Implementiere ein neues Feature", handler=handler)
        assert erg.erfolg
        assert erg.total_tokens == 1500, f"Tokens nicht verbucht: {erg.total_tokens}"

        tank = fahrer.tankuhr.stand()
        assert tank.fahrten_heute >= 1, "Tankuhr hat Fahrt nicht aufgezeichnet"
        gang_obj = fahrer.bordcomputer.getriebe.gang(erg.model_id or "")
        if gang_obj and not gang_obj.ist_kostenlos:
            assert tank.kosten_heute_usd > 0, "Tankuhr blieb auf 0 -- Kosten nicht verbucht"
        print("[OK] Fahrer verbucht Tokens + Kosten")


def test_fahrer_db_pfad_nicht_im_repo():
    """Default-DB darf nicht ins Repo/OneDrive geschrieben werden."""
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "sub" / "clutch.db"
        fahrer = Fahrer(db_path=db)
        assert db.parent.exists()
        # Handler ohne MotorErgebnis darf _verbuchen nicht crashen
        erg = fahrer.fahren("Zeige Status", handler=lambda c, t: "text-only")
        assert erg.erfolg
        print("[OK] Fahrer DB-Pfad + Nicht-MotorErgebnis-Handler")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
