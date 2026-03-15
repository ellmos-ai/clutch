"""Tests fuer Fahrschule (Lernengine) und FitnessBewerter."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag, FahrtStatistik
from clutch.fahrschule import FitnessBewerter, FitnessErgebnis, Fahrschule
from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung


def test_fitness_bewerter_perfekt():
    """Perfekte Statistik -> hoher Fitness-Score."""
    bewerter = FitnessBewerter()

    stats = FahrtStatistik(
        strecken_typ="bundesstrasse",
        gang="claude-sonnet",
        provider="anthropic",
        gas_durchschnitt=0.5,
        gesamt_fahrten=20,
        erfolgsrate=1.0,
        avg_tokens=5000,
        avg_latenz=15.0,
        avg_wiederholungen=0.0,
        avg_korrekturen=0.0,
        effizienz=0.2,
        stichproben=20,
    )

    fitness = bewerter.bewerten(stats)
    assert isinstance(fitness, FitnessErgebnis)
    assert fitness.gesamt > 0.5, f"Perfekte Stats sollten > 0.5 haben, got {fitness.gesamt}"
    assert fitness.qualitaet >= 0.9, f"100% Erfolg -> hohe Qualitaet, got {fitness.qualitaet}"
    assert fitness.zuverlaessigkeit >= 0.9, f"Keine Retries -> hohe Zuverlaessigkeit, got {fitness.zuverlaessigkeit}"

    print(f"[OK] Fitness perfekt (gesamt={fitness.gesamt:.4f})")


def test_fitness_bewerter_schlecht():
    """Schlechte Statistik -> niedriger Fitness-Score."""
    bewerter = FitnessBewerter()

    stats = FahrtStatistik(
        strecken_typ="autobahn",
        gang="claude-haiku",
        provider="anthropic",
        gas_durchschnitt=0.3,
        gesamt_fahrten=10,
        erfolgsrate=0.4,
        avg_tokens=50000,
        avg_latenz=120.0,
        avg_wiederholungen=3.0,
        avg_korrekturen=2.0,
        effizienz=0.008,
        stichproben=10,
    )

    fitness = bewerter.bewerten(stats)
    assert fitness.gesamt < 0.4, f"Schlechte Stats sollten < 0.4 haben, got {fitness.gesamt}"
    assert fitness.qualitaet < 0.5, f"40% Erfolg -> niedrige Qualitaet, got {fitness.qualitaet}"

    print(f"[OK] Fitness schlecht (gesamt={fitness.gesamt:.4f})")


def test_fitness_vergleich():
    """Bessere Stats -> hoeherer Fitness-Score."""
    bewerter = FitnessBewerter()

    good = FahrtStatistik(
        strecken_typ="landstrasse", gang="claude-sonnet", provider="anthropic",
        gas_durchschnitt=0.5, gesamt_fahrten=15, erfolgsrate=0.95,
        avg_tokens=4000, avg_latenz=10.0, avg_wiederholungen=0.1,
        avg_korrekturen=0.0, effizienz=0.2375, stichproben=15,
    )
    bad = FahrtStatistik(
        strecken_typ="landstrasse", gang="claude-haiku", provider="anthropic",
        gas_durchschnitt=0.3, gesamt_fahrten=15, erfolgsrate=0.6,
        avg_tokens=15000, avg_latenz=60.0, avg_wiederholungen=2.0,
        avg_korrekturen=1.5, effizienz=0.04, stichproben=15,
    )

    fitness_good = bewerter.bewerten(good)
    fitness_bad = bewerter.bewerten(bad)

    assert fitness_good.gesamt > fitness_bad.gesamt, (
        f"Good ({fitness_good.gesamt}) sollte > bad ({fitness_bad.gesamt}) sein"
    )

    print(f"[OK] Fitness-Vergleich (good={fitness_good.gesamt:.4f} > bad={fitness_bad.gesamt:.4f})")


def test_fitness_gewichte():
    """Benutzerdefinierte Gewichte aendern das Ergebnis."""
    # Speed-fokussiert
    speed_bewerter = FitnessBewerter(gewichte={
        "effizienz": 0.10,
        "qualitaet": 0.10,
        "speed": 0.70,
        "zuverlaessigkeit": 0.10,
    })

    stats = FahrtStatistik(
        strecken_typ="feldweg", gang="claude-haiku", provider="anthropic",
        gas_durchschnitt=0.2, gesamt_fahrten=50, erfolgsrate=0.8,
        avg_tokens=2000, avg_latenz=2.0, avg_wiederholungen=0.0,
        avg_korrekturen=0.0, effizienz=0.4, stichproben=50,
    )

    fitness_speed = speed_bewerter.bewerten(stats)
    # Schnelle Latenz (2s vs 30s baseline) sollte bei Speed-Gewichtung dominieren
    assert fitness_speed.speed > 0.8, f"2s Latenz bei 30s Baseline -> hoher Speed, got {fitness_speed.speed}"

    print(f"[OK] Fitness-Gewichte (speed={fitness_speed.speed:.4f})")


def test_fahrschule_sammelphase():
    """Unter 200 Fahrten -> Sammelphase, keine Policy-Updates."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        buch = Fahrtenbuch(db_path=db_path)
        getriebe = Getriebe()
        kupplung = Kupplung(getriebe)
        schule = Fahrschule(buch, kupplung)

        # 5 Fahrten eintragen (weit unter 200)
        for i in range(5):
            buch.eintragen(FahrtEintrag(
                fahrt_id=f"f_{i}",
                strecken_typ="bundesstrasse",
                gang="claude-sonnet",
                provider="anthropic",
                gas=0.5,
                muster="einzelfahrt",
                total_tokens=5000,
                latenz_sekunden=15.0,
                erfolg=True,
            ))

        ergebnis = schule.trainieren()
        assert ergebnis["phase"] == "sammeln", f"Expected sammeln, got {ergebnis['phase']}"
        assert ergebnis["gesamte_fahrten"] == 5
        assert len(ergebnis["updates"]) == 0

        print(f"[OK] Fahrschule Sammelphase ({ergebnis['gesamte_fahrten']} Fahrten)")


