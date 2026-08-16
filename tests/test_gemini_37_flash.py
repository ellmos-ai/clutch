"""Tests fuer die Aufnahme von Gemini 3.7 Flash in das Getriebe.

Deckt vier Zusagen ab:
  1. Der Gang steht im Katalog (Modell-ID, Kontext, Stufe, Denkstufen).
  2. Er ist der bevorzugte Flash-Gang -- Upshift und Downshift in die
     Flash-Stufe landen auf 3.7, nicht mehr auf 3.5.
  3. Der aeltere gemini-flash (3.5) bleibt als Fallback erhalten.
  4. Nichts wurde umgewichtet: Die Auswahl unbeteiligter Gaenge
     (ollama-mistral, claude-sonnet, agy-Familie) bleibt unveraendert.
"""

from clutch.getriebe import Getriebe


NEU = "gemini-3.7-flash"
ALT = "gemini-flash"


def test_katalog_gemini_37_flash():
    g = Getriebe()

    neu = g.gang(NEU)
    assert neu is not None, f"{NEU} fehlt im Getriebe"
    assert neu.provider == "google"
    assert neu.model_id == "gemini-3.7-flash"
    assert neu.gang == 2, "Flash-Tier: gleiche Stufe wie gemini-flash"
    assert neu.max_context == 1048576
    assert neu.catalog_checked_at == "2026-08-13"
    assert neu.catalog_source == "https://ai.google.dev/gemini-api/docs/latest-model"

    # Die drei Denkstufen des Modells stehen im Katalog -- als ein Gang,
    # nicht als drei. Der GeminiMotor reicht sie noch nicht durch.
    assert neu.efforts == ["low", "medium", "high"]

    print(f"[OK] Katalog kennt {NEU} ({neu.model_id})")


def test_37_ist_der_bevorzugte_flash_gang():
    """Bevorzugung entsteht durch die Position vor gemini-flash im Katalog.

    Bei gleicher Stufe gewinnt der zuerst eingetragene Gang: `filter` sortiert
    stabil, `naechster_gang_hoch`/`-runter` nehmen das erste Extremum.
    """
    g = Getriebe()

    hoch = g.naechster_gang_hoch("claude-haiku")
    assert hoch is not None and hoch.name == NEU, (
        f"Upshift aus G1 muss auf {NEU} laufen, ging auf "
        f"{hoch.name if hoch else None}"
    )

    runter = g.naechster_gang_runter("claude-sonnet")
    assert runter is not None and runter.name == NEU, (
        f"Downshift aus G3 muss auf {NEU} laufen, ging auf "
        f"{runter.name if runter else None}"
    )

    # Innerhalb der Google-Flash-Stufe steht 3.7 vor 3.5.
    google_g2 = [x.name for x in g.filter(provider="google", max_gang=2)]
    assert google_g2.index(NEU) < google_g2.index(ALT)

    print(f"[OK] {NEU} ist der bevorzugte Flash-Gang")


def test_gemini_35_flash_bleibt_als_fallback():
    g = Getriebe()

    alt = g.gang(ALT)
    assert alt is not None, f"{ALT} darf nicht entfernt werden"
    assert alt.model_id == "gemini-3.5-flash"
    assert alt.gang == 2

    # Faellt 3.7 aus (Circuit-Breaker), bleibt in der Flash-Stufe ein
    # Google-Gang uebrig -- der Fallback ist real erreichbar.
    ohne_37 = [x for x in g.filter(provider="google", max_gang=2)
               if x.name != NEU]
    assert [x.name for x in ohne_37] == [ALT]

    print(f"[OK] {ALT} bleibt als Fallback erhalten")


def test_keine_umgewichtung_anderer_gaenge():
    """Der neue Gang darf die Auswahl unbeteiligter Modelle nicht verschieben."""
    g = Getriebe()

    # Budget-Downshift (Kupplung Schritt 6/10a) nimmt den letzten erlaubten Gang.
    guenstige = g.filter(max_gang=2)
    assert guenstige[-1].name == "ollama-mistral", (
        f"Downshift-Ziel veraendert: {guenstige[-1].name}"
    )

    # Stufen unbeteiligter Gaenge unveraendert.
    assert g.gang("claude-sonnet").gang == 3
    assert g.gang("ollama-mistral").gang == 2
    assert g.gang(ALT).gang == 2

    # Die agy-Familie bleibt unberuehrt: 3.7 existiert dort nicht (agy 1.1.8
    # kennt das Modell nicht, Live-Probe 2026-08-13), 3.6 bleibt ihr Spitzenmodell.
    agy_ids = {x.model_id for x in g.filter(provider="agy")}
    assert "gemini-3.7-flash" not in agy_ids
    assert g.gang("agy-gemini-3.6-flash").gang == 4
    assert g.gang("agy-gemini-3.5-flash").gang == 3

    print("[OK] Keine Umgewichtung anderer Gaenge")


if __name__ == "__main__":
    test_katalog_gemini_37_flash()
    test_37_ist_der_bevorzugte_flash_gang()
    test_gemini_35_flash_bleibt_als_fallback()
    test_keine_umgewichtung_anderer_gaenge()
    print("\n=== ALLE 4 TESTS BESTANDEN ===")
