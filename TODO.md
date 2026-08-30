# TODO - clutch

Public-readiness was completed before the repository was published as
`ellmos-ai/clutch`. This file now tracks follow-up work for a public,
provider-neutral LLM orchestration library.

## Review 2026-07-04 (Modul-Review-Loop, Subagent-Review — alle 4 Funde gefixt)

- [x] **(hoch)** Web-API ohne jede Authentifizierung (Credential-/Config-CRUD offen)
  → DNS-Rebinding-Schutz (TrustedHostMiddleware), optionales Token-Gate
  (`CLUTCH_WEB_TOKEN`), Bind-Schutz in `serve()` (nicht-loopback ⇒ Token-Pflicht),
  CORS gehärtet. Tests in `test_webapp_security.py`.
- [x] **(mittel)** Circuit-Breaker las `consecutive_failures`, nutzte es nie —
  jetzt zusätzlicher Serien-Auslöser (Regressionstest).
- [x] **(mittel)** Fahrtenbuch-SQLite ohne WAL unter dem Web-Server → WAL +
  Busy-Timeout.
- [x] **(niedrig)** credentials.json chmod-Race → atomare Anlage mit 0600.
- [x] **(Folge)** Optional: das Web-Token beim Loopback-Start automatisch generieren und in die ausgelieferte UI injizieren — DONE 2026-07-28 (`secrets.token_urlsafe(32)` Auto-Generierung in `serve()`, UI-Token-Injizierung in `index()`, Fetch-Headers in `index.html` und Regressionstests).

## Current

- [x] **W195 / T-20260830-195164348 (U1-U3):** Persistente Modell-/Provider-
  Verfügbarkeit, update-festes Nutzer-Overlay und Routing-Wünsche/Ausschlüsse
  pro Aufruf einschließlich zweier JSON-Alternativen. DONE 2026-08-30 in
  Version 0.6.0. U4+ bleibt separat offen; der nachfolgende Katalogvertrag
  ersetzt keine echten Provider-I/O-Adapter oder Account-/Host-Probes.
- [x] **T-20260822-230246761 (Provider-Katalogvertrag):** Validierte, injizierbare
  Provider-Snapshots, deterministischer Diff und fünf getrennte Evidenzstufen
  für fail-closed Ausführungsauflösung. DONE 2026-08-30 im 0.6.1-Kandidaten auf
  PR #6 mit 16 Resolver-/Katalogtests und fünf Offline-Fixtures. Merge, erste
  Registry-Veröffentlichung und OneDrive-Projektion warten auf unabhängiges
  Review; fehlende Live-Evidenz wird nicht als Verfügbarkeit ausgegeben.

- [x] **M6 Web-UI: CLI- + Env-/Key-Verwaltung spiegeln** — Settings-Panel in der
  Web-Oberfläche, das `clutch keys` (set/list/remove, Werte nie anzeigen) und
  `clutch config` spiegelt und erkannte Env-Keys anzeigt. Endpunkte
  `/api/credentials` (Namen + Quelle) und `/api/config`. DONE 2026-07-28:
  gemeinsames, einklappbares Panel mit sicherem Credential-CRUD, Config-Liste,
  Editierformular und sichtbarem Erfolgs-/Fehlerstatus; laufende API-Motoren
  erkennen neu gespeicherte Keys ohne Serverneustart.
- [x] **i18n ausbauen** — App-Strings (CLI + Web-UI) auf DE/EN + Standardsprachen
  (es, zh, ja, ru) wie bei den MCP-Servern; Übersetzungen delegierbar (Sonnet/Haiku/agy,
  JSON-Locales). README in allen Sprachen. DONE 2026-08-11: gemeinsamer
  Locale-Bootstrap für die Web-UI, lokalisierte Statusmeldungen und CLI-Ausgaben.
- [ ] Keep German code identifiers as the stable domain language, but make all
  contributor-facing explanations bilingual or English-first.
