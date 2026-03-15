#!/usr/bin/env python3
"""Kupplung -- Live-Test mit echten LLM-Aufrufen.

Testet die Kupplung mit echten Modellen:
  --ollama     Lokaler Ollama-Test (kostenlos)
  --claude     Claude Haiku API-Test (~$0.01)
  --all        Beide

Voraussetzungen:
  --ollama: Ollama muss laufen (http://localhost:11434)
  --claude: ANTHROPIC_API_KEY muss gesetzt sein
"""

import sys
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

sys.path.insert(0, str(Path(__file__).parent))

from clutch.fahrer import Fahrer, FahrtConfig
from clutch.getriebe import Gang


class C:
    GRUEN = "\033[92m"
    GELB = "\033[93m"
    ROT = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def test_ollama(fahrer: Fahrer):
    """Live-Test mit lokalem Ollama."""
    print(f"\n{C.BOLD}{'=' * 50}")
    print(f"  OLLAMA LIVE-TEST")
    print(f"{'=' * 50}{C.RESET}")

    # Pruefen ob Ollama laeuft
    try:
        req = Request("http://localhost:11434/api/tags")
        resp = urlopen(req, timeout=5)
        data = json.loads(resp.read())
        modelle = [m["name"] for m in data.get("models", [])]
        print(f"  Ollama laeuft. Modelle: {', '.join(modelle)}")
    except (URLError, ConnectionError, OSError) as e:
        print(f"  {C.ROT}Ollama nicht erreichbar: {e}{C.RESET}")
        print(f"  Starte Ollama mit: ollama serve")
        return False

    # Finde ein verfuegbares Modell
    ollama_gaenge = fahrer.getriebe.filter(nur_lokal=True)
    verfuegbar = None
    for gang in ollama_gaenge:
        model_name = gang.model_id.split(":")[0] if ":" in gang.model_id else gang.model_id
        if any(model_name in m for m in modelle):
            verfuegbar = gang
            break

    if not verfuegbar:
        # Fallback: erstes lokales Modell nehmen
        if modelle:
            verfuegbar = Gang(
                name=f"ollama-{modelle[0].split(':')[0]}",
                provider="ollama",
                model_id=modelle[0],
                gang=1,
                leistung="basis",
                kosten_input_1k=0,
                kosten_output_1k=0,
                endpoint="http://localhost:11434",
            )
            fahrer.getriebe.registriere_gang(verfuegbar)
            print(f"  Nutze: {verfuegbar.model_id}")
        else:
            print(f"  {C.ROT}Keine Modelle installiert. ollama pull qwen3:4b{C.RESET}")
            return False

    # Echter API-Call
    prompt = "Was ist 2 + 2? Antworte nur mit der Zahl."
    print(f"\n  {C.BOLD}Prompt:{C.RESET} {prompt}")
    print(f"  {C.BOLD}Modell:{C.RESET} {verfuegbar.model_id}")

    # Ollama-Modell als feststehendes Ziel
    ollama_model = verfuegbar.model_id

    def ollama_handler(config: FahrtConfig, task: str) -> str:
        payload = json.dumps({
            "model": ollama_model,
            "prompt": task,
            "stream": False,
        }).encode("utf-8")

        req = Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )

        t0 = time.time()
        resp = urlopen(req, timeout=300)
        data = json.loads(resp.read())
        latenz = time.time() - t0

        antwort = data.get("response", "").strip()
        tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
        print(f"  {C.GRUEN}Antwort:{C.RESET} {antwort}")
        print(f"  {C.DIM}Tokens: {tokens}, Latenz: {latenz:.1f}s{C.RESET}")
        return antwort

    # Alle Strecken auf Ollama umleiten fuer diesen Test
    for stype in ("feldweg", "landstrasse", "bundesstrasse", "testfahrt"):
        fahrer.kupplungs_mechanik.override(stype, {
            "gang": verfuegbar.name,
            "gas": 0.3,
            "muster": "einzelfahrt",
        })

    ergebnis = fahrer.fahren(
        "Einfach den Typo fixen: " + prompt,
        handler=ollama_handler,
    )

    print(f"\n  {C.BOLD}Ergebnis:{C.RESET}")
    print(f"  Erfolg:  {'✓' if ergebnis.erfolg else '✗'}")
    print(f"  Gang:    {ergebnis.config.gang.name} ({ergebnis.config.gang.provider})")
    print(f"  Gas:     {ergebnis.config.gas.wert:.0%}")
    print(f"  Latenz:  {ergebnis.latenz_sekunden:.1f}s")

    return ergebnis.erfolg


