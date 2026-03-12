#!/usr/bin/env python3
"""Kupplung -- Interaktive Demo.

Zeigt wie der Fahrer verschiedene Tasks klassifiziert und routet.
Mit --live werden echte LLM-Calls gemacht (API-Keys noetig).

Nutzung:
    python demo.py                  # Vordefinierte Szenarien (nur Routing)
    python demo.py --interaktiv     # Eigene Tasks eingeben
    python demo.py --live           # Echte LLM-Calls mit MotorBlock
    python demo.py --live --prompt "Erklaere Quantenmechanik"
    python demo.py --motoren        # Zeige verfuegbare Motoren
    python demo.py --hybrid         # Hybrid-Pattern Demo
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kupplung.fahrer import Fahrer, FahrtConfig
from kupplung.motorblock import MotorBlock, MotorErgebnis


# ANSI-Farben
class C:
    GRUEN = "\033[92m"
    GELB = "\033[93m"
    ROT = "\033[91m"
    BLAU = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def gas_balken(wert: float, breite: int = 20) -> str:
    gefuellt = int(wert * breite)
    leer = breite - gefuellt
    if wert < 0.3:
        farbe = C.BLAU
    elif wert < 0.6:
        farbe = C.GELB
    elif wert < 0.8:
        farbe = C.GRUEN
    else:
        farbe = C.ROT
    return f"{farbe}{'█' * gefuellt}{'░' * leer}{C.RESET} {wert:.0%}"


def zone_farbe(zone: str) -> str:
    farben = {"green": C.GRUEN, "yellow": C.GELB, "orange": C.ROT, "red": C.ROT}
    return f"{farben.get(zone, '')}{zone.upper()}{C.RESET}"


def zeige_fahrt(task: str, fahrer: Fahrer):
    """Zeigt die komplette Routing-Entscheidung fuer einen Task."""
    profil = fahrer.strecke_analysieren(task)
    config = fahrer.kuppeln(profil)

    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"{C.BOLD}Task:{C.RESET} {task}")
    print(f"{C.BOLD}{'─' * 60}{C.RESET}")
    print(f"  Strecke:    {C.CYAN}{profil.typ.value}{C.RESET}")
    print(f"  Tempo:      {profil.tempo.value}")
    print(f"  Schwierigk: {profil.schwierigkeit:.0%}")
    print(f"  Etappen:    {profil.etappen}")
    if profil.erkannte_keywords:
        print(f"  Keywords:   {', '.join(profil.erkannte_keywords)}")
    print()
    print(f"  {C.BOLD}Gang:{C.RESET}       {C.GRUEN}{config.gang.name}{C.RESET} (G{config.gang.gang})")
    print(f"  {C.BOLD}Provider:{C.RESET}    {config.gang.provider}")
    print(f"  {C.BOLD}Model-ID:{C.RESET}    {config.gang.model_id}")
    print(f"  {C.BOLD}Gas:{C.RESET}         {gas_balken(config.gas.wert)}")
    print(f"  {C.BOLD}Strategie:{C.RESET}   {config.gas.prompt_strategie}")
    print(f"  {C.BOLD}Token-Mult:{C.RESET}  {config.gas.token_multiplikator}x")
    print(f"  {C.BOLD}Muster:{C.RESET}      {config.muster}")
    if config.ist_erkundung:
        print(f"  {C.GELB}ERKUNDUNGSFAHRT (Epsilon-Greedy){C.RESET}")
    print(f"  {C.DIM}Grund: {config.entscheidungs_grund}{C.RESET}")

    # Kosten schaetzen
    kosten = config.gang.kosten_schaetzen(5000)
    if kosten > 0:
        print(f"  {C.DIM}Geschaetzte Kosten (5K Tokens): ${kosten:.4f}{C.RESET}")
    else:
        print(f"  {C.GRUEN}Kostenlos (lokal){C.RESET}")


def vordefinierte_szenarien(fahrer: Fahrer):
    """Zeigt verschiedene Szenarien und wie sie geroutet werden."""
    szenarien = [
        "Fix den Typo in der README",
        "Fix den Bug in der Authentifizierung -- Users koennen sich nicht einloggen",
        "Refactore die gesamte Architektur des Payment-Moduls",
        "Schnell den Import-Fehler fixen, Deployment wartet!",
        "Schreib Tests fuer alle API-Endpoints",
        "Formatiere alle Python-Dateien im Projekt mit Black",
        "Review den Pull Request gruendlich, nimm dir Zeit",
        "Baue Frontend und Backend fuer das neue Feature parallel",
        "Pipeline: Analysiere Code, plane Refactoring, setze um, teste",
        "Migriere die gesamte Datenbank auf das neue Schema, mehrere Tabellen betroffen",
    ]

    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  KUPPLUNG v0.3 -- Routing-Demo")
    print(f"  {len(szenarien)} Szenarien, {len(fahrer.getriebe)} Gaenge")
    print(f"{'=' * 60}{C.RESET}")

    for task in szenarien:
        zeige_fahrt(task, fahrer)

    # Status
    status = fahrer.status()
    print(f"\n{C.BOLD}{'═' * 60}")
    print(f"  ARMATURENBRETT")
    print(f"{'═' * 60}{C.RESET}")
    print(f"  Bordcomputer: {'Gesund' if status['bordcomputer']['gesund'] else 'Problem'}")
    print(f"  Tankuhr:      {zone_farbe(status['tankuhr']['zone'])}")
    print(f"  Getriebe:     {status['getriebe']}")


def interaktiver_modus(fahrer: Fahrer):
    """User gibt Tasks ein, sieht Routing-Entscheidung."""
    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  KUPPLUNG v0.3 -- Interaktiver Modus")
    print(f"  Getriebe: {fahrer.getriebe}")
    print(f"{'=' * 60}{C.RESET}")
    print(f"  Beschreibe einen Task und sieh wie er geroutet wird.")
    print(f"  Eingabe 'q' zum Beenden, 's' fuer Status.\n")

    while True:
        try:
            task = input(f"{C.BOLD}Task > {C.RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not task:
            continue
        if task.lower() in ("q", "quit", "exit"):
            break
        if task.lower() in ("s", "status"):
            status = fahrer.status()
            print(f"  Bordcomputer: {'Gesund' if status['bordcomputer']['gesund'] else 'Problem'}")
            print(f"  Tank: {zone_farbe(status['tankuhr']['zone'])}")
            continue

        zeige_fahrt(task, fahrer)

    print("\nTschuess!")


def zeige_motoren():
    """Zeigt welche Motoren verfuegbar sind."""
    block = MotorBlock()
    status = block.verfuegbare_motoren()

    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  MOTORBLOCK -- Verfuegbare Motoren")
    print(f"{'=' * 60}{C.RESET}")

    for provider, verfuegbar in status.items():
        symbol = f"{C.GRUEN}BEREIT{C.RESET}" if verfuegbar else f"{C.ROT}OFFLINE{C.RESET}"
        print(f"  {provider:15s} {symbol}")

    print()
    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for provider, var in env_vars.items():
        gesetzt = bool(os.environ.get(var, ""))
        symbol = f"{C.GRUEN}gesetzt{C.RESET}" if gesetzt else f"{C.ROT}fehlt{C.RESET}"
        print(f"  {var:25s} {symbol}")


def live_modus(fahrer: Fahrer, prompt: str = None):
    """Fuehrt echte LLM-Calls aus."""
    block = MotorBlock()

    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  KUPPLUNG v0.3 -- Live-Modus (echte LLM-Calls)")
    print(f"{'=' * 60}{C.RESET}")

    # Motoren-Status
    status = block.verfuegbare_motoren()
    verfuegbar = [p for p, v in status.items() if v]
    print(f"  Verfuegbare Motoren: {', '.join(verfuegbar) if verfuegbar else 'KEINE'}")

    if not verfuegbar:
        print(f"\n  {C.ROT}Kein Motor verfuegbar!{C.RESET}")
        print(f"  Setze ANTHROPIC_API_KEY oder GOOGLE_API_KEY als Umgebungsvariable.")
        return

    if prompt:
        aufgaben = [prompt]
    else:
        aufgaben = [
            "Erklaere in einem Satz was Python ist.",
            "Was ist 2+2? Antworte nur mit der Zahl.",
        ]

    for task in aufgaben:
        print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
        print(f"{C.BOLD}Task:{C.RESET} {task}")

        def live_handler(config: FahrtConfig, beschreibung: str) -> MotorErgebnis:
            return block.ausfuehren(config, beschreibung)

        ergebnis = fahrer.fahren(task, handler=live_handler)

        if ergebnis.erfolg and isinstance(ergebnis.output, MotorErgebnis):
            me = ergebnis.output
            print(f"  {C.BOLD}Provider:{C.RESET}  {me.provider}")
            print(f"  {C.BOLD}Modell:{C.RESET}    {me.model_id}")
            print(f"  {C.BOLD}Tokens:{C.RESET}    {me.input_tokens} in / {me.output_tokens} out")
            print(f"  {C.BOLD}Latenz:{C.RESET}    {me.latenz_sekunden:.2f}s")
            print(f"\n  {C.BOLD}Antwort:{C.RESET}")
            # Antwort eingerueckt anzeigen
            for line in me.text.strip().split("\n"):
                print(f"  {C.CYAN}{line}{C.RESET}")
        elif ergebnis.erfolg:
            print(f"  {C.GRUEN}Erfolg{C.RESET}: {ergebnis.output}")
        else:
            print(f"  {C.ROT}Fehlgeschlagen{C.RESET}")
            if ergebnis.warnungen:
                for w in ergebnis.warnungen:
                    print(f"    {C.GELB}{w}{C.RESET}")


def hybrid_demo(fahrer: Fahrer):
    """Demonstriert das Hybrid-Muster (Kolonne + Team)."""
    from kupplung.patterns.hybrid import HybridFahrt
    from kupplung.patterns.kolonne import KolonnenSchritt
    from kupplung.patterns.team import TeamMitglied
    from kupplung.kupplung import FahrtConfig
    from kupplung.getriebe import Gang
    from kupplung.gas_bremse import GasBremse

    print(f"\n{C.BOLD}{'=' * 60}")
    print(f"  HYBRID-FAHRT Demo")
    print(f"  Kolonne -> Team -> Kolonne")
    print(f"{'=' * 60}{C.RESET}")

    # Einen einfachen Gang erstellen fuer die Demo
    pedal = GasBremse()
    demo_gang = fahrer.getriebe.gang("claude-haiku") or Gang(
        name="demo", provider="mock", model_id="mock",
        gang=1, leistung="basis", kosten_input_1k=0, kosten_output_1k=0,
    )
    demo_config = FahrtConfig(
        gang=demo_gang,
        gas=pedal.stellung(0.5),
        muster="hybrid",
        entscheidungs_grund="demo",
    )

    # Mock-Handler fuer die Demo
    def analyse_handler(inp):
        print(f"    {C.DIM}[Kolonne] Analyse laeuft...{C.RESET}")
        return {"code_files": ["auth.py", "api.py", "db.py"], "plan": "Refactoring"}

    def plan_handler(inp):
        print(f"    {C.DIM}[Kolonne] Plan erstellt aus: {inp}{C.RESET}")
        return {
            "tasks": [
                {"file": "auth.py", "action": "refactor"},
                {"file": "api.py", "action": "refactor"},
                {"file": "db.py", "action": "refactor"},
            ]
        }

    def refactor_auth(kontext):
        print(f"    {C.DIM}[Team] auth.py refactored{C.RESET}")
        return "auth.py: 5 Funktionen vereinfacht"

    def refactor_api(kontext):
        print(f"    {C.DIM}[Team] api.py refactored{C.RESET}")
        return "api.py: 3 Endpoints konsolidiert"

    def refactor_db(kontext):
        print(f"    {C.DIM}[Team] db.py refactored{C.RESET}")
        return "db.py: Connection-Pooling hinzugefuegt"

    def test_handler(kontext):
        print(f"    {C.DIM}[Kolonne] Tests laufen ueber: {list(kontext.keys()) if isinstance(kontext, dict) else kontext}{C.RESET}")
        return "Alle 42 Tests bestanden"

    # Hybrid aufbauen
    hybrid = HybridFahrt()

    hybrid.kolonne_phase("vorbereitung", [
        KolonnenSchritt("analyse", demo_config, analyse_handler),
        KolonnenSchritt("planung", demo_config, plan_handler),
    ])

    hybrid.team_phase("umsetzung", [
        TeamMitglied("auth_refactor", demo_config, refactor_auth, "auth"),
        TeamMitglied("api_refactor", demo_config, refactor_api, "api"),
        TeamMitglied("db_refactor", demo_config, refactor_db, "db"),
    ])

    hybrid.kolonne_phase("nachbereitung", [
        KolonnenSchritt("tests", demo_config, test_handler),
    ])

    print(f"\n  {C.BOLD}Starte Hybrid-Fahrt (3 Phasen)...{C.RESET}\n")
    ergebnis = hybrid.fahren()

    print(f"\n{C.BOLD}{'─' * 60}{C.RESET}")
    status = f"{C.GRUEN}ERFOLG{C.RESET}" if ergebnis.erfolg else f"{C.ROT}FEHLGESCHLAGEN{C.RESET}"
    print(f"  Status:  {status}")
    print(f"  Phasen:  {ergebnis.phasen_fertig}/{ergebnis.phasen_gesamt}")
    print(f"  Latenz:  {ergebnis.latenz:.3f}s")

    for name, res in ergebnis.phasen_ergebnisse.items():
        print(f"\n  {C.BOLD}Phase '{name}':{C.RESET}")
        if hasattr(res, "outputs"):
            for i, o in enumerate(res.outputs):
                print(f"    Schritt {i}: {o}")
        elif hasattr(res, "ergebnisse"):
            for k, v in res.ergebnisse.items():
                print(f"    {k}: {v}")

    if ergebnis.fehler:
        print(f"\n  {C.ROT}Fehler:{C.RESET}")
        for f in ergebnis.fehler:
            print(f"    {f}")


if __name__ == "__main__":
    fahrer = Fahrer()

    if "--motoren" in sys.argv:
        zeige_motoren()
    elif "--hybrid" in sys.argv:
        hybrid_demo(fahrer)
    elif "--live" in sys.argv:
        # Optionaler Prompt
        prompt = None
        if "--prompt" in sys.argv:
            idx = sys.argv.index("--prompt")
            if idx + 1 < len(sys.argv):
                prompt = sys.argv[idx + 1]
        live_modus(fahrer, prompt)
    elif "--interaktiv" in sys.argv or "-i" in sys.argv:
        interaktiver_modus(fahrer)
    else:
        vordefinierte_szenarien(fahrer)