- [x] Review `demo.py`, `live_test.py`, and `claude_code_test.py` as manual
  provider smoke scripts; keep them out of normal `pytest` collection.
  (Erledigt: `pyproject.toml` begrenzt `testpaths` auf `tests/`; README
  dokumentiert die Smoke-Scripts als manuelle Provider-Checks.)
- [x] Add focused tests for provider availability checks without requiring live
  Anthropic, Google, Ollama, or Claude Code credentials.
  DONE 2026-08-30: persistente Circuit-/Kontingentpfade, rote 5h/7d-Signale,
  `notaus`, 429-/Rate-Limit und agy-Leerausgabe werden offline getestet. Der
  0.6.1-Kandidat ergänzt unabhängige Provider-Dokumentation, API-Listung,
  Accountzugriff, Runner-Kompatibilität und Hostbereitschaft per Offline-Fixture.
- [ ] Decide whether `clutch/config/` display strings should stay German or gain parallel
  English descriptions.
- [ ] Verify current provider model IDs before the next release.

## Routing- und Lern-Governance nach ArenaOS/HarnessRanger [2026-08-15]

- [ ] Einen versionierten, redigierten Event-Vertrag für Routingläufe
  definieren: Eingabe-Fingerprint, gewählter Provider/Modus, beobachtete Kosten,
  Latenz, Fehlerklasse und **extern geliefertes** Ergebnislabel. Telemetrie darf
  nicht als Beweis für Aufgabenerfolg umgedeutet werden.
- [ ] Deterministischen Offline-Replay gegen feste Fälle ermöglichen. Live-
  Routing erzeugt höchstens einen unveränderlichen Kandidaten; es verändert
  keine Gewichte, Regeln oder Providerzuordnungen selbst.
- [ ] Promotion-Pipeline spezifizieren: Kandidat → Holdout-Evaluation → explizite
  Freigabe → begrenzter Canary → Readback → Rollback. Jede Stufe braucht einen
  Receipt und darf bei fehlendem/mehrdeutigem Outcome konservativ abbrechen.
- [ ] Strukturierte Streaming-Ereignisse und Kompaktierung so entwerfen, dass
  Entscheidungen, Toolergebnisse, Fehler und offene Aktionen erhalten bleiben;
  Rohinhalte und Geheimnisse werden vor Persistenz redigiert und durch harte
  Größen-/TTL-Grenzen begrenzt.
- [ ] Host-spezifische Integration über Adapter statt Kernverzweigungen:
  `detect`, `status`, `setup --dry-run`, `uninstall`; nur belegte Laufzeitpfade
  als unterstützt kennzeichnen, Scaffolds ausdrücklich als solche ausweisen.

## Modell-Erkennung & -Verwaltung (Feature-Block) [2026-06-12]

Clutch kennt aktuell nur statisch in `getriebe.json` hinterlegte Modelle. Das Ziel:
Modelle müssen **entdeckbar**, **aktualisierbar** und **nutzeranpassbar** sein.

### Lücken im aktuellen Modellkatalog

- [x] **Codex/GPT-Provider:** DONE 2026-07-28. Provider `openai` mit
  `OpenAIMotor`, `OPENAI_API_KEY` und aktuellen Gängen für `gpt-5.6-sol`,
  `gpt-5.6-terra` sowie das spezialisierte `gpt-5.3-codex` registriert.
  Der Motor nutzt den offiziellen Chat-Completions-Parameter
  `max_completion_tokens`.
- [x] **Moonshot/Kimi-API-Motor:** Kimi ist
  aktuell auf drei Wegen erreichbar — als agentische CLI (`kimi-cli`/`kimi-code`
  Motoren, erledigt) und als Rohmodell via Ollama Cloud (`ollama-kimi-k2`,
  erledigt). Sauberster Rohmodell-Weg ist `platform.moonshot.ai` /
  `api.moonshot.ai/v1` (OpenAI- UND Anthropic-kompatibel, volle Usage,
  ~$0.95/$4 pro M Token K2.6). DONE: Der generische
  **OpenAI-kompatible Motor** besitzt eine konfigurierbare `base_url`; Kimi-Gänge
  laufen über den `KimiApiMotor` mit `MOONSHOT_API_KEY` und echter Usage.