def test_fahrschule_erkundungs_decay():
    """Erkundungsrate sinkt nach trainieren()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        buch = Fahrtenbuch(db_path=db_path)
        getriebe = Getriebe()
        kupplung = Kupplung(getriebe)
        schule = Fahrschule(buch, kupplung)

        initial_rate = schule.erkundungsrate

        # Genuegend Fahrten fuer Optimierungsphase
        for i in range(250):
            buch.eintragen(FahrtEintrag(
                fahrt_id=f"f_{i}",
                strecken_typ="bundesstrasse",
                gang="claude-sonnet",
                provider="anthropic",
                gas=0.5,
                muster="einzelfahrt",
                total_tokens=5000,
                latenz_sekunden=15.0,
                erfolg=True,
            ))

        ergebnis = schule.trainieren()
        assert ergebnis["phase"] == "optimieren"
        assert schule.erkundungsrate < initial_rate, (
            f"Rate sollte sinken: {schule.erkundungsrate} < {initial_rate}"
        )

        print(f"[OK] Erkundungs-Decay ({initial_rate:.4f} -> {schule.erkundungsrate:.4f})")


def test_fitness_edge_cases():
    """Edge Cases: Null-Tokens, Null-Latenz."""
    bewerter = FitnessBewerter()

    # avg_tokens = 0 -> Effizienz = 1.0
    stats_zero_tokens = FahrtStatistik(
        strecken_typ="feldweg", gang="ollama-qwen3", provider="ollama",
        gas_durchschnitt=0.2, gesamt_fahrten=3, erfolgsrate=1.0,
        avg_tokens=0, avg_latenz=1.0, avg_wiederholungen=0.0,
        avg_korrekturen=0.0, effizienz=0, stichproben=3,
    )
    fitness = bewerter.bewerten(stats_zero_tokens)
    assert fitness.effizienz == 1.0, f"0 Tokens -> Effizienz 1.0, got {fitness.effizienz}"

    # avg_latenz = 0 -> Speed = 1.0
    stats_zero_latenz = FahrtStatistik(
        strecken_typ="feldweg", gang="ollama-qwen3", provider="ollama",
        gas_durchschnitt=0.2, gesamt_fahrten=3, erfolgsrate=1.0,
        avg_tokens=1000, avg_latenz=0, avg_wiederholungen=0.0,
        avg_korrekturen=0.0, effizienz=1.0, stichproben=3,
    )
    fitness = bewerter.bewerten(stats_zero_latenz)
    assert fitness.speed == 1.0, f"0 Latenz -> Speed 1.0, got {fitness.speed}"

    print("[OK] Fitness Edge Cases")


if __name__ == "__main__":
    test_fitness_bewerter_perfekt()
    test_fitness_bewerter_schlecht()
    test_fitness_vergleich()
    test_fitness_gewichte()
    test_fahrschule_sammelphase()
    test_fahrschule_erkundungs_decay()
    test_fitness_edge_cases()
    print("\n=== ALLE 7 FAHRSCHULE-TESTS BESTANDEN ===")
