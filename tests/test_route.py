"""Tests fuer StreckenAnalyse -- Task-Klassifikation und Profil-Erstellung."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.strecke import StreckenAnalyse, StreckenTyp, StreckenProfil, Tempo


def test_feldweg_erkennung():
    """Triviale Tasks (Typos, Formatting) -> Feldweg."""
    a = StreckenAnalyse()

    profil = a.analysiere("Rename the variable foo to bar")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    profil = a.analysiere("Fix the typo in the docstring")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    profil = a.analysiere("Format the indentation in utils.py")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    print("[OK] Feldweg-Erkennung")


def test_autobahn_erkennung():
    """Architektur-Tasks -> Autobahn."""
    a = StreckenAnalyse()

    profil = a.analysiere("Refactor the entire architecture of the auth module")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    profil = a.analysiere("Design a new API interface for the payment system")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    profil = a.analysiere("Migration der gesamten Datenbankstruktur")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    print("[OK] Autobahn-Erkennung")


def test_bundesstrasse_erkennung():
    """Bugfix-Tasks -> Bundesstrasse."""
    a = StreckenAnalyse()

    profil = a.analysiere("Fix the crash when user clicks login button")
    assert profil.typ == StreckenTyp.BUNDESSTRASSE, f"Expected BUNDESSTRASSE, got {profil.typ}"

    profil = a.analysiere("Debug the exception in the payment module")
    assert profil.typ == StreckenTyp.BUNDESSTRASSE, f"Expected BUNDESSTRASSE, got {profil.typ}"

    print("[OK] Bundesstrasse-Erkennung")


def test_rallye_erkennung():
    """Bulk-Operations -> Rallye."""
    a = StreckenAnalyse()

    profil = a.analysiere("Batch rename all test files")
    assert profil.typ == StreckenTyp.RALLYE, f"Expected RALLYE, got {profil.typ}"

    profil = a.analysiere("Format all files in the src directory")
    assert profil.typ == StreckenTyp.RALLYE, f"Expected RALLYE, got {profil.typ}"

    print("[OK] Rallye-Erkennung")


def test_testfahrt_erkennung():
    """Test-Generierung -> Testfahrt."""
    a = StreckenAnalyse()

    profil = a.analysiere("Write unit tests for the payment module")
    assert profil.typ == StreckenTyp.TESTFAHRT, f"Expected TESTFAHRT, got {profil.typ}"

    profil = a.analysiere("Add pytest coverage for the auth handler")
    assert profil.typ == StreckenTyp.TESTFAHRT, f"Expected TESTFAHRT, got {profil.typ}"

    print("[OK] Testfahrt-Erkennung")


def test_tempo_erkennung():
    """Tempo-Keywords korrekt erkannt."""
    a = StreckenAnalyse()

    profil = a.analysiere("Schnell den Fehler beheben bitte!")
    assert profil.tempo == Tempo.EILIG, f"Expected EILIG, got {profil.tempo}"

    profil = a.analysiere("Gruendlich und sorgfaeltig den Code pruefen, keine Eile")
    assert profil.tempo == Tempo.GEMUETLICH, f"Expected GEMUETLICH, got {profil.tempo}"

    profil = a.analysiere("Implement the new user login feature")
    assert profil.tempo == Tempo.NORMAL, f"Expected NORMAL, got {profil.tempo}"

    print("[OK] Tempo-Erkennung")


def test_tempo_kontext_override():
    """Kontext-Dict ueberschreibt Tempo-Erkennung."""
    a = StreckenAnalyse()

    # Ohne Kontext: "schnell" -> eilig
    profil = a.analysiere("Schnell den Bug fixen", {})
    assert profil.tempo == Tempo.EILIG

    # Mit Kontext-Override: erzwinge gemuetlich
    profil = a.analysiere("Schnell den Bug fixen", {"tempo": "gemuetlich"})
    assert profil.tempo == Tempo.GEMUETLICH, f"Expected GEMUETLICH, got {profil.tempo}"

    print("[OK] Tempo-Kontext-Override")


def test_schwierigkeit_signale():
    """Schwierigkeitssignale beeinflussen den Score."""
    a = StreckenAnalyse()

    # Explizit schwierig
    profil_schwer = a.analysiere("This is a very complex and challenging task that is difficult")
    # Explizit einfach
    profil_leicht = a.analysiere("Simple small quick one-liner change")

    assert profil_schwer.schwierigkeit > profil_leicht.schwierigkeit, (
        f"Schwer ({profil_schwer.schwierigkeit}) sollte > leicht ({profil_leicht.schwierigkeit}) sein"
    )

    print(f"[OK] Schwierigkeit (schwer={profil_schwer.schwierigkeit:.2f}, leicht={profil_leicht.schwierigkeit:.2f})")


def test_schwierigkeit_kontext_override():
    """Schwierigkeit kann per Kontext exakt vorgegeben werden."""
    a = StreckenAnalyse()

    profil = a.analysiere("Irgendwas", {"schwierigkeit": 0.95})
    assert profil.schwierigkeit == 0.95, f"Expected 0.95, got {profil.schwierigkeit}"

    print("[OK] Schwierigkeit-Kontext-Override")


def test_etappen_schaetzung():
    """Etappen werden korrekt geschaetzt."""
    a = StreckenAnalyse()

    # Einzelne Aufgabe
    profil = a.analysiere("Fix the login bug")
    assert profil.etappen >= 1

    # Mehrere Aufgaben durch 'und/and'
    profil = a.analysiere("Fix the login bug and update the tests and refactor the handler")
    assert profil.etappen >= 3, f"Expected >= 3, got {profil.etappen}"

    print(f"[OK] Etappen-Schaetzung")


def test_etappen_kontext_override():
    """Etappen koennen per Kontext gesetzt werden."""
    a = StreckenAnalyse()

    profil = a.analysiere("Grosses Projekt", {"etappen": 7})
    assert profil.etappen == 7, f"Expected 7, got {profil.etappen}"

    print("[OK] Etappen-Kontext-Override")


def test_strecken_profil_felder():
    """StreckenProfil hat alle erwarteten Felder."""
    a = StreckenAnalyse()
    profil = a.analysiere("Design the new system architecture")

    assert isinstance(profil, StreckenProfil)
    assert isinstance(profil.typ, StreckenTyp)
    assert isinstance(profil.tempo, Tempo)
    assert 0.0 <= profil.schwierigkeit <= 1.0
    assert profil.etappen >= 1
    assert isinstance(profil.braucht_spezialisten, bool)
    assert isinstance(profil.ist_pipeline, bool)
    assert 0.0 <= profil.konfidenz <= 1.0
    assert isinstance(profil.erkannte_keywords, list)

    # Autobahn braucht Spezialisten
    assert profil.braucht_spezialisten, "Autobahn sollte Spezialisten brauchen"

    print("[OK] StreckenProfil-Felder")


def test_konvoi_pipeline_flag():
    """Konvoi setzt ist_pipeline auf True."""
    a = StreckenAnalyse()
    profil = a.analysiere("Execute the pipeline step by step")
    assert profil.typ == StreckenTyp.KONVOI, f"Expected KONVOI, got {profil.typ}"
    assert profil.ist_pipeline, "Konvoi sollte ist_pipeline=True setzen"

    print("[OK] Konvoi-Pipeline-Flag")


def test_unbekannte_aufgabe_fallback():
    """Nicht erkannte Aufgabe -> Landstrasse (Fallback)."""
    a = StreckenAnalyse()
    profil = a.analysiere("Mach was mit dem Ding")
    assert profil.typ == StreckenTyp.LANDSTRASSE, f"Expected LANDSTRASSE, got {profil.typ}"
    assert profil.konfidenz <= 0.5, "Unbekannte Aufgabe sollte niedrige Konfidenz haben"

    print("[OK] Unbekannte Aufgabe -> Landstrasse-Fallback")


if __name__ == "__main__":
    test_feldweg_erkennung()
    test_autobahn_erkennung()
    test_bundesstrasse_erkennung()
    test_rallye_erkennung()
    test_testfahrt_erkennung()
    test_tempo_erkennung()
    test_tempo_kontext_override()
    test_schwierigkeit_signale()
    test_schwierigkeit_kontext_override()
    test_etappen_schaetzung()
    test_etappen_kontext_override()
    test_strecken_profil_felder()
    test_konvoi_pipeline_flag()
    test_unbekannte_aufgabe_fallback()
    print("\n=== ALLE 14 STRECKEN-TESTS BESTANDEN ===")