- [x] **Fable 5:** Claude Fable 5 (`claude-fable-5`) als **höchsten Gang
  (Spitzen-Niveau)** in `getriebe.json` aufgenommen.
  **ACHTUNG — frühere Beschreibung war falsch [U 2026-07-11]:** Hier stand
  "kreativer Gang (G3-G4 Niveau)". Fable 5 ist **kein Kreativmodell**, sondern
  das Modell für die **schwersten** Aufgaben: Mathematik/Beweisführung,
  wissenschaftliche Arbeit und Beweisführung, anspruchsvolle App-/Software-Entwicklung,
  Spieleentwicklung. Rolle laut interner Modell-Strategie:
  *"Fable = der Forscher, das Gehirn"* — Gehirn/Operator/Advisor/Orchestrator.
  **Kostenprofil beim Einsortieren beachten:** teuerstes Modell ($10/$50 pro MTok
  = teuerster kuratierter Anthropic-Gang) und Adaptive Thinking immer aktiv.
  Router-Regel: **höchster Gang, nur für das Schwerste — niemals als
  Default-Worker für Masse/Mechanik.** DONE 2026-07-28; G5, 1M Kontext und
  offizielle Preise hinterlegt.
- [x] **Gemini-Modelle aktualisiert:** DONE 2026-07-28. Flash nutzt die stabile
  offizielle ID `gemini-3.5-flash`; der aktuelle Pro-API-Weg ist
  `gemini-3.1-pro-preview`. Die ursprünglich geforderte ID
  `gemini-3.5-pro` existiert im offiziellen Google-Katalog nicht und wurde
  deshalb ausdrücklich nicht erfunden. Kosten und Kontextgrenzen sind
  aktualisiert.
- [x] **Remote-Ollama nicht abgebildet:** Endpoint sollte konfigurierbar sein
  (lokal vs. remote, z.B. via VPN). Über `CLUTCH_REMOTE_OLLAMA` gesetzt; siehe
  `discovery.REMOTE_OLLAMA`. Grössere lokale Modelle automatisch höher einstufen.
  DONE 2026-08-11: Laufzeit-Hostliste, normalisierte `/api/tags`-Abfrage und
  Endpoint-Weitergabe an den Gang.
- [ ] **Advisor-Pairing-Konzept fehlt:** Keine Möglichkeit, ein Modell als
  Reviewer/Advisor einem anderen Modell zuzuordnen. Mindestens als
  Metadaten-Feld in FahrtConfig (`reviewer_gang: Optional[Gang]`).

### Auto-Discovery: Neue Modelle erkennen

- [x] **Ollama-Discovery:** `GET /api/tags` am konfigurierten Ollama-Endpoint
  abfragen → alle lokal installierten Modelle automatisch als Gänge
  registrieren (Name, Parameter-Größe, Quantisierung → Gang-Niveau ableiten).
  Sollte sowohl localhost als auch Remote-Endpoints (Mac Studio) unterstützen.
  DONE 2026-08-11: CLI `models` und Web `/api/models` lösen die Discovery
  on-demand aus; Name-Fallback, Parametergröße und Quantisierung werden geführt.
- [ ] **Provider-API-Discovery:** Anthropic und OpenAI bieten `/v1/models`
  Endpoints. Verfügbare Modelle periodisch oder on-demand abfragen und
  mit getriebe.json abgleichen. Neue Modelle als "unbewertet" markieren,
  bis Fitness-Daten vorliegen.
- [ ] **Web-basierte Modell-Suche:** Optionaler Mechanismus (z.B. via
  WebSearch oder eine kuratierte Modell-Registry-URL) um neue Modell-
  Releases zu entdecken. Ergebnis: Vorschlagsliste, die der Nutzer
  bestätigen oder verwerfen kann.
