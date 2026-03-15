"""Tests fuer Execution Patterns: Kolonne, Team, Schwarm, Hybrid."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.getriebe import Getriebe, Gang
from clutch.gas_bremse import GasBremse
from clutch.kupplung import FahrtConfig
from clutch.patterns.kolonne import Kolonne, KolonnenSchritt, KolonnenErgebnis
from clutch.patterns.team import TeamFahrt, TeamMitglied, TeamErgebnis
from clutch.patterns.schwarm import Schwarm, SchwarmAufgabe, SchwarmErgebnis
from clutch.patterns.hybrid import HybridFahrt, HybridErgebnis


def _make_config(gang_name: str = "claude-haiku", gas: float = 0.3) -> FahrtConfig:
    """Hilfsfunktion: Erzeugt eine FahrtConfig fuer Tests."""
    g = Getriebe()
    pedal = GasBremse()
    gang = g.gang(gang_name)
    gas_stellung = pedal.stellung(gas)
    return FahrtConfig(gang, gas_stellung, "test")


# --- Kolonne (Chain) ---

def test_kolonne_leere_kette():
    """Leere Kolonne -> Erfolg, keine Outputs."""
    kolonne = Kolonne()
    result = kolonne.fahren(start_input="start")
    assert result.erfolg
    assert result.schritte_fertig == 0
    assert result.schritte_gesamt == 0
    assert result.outputs == []

    print("[OK] Kolonne leer")


def test_kolonne_fehler_bricht_ab():
    """Fehler in einem Schritt bricht die Kolonne ab."""
    config = _make_config()
    kolonne = Kolonne()
    kolonne.schritt(KolonnenSchritt("ok", config, lambda x: x * 2))
    kolonne.schritt(KolonnenSchritt("fail", config, lambda x: 1 / 0))  # ZeroDivisionError
    kolonne.schritt(KolonnenSchritt("nie", config, lambda x: x + 1))

    result = kolonne.fahren(start_input=5)
    assert not result.erfolg
    assert result.schritte_fertig == 1  # Nur erster Schritt
    assert len(result.fehler) == 1
    assert "fail" in result.fehler[0]

    print("[OK] Kolonne Fehler-Abbruch")


def test_kolonne_drei_schritte():
    """Drei Schritte sequentiell: Input fliesst durch."""
    config = _make_config()
    kolonne = Kolonne()
    kolonne.schritt(KolonnenSchritt("verdoppeln", config, lambda x: x * 2))
    kolonne.schritt(KolonnenSchritt("plus_100", config, lambda x: x + 100))
    kolonne.schritt(KolonnenSchritt("string", config, lambda x: f"result={x}"))

    result = kolonne.fahren(start_input=10)
    assert result.erfolg
    assert result.schritte_fertig == 3
    assert result.outputs == [20, 120, "result=120"]

    print("[OK] Kolonne 3 Schritte")


def test_kolonne_hat_latenz():
    """Kolonne misst die Gesamtlatenz."""
    config = _make_config()
    kolonne = Kolonne()
    kolonne.schritt(KolonnenSchritt("s1", config, lambda x: x))

    result = kolonne.fahren(start_input=1)
    assert result.latenz >= 0, "Latenz sollte >= 0 sein"

    print("[OK] Kolonne Latenz")


# --- Team (Parallel) ---

def test_team_leeres_team():
    """Leeres Team -> Erfolg, keine Ergebnisse."""
    team = TeamFahrt()
    result = team.fahren()
    assert result.erfolg
    assert result.fertig == 0
    assert result.gesamt == 0
    assert result.ergebnisse == {}

    print("[OK] Team leer")


def test_team_drei_mitglieder():
    """Drei Worker parallel, alle erfolgreich."""
    config = _make_config("claude-sonnet", 0.5)
    team = TeamFahrt()
    team.mitglied(TeamMitglied("alpha", config, lambda _: "a_done"))
    team.mitglied(TeamMitglied("beta", config, lambda _: "b_done"))
    team.mitglied(TeamMitglied("gamma", config, lambda _: "c_done"))

    result = team.fahren()
    assert result.erfolg
    assert result.fertig == 3
    assert result.gesamt == 3
    assert set(result.ergebnisse.keys()) == {"alpha", "beta", "gamma"}

    print("[OK] Team 3 Mitglieder")


def test_team_teilweiser_fehler():
    """Ein Worker scheitert, Rest erfolgreich -> erfolg=False."""
    config = _make_config()
    team = TeamFahrt()
    team.mitglied(TeamMitglied("ok1", config, lambda _: "done"))
    team.mitglied(TeamMitglied("fail", config, lambda _: (_ for _ in ()).throw(ValueError("boom"))))
    team.mitglied(TeamMitglied("ok2", config, lambda _: "done"))

    result = team.fahren()
    assert not result.erfolg
    assert "fail" in result.fehler
    assert result.fertig == 2  # 2 von 3 ok

    print("[OK] Team teilweiser Fehler")


def test_team_kontext_weitergabe():
    """Kontext wird an alle Worker uebergeben."""
    config = _make_config()
    team = TeamFahrt()
    team.mitglied(TeamMitglied("upper", config, lambda ctx: ctx.upper()))
    team.mitglied(TeamMitglied("repeat", config, lambda ctx: ctx * 3))

    result = team.fahren(kontext="hello")
    assert result.erfolg
    assert result.ergebnisse["upper"] == "HELLO"
    assert result.ergebnisse["repeat"] == "hellohellohello"

    print("[OK] Team Kontext-Weitergabe")


# --- Schwarm (Bulk) ---

def test_schwarm_ohne_aggregator():
    """Schwarm ohne Aggregator -> aggregiert ist None."""
    schwarm = Schwarm(
        worker=lambda x: x + 1,
        aggregator=None,
        max_parallel=4,
    )
    aufgaben = [SchwarmAufgabe(f"a{i}", i) for i in range(5)]
    result = schwarm.ausfuehren(aufgaben)
    assert result.erfolg
    assert result.fertig == 5
    assert result.aggregiert is None

    print("[OK] Schwarm ohne Aggregator")


def test_schwarm_mit_fehlern():
    """Einige Tasks scheitern -> erfolg=False, Rest trotzdem verarbeitet."""
    def risky_worker(x):
        if x == 3:
            raise RuntimeError("bad input")
        return x * 10

    schwarm = Schwarm(worker=risky_worker, max_parallel=4)
    aufgaben = [SchwarmAufgabe(f"a{i}", i) for i in range(6)]

    result = schwarm.ausfuehren(aufgaben)
    assert not result.erfolg
    assert result.fertig == 5  # 5 von 6 ok
    assert "a3" in result.fehler

    print("[OK] Schwarm mit Fehlern")


def test_schwarm_grosser_batch():
    """100 Tasks parallel -> alle erfolgreich."""
    schwarm = Schwarm(
        worker=lambda x: x ** 2,
        aggregator=lambda r: sum(r.values()),
        max_parallel=20,
    )
    aufgaben = [SchwarmAufgabe(f"t{i}", i) for i in range(100)]
    result = schwarm.ausfuehren(aufgaben)
    assert result.erfolg
    assert result.fertig == 100
    assert result.aggregiert == sum(i ** 2 for i in range(100))

    print("[OK] Schwarm 100 Tasks")


# --- Hybrid (Kolonne + Team) ---

def test_hybrid_kolonne_dann_team():
    """Hybrid: Kolonne-Phase -> Team-Phase."""
    config = _make_config()

    hybrid = HybridFahrt()

    # Phase 1: Kolonne -- verdoppeln + addieren
    hybrid.kolonne_phase("vorbereitung", [
        KolonnenSchritt("verdoppeln", config, lambda x: x * 2),
        KolonnenSchritt("plus_5", config, lambda x: x + 5),
    ])

    # Phase 2: Team -- parallel verarbeiten (bekommt letzten Kolonne-Output als Kontext)
    hybrid.team_phase("verarbeitung", [
        TeamMitglied("to_str", config, lambda ctx: f"value={ctx}"),
        TeamMitglied("negate", config, lambda ctx: -ctx),
    ])

    result = hybrid.fahren(start_input=10)
    assert result.erfolg, f"Fehler: {result.fehler}"
    assert result.phasen_fertig == 2
    assert result.phasen_gesamt == 2

    # Kolonne: 10 -> 20 -> 25
    kolonne_result = result.phasen_ergebnisse["vorbereitung"]
    assert kolonne_result.outputs == [20, 25]

    # Team bekommt 25 als Kontext
    team_result = result.phasen_ergebnisse["verarbeitung"]
    assert team_result.ergebnisse["to_str"] == "value=25"
    assert team_result.ergebnisse["negate"] == -25

    print("[OK] Hybrid Kolonne->Team")


def test_hybrid_fehler_stoppt_pipeline():
    """Fehler in einer Phase stoppt die gesamte Hybrid-Fahrt."""
    config = _make_config()

    hybrid = HybridFahrt()
    hybrid.kolonne_phase("phase1", [
        KolonnenSchritt("ok", config, lambda x: x),
        KolonnenSchritt("fail", config, lambda x: 1 / 0),
    ])
    hybrid.team_phase("phase2_nie", [
        TeamMitglied("w", config, lambda _: "never"),
    ])

    result = hybrid.fahren(start_input=1)
    assert not result.erfolg
    assert result.phasen_fertig == 0  # Phase 1 scheiterte
    assert len(result.fehler) > 0

    print("[OK] Hybrid Fehler-Stopp")


def test_hybrid_drei_phasen():
    """Drei Phasen: Kolonne -> Team -> Kolonne."""
    config = _make_config()

    hybrid = HybridFahrt()

    hybrid.kolonne_phase("prep", [
        KolonnenSchritt("init", config, lambda x: {"base": x}),
    ])

    hybrid.team_phase("work", [
        TeamMitglied("a", config, lambda ctx: ctx["base"] * 2),
        TeamMitglied("b", config, lambda ctx: ctx["base"] + 100),
    ])

    hybrid.kolonne_phase("finish", [
        KolonnenSchritt("merge", config, lambda ctx: sum(ctx.values())),
    ])

    result = hybrid.fahren(start_input=10)
    assert result.erfolg, f"Fehler: {result.fehler}"
    assert result.phasen_fertig == 3

    # Team: a=20, b=110 -> Kontext = {"a": 20, "b": 110}
    # Finish: sum({20, 110}) = 130
    finish_result = result.phasen_ergebnisse["finish"]
    assert finish_result.outputs == [130], f"Expected [130], got {finish_result.outputs}"

    print("[OK] Hybrid 3 Phasen")


if __name__ == "__main__":
    test_kolonne_leere_kette()
    test_kolonne_fehler_bricht_ab()
    test_kolonne_drei_schritte()
    test_kolonne_hat_latenz()
    test_team_leeres_team()
    test_team_drei_mitglieder()
    test_team_teilweiser_fehler()
    test_team_kontext_weitergabe()
    test_schwarm_ohne_aggregator()
    test_schwarm_mit_fehlern()
    test_schwarm_grosser_batch()
    test_hybrid_kolonne_dann_team()
    test_hybrid_fehler_stoppt_pipeline()
    test_hybrid_drei_phasen()
    print("\n=== ALLE 14 PATTERN-TESTS BESTANDEN ===")
