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
  Version 0.6.0. U4+ (Discovery/Probe/Katalogpflege) bleibt separat offen.

- [x] **M6 Web-UI: CLI- + Env-/Key-Verwaltung spiegeln** — Settings-Panel in der
  Web-Oberfläche, das `clutch keys` (set/list/remove, Werte nie anzeigen) und
  `clutch config` spiegelt und erkannte Env-Keys anzeigt. Endpunkte
  `/api/credentials` (Namen + Quelle) und `/api/config`. DONE 2026-07-28:
  gemeinsames, einklappbares Panel mit sicherem Credential-CRUD, Config-Liste,
  Editierformular und sichtbarem Erfolgs-/Fehlerstatus; laufende API-Motoren
  erkennen neu gespeicherte Keys ohne Serverneustart.
- [ ] **i18n ausbauen** — App-Strings (CLI + Web-UI) auf DE/EN + Standardsprachen
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
  `notaus`, 429-/Rate-Limit und agy-Leerausgabe werden offline getestet.
- [ ] Decide whether `clutch/config/` display strings should stay German or gain parallel
  English descriptions.
- [ ] Verify current provider model IDs before the next release. (Task 183)

## Routing- und Lern-Governance nach ArenaOS/HarnessRanger [2026-08-15] (Tasks 184–185)

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
- [ ] **Advisor-Pairing-Konzept fehlt (Task 185):** Keine Möglichkeit, ein Modell als
  Reviewer/Advisor einem anderen Modell zuzuordnen. Mindestens als
  Metadaten-Feld in FahrtConfig (`reviewer_gang: Optional[Gang]`).

### Auto-Discovery: Neue Modelle erkennen

- [x] **Ollama-Discovery:** `GET /api/tags` am konfigurierten Ollama-Endpoint
  abfragen → alle lokal installierten Modelle automatisch als Gänge
  registrieren (Name, Parameter-Größe, Quantisierung → Gang-Niveau ableiten).
  Sollte sowohl localhost als auch Remote-Endpoints (Mac Studio) unterstützen.
  DONE 2026-08-11: CLI `models` und Web `/api/models` lösen die Discovery
  on-demand aus; Name-Fallback, Parametergröße und Quantisierung werden geführt.
- [ ] **Provider-API-Discovery (Task 183):** Anthropic und OpenAI bieten `/v1/models`
  Endpoints. Verfügbare Modelle periodisch oder on-demand abfragen und
  mit getriebe.json abgleichen. Neue Modelle als "unbewertet" markieren,
  bis Fitness-Daten vorliegen.
- [ ] **Web-basierte Modell-Suche (Task 183):** Optionaler Mechanismus (z.B. via
  WebSearch oder eine kuratierte Modell-Registry-URL) um neue Modell-
  Releases zu entdecken. Ergebnis: Vorschlagsliste, die der Nutzer
  bestätigen oder verwerfen kann.
- [ ] **Versions-Tracking (Task 183):** Zu jedem Gang ein `discovered_at` und
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
- [ ] **Fallback bei unbekanntem Modell (Task 183/185):** Wenn ein Task ein Modell erfordert
  das nicht registriert ist → Discovery-Lauf triggern → wenn gefunden,
  automatisch registrieren → wenn nicht, Nutzer informieren.
- [ ] **Offline-Fähigkeit (Task 183):** Discovery ist optional. Ohne Netz oder API-Keys
  muss clutch mit dem statischen Katalog + custom_models.txt funktionieren.

## Audit-Abgleich 2026-09-05 — aktueller v0.6.0-Stand

Dieser Abschnitt ist die aktuelle Steuerungsebene für den Audit vom 2026-06-12.
Geprüft wurden der Quellstand `bcd1805`, die 0.6.0-Einträge im Changelog, die
aktuelle CI-/Paketkonfiguration und `374` gesammelte Tests. Der historische
Originaltext bleibt darunter inhaltlich nachvollziehbar, ist aber keine
aktuelle Aufgabenliste mehr.

### Behoben und am 2026-09-05 erneut belegt

- [x] **Token-/Kostenfluss im Fahrer:** `_verbuchen()` schreibt Token- und
  Kostendaten über `Tacho.update()` ins Fahrtenbuch; die Regressionstests
  `test_fahrer_verbucht_tokens_und_kosten` und
  `test_sqlite_migration_and_usage_cost_persistence` decken den Pfad ab.
