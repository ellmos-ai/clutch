"""Tests fuer Kupplung v0.2 -- Provider-neutrale LLM Orchestration."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.strecke import StreckenAnalyse, StreckenTyp, Tempo
from clutch.getriebe import Getriebe, Gang
from clutch.gas_bremse import GasBremse
from clutch.kupplung import Kupplung, FahrtConfig
from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag
from clutch.bordcomputer import Bordcomputer
from clutch.tankuhr import Tankuhr
from clutch.tacho import Tacho
from clutch.fahrer import Fahrer
from clutch.patterns.kolonne import Kolonne, KolonnenSchritt
from clutch.patterns.team import TeamFahrt, TeamMitglied
from clutch.patterns.schwarm import Schwarm, SchwarmAufgabe


def test_streckenanalyse():
    a = StreckenAnalyse()

    p = a.analysiere("Fix den Bug in der Auth-Komponente")
    assert p.typ == StreckenTyp.BUNDESSTRASSE, f"Expected BUNDESSTRASSE, got {p.typ}"

    p = a.analysiere("Refactore die gesamte Architektur")
    assert p.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {p.typ}"

    p = a.analysiere("Mach das schnell bitte!")
    assert p.tempo == Tempo.EILIG, f"Expected EILIG, got {p.tempo}"

    p = a.analysiere("Implementiere die neue Funktion")
    assert p.typ == StreckenTyp.LANDSTRASSE, f"Expected LANDSTRASSE, got {p.typ}"

    print("[OK] StreckenAnalyse")


def test_getriebe():
    g = Getriebe()
    assert len(g) > 0, "Getriebe leer"

    # Spezifischer Gang
    sonnet = g.gang("claude-sonnet")
    assert sonnet is not None
    assert sonnet.provider == "anthropic"
    assert sonnet.gang == 3

    # Filter
    lokale = g.filter(nur_lokal=True)
    assert all(m.provider == "ollama" for m in lokale)

    guenstige = g.filter(max_gang=2)
    assert all(m.gang <= 2 for m in guenstige)

    kostenlose = g.filter(nur_kostenlos=True)
    assert all(m.ist_kostenlos for m in kostenlose)

    # Hoch/Runterschalten
    runter = g.naechster_gang_runter("claude-sonnet")
    assert runter is not None
    assert runter.gang < 3

    hoch = g.naechster_gang_hoch("claude-sonnet")
    assert hoch is not None
    assert hoch.gang > 3

    # Standard-Fahrer
    fahrer = g.standard_fahrer()
    assert fahrer is not None
    assert fahrer.name == "claude-code"

    print(f"[OK] Getriebe ({len(g)} Gaenge: {g})")


def test_gas_bremse():
    pedal = GasBremse()

    # Vollgas
    s = pedal.stellung(1.0)
    assert s.prompt_strategie == "gruendlich"
    assert s.token_multiplikator > 1.5

    # Leerlauf
    s = pedal.stellung(0.0)
    assert s.prompt_strategie == "direkt"
    assert s.token_multiplikator < 0.5

    # Anpassen: schwierig + eilig
    gas = pedal.anpassen(0.5, schwierigkeit=0.9, tempo="eilig")
    assert gas <= 0.5, "Bei eilig sollte Gas gekappt werden"

    # Anpassen: einfach + gemuetlich
    gas = pedal.anpassen(0.3, schwierigkeit=0.1, tempo="gemuetlich")
    assert gas >= 0.6, "Bei gemuetlich mindestens 60%"

    print("[OK] GasBremse")


def test_kupplung_mechanik():
    getriebe = Getriebe()
    kupplung = Kupplung(getriebe)
    analyse = StreckenAnalyse()

    # Bug -> Bundesstrasse -> Sonnet
    profil = analyse.analysiere("Fix den Bug in auth.py")
    config = kupplung.einlegen(profil)
    assert config.gang.name in [g.name for g in getriebe.alle_gaenge()]
    assert config.muster in ("einzelfahrt", "kolonne", "team", "schwarm", "hybrid")

    # Budget-Constraint: Orange -> nur guenstige Gaenge
    config_orange = kupplung.einlegen(profil, budget_zone="orange")
    assert config_orange.gang.gang <= 1, f"In Orange max Gang 1, got {config_orange.gang.gang}"

    # Eilig -> kein Opus
    profil_eilig = analyse.analysiere("Schnell den Typo fixen!", {"tempo": "eilig"})
    config_eilig = kupplung.einlegen(profil_eilig)
    assert config_eilig.gas.wert <= 0.5, "Bei eilig max 50% Gas"

    print(f"[OK] Kupplung (Gang={config.gang.name}, Gas={config.gas.wert:.0%})")


def test_getriebe_multi_provider():
    """Testet dass verschiedene Provider verfuegbar sind."""
    g = Getriebe()

    provider_set = {gang.provider for gang in g.alle_gaenge()}
    assert "anthropic" in provider_set, "Anthropic fehlt"
    assert "google" in provider_set, "Google fehlt"
    assert "ollama" in provider_set, "Ollama fehlt"

    # Gemini Gang testen
    gemini = g.gang("gemini-pro")
    assert gemini is not None
    assert gemini.provider == "google"
    assert gemini.gang == 4

    # Ollama Gang testen
    ollama = g.gang("ollama-qwen3")
    assert ollama is not None
    assert ollama.ist_lokal
    assert ollama.ist_kostenlos

    print(f"[OK] Multi-Provider ({provider_set})")


def test_fahrtenbuch():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        buch = Fahrtenbuch(db_path=db_path)

        for i in range(3):
            buch.eintragen(FahrtEintrag(
                fahrt_id=f"f_{i}",
                strecken_typ="bundesstrasse",
                gang="claude-sonnet",
                provider="anthropic",
                gas=0.5,
                muster="einzelfahrt",
                total_tokens=5000 + i * 1000,
                latenz_sekunden=15.0,
                erfolg=True,
            ))

        stats = buch.statistik("bundesstrasse", "claude-sonnet")
        assert stats is not None
        assert stats.gesamt_fahrten == 3
        assert stats.erfolgsrate == 1.0

        assert buch.gesamte_fahrten() == 3

        print("[OK] Fahrtenbuch")


def test_bordcomputer():
    with tempfile.TemporaryDirectory() as tmpdir:
        buch = Fahrtenbuch(db_path=Path(tmpdir) / "test.db")
        bc = Bordcomputer(buch)

        # Gesund
        status = bc.pruefe(budget_verbraucht_pct=10)
        assert status.gesund
        assert status.budget_zone == "green"

        # Tank leer
        status = bc.pruefe(budget_verbraucht_pct=90)
        assert not status.gesund
        assert status.budget_zone == "red"

        # Circuit-Breaker
        for i in range(6):
            bc.fahrt_auswerten(FahrtEintrag(
                fahrt_id=f"fail_{i}",
                strecken_typ="autobahn",
                gang="gemini-pro",
                provider="google",
                gas=0.8,
                muster="einzelfahrt",
                erfolg=False,
            ))
        assert not bc.modell_verfuegbar("gemini-pro")

        print("[OK] Bordcomputer")


def test_tankuhr():
    tank = Tankuhr()

    # Ollama: kostenlos
    ollama_gang = Gang("test-ollama", "ollama", "test", 1, "basis", 0, 0)
    cost = tank.tanken(ollama_gang, 10000, 5000)
    assert cost == 0.0, "Ollama sollte kostenlos sein"

    # Claude Sonnet
    sonnet_gang = Gang("test-sonnet", "anthropic", "test", 3, "hoch", 0.003, 0.015)
    cost = tank.tanken(sonnet_gang, 1000, 2000)
    assert cost > 0

    stand = tank.stand()
    assert stand.zone == "green"
    assert stand.kosten_heute_usd > 0

    print(f"[OK] Tankuhr (Kosten={stand.kosten_heute_usd:.4f} USD, Zone={stand.zone})")


def test_kolonne():
    from clutch.gas_bremse import GasBremse
    pedal = GasBremse()
    g = Getriebe()
    haiku = g.gang("claude-haiku")
    gas = pedal.stellung(0.3)

    kolonne = Kolonne()
    kolonne.schritt(KolonnenSchritt(
        "verdoppeln",
        FahrtConfig(haiku, gas, "kolonne"),
        lambda x: (x or 1) * 2,
    ))
    kolonne.schritt(KolonnenSchritt(
        "plus_zehn",
        FahrtConfig(haiku, gas, "kolonne"),
        lambda x: x + 10,
    ))

    r = kolonne.fahren(start_input=5)
    assert r.erfolg
    assert r.outputs == [10, 20]
    print("[OK] Kolonne")


def test_team():
    from clutch.gas_bremse import GasBremse
    g = Getriebe()
    sonnet = g.gang("claude-sonnet")
    gas = GasBremse().stellung(0.5)

    team = TeamFahrt()
    team.mitglied(TeamMitglied("frontend", FahrtConfig(sonnet, gas, "team"), lambda _: "fe_done"))
    team.mitglied(TeamMitglied("backend", FahrtConfig(sonnet, gas, "team"), lambda _: "be_done"))

    r = team.fahren()
    assert r.erfolg
    assert r.fertig == 2
    assert "frontend" in r.ergebnisse
    print("[OK] TeamFahrt")


def test_schwarm():
    schwarm = Schwarm(
        worker=lambda x: x * 2,
        aggregator=lambda r: sum(r.values()),
        max_parallel=4,
    )
    aufgaben = [SchwarmAufgabe(f"a{i}", i) for i in range(10)]
    r = schwarm.ausfuehren(aufgaben)
    assert r.erfolg
    assert r.fertig == 10
    assert r.aggregiert == sum(i * 2 for i in range(10))
    print("[OK] Schwarm")


def test_fahrer_integration():
    """Integration: Kompletter Durchlauf."""
    fahrer = Fahrer()

    def mock_handler(config: FahrtConfig, task: str):
        return f"Erledigt mit {config.gang.name} (G{config.gang.gang}) / Gas {config.gas.wert:.0%}"

    ergebnis = fahrer.fahren("Fix den Bug in der Login-Seite", handler=mock_handler)
    assert ergebnis.erfolg
    assert ergebnis.config is not None
    assert "Erledigt" in str(ergebnis.output)

    # Gemini-Task (Architektur)
    ergebnis2 = fahrer.fahren(
        "Design die gesamte Architektur des neuen Systems neu",
        handler=mock_handler,
    )
    assert ergebnis2.erfolg
    assert ergebnis2.config.gang.gang >= 3, "Architektur braucht hohen Gang"

    # Status (Armaturenbrett)
    status = fahrer.status()
    assert "bordcomputer" in status
    assert "tankuhr" in status
    assert "getriebe" in status
    assert status["bordcomputer"]["gesund"]

    print(f"[OK] Fahrer Integration")
    print(f"     Fahrt 1: {ergebnis.output}")
    print(f"     Fahrt 2: {ergebnis2.output}")


def test_mixed_provider_routing():
    """Testet dass Kupplung auch nicht-Claude Gaenge waehlen kann."""
    getriebe = Getriebe()
    kupplung = Kupplung(getriebe)
    analyse = StreckenAnalyse()

    # Override: Feldweg soll Ollama nutzen
    kupplung.override("feldweg", {
        "gang": "ollama-qwen3",
        "gas": 0.2,
        "muster": "einzelfahrt",
    })

    profil = analyse.analysiere("Einfach den Typo fixen")
    config = kupplung.einlegen(profil)

    # Sollte Ollama nehmen (wenn nicht durch Exploration ueberschrieben)
    if not config.ist_erkundung:
        assert config.gang.provider == "ollama", f"Expected ollama, got {config.gang.provider}"
        assert config.gang.ist_kostenlos

    print(f"[OK] Mixed-Provider Routing (Gang={config.gang.name})")


if __name__ == "__main__":
    test_streckenanalyse()
    test_getriebe()
    test_gas_bremse()
    test_kupplung_mechanik()
    test_getriebe_multi_provider()
    test_fahrtenbuch()
    test_bordcomputer()
    test_tankuhr()
    test_kolonne()
    test_team()
    test_schwarm()
    test_fahrer_integration()
    test_mixed_provider_routing()
    print("\n=== ALLE 13 TESTS BESTANDEN ===")