- [ ] **Versions-Tracking:** Zu jedem Gang ein `discovered_at` und
  `last_verified` Timestamp speichern. Warnung wenn Modell-Info älter
  als N Tage (konfigurierbar, Default: 30).

### Nutzer-Verwaltung: Modelle hinzufügen/ändern/löschen

Drei Zugangswege, aufsteigend nach Komfort:

- [ ] **Stufe 1 — JSON direkt:** `getriebe.json` bleibt die Single Source of
  Truth. Fortgeschrittene Nutzer editieren direkt. Dokumentation mit
  Beispiel-Eintrag für neues Modell in CONTRIBUTING.md ergänzen.
- [ ] **Stufe 2 — Nutzerfreundliche .txt-Datei:** Neue Datei
  `config/custom_models.txt` mit einfacher Syntax:
  ```
  # Ein Modell pro Block, Leerzeile trennt Einträge
  name: mein-modell
  provider: ollama
  model_id: llama3:70b
  gang: 3
  endpoint: http://192.168.1.50:11434
  staerken: reasoning, code
  schwaechen: latenz
  ```
  Beim Start: custom_models.txt wird geparst und mit getriebe.json gemergt
  (custom überschreibt bei Namenskollision). Fehlerhafte Einträge loggen,
  nicht stillschweigend ignorieren.
- [ ] **Stufe 3 — GUI/Tray-App:** Kleines PySide6-Fenster oder System-Tray-
  Menü zum Verwalten der Modell-Registry:
  - Liste aller bekannten Modelle (aus getriebe.json + custom_models.txt + discovered)
  - Hinzufügen / Bearbeiten / Löschen mit Formularfeldern
  - "Discover"-Button: Ollama-Scan + API-Abfrage
  - "Test"-Button: Ping an Endpoint, Latenz messen
  - Export/Import der Konfiguration
  Erst nach Stufe 1+2 stabil umsetzen, nicht vorher.

### Architektur-Entscheidungen

- [x] **Getrennte Schichten:** `getriebe.json` (mitgelieferte Defaults) vs.
  `custom_models.txt` / `user_getriebe.json` (Nutzer-Overrides) vs.
  Discovery-Cache (auto-generiert). Merge-Reihenfolge:
  Defaults < Discovery < User-Overrides.
  DONE 2026-08-30 für die Nutzer-Schicht als
  `~/.clutch/user_overrides.json`; Discovery bleibt on-demand und U4 separat.
- [ ] **Fallback bei unbekanntem Modell:** Wenn ein Task ein Modell erfordert
  das nicht registriert ist → Discovery-Lauf triggern → wenn gefunden,
  automatisch registrieren → wenn nicht, Nutzer informieren.
- [ ] **Offline-Fähigkeit:** Discovery ist optional. Ohne Netz oder API-Keys
  muss clutch mit dem statischen Katalog + custom_models.txt funktionieren.

## Audit 2026-06-12

Vollständiger Code-Audit (Paket `clutch/`, `config/`, `tests/`, Smoke-Scripts,
CI, Doku). Prioritäten: **hoch** = funktionaler Defekt, **mittel** = spürbare
Einschränkung, **niedrig** = Hygiene/Konsistenz.

### Fixes

- [ ] **(hoch) Budget-Zonen dreifach inkonsistent definiert:** README
  (Orange = G1–G2, Green = G1–G5), `clutch/kupplung.py:136`
  (`zone_max = {"green": 5, "yellow": 3, "orange": 1, "red": 0}` → Orange nur G1)
  und `clutch/config/fitness_criteria.json` (`budget_zones`: green = [1,2,3],
  yellow = [1,2], orange = [1]) widersprechen sich. `Bordcomputer.max_gang_fuer_zone()`
  (`clutch/bordcomputer.py:130`) liest aus der JSON, `Kupplung.einlegen()` hardcodet.
  Eine Single Source of Truth festlegen (empfohlen: JSON), Kupplung darauf umstellen,
  README-Tabelle angleichen.