- [x] **Tankuhr-Persistenz im regulären Fahrer-Flow:** `Fahrer` injiziert sein
  SQLite-Fahrtenbuch in `Tankuhr`; `stand()` aggregiert daraus Tages- und
  Monatskosten. Die In-Memory-Liste bleibt nur der bewusste Standalone-Fallback.
- [x] **Fahrer-DB-Pfad:** `Fahrer(db_path=...)` ist verdrahtet; der Default liegt
  unter `clutch_home()` statt im Repository. Die fokussierten Regressionstests
  verwenden temporäre Datenbanken; der ältere Integrationstest nutzt den
  User-Home-Default.
- [x] **Ungenutzte Importe:** Der aktuelle Quellbaum ist nach Abschluss von
  Task 174 Ruff-grün; die alten `asdict`-/`StreckenTyp`-/`Optional`-Treffer sind
  nicht mehr vorhanden.
- [x] **Python 3.13 und Ruff-CI:** Python 3.13 steht in CI-Matrix und
  `pyproject.toml`; Ruff ist konfiguriert und läuft vor Pytest. Die letzten zwei
  E741-Testtreffer wurden mit Task 174 behoben. Python 3.14 ist separat geparkt.
- [x] **Leeres Top-Level-`config/`:** Das historische Verzeichnis existiert im
  aktuellen Checkout nicht mehr; `clutch/config/` bleibt die Paketquelle.
- [x] **CHANGELOG-Reihenfolge/Testdatei:** Die Korrektur vom 2026-07-03 bleibt
  belegt. Die dort genannten `280` Tests sind ausdrücklich ein historischer
  Snapshot; aktueller Stand sind `374` gesammelte Tests.

### Noch offen — mit bestehendem TASKPLAN-Folgeauftrag

- [ ] **Budget-Zonen-SSOT (Task 175, geprüft 2026-09-05):** README,
  `kupplung.py` und `fitness_criteria.json` bleiben widersprüchlich.
- [ ] **Fahrtenbuch-Defaultpfad (Task 179, geprüft 2026-09-05):** Der direkte
  Aufruf `Fahrtenbuch()` verwendet weiterhin einen Pfad im Paketbaum.
- [ ] **ClaudeCodeMotor (Task 180, geprüft 2026-09-05):** Der Aufruf übergibt
  weiterhin kein `--model` und löst den Windows-CMD-Shim nicht explizit auf.
- [ ] **`Fahrtenbuch.statistik(gang=None)` (Task 181, geprüft 2026-09-05):**
  `GROUP BY gang` plus `fetchone()` liefert weiterhin nur eine Gruppe.
- [ ] **Persistentes Nutzerfeedback (Task 182, geprüft 2026-09-05):** Freitext
  und Bewertung werden weiterhin nur geloggt; nur explizite Eval-Labels werden
  bei vollständig gesetztem `quality_score`/`passed` gespeichert.
- [ ] **MotorBlock-Testvertrag (Task 186, geprüft 2026-09-05):** Es gibt heute
  Provider- und Availability-Tests, aber noch keine vollständige
  credential-freie Mock-Abdeckung aller Provider-Motoren.
- [ ] **Dependency-/requirements-Vertrag (Task 187, geprüft 2026-09-05):**
  `requirements.txt` dupliziert Paketabhängigkeiten; optionale Provider-SDKs
  sind weiterhin als harte Dependencies deklariert.

### Bewusst geparkt — am 2026-09-05 weiterhin reproduzierbar, kein eigener Task

- [ ] **Listen-Regex:** Die Zeichenklasse in `strecke.py` erkennt nummerierte
  Einträge wie `1. Schritt` weiterhin nicht zuverlässig.
- [ ] **Redundanter Gesperrt-Fallback:** `Fahrer.kuppeln()` prüft nach
  `Kupplung.einlegen()` weiterhin ein zweites Mal auf gesperrte Modelle.
- [ ] **Mutable-Default-Annotation:** `FahrtErgebnis.warnungen` nutzt weiterhin
  `None` plus `__post_init__` statt `field(default_factory=list)`.
- [ ] **Fitness-Gewichte:** `FitnessBewerter` lädt die Gewichte aus
  `fitness_criteria.json` weiterhin nicht automatisch.
- [ ] **Phantom-`fitness.json`:** Der Bordcomputer prüft weiterhin zuerst eine
  nicht ausgelieferte `fitness.json` und fällt dann auf die echte Datei zurück.
- [ ] **Gas/Bremse-Tabellenwerte:** Token- und Timeoutwerte aus `_STELLUNGEN`
  werden weiterhin direkt danach durch lineare Formeln ersetzt.
