#!/usr/bin/env python3
"""Kupplung -- Claude Code Session Test.

Testet die Kupplung aus der Perspektive einer Claude Code Session.
Der "Fahrer" ist die aktuelle Claude Code Instanz -- sie nutzt
die Kupplung um Tasks zu analysieren und Routing-Entscheidungen zu treffen.

Dieser Test braucht KEIN echtes LLM -- er simuliert was Claude Code
tun wuerde wenn es die Kupplung als Decision-Engine nutzt.

Nutzung:
    python claude_code_test.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from clutch.fahrer import Fahrer, FahrtConfig, FahrtErgebnis
from clutch.strecke import StreckenAnalyse, StreckenTyp
from clutch.getriebe import Getriebe


class C:
    GRUEN = "\033[92m"
    GELB = "\033[93m"
    ROT = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def banner(text: str):
    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{C.RESET}")


def test_claude_code_als_fahrer():
    """Test: Claude Code als Fahrer (Orchestrator)."""
    banner("TEST 1: Claude Code als Fahrer")

    fahrer = Fahrer()
    cc = fahrer.getriebe.gang("claude-code")

    if cc:
        print(f"  Claude Code im Getriebe: {C.GRUEN}JA{C.RESET}")
        print(f"  Provider:    {cc.provider}")
        print(f"  Gang:        G{cc.gang} ({cc.leistung})")
        print(f"  Staerken:    {', '.join(cc.staerken)}")
        print(f"  Kostenlos:   {C.GRUEN}Ja (Max/Pro Plan){C.RESET}" if cc.ist_kostenlos else "")
    else:
        print(f"  {C.ROT}claude-code nicht im Getriebe!{C.RESET}")
        return False

    std_fahrer = fahrer.getriebe.standard_fahrer()
    print(f"\n  Standard-Fahrer: {C.CYAN}{std_fahrer.name}{C.RESET}")

    return True


def test_routing_entscheidungen():
    """Test: Verschiedene Tasks, verschiedene Routing-Entscheidungen."""
    banner("TEST 2: Routing-Entscheidungen")

    fahrer = Fahrer()

    tasks = [
        ("Einfach: README Typo", "Fix den Typo in Zeile 42 der README"),
        ("Standard: Neue Funktion", "Implementiere die neue Login-Funktion"),
        ("Bug: Auth kaputt", "Fix den Bug: Users koennen sich nicht einloggen"),
        ("Komplex: Architektur", "Redesigne die gesamte Datenbank-Architektur"),
        ("Eilig: Hotfix", "Schnell! Production ist down, fix den Crash in main.py"),
        ("Bulk: Alle formatieren", "Formatiere alle Python-Dateien im Projekt"),
        ("Review: PR pruefen", "Review den PR gruendlich, pruefe die Sicherheit"),
    ]

    print(f"\n  {'Task':<25} {'Strecke':<15} {'Gang':<15} {'Gas':<6} {'Muster':<12} {'Provider'}")
    print(f"  {'─' * 95}")

    for label, task in tasks:
        profil = fahrer.strecke_analysieren(task)
        config = fahrer.kuppeln(profil)

        erkundung = " *" if config.ist_erkundung else ""
        print(
            f"  {label:<25} "
            f"{profil.typ.value:<15} "
            f"{config.gang.name:<15} "
            f"{config.gas.wert:<6.0%} "
            f"{config.muster:<12} "
            f"{config.gang.provider}{erkundung}"
        )

    print(f"\n  {C.DIM}* = Erkundungsfahrt (Epsilon-Greedy){C.RESET}")
    return True


def test_gang_wechsel_simulation():
    """Test: Simuliert einen Gangwechsel waehrend einer Aufgabe."""
    banner("TEST 3: Gangwechsel-Simulation (Kuppeln)")

    fahrer = Fahrer()
    analyse = StreckenAnalyse()

    # Phase 1: Analyse mit Opus
    print(f"\n  {C.BOLD}Phase 1: Analyse{C.RESET}")
    p1 = analyse.analysiere("Analysiere die Architektur des Payment-Systems gruendlich")
    c1 = fahrer.kuppeln(p1)
    print(f"  -> {c1.gang.name} (G{c1.gang.gang}) / Gas {c1.gas.wert:.0%}")

    # Phase 2: Umsetzung mit Sonnet
    print(f"\n  {C.BOLD}Phase 2: Umsetzung (einfacher){C.RESET}")
    p2 = analyse.analysiere("Implementiere das Payment-Interface basierend auf der Analyse")
    c2 = fahrer.kuppeln(p2)
    print(f"  -> {c2.gang.name} (G{c2.gang.gang}) / Gas {c2.gas.wert:.0%}")

    # Phase 3: Tests mit Haiku
    print(f"\n  {C.BOLD}Phase 3: Tests generieren (Bulk){C.RESET}")
    p3 = analyse.analysiere("Generiere Tests fuer alle Payment-Endpoints, batch alle Dateien")
    c3 = fahrer.kuppeln(p3)
    print(f"  -> {c3.gang.name} (G{c3.gang.gang}) / Gas {c3.gas.wert:.0%} / Muster: {c3.muster}")

    # Gangwechsel visualisieren
    print(f"\n  {C.BOLD}Gangwechsel-Protokoll:{C.RESET}")
    print(f"  [Analyse]     G{c1.gang.gang} {c1.gang.name:15} Gas {c1.gas.wert:.0%}")
    print(f"       │  {C.GELB}KUPPELN{C.RESET}")
    print(f"  [Umsetzung]   G{c2.gang.gang} {c2.gang.name:15} Gas {c2.gas.wert:.0%}")
    print(f"       │  {C.GELB}KUPPELN{C.RESET}")
    print(f"  [Tests]       G{c3.gang.gang} {c3.gang.name:15} Gas {c3.gas.wert:.0%}")

    return True


def test_budget_einfluss():
    """Test: Wie beeinflusst das Budget die Gangwahl?"""
    banner("TEST 4: Budget-Zonen-Einfluss")

    fahrer = Fahrer()
    analyse = StreckenAnalyse()

    task = "Redesigne die gesamte Architektur (normalerweise Opus)"
    profil = analyse.analysiere(task)

    zonen = ["green", "yellow", "orange", "red"]
    farben = {"green": C.GRUEN, "yellow": C.GELB, "orange": C.ROT, "red": C.ROT}

    print(f"\n  Task: {C.DIM}{task}{C.RESET}\n")
    print(f"  {'Zone':<10} {'Gang':<18} {'G#':<5} {'Provider':<12} {'Kosten/5K'}")
    print(f"  {'─' * 65}")

    for zone in zonen:
        config = fahrer.kupplungs_mechanik.einlegen(profil, budget_zone=zone)
        kosten = config.gang.kosten_schaetzen(5000)
        farbe = farben[zone]
        print(
            f"  {farbe}{zone:<10}{C.RESET} "
            f"{config.gang.name:<18} "
            f"G{config.gang.gang:<4} "
            f"{config.gang.provider:<12} "
            f"{'$' + f'{kosten:.4f}' if kosten > 0 else 'kostenlos'}"
        )

    return True


def test_provider_vielfalt():
    """Test: Alle Provider im Getriebe."""
    banner("TEST 5: Provider-Vielfalt")

    g = Getriebe()
    provider_gaenge: dict[str, list] = {}

    for gang in g.alle_gaenge():
        if gang.provider not in provider_gaenge:
            provider_gaenge[gang.provider] = []
        provider_gaenge[gang.provider].append(gang)

    for provider, gaenge in provider_gaenge.items():
        print(f"\n  {C.BOLD}{provider}{C.RESET}")
        for gang in gaenge:
            kosten = f"${gang.kosten_schaetzen(5000):.4f}/5K" if not gang.ist_kostenlos else "kostenlos"
            print(f"    G{gang.gang} {gang.name:<20} {gang.leistung:<8} {kosten}")

    print(f"\n  {C.BOLD}Gesamt:{C.RESET} {len(g)} Gaenge von {len(provider_gaenge)} Providern")
    return True


def test_end_to_end():
    """Test: Kompletter Durchlauf mit Mock-Handler."""
    banner("TEST 6: End-to-End (Mock)")

    fahrer = Fahrer()
    ergebnisse = []

    tasks = [
        "Fix den Typo in der README",
        "Fix den Bug in auth.py -- Login geht nicht",
        "Refactore die Architektur des gesamten Backends",
    ]

    def mock_handler(config: FahrtConfig, task: str) -> str:
        return f"OK ({config.gang.name}/G{config.gang.gang}/{config.gas.wert:.0%})"

    for task in tasks:
        ergebnis = fahrer.fahren(task, handler=mock_handler)
        ergebnisse.append(ergebnis)
        status = "OK" if ergebnis.erfolg else "FEHLER"
        print(f"  [{status}] {task[:40]:<42} -> {ergebnis.output}")

    # Armaturenbrett
    status = fahrer.status()
    print(f"\n  {C.BOLD}Armaturenbrett nach {len(ergebnisse)} Fahrten:{C.RESET}")
    print(f"  Gesund:      {C.GRUEN}Ja{C.RESET}" if status["bordcomputer"]["gesund"] else f"  Gesund: {C.ROT}Nein{C.RESET}")
    print(f"  Tank:        {status['tankuhr']['zone']}")
    print(f"  Fahrten:     {status['tacho']['gesamte_fahrten']}")
    print(f"  Getriebe:    {status['getriebe']}")

    return all(e.erfolg for e in ergebnisse)


if __name__ == "__main__":
    tests = [
        ("Claude Code als Fahrer", test_claude_code_als_fahrer),
        ("Routing-Entscheidungen", test_routing_entscheidungen),
        ("Gangwechsel-Simulation", test_gang_wechsel_simulation),
        ("Budget-Einfluss", test_budget_einfluss),
        ("Provider-Vielfalt", test_provider_vielfalt),
        ("End-to-End", test_end_to_end),
    ]

    ergebnisse = []
    for name, test_fn in tests:
        try:
            ok = test_fn()
            ergebnisse.append((name, ok))
        except Exception as e:
            print(f"  {C.ROT}FEHLER: {e}{C.RESET}")
            ergebnisse.append((name, False))

    banner("ERGEBNIS")
    for name, ok in ergebnisse:
        symbol = f"{C.GRUEN}OK{C.RESET}" if ok else f"{C.ROT}FEHLER{C.RESET}"
        print(f"  [{symbol}] {name}")

    gesamt = sum(1 for _, ok in ergebnisse if ok)
    print(f"\n  {gesamt}/{len(ergebnisse)} Tests bestanden")