- [ ] **(hoch) Tankuhr wird im Fahrer-Flow nie befüllt:** `Fahrer.fahren()`
  (`clutch/fahrer.py:130–179`) ruft `Tankuhr.tanken()` nirgends auf, und die
  Token aus einem `MotorErgebnis` fließen nicht via `Tacho.update()` in den
  Fahrteintrag. Folge: Budget bleibt immer 0 USD / Zone "green",
  `total_tokens` immer 0 → Fahrschule und Token-Explosions-Erkennung lernen
  auf Nulldaten. Wenn der Handler ein `MotorErgebnis` zurückgibt, Tokens
  extrahieren, `tacho.update(fahrt_id, total_tokens=...)` und
  `tankuhr.tanken(gang, input, output)` aufrufen.
- [ ] **(mittel) Tankuhr nicht persistent:** `_kosten_log` ist eine reine
  In-Memory-Liste (`clutch/tankuhr.py:43`). Tages-/Monatslimits sind über
  Prozessgrenzen hinweg wirkungslos — jeder Neustart setzt das Budget auf 0.
  Kosten ins Fahrtenbuch (SQLite) schreiben und `stand()` daraus aggregieren.
- [ ] **(mittel) Fahrtenbuch-Default-Pfad bricht bei Wheel-Installation:**
  `Path(__file__).parent.parent / "data" / "clutch.db"` (`clutch/fahrtenbuch.py:109`)
  zeigt bei installiertem Paket nach `site-packages/data/`. Auf `platformdirs`
  (user_data_dir) oder ein konfigurierbares `db_path` mit cwd-Fallback umstellen.
- [ ] **(mittel) ClaudeCodeMotor ignoriert die Modellwahl:** Der CLI-Aufruf
  `["claude", "-p", ...]` (`clutch/motorblock.py:336`) übergibt kein
  `--model` — `config.model_id` ist wirkungslos, es läuft immer das
  Default-Modell der Session. Zusätzlich Windows-Problem: `claude` ist dort
  ein `.cmd`-Shim, `subprocess.run` ohne `shell=True`/vollen Pfad kann
  fehlschlagen (betrifft auch `ist_verfuegbar()`, Zeile 321).
- [ ] **(mittel) Fahrer akzeptiert keinen DB-Pfad:** `Fahrer.__init__`
  (`clutch/fahrer.py:69`) instanziiert `Fahrtenbuch()` ohne Parameter.
  `test_fahrer_integration` (`tests/test_clutch.py:284`) schreibt dadurch bei
  jedem Testlauf (auch in CI) eine echte `data/clutch.db` ins Repo.
  `db_path`-Parameter durchreichen und den Test auf tmp_path umstellen.
- [ ] **(niedrig) Regex für nummerierte Listen defekt:**
  `r"^\s*[-*\d+\.]\s+"` (`clutch/strecke.py:184`) ist eine Zeichenklasse —
  "1. Schritt" wird NICHT als Etappe erkannt (nach der Ziffer folgt "."
  statt Whitespace). Korrekt: `r"^\s*(?:[-*]|\d+\.)\s+"`.
- [ ] **(niedrig) Redundante/tote Gesperrt-Fallback-Logik in Fahrer:**
  `Fahrer.kuppeln()` (`clutch/fahrer.py:107–118`) prüft erneut auf gesperrte
  Modelle, obwohl `Kupplung.einlegen()` (`clutch/kupplung.py:147–153`) das
  bereits behandelt — der Block ist praktisch unerreichbar; darin außerdem
  ungenutzter Import `GasBremse` (Zeile 111). Entfernen oder begründen.
- [ ] **(niedrig) Falsche Default-Annotation:** `warnungen: list[str] = None`
  (`clutch/fahrer.py:45`) — auf `field(default_factory=list)` umstellen und
  den `__post_init__`-Workaround streichen.
- [ ] **(niedrig) Ungenutzte Importe:** `asdict` und `StreckenTyp` in
  `clutch/kupplung.py:22,26`; `Optional` in `clutch/gas_bremse.py:13`.