- [ ] **Future-Timeouts:** `future.result(timeout=...)` wird in Team und Schwarm
  weiterhin erst nach `as_completed()` aufgerufen.
- [ ] **Schwarm-Config:** `Schwarm` übernimmt weiterhin nicht automatisch
  `max_parallele_worker` und `worker_timeout_sekunden` aus `kupplung.json`.
- [ ] **Tote Fahrer-/Bridge-Config:** Mehrere historische Schlüssel bleiben
  ohne belegten Laufzeitkonsumenten beziehungsweise widersprüchlich.
- [ ] **Python 3.14:** Nicht in Matrix oder Classifier aufgenommen und ohne
  eigenständigen Kompatibilitätsnachweis bewusst nicht behauptet.
- [ ] **Statischer Typecheck:** Ruff ist aktiv; mypy/pyright bleibt eine
  separate, derzeit nicht priorisierte Tooling-Entscheidung.
- [ ] **Coverage-Reporting:** CI erzeugt weiterhin keinen Coverage-Bericht.
- [ ] **Lokale ignorierte Artefakte:** Cache-/DB-Artefakte sind kein
  Repositoryinhalt; ihre lokale Bereinigung bleibt außerhalb dieses Audits.
- [ ] **README-Streckentyp-Tabelle:** Die kompakte Haupttabelle führt
  `Prüfstrecke` und `Testfahrt` weiterhin nicht auf; die ausführliche Tabelle
  weiter unten enthält beide.
- [ ] **`sys.path.insert` in Tests:** Die historischen Repo-Root-Injektionen
  bestehen weiterhin und bleiben bis zu einer eigenen Test-Hygiene-Aufgabe.

## Audit 2026-06-12 — historischer Originalbefund

<details>
<summary>Originalaudit mit damaligen Zeilenangaben und Prioritäten</summary>

Der folgende Block ist ausschließlich historische Herkunftsevidenz. Sein
Checkbox-Status wird nicht mehr zur aktuellen Arbeitssteuerung verwendet.

Vollständiger Code-Audit (Paket `clutch/`, `config/`, `tests/`, Smoke-Scripts,
CI, Doku). Prioritäten: **hoch** = funktionaler Defekt, **mittel** = spürbare
Einschränkung, **niedrig** = Hygiene/Konsistenz.

### Fixes

- [x] **(hoch) Budget-Zonen dreifach inkonsistent definiert:** Behoben mit
  T-20260826-117243495. `clutch/config/fitness_criteria.json` enthält den
  dokumentierten Vertrag Grün G1–G5 / Gelb G1–G3 / Orange G1–G2 / Rot keine.
  `Bordcomputer` und `Kupplung` lesen beide die validierte Policy aus
  `clutch/budget_policy.py`; Rot stoppt das Routing explizit.
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
- [ ] **(mittel, Task 179) Fahrtenbuch-Default-Pfad bricht bei Wheel-Installation:**
  `Path(__file__).parent.parent / "data" / "clutch.db"` (`clutch/fahrtenbuch.py:109`)
  zeigt bei installiertem Paket nach `site-packages/data/`. Auf `platformdirs`
  (user_data_dir) oder ein konfigurierbares `db_path` mit cwd-Fallback umstellen.
- [ ] **(mittel, Task 180) ClaudeCodeMotor ignoriert die Modellwahl:** Der CLI-Aufruf
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
- [x] **(niedrig) Phantom-Datei `fitness.json`:** Mit T-20260826-117243495
  entfernt. Die Fitness- und Budgetkonfiguration wird ausschließlich aus
  `fitness_criteria.json` geladen; ein Regressionstest ignoriert eine zusätzlich
  vorhandene `fitness.json`.
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
- [ ] **(niedrig, Task 181) `Fahrtenbuch.statistik()` mit `gang=None` liefert
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

- [ ] **(mittel, Task 178) Python 3.13/3.14 unterstützen:** CI-Matrix
  (`.github/workflows/tests.yml:19`) endet bei 3.12; `pyproject.toml`-Classifiers
  ebenso. 3.13 (und nach Verifikation 3.14) ergänzen.
- [ ] **(mittel, Task 174/178) Lint-/Typecheck-Tooling einführen:** Kein ruff/flake8/mypy
  konfiguriert. `[tool.ruff]` in `pyproject.toml` + Lint-Step in
  `.github/workflows/tests.yml` würde u. a. die oben gelisteten toten Importe
  automatisch finden.
