"""CLI-Entry für clutch — M4 CLI-Ansteuerbarkeit.

Subcommands:
  clutch route "<prompt>"    Routing-Entscheidung anzeigen (dry-run)
  clutch models              Alle Gänge listen
  clutch config <key> [val]  Einstellungen lesen/setzen
  clutch stats [--days N]    Nutzungsstatistik
  clutch run "<prompt>"      One-shot: routet + führt aus
  clutch "<prompt>"          One-shot (positional)
  clutch chat                Minimaler REPL

Globale Option: --db <pfad>   Pfad zur clutch.db
               --json          Maschinenlesbare JSON-Ausgabe
               --lang <code>   Ausgabesprache (en, de, es, zh, ja, ru)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from clutch.i18n import t, set_lang, LANGS


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _config_pfad() -> Path:
    """Gibt den Pfad zur CLI-Konfigurationsdatei zurück."""
    config_dir = Path.home() / ".clutch"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "cli_config.json"


def _lade_config() -> dict:
    p = _config_pfad()
    if p.exists():
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _speichere_config(daten: dict) -> None:
    p = _config_pfad()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)


def _drucke_json(obj: object) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _fahrer_erstellen(db_path: Optional[str] = None):
    """Erstellt einen Fahrer mit optionalem db_path."""
    from clutch.fahrer import Fahrer
    if db_path:
        return Fahrer(db_path=Path(db_path))
    return Fahrer()


# ---------------------------------------------------------------------------
# Subcommand-Handler
# ---------------------------------------------------------------------------

def _cmd_route(args: argparse.Namespace) -> int:
    """Routing-Entscheidung anzeigen (dry-run, keine LLM-Ausführung)."""
    try:
        from clutch.scorer import get_scorer
        fahrer = _fahrer_erstellen(args.db)

        prompt = args.prompt
        profil = fahrer.strecke_analysieren(prompt)
        scorer = get_scorer()
        score_ergebnis = scorer.bewerte(prompt)
        config = fahrer.kuppeln(profil, zweck=score_ergebnis.zweck)

        ergebnis = {
            "gang": config.gang.name,
            "provider": config.gang.provider,
            "gas": round(config.gas.wert, 3),
            "effort": config.effort,
            "muster": config.muster,
            "zweck": score_ergebnis.zweck,
            "score": score_ergebnis.score,
            "gang_stufe": config.gang.gang,
            "grund": config.entscheidungs_grund,
        }

        if args.json:
            _drucke_json(ergebnis)
        else:
            print(t("route.header", prompt=repr(prompt)))
            print(f"  {t('route.gang'):<9} {ergebnis['gang']} (G{ergebnis['gang_stufe']})")
            print(f"  {t('route.provider'):<9} {ergebnis['provider']}")
            print(f"  {t('route.gas'):<9} {ergebnis['gas']:.0%}")
            print(f"  {t('route.effort'):<9} {ergebnis['effort'] or '-'}")
            print(f"  {t('route.muster'):<9} {ergebnis['muster']}")
            print(f"  {t('route.zweck'):<9} {ergebnis['zweck']}")
            print(f"  {t('route.score'):<9} {ergebnis['score']}/100")
            print(f"  {t('route.grund'):<9} {ergebnis['grund']}")

        return 0

    except Exception as e:
        print(t("error.routing", e=e), file=sys.stderr)
        return 1


def _cmd_models(args: argparse.Namespace) -> int:
    """Alle Gänge aus dem Getriebe listen."""
    try:
        from clutch.getriebe import Getriebe
        from clutch.execution_registry import ModelAvailability
        from pathlib import Path as _Path
        import clutch as _clutch_pkg
        config_dir = _Path(_clutch_pkg.__file__).parent / "config"
        getriebe = Getriebe(config_dir=config_dir)
        # Discovery ist on-demand und nicht persistent: statische Katalogdaten
        # bleiben die Quelle der Wahrheit, neue Ollama-Gänge gelten für diesen
        # Aufruf und die Web-Anfrage. Ein kurzer Timeout hält die CLI offline
        # gut benutzbar, während Remote-Endpunkte weiterhin unterstützt werden.
        from clutch.discovery import ModellDiscovery, konfigurierte_ollama_hosts
        import os as _os
        try:
            discovery_timeout = float(_os.environ.get("CLUTCH_DISCOVERY_TIMEOUT", "1.0"))
        except ValueError:
            discovery_timeout = 1.0
        discovery_timeout = min(max(discovery_timeout, 0.1), 30.0)
        if not getattr(args, "no_discovery", False):
            ModellDiscovery().entdecke_und_registriere(
                getriebe,
                ollama_hosts=konfigurierte_ollama_hosts(),
                ollama_timeout=discovery_timeout,
            )
        gaenge = getriebe.alle_gaenge()

        if args.json:
            liste = [
                {
                    "name": g.name,
                    "provider": g.provider,
                    "gang_stufe": g.gang,
                    "leistung": g.leistung,
                    "kosten_input_1k_usd": g.kosten_input_1k,
                    "kosten_output_1k_usd": g.kosten_output_1k,
                    "staerken": g.staerken,
                    "model_id": g.model_id,
                    "endpoint": g.endpoint,
                    "catalog_source": g.catalog_source,
                    "catalog_checked_at": g.catalog_checked_at,
                    "lifecycle": g.lifecycle,
                    "availability": ModelAvailability.from_mapping(g.availability).to_dict(),
                    "runners": g.runners,
                    "quantization": g.quantization,
                    "efforts": g.efforts,
                    "reasoning_modes": g.reasoning_modes,
                    "pricing": g.pricing.to_dict() if g.pricing else None,
                    "pricing_stale": g.pricing.is_stale() if g.pricing else None,
                }
                for g in gaenge
            ]
            _drucke_json(liste)
        else:
            h_name = t("models.header_name")
            h_prov = t("models.header_provider")
            h_stufe = t("models.header_stufe")
            h_leist = t("models.header_leistung")
            h_in = t("models.header_kosten_in")
            h_out = t("models.header_kosten_out")
            print(f"{h_name:<25} {h_prov:<15} {h_stufe:>5}  {h_leist:<10}  {h_in:>8}  {h_out:>9}")
            print("-" * 80)
            for g in gaenge:
                print(
                    f"{g.name:<25} {g.provider:<15} {'G' + str(g.gang):>5}  "
                    f"{g.leistung:<10}  {g.kosten_input_1k:>8.4f}  {g.kosten_output_1k:>9.4f}"
                )

        return 0

    except Exception as e:
        print(t("error.models", e=e), file=sys.stderr)
        return 1


def _cmd_resolve(args: argparse.Namespace) -> int:
    """Öffentlichen Execution-Selektor rein lesend auflösen."""
    try:
        from clutch.execution_registry import resolve_execution_selector

        result = resolve_execution_selector(args.selector, runner=args.runner)
        if args.json:
            _drucke_json(result.to_dict())
        else:
            status = "resolved" if result.resolved else "unresolved"
            print(f"{status}: {result.canonical_selector or result.normalized_selector}")
            print(f"fingerprint: {result.registry_fingerprint}")
            print(f"claimable: {str(result.claimable).lower()}")
            if result.reason:
                print(f"reason: {result.reason}")
        if not result.resolved:
            return 3
        if args.require_claimable and not result.claimable:
            return 4
        return 0
    except Exception as exc:
        print(f"Resolver-Fehler: {type(exc).__name__}", file=sys.stderr)
        return 1


def _cmd_config(args: argparse.Namespace) -> int:
    """Einstellungen lesen oder setzen."""
    try:
        daten = _lade_config()

        if args.value is None:
            # Lesen
            if args.key in daten:
                val = daten[args.key]
                if args.json:
                    _drucke_json({args.key: val})
                else:
                    print(f"{args.key} = {val!r}")
            else:
                if args.json:
                    _drucke_json({args.key: None})
                else:
                    print(t("config.not_set", key=args.key))
        else:
            # Setzen
            daten[args.key] = args.value
            _speichere_config(daten)
            if args.json:
                _drucke_json({args.key: args.value, "gespeichert": True})
            else:
                print(t("config.saved", key=args.key, value=repr(args.value)))

        return 0

    except Exception as e:
        print(t("error.config", e=e), file=sys.stderr)
        return 1


def _cmd_stats(args: argparse.Namespace) -> int:
    """Nutzungsstatistik ausgeben."""
    try:
        fahrer = _fahrer_erstellen(args.db)
        st = fahrer.status()

        if args.json:
            _drucke_json(st)
        else:
            bc = st.get("bordcomputer", {})
            tank = st.get("tankuhr", {})
            tacho = st.get("tacho", {})

            print(t("stats.header"))
            print()
            print(t("stats.bordcomputer") + ":")
            gesund = bc.get("gesund", True)
            print(f"  {t('stats.gesund'):<20} {gesund}")
            warnungen = bc.get("warnungen", [])
            if warnungen:
                for w in warnungen:
                    print(f"  {t('stats.warnung'):<20} {w}")
            gesperrte = bc.get("gesperrte_modelle", [])
            if gesperrte:
                print(f"  {t('stats.gesperrte_modelle')}: {', '.join(gesperrte)}")

            print()
            print(t("stats.tankuhr") + ":")
            print(f"  {t('stats.zone'):<20} {tank.get('zone', t('stats.unknown'))}")
            kosten = tank.get("kosten_heute_usd", 0.0)
            print(f"  {t('stats.kosten_heute'):<20} ${kosten:.4f} USD")
            verbrauch = tank.get("verbrauch_pct", 0.0)
            print(f"  {t('stats.tagesverbrauch'):<20} {verbrauch:.1%}")
            nachricht = tank.get("nachricht", "")
            if nachricht:
                print(f"  {t('stats.nachricht'):<20} {nachricht}")

            print()
            print(t("stats.tacho") + ":")
            if tacho:
                for k, v in tacho.items():
                    print(f"  {k:<22} {v}")
            else:
                print(f"  {t('stats.keine_fahrten')}")

        return 0

    except Exception as e:
        print(t("error.stats", e=e), file=sys.stderr)
        return 1


def _cmd_cost(args: argparse.Namespace) -> int:
    """Deterministischer Kostenrechner aus derselben SSOT wie Laufzeit/Stats."""
    try:
        from clutch.getriebe import Getriebe
        from clutch.pricing import UsageRecord, cost_for_gang

        getriebe = Getriebe()
        gang = getriebe.gang(args.model)
        if gang is None:
            gang = next((g for g in getriebe.alle_gaenge() if g.model_id == args.model), None)
        if gang is None:
            raise ValueError(f"unbekanntes Modell: {args.model}")
        if gang.pricing is None:
            raise ValueError(f"Modell hat keinen versionierten Tarif: {args.model}")

        unknown = args.data_status == "unknown"
        usage = UsageRecord(
            input_tokens=None if unknown else args.input_tokens,
            cached_input_tokens=None if unknown else args.cached_input_tokens,
            cache_write_tokens=None if unknown else args.cache_write_tokens,
            output_tokens=None if unknown else args.output_tokens,
            reasoning_tokens=None if unknown else args.reasoning_tokens,
            tool_fees_usd=args.tool_fees_usd,
            service_tier=args.service_tier,
            data_status=args.data_status,
        )
        ergebnis = cost_for_gang(gang, usage).to_dict()
        ergebnis.update({"model_id": gang.model_id, "gang": gang.name})
        if args.json:
            _drucke_json(ergebnis)
        elif not ergebnis["known"]:
            print(f"{gang.model_id}: Usage unbekannt/ungemessen; keine Kostenschätzung")
        else:
            print(f"{gang.model_id}: ${ergebnis['total_usd']:.8f} USD ({args.data_status})")
            print(
                f"Tarif {ergebnis['pricing_version']} · geprüft {ergebnis['pricing_checked_at']} · "
                f"stale={ergebnis['pricing_stale']}"
            )
        return 0
    except Exception as e:
        print(f"Kostenberechnung fehlgeschlagen: {e}", file=sys.stderr)
        return 1


def _one_shot(prompt: str, db_path: Optional[str], als_json: bool) -> int:
    """Routet und führt einen Prompt aus (one-shot)."""
    try:
        from clutch.motorblock import MotorBlock
        fahrer = _fahrer_erstellen(db_path)
        block = MotorBlock()

        # Prüfen ob der gewünschte Provider verfügbar ist
        verfuegbar = block.verfuegbare_motoren()

        # Routing-Vorab-Check: Welcher Provider würde gewählt?
        profil = fahrer.strecke_analysieren(prompt)
        from clutch.scorer import get_scorer
        scorer = get_scorer()
        score_ergebnis = scorer.bewerte(prompt)
        config_vorschau = fahrer.kuppeln(profil, zweck=score_ergebnis.zweck)
        gewaehlter_provider = config_vorschau.provider

        if not verfuegbar.get(gewaehlter_provider, False):
            # Provider nicht verfügbar — route anzeigen statt Crash
            print(
                t("run.motor_nicht_verfuegbar", provider=gewaehlter_provider),
                file=sys.stderr,
            )
            print(t("run.routing_vorschau"), file=sys.stderr)
            print(f"  {t('route.gang'):<9} {config_vorschau.gang.name}", file=sys.stderr)
            print(f"  {t('route.provider'):<9} {gewaehlter_provider}", file=sys.stderr)
            print(f"  {t('route.zweck'):<9} {score_ergebnis.zweck}", file=sys.stderr)
            print(f"  {t('route.score'):<9} {score_ergebnis.score}/100", file=sys.stderr)
            return 2

        ergebnis = fahrer.fahren(prompt, handler=block.handler())

        if not ergebnis.erfolg:
            print(t("run.fahrt_fehlgeschlagen", ergebnis=ergebnis), file=sys.stderr)
            return 1

        output_text = ""
        if ergebnis.output is not None:
            output_text = getattr(ergebnis.output, "text", str(ergebnis.output))

        if als_json:
            _drucke_json({
                "output": output_text,
                "fahrt_id": ergebnis.fahrt_id,
                "gang": ergebnis.config.gang.name if ergebnis.config else None,
                "provider": ergebnis.config.provider if ergebnis.config else None,
                "latenz_sekunden": round(ergebnis.latenz_sekunden, 3),
                "total_tokens": ergebnis.total_tokens,
                "cost_usd": ergebnis.cost_usd,
                "usage_status": ergebnis.usage_status,
                "requested_effort": ergebnis.requested_effort,
                "effective_effort": ergebnis.effective_effort,
                "warnungen": ergebnis.warnungen,
            })
        else:
            print(output_text)

        return 0

    except Exception as e:
        print(t("error.ausfuehrung", e=e), file=sys.stderr)
        return 1


def _cmd_run(args: argparse.Namespace) -> int:
    """One-shot-Ausführung via 'run'-Subcommand."""
    return _one_shot(args.prompt, args.db, args.json)


def _cmd_serve(args: argparse.Namespace) -> int:
    """Startet die Web-Oberfläche (FastAPI + uvicorn).

    Benötigt: pip install clutch[web]
    """
    if not getattr(args, "web", True):
        print(t("error.serve_only_web"), file=sys.stderr)
        return 1

    host = getattr(args, "host", "127.0.0.1") or "127.0.0.1"
    port = getattr(args, "port", 8760) or 8760

    db_path = Path(args.db) if args.db else None

    try:
        from clutch.webapp import serve
    except ImportError:
        # Wird nur ausgelöst, wenn webapp.py selbst fehlt
        print(t("error.serve_webapp_missing"), file=sys.stderr)
        return 1

    try:
        serve(host=host, port=port, db_path=db_path)
        return 0
    except ImportError as e:
        print(t("error.serve_deps", e=e), file=sys.stderr)
        return 1
    except Exception as e:
        print(t("error.serve_start", e=e), file=sys.stderr)
        return 1


def _cmd_keys(args: argparse.Namespace) -> int:
    """Verwaltet lokale API-Keys (~/.clutch/credentials.json). Werte werden NIE angezeigt."""
    try:
        from clutch.credentials import CredentialStore
        store = CredentialStore()
        action = args.action

        if action == "list":
            namen = store.namen()
            if args.json:
                _drucke_json(namen)
            elif namen:
                print(t("keys.list_header"))
                for n in namen:
                    print(f"  {n}")
            else:
                print(t("keys.list_empty"))
            return 0

        if action == "set":
            if not args.name:
                print(t("keys.name_fehlt"), file=sys.stderr)
                return 1
            wert = args.value
            if wert is None:
                import getpass
                try:
                    wert = getpass.getpass(t("keys.wert_prompt", name=args.name)).strip()
                except Exception:
                    wert = sys.stdin.readline().strip()
            if not wert:
                print(t("keys.kein_wert"), file=sys.stderr)
                return 1
            store.set(args.name, wert)
            print(t("keys.gespeichert", name=args.name))
            return 0

        if action == "remove":
            if not args.name:
                print(t("keys.remove_name_fehlt"), file=sys.stderr)
                return 1
            ok = store.remove(args.name)
            if ok:
                print(t("keys.entfernt", name=args.name))
            else:
                print(t("keys.nicht_vorhanden", name=args.name))
            return 0 if ok else 1

        print(t("keys.unbekannte_aktion", action=action), file=sys.stderr)
        return 1

    except Exception as e:
        print(t("error.keys", e=e), file=sys.stderr)
        return 1


def _cmd_chat(args: argparse.Namespace) -> int:
    """Minimaler REPL — liest Zeilen von stdin, je Zeile one-shot."""
    db_path = args.db
    als_json = args.json

    print(t("chat.begruessung"))
    print()

    while True:
        try:
            zeile = input("Du> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{t('chat.auf_wiedersehen')}")
            return 0

        if not zeile:
            continue
        if zeile.lower() in {"exit", "quit", "beenden"}:
            print(t("chat.auf_wiedersehen"))
            return 0

        rc = _one_shot(zeile, db_path, als_json)
        if rc not in (0, 2):
            # Fehler, aber REPL weiterführen
            print(t("chat.fehler_repl"))

    return 0


# ---------------------------------------------------------------------------
# Argparse-Setup
# ---------------------------------------------------------------------------

_SUBCOMMANDS = {"route", "models", "resolve", "cost", "config", "stats", "run", "chat", "serve", "keys"}


def _build_subparser(subparsers: argparse._SubParsersAction) -> None:  # noqa: SLF001
    """Registriert alle Subparser."""

    # --- route ---
    p_route = subparsers.add_parser(
        "route",
        help="Routing-Entscheidung anzeigen (dry-run, kein LLM-Aufruf)",
    )
    p_route.add_argument("prompt", help="Der Prompt")
    p_route.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_route.add_argument("--db", metavar="PFAD", default=None)

    # --- models ---
    p_models = subparsers.add_parser(
        "models",
        help="Alle Gänge (Modelle) listen",
    )
    p_models.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_models.add_argument(
        "--no-discovery",
        action="store_true",
        help="Ollama-Discovery für diesen Aufruf deaktivieren",
    )
    p_models.add_argument("--db", metavar="PFAD", default=None)

    # --- resolve ---
    p_resolve = subparsers.add_parser(
        "resolve",
        help="Runner-, Self-, Familien- oder exakten Modellselektor auflösen",
    )
    p_resolve.add_argument("selector", help="Selektor, z. B. gpt, self, gpt5 oder ein exakter Modellname")
    p_resolve.add_argument("--runner", default=None, help="Optionaler Runner-Kontext")
    p_resolve.add_argument(
        "--require-claimable",
        action="store_true",
        help="Exit 4, wenn der Selektor bekannt, aber aktuell nicht claimbar ist",
    )
    p_resolve.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_resolve.add_argument("--db", metavar="PFAD", default=None)

    # --- cost ---
    p_cost = subparsers.add_parser(
        "cost",
        help="Kosten aus versioniertem Tarif und Token-Usage berechnen",
    )
    p_cost.add_argument("--model", required=True, help="Gangname oder API-Modell-ID")
    p_cost.add_argument("--input", dest="input_tokens", type=int, default=0)
    p_cost.add_argument("--cached-input", dest="cached_input_tokens", type=int, default=0)
    p_cost.add_argument("--cache-write", dest="cache_write_tokens", type=int, default=0)
    p_cost.add_argument("--output", dest="output_tokens", type=int, default=0)
    p_cost.add_argument("--reasoning", dest="reasoning_tokens", type=int, default=0)
    p_cost.add_argument("--tool-fees-usd", type=float, default=0.0)
    p_cost.add_argument(
        "--service-tier",
        choices=["default", "standard", "auto", "fast", "priority"],
        default="default",
    )
    p_cost.add_argument(
        "--data-status",
        choices=["assumed", "observed", "unknown"],
        default="assumed",
        help="CLI-Eingaben sind standardmäßig Annahmen",
    )
    p_cost.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_cost.add_argument("--db", metavar="PFAD", default=None)

    # --- config ---
    p_config = subparsers.add_parser(
        "config",
        help="Einstellungen lesen oder setzen (~/.clutch/cli_config.json)",
    )
    p_config.add_argument("key", help="Schlüssel")
    p_config.add_argument("value", nargs="?", default=None, help="Wert (leer = lesen)")
    p_config.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_config.add_argument("--db", metavar="PFAD", default=None)

    # --- stats ---
    p_stats = subparsers.add_parser(
        "stats",
        help="Nutzungsstatistik ausgeben",
    )
    p_stats.add_argument("--days", type=int, default=7, metavar="N",
                         help="Zeitraum in Tagen (Standard: 7)")
    p_stats.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_stats.add_argument("--db", metavar="PFAD", default=None)

    # --- run ---
    p_run = subparsers.add_parser(
        "run",
        help="One-shot: routet und führt aus",
    )
    p_run.add_argument("prompt", help="Der Prompt")
    p_run.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_run.add_argument("--db", metavar="PFAD", default=None)

    # --- chat ---
    p_chat = subparsers.add_parser(
        "chat",
        help="Interaktiver REPL (EOF oder 'exit' zum Beenden)",
    )
    p_chat.add_argument("--json", action="store_true", help="JSON-Ausgabe je Antwort")
    p_chat.add_argument("--db", metavar="PFAD", default=None)

    # --- serve ---
    p_serve = subparsers.add_parser(
        "serve",
        help="Web-Oberfläche starten (benötigt: pip install clutch[web])",
    )
    p_serve.add_argument(
        "--web",
        action="store_true",
        default=True,
        help="Web-UI starten (Standard: an)",
    )
    p_serve.add_argument(
        "--port",
        type=int,
        default=8760,
        metavar="PORT",
        help="Port für den Web-Server (Standard: 8760)",
    )
    p_serve.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help="Bind-Adresse (Standard: 127.0.0.1)",
    )
    p_serve.add_argument("--db", metavar="PFAD", default=None)

    # --- keys ---
    p_keys = subparsers.add_parser(
        "keys",
        help="Lokale API-Keys verwalten (~/.clutch/credentials.json)",
    )
    p_keys.add_argument("action", choices=["list", "set", "remove"],
                        help="list | set <NAME> [WERT] | remove <NAME>")
    p_keys.add_argument("name", nargs="?", default=None,
                        help="Key-Name, z.B. MOONSHOT_API_KEY")
    p_keys.add_argument("value", nargs="?", default=None,
                        help="Wert (leer = versteckte Eingabe)")
    p_keys.add_argument("--json", action="store_true", help="JSON-Ausgabe")
    p_keys.add_argument("--db", metavar="PFAD", default=None)

    # Das globale --lang darf aus ergonomischen Gründen auch hinter dem
    # Subcommand stehen (z.B. `clutch models --lang de`). SUPPRESS verhindert,
    # dass ein fehlender Subcommand-Wert einen vorher gesetzten globalen Wert
    # überschreibt.
    for subparser in (p_route, p_models, p_resolve, p_cost, p_config, p_stats, p_run, p_chat, p_serve, p_keys):
        subparser.add_argument(
            "--lang",
            metavar="CODE",
            choices=LANGS,
            default=argparse.SUPPRESS,
            help=f"Ausgabesprache ({', '.join(LANGS)})",
        )


def _build_top_parser() -> argparse.ArgumentParser:
    """Parser für direkte Aufrufe (Hilfe + globale Flags)."""
    parser = argparse.ArgumentParser(
        prog="clutch",
        description="clutch — Provider-neutraler LLM-Router",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=True,
        epilog=(
            "Beispiele:\n"
            "  clutch route \"Fix den Bug in auth.py\"\n"
            "  clutch models --json\n"
            "  clutch resolve gpt5 --json\n"
            "  clutch cost --model gpt-5.6-terra --input 100000 --output 10000 --json\n"
            "  clutch run \"Erkläre Quantenmechanik\"\n"
            "  clutch \"Erkläre Quantenmechanik\"\n"
            "  clutch stats\n"
            "  clutch config default_provider\n"
            "  clutch config default_provider anthropic\n"
            "  clutch chat\n"
        ),
    )
    parser.add_argument("--db", metavar="PFAD", default=None,
                        help="Pfad zur clutch.db (Standard: ~/.clutch/clutch.db)")
    parser.add_argument("--json", action="store_true",
                        help="Ausgabe als JSON (maschinenlesbar)")
    parser.add_argument(
        "--lang",
        metavar="CODE",
        default=None,
        choices=LANGS,
        help=f"Ausgabesprache ({', '.join(LANGS)})",
    )
    subparsers = parser.add_subparsers(dest="subcommand")
    _build_subparser(subparsers)
    return parser


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Entry-Point. Gibt Exit-Code zurück (0 = Erfolg)."""
    if argv is None:
        argv = sys.argv[1:]

    # Bereits vor argparse setzen, damit auch `--lang de --help` und die
    # Parser-Hilfetexte in der gewünschten Sprache erscheinen.
    for _i, _tok in enumerate(argv[:-1]):
        if _tok == "--lang":
            set_lang(argv[_i + 1])
            break

    # Wenn das erste nicht-Flag-Argument ein bekannter Subcommand ist,
    # normal parsen. Sonst: als positionales Prompt behandeln.
    # Werte von wert-tragenden Flags (--db/--lang) duerfen NICHT als
    # Positional zaehlen, sonst misslingt z.B. `clutch --lang de route ...`.
    _value_flags = {"--db", "--lang"}
    positional_tokens = []
    _i = 0
    while _i < len(argv):
        _tok = argv[_i]
        if _tok in _value_flags:
            _i += 2  # Flag + dessen Wert ueberspringen
            continue
        if _tok.startswith("-"):
            _i += 1
            continue
        positional_tokens.append(_tok)
        _i += 1
    first_positional = positional_tokens[0] if positional_tokens else None

    if first_positional is not None and first_positional not in _SUBCOMMANDS:
        # Direkter Prompt-Modus: alles nicht-Flag als Prompt zusammensetzen
        flags: list[str] = []
        prompt_parts: list[str] = []
        i = 0
        db_val: Optional[str] = None
        als_json = False
        lang_val: Optional[str] = None
        while i < len(argv):
            tok = argv[i]
            if tok == "--json":
                als_json = True
            elif tok == "--db" and i + 1 < len(argv):
                db_val = argv[i + 1]
                i += 1
            elif tok == "--lang" and i + 1 < len(argv):
                lang_val = argv[i + 1]
                i += 1
            elif tok.startswith("-"):
                flags.append(tok)
            else:
                prompt_parts.append(tok)
            i += 1
        if lang_val:
            set_lang(lang_val)
        prompt = " ".join(prompt_parts)
        if prompt:
            return _one_shot(prompt, db_val, als_json)
        # Kein Prompt -> Hilfe zeigen
        _build_top_parser().print_help()
        return 0

    # Normaler Subcommand-Modus
    parser = _build_top_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1

    # Sprache aus globalem Flag setzen (vor Subcommand-Dispatch)
    if getattr(args, "lang", None):
        set_lang(args.lang)

    sub = args.subcommand

    if sub == "route":
        return _cmd_route(args)
    elif sub == "models":
        return _cmd_models(args)
    elif sub == "resolve":
        return _cmd_resolve(args)
    elif sub == "cost":
        return _cmd_cost(args)
    elif sub == "config":
        return _cmd_config(args)
    elif sub == "stats":
        return _cmd_stats(args)
    elif sub == "run":
        return _cmd_run(args)
    elif sub == "chat":
        return _cmd_chat(args)
    elif sub == "serve":
        return _cmd_serve(args)
    elif sub == "keys":
        return _cmd_keys(args)
    elif sub is None:
        parser.print_help()
        return 0
    else:
        print(t("error.unbekannter_subcommand", sub=sub), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