- [ ] **(niedrig) FitnessBewerter ignoriert Config-Gewichte:** Die `criteria`-
  Gewichte in `clutch/config/fitness_criteria.json` werden nie geladen —
  `FitnessBewerter.__init__` (`clutch/fahrschule.py:33`) hardcodet eigene
  Werte. Entweder Gewichte aus der JSON laden oder den `criteria`-Block
  als tot entfernen.
- [ ] **(niedrig) Phantom-Datei `fitness.json`:** `clutch/bordcomputer.py:183,195`
  sucht zuerst `fitness.json`, die weder im Repo existiert noch dokumentiert
  ist. Auf `fitness_criteria.json` vereinheitlichen.
- [ ] **(niedrig) Tote Tabellenwerte in GasBremse:** Die Token-/Timeout-
  Multiplikatoren in `_STELLUNGEN` (`clutch/gas_bremse.py:27–35`) werden in
  `stellung()` (Zeilen 71–72) immer durch lineare Interpolation überschrieben —
  Spalten 2–3 der Tabelle sind wirkungslos. Vereinfachen oder Interpolation
  zwischen Tabellenwerten implementieren.
- [ ] **(niedrig) Wirkungslose Future-Timeouts:** `future.result(timeout=...)`
  NACH `as_completed` (`clutch/patterns/team.py:57`,
  `clutch/patterns/schwarm.py:58`) ist wirkungslos, da die Future dort schon
  fertig ist. Timeout gehört auf `as_completed(futures, timeout=...)` —
  sonst blockiert ein hängender Worker unbegrenzt.
- [ ] **(niedrig) Schwarm-Config nicht verdrahtet:** `kupplung.json` →
  `schwarm.max_parallele_worker`/`worker_timeout_sekunden` wird von der
  `Schwarm`-Klasse (`clutch/patterns/schwarm.py:35–45`) nicht gelesen
  (Defaults 10/60 statt 10/120).
- [ ] **(niedrig) `Fahrtenbuch.statistik()` mit `gang=None` liefert
  willkürliche Gruppe:** GROUP BY gang + `fetchone()`
  (`clutch/fahrtenbuch.py:176–179`) gibt nur die erste Gruppierung zurück.
  Entweder über alle Gänge aggregieren oder `gang` verpflichtend machen.
- [ ] **(niedrig) Tote Fahrer-Config-Schlüssel:** `einfache_strecken_bypass`
  wird geladen aber nie verwendet (`clutch/fahrer.py:85`); `eskalation_erlaubt`,
  `gas_standard`, `standard_modell` und der komplette `bach_bridge`-Block in
  `clutch/config/kupplung.json` werden nirgends im Code referenziert.
  Implementieren oder entfernen. Zudem widersprechen sich
  `kupplung.json` → `fahrer.standard_modell: "claude-opus"` und
  `getriebe.json` → `fahrer_optionen.standard: "claude-code"`.

### Upgrades

- [ ] **(mittel) Python 3.14 unterstützen:** Python 3.13 ist seit 2026-08-30 in
  CI-Matrix und Paket-Classifiers enthalten und auf PR #6 grün. Python 3.14
  bleibt bis zur separaten Kompatibilitätsprüfung offen.
- [x] **(mittel) Lint-Tooling einführen:** Ruff ist in `pyproject.toml`
  konfiguriert und läuft in `.github/workflows/tests.yml`; PR #6 ist grün.
  Ein statischer Typecheck bleibt eine unabhängige mögliche Erweiterung.
- [x] **(mittel) Tests für MotorBlock ergänzen:** Gemockte Motor-/SDK-, CLI- und
  Remote-Ollama-Pfade werden ohne Credentials getestet; zusätzliche
  Provider-Katalogtests prüfen die fünf Evidenzstufen fail-closed.
- [ ] **(niedrig) Coverage-Reporting in CI:** `pytest --cov=clutch` +
  Coverage-Artefakt im Workflow.