- [ ] **(mittel, Task 186) Tests für MotorBlock ergänzen:** `clutch/motorblock.py`
  (468 Zeilen, 4 Provider-Motoren) hat keinerlei Testabdeckung. Mit gemockten
  SDK-Clients/`requests` testbar ohne Credentials — deckt zugleich den
  bestehenden TODO-Punkt "provider availability checks" ab.
- [ ] **(niedrig) Coverage-Reporting in CI:** `pytest --cov=clutch` +
  Coverage-Artefakt im Workflow.
- [ ] **(niedrig, Task 187) `requirements.txt` konsolidieren:** Dupliziert die
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
- [ ] **(niedrig, Task 182) `Fahrer.feedback()` ist ein Stub:** Loggt nur
  (`clutch/fahrer.py:238–243`), persistiert aber nichts — `user_korrekturen`
  im Fahrtenbuch bleibt ungenutzt. Entweder ins Fahrtenbuch schreiben
  (Anschluss an Fahrschule-Qualitätsscore) oder als experimentell markieren.
- [ ] **(niedrig) `sys.path.insert`-Hacks in Tests entfernen:**
  `tests/test_*.py` patchen sich den Repo-Root in den Pfad — bei
  `pip install -e .` (wie in CI) unnötig.

</details>

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

## TASKWRITER-REVIEW-LOG — 2026-09-05

Dieser Readback dokumentiert den unveränderten Ausgangsstand vor TASKSOLVER
#174/#178. Aktuelle Abschlussbelege stehen im nachfolgenden Closeout.

- Der Checkout `master` steht sauber auf `bcd1805` und ist exakt zu
  `origin/master` synchron. Das öffentliche Repository hat keine offenen
  Issues, aber PR #5 (Budget-SSOT, BLOCKED), PR #6 (Provider-Resolver,
  CONFLICTING) und PR #7 (Signed Review Gate, BLOCKED) offen; der aktuelle
  PyPI-Release `v0.4.0` bleibt vom lokalen Source-Stand `0.6.0` getrennt.
- Read-only-Verifikation: `python -m pytest -q` ergibt **374 passed**;
  `compileall` ist grün. `ruff check .` meldet genau zwei E741-Fehler in
  `tests/test_m13_token_throughput.py:66,147`; deshalb ist der CI-Testjob trotz
  bestandener Tests rot. Es wurden keine Provider-APIs, Credentials oder
  Live-Modelle angesprochen.
- Die Tasks 174–187 erfassen den E741-CI-Blocker, die drei offenen PR-/Review-
  Gates, veraltete Auditbefunde, direkte Paket-/SQLite-Risiken, Provider-
  Discovery/Governance, MotorBlock-Tests und den Dependency-Vertrag. Die
  bereits im aktuellen Code belegten Tankuhr-/Fahrer-/Discovery-Funktionen
  bleiben als historische TODO-Korrektur in Task 178, nicht als Duplikat.

## TASKSOLVER-Closeout — 2026-09-05 — Tasks 174 und 178

- Task 174: Ausschließlich die beiden mehrdeutigen Comprehension-Variablen in
  `tests/test_m13_token_throughput.py` wurden umbenannt; Testsemantik und
  Fixture-Daten blieben unverändert (`f6ba73d`).
- Task 178: Der Audit von 2026-06-12 ist nun in 7 live belegte Erledigungen,
  7 offene Befunde mit bestehenden TASKPLAN-Aufträgen und 15 bewusst geparkte
  Befunde gegliedert. Der vom TASKWRITER übergebene Originalaudit bleibt
  eingeklappt als historische Herkunftsevidenz erhalten.
- Verifikation: `374 passed` (eine externe StarletteDeprecationWarning),
  `374 tests collected`, Ruff, Compileall, Diff-Check, Auditstruktur und
  UTF-8-/Umlautprüfung sind grün.
- Live-Readback: PR #5 und #7 stehen auf `BLOCKED`, PR #6 auf `DIRTY`. Der
  jüngste `tests.yml`-Lauf für `bcd1805` scheiterte in der Ruff-Stufe exakt an
  den beiden nun lokal behobenen E741-Treffern; ohne Push gibt es noch keinen
  Remote-Nachweis für `f6ba73d`.
- Offen bleiben insbesondere Tasks 175, 179–187 sowie die getrennten PR-/
  Review-Gates 176/177. Es erfolgten keine Provider-Aufrufe, Credential-Zugriffe,
  PR-Änderungen, Releases oder Pushes.