def test_claude(fahrer: Fahrer):
    """Live-Test mit Claude Haiku (guenstig)."""
    import os

    print(f"\n{C.BOLD}{'=' * 50}")
    print(f"  CLAUDE API LIVE-TEST")
    print(f"{'=' * 50}{C.RESET}")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(f"  {C.ROT}ANTHROPIC_API_KEY nicht gesetzt{C.RESET}")
        return False

    prompt = "Was ist die Hauptstadt von Deutschland? Antworte in einem Wort."
    print(f"  {C.BOLD}Prompt:{C.RESET} {prompt}")
    print(f"  {C.BOLD}Modell:{C.RESET} claude-haiku-4-5-20251001 (guenstigstes)")

    def claude_handler(config: FahrtConfig, task: str) -> str:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": task}],
        }).encode("utf-8")

        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )

        t0 = time.time()
        resp = urlopen(req, timeout=30)
        data = json.loads(resp.read())
        latenz = time.time() - t0

        antwort = data["content"][0]["text"].strip()
        input_tokens = data.get("usage", {}).get("input_tokens", 0)
        output_tokens = data.get("usage", {}).get("output_tokens", 0)

        print(f"  {C.GRUEN}Antwort:{C.RESET} {antwort}")
        print(f"  {C.DIM}Tokens: {input_tokens}in + {output_tokens}out, Latenz: {latenz:.1f}s{C.RESET}")

        # Kosten loggen
        haiku = fahrer.getriebe.gang("claude-haiku")
        if haiku:
            kosten = fahrer.tankuhr.tanken(haiku, input_tokens, output_tokens)
            print(f"  {C.DIM}Kosten: ${kosten:.6f}{C.RESET}")

        return antwort

    ergebnis = fahrer.fahren(
        "Einfache Wissensfrage: " + prompt,
        handler=claude_handler,
    )

    print(f"\n  {C.BOLD}Ergebnis:{C.RESET}")
    print(f"  Erfolg:  {'✓' if ergebnis.erfolg else '✗'}")
    print(f"  Gang:    {ergebnis.config.gang.name}")
    print(f"  Latenz:  {ergebnis.latenz_sekunden:.1f}s")

    return ergebnis.erfolg


def main():
    fahrer = Fahrer()

    args = sys.argv[1:]
    if not args:
        print("Nutzung: python live_test.py [--ollama] [--claude] [--all]")
        print("  --ollama  Lokaler Ollama-Test (kostenlos)")
        print("  --claude  Claude Haiku API-Test (~$0.01)")
        print("  --all     Beide")
        return

    ergebnisse = {}

    if "--ollama" in args or "--all" in args:
        ergebnisse["ollama"] = test_ollama(fahrer)

    if "--claude" in args or "--all" in args:
        ergebnisse["claude"] = test_claude(fahrer)

    # Zusammenfassung
    print(f"\n{C.BOLD}{'=' * 50}")
    print(f"  ZUSAMMENFASSUNG")
    print(f"{'=' * 50}{C.RESET}")
    for name, ok in ergebnisse.items():
        symbol = f"{C.GRUEN}✓{C.RESET}" if ok else f"{C.ROT}✗{C.RESET}"
        print(f"  {symbol} {name}")

    tank = fahrer.tankuhr.stand()
    if tank.kosten_heute_usd > 0:
        print(f"\n  Kosten heute: ${tank.kosten_heute_usd:.6f}")


if __name__ == "__main__":
    main()