- [ ] **(niedrig) `requirements.txt` konsolidieren:** Dupliziert die
  Dependencies aus `pyproject.toml`. Entweder löschen (pip install -e . reicht)
  oder als generierte Lock-Datei kennzeichnen.
- [ ] **(niedrig) `dependencies` prüfen:** `anthropic`/`google-genai` sind
  harte Dependencies, werden aber nur lazy importiert (`clutch/motorblock.py:113,183`).
  Kandidaten für `[project.optional-dependencies]` (z. B. `clutch[anthropic]`,
  `clutch[google]`) — Kern bliebe dependency-arm (nur `requests`).

### Änderungen

- [ ] **(mittel) Leeres Top-Level-`config/`-Verzeichnis entfernen:** Es ist
  leer und kollidiert konzeptionell mit `clutch/config/` (der echten
  Config-Quelle laut README). Verwirrt Contributor und Audits.
- [ ] **(niedrig) Lokale Artefakte aufräumen:** `__pycache__/` (Root, Paket,
  tests, patterns), `.pytest_cache/` und `data/clutch.db` liegen im
  OneDrive-Ordner (Sync-Last). Sie sind korrekt gitignored, sollten aber
  lokal gelöscht werden; `data/clutch.db` entsteht durch Fix
  "Fahrer akzeptiert keinen DB-Pfad" künftig nicht mehr.
- [x] **(niedrig) CHANGELOG-Inkonsistenzen:** Erledigt 2026-07-03:
  Der historische `[0.3.0-rc1] -- 2026-03-15`-Abschnitt steht jetzt vor
  `[0.3.0] -- 2026-03-12`; die initiale Testreferenz nennt
  `tests/test_clutch.py` statt des alten `test_kupplung.py`-Namens.
  Aktueller Smoke: `python -m pytest --collect-only -q` sammelt 280 Tests.
- [ ] **(niedrig) README-Architekturdiagramm vs. Code:** Diagramm nennt
  "G2: Flash, G4: Gemini Pro" als feste Zuordnung — konsistent mit
  `getriebe.json`, aber die Road-Types-Tabelle (README) listet 8 Typen,
  `strecken.json`/`StreckenTyp` kennen 10 (+ `pruefstrecke`, `testfahrt`,
  `unbekannt`). Englische Tabelle um die fehlenden Typen ergänzen (die
  deutsche Tabelle hat sie bereits).
- [ ] **(niedrig) `Fahrer.feedback()` ist ein Stub:** Loggt nur
  (`clutch/fahrer.py:238–243`), persistiert aber nichts — `user_korrekturen`
  im Fahrtenbuch bleibt ungenutzt. Entweder ins Fahrtenbuch schreiben
  (Anschluss an Fahrschule-Qualitätsscore) oder als experimentell markieren.
- [ ] **(niedrig) `sys.path.insert`-Hacks in Tests entfernen:**
  `tests/test_*.py` patchen sich den Repo-Root in den Pfad — bei
  `pip install -e .` (wie in CI) unnötig.

## STATUS

| Category | Status | Notes |
|----------|--------|-------|
| Secrets | PASS | Gate check found no secret patterns in tracked files. |
| Private Data (PII) | PASS | Gate check found no known PII patterns. |
| .gitignore | PASS | Minimum release entries are present, including explicit `*.pyc`. |
| Language (English) | PASS | README is English-first; German domain terms are intentional. |
| BACH Internals | PASS | BACH-internal release blocker files are absent. |
| Database Files | PASS | No tracked `.db` files. |
| README.md | PASS | Public README is present. |
| LICENSE | PASS | MIT license is present. |
| Overall | READY | Public repository is already published; current follow-ups are non-blocking. |

## Done

- [x] Removed BACH-internal public-readiness blockers before publication.
- [x] Kept German identifiers as intentional domain language.
- [x] Published public repository under `ellmos-ai/clutch`.
- [x] Added `llms.txt` for LLM crawler discovery.
- [x] Added `GLOSSARY.md` for contributor orientation.
