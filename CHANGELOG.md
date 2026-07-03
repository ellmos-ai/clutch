# Changelog

Alle wesentlichen Änderungen an **clutch** werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Packaging
- **PyPI-Vorbereitung (noch nicht veröffentlicht):** Distributionsname `clutch-router`
  (Import bleibt `clutch`; `clutch` auf PyPI vergeben). package-data erweitert um
  `locales/*.json` + `web/*.html` (sonst fehlten i18n + Web-UI im pip-Paket). Classifiers/
  keywords/URLs ergänzt. GitHub-Action `publish.yml` (PyPI Trusted Publishing/OIDC, triggert
  auf `v*`-Tags) — Release erfolgt erst nach der Testphase + einmaliger PyPI-Publisher-Einrichtung.

### Added
- **Web-UI: CLI-/Env-Spiegel (M6+):** Endpunkte `GET/POST /api/credentials` +
  `DELETE /api/credentials/{name}` und `GET/POST /api/config`; Sidebar-Panel „API-Schlüssel"
  zum Setzen/Löschen von Keys (Werte werden NIE angezeigt/zurückgegeben; nur Namen + Quelle
  env/store). Tests in `test_m12_web_settings.py` (inkl. Wert-Leak-Schutz).

### Fixed
- **Changelog-Hygiene:** Die historische `0.3.0-rc1`-Sektion steht jetzt vor
  dem finalen `0.3.0`-Release, und die initiale Testreferenz nennt die
  tatsächliche Datei `tests/test_clutch.py`.
- **Ollama-Remote-Host wurde ignoriert:** `OllamaMotor` lief bei Ausführung *und*
  Verfügbarkeitscheck stets gegen die bei Konstruktion gesetzte Basis-URL
  (Default `localhost:11434`) und ignorierte den per Discovery gesetzten
  `Gang.endpoint`. Dadurch war ein entdeckter Remote-Ollama-Host (z. B. im VPN)
  nie erreichbar. Jetzt bevorzugt der Motor `Gang.endpoint` und fällt nur ohne
  Endpoint auf die Basis-URL zurück; `MotorBlock.ausfuehren` prüft die
  Ollama-Verfügbarkeit gegen denselben Ziel-Host. Regressionstests in
  `test_ollama_endpoint.py`.

### Added
- **Ollama-Timeout konfigurierbar:** Der bisher fest auf 60 s gesetzte Basis-Timeout
  des `OllamaMotor` ist jetzt über den Konstruktor-Parameter `timeout_basis` bzw. die
  Env-Variable `CLUTCH_OLLAMA_TIMEOUT` (Sekunden) einstellbar. Grosse lokale Modelle
  (30B+) brauchen beim Kaltstart länger als der Cloud-orientierte Default; ohne
  Override bleibt das Verhalten unverändert (60 s). Tests in `test_ollama_endpoint.py`.

## [0.4.0] -- 2026-06-14

Großer Ausbau von der Library zur Routing-**Anwendung** (CLI + Web + API), Kimi-Anbindung,
Zweck-/bildbewusstes Routing, Modell-Discovery, Service-Layer, Credential-Store und i18n
(en/de/es/zh/ja/ru). 270 Tests grün.

### Added
- **App-Ausbau (DEVELOPMENT_PLAN.md M0–M7):** clutch wird von der Library zur Routing-Anwendung.
  - **M0 Engine:** `scorer.py` (Komplexitäts-Score 0–100 + Zweck-/Modalitätserkennung),
    `partner.py` (Cross-Agent-Delegation mit Budget-Zonen + Mensch-Eskalation), Tankuhr/Token-Fluss
    im Fahrer verdrahtet, Budget-Zonen-SSOT (orange=G1–G2), DB-Pfad nach `~/.clutch` (nicht ins Repo).
  - **M1 Kimi-API:** `OpenAICompatibleMotor` + `KimiApiMotor` (api.moonshot.ai/v1, `MOONSHOT_API_KEY`),
    Gänge `kimi-api-code`/`kimi-api-vision` mit voller Usage.
  - **M2 Zweck-Routing:** Gang-Auswahl nach `staerken`-Tags (coding/vision/...), bildbewusst
    (Bild-Anhang → Vision-Modell), respektiert Budget-Limit.
  - **M3 Discovery:** `discovery.py` (Ollama `/api/tags` lokal+remote, `/v1/models`, `custom_models.txt`).
  - **M4 CLI:** `cli.py` + `[project.scripts] clutch` (route/models/config/stats/run/chat).
  - **M5 Service-Layer:** `session_store.py` (Sessions+Verlauf), `prompt_library.py`
    (+PromptBoard-Import), `profile_manager.py` (user/zweck/toolset-Profile + Systemprompt-Toggle),
    `chat_runtime.py` (Konversation über dem Router) + `CLUTCH.md` (mitlieferbarer Systemprompt).
  - **M7 Toolsets:** `toolsets.py` (Tool-Permissions default-deny, ControlCenter-Katalog-Bridge,
    versendbares Toolset-Paket).
  - **M6 Web-UI:** `webapp.py` (FastAPI, optionale Dependency `clutch[web]`), `web/index.html`
    (Vanilla-JS-Chat mit Bild-Upload, Sessions, Stats, Systemprompt-Toggle), `clutch serve --web`.
  - **M8:** Migrationsanleitung „BACH übernimmt clutch" (`docs/BACH_MIGRATION.md`, gegatet).
  - **Phase 9 /bugsweep:** 3 Reviewer-Agenten (Security/Routing/Robustheit) → Fixes:
    zone_nummer fail-safe (unbekannt→restriktivste Zone), untrusted Web/API schließt agentische
    CLI-Motoren mit Auto-Approve aus, Vision-Warnung wenn kein Vision-Modell, webapp generische
    500-Fehler + Upload-Limit (10 MB), `loesche()` cursor-in-with, import_promptboard robust gegen
    kaputtes/fehlendes JSON, LIKE-Escape in Prompt-Suche. Regressionstests in `test_m9_bugsweep_fixes.py`.
  - **Credentials-Store:** `credentials.py` — lokaler API-Key-Speicher `~/.clutch/credentials.json`
    (zero-dep, 0600-Rechte). Auflösung Env → clutch-Store → BACH-`~/.credentials/<name>` (Interop).
    Motoren (Anthropic/Gemini/Kimi-API) nutzen den Resolver; CLI `clutch keys set|list|remove`
    (Werte nie angezeigt). **Kimi-API live verifiziert** (kimi-k2.7-code → PONG, Usage erfasst).
  - Tests: +~160 (test_m0..m10), Gesamtsuite **236 passed** (`py -m pytest`).
- **Kimi-Anbindung:** Drei Gänge für Moonshots Kimi ergänzt. (1) `kimi-cli` und
  `kimi-code` als agentische CLI-Motoren (`KimiCliMotor`/`KimiCodeMotor` in
  `motorblock.py`) — Subprozess im Print-Modus, Login via Moonshot-Account
  (kein API-Key), ohne Token-/Usage-Tracking. (2) `ollama-kimi-k2`
  (`kimi-k2.7-code:cloud`) als Rohmodell über den vorhandenen `OllamaMotor` —
  Token-Usage wird erfasst; läuft über Ollama **Cloud** (nicht lokal). Neue
  Tests in `tests/test_kimi_motoren.py` (Gang-Registrierung, Factory-Mapping,
  argv/Output-Parsing per gemocktem Subprozess, Fehlerpfad).
- `GLOSSARY.md` für die deutschen Code-Begriffe der Auto-Metapher.
- GitHub Actions Test-Workflow für Python 3.10 bis 3.12.

### Changed
- README-Quickstart, Projektstruktur und Testanleitung an das tatsächliche Paket `clutch` angepasst.
- Community-Workflows auf aktuelle Actions-Versionen aktualisiert.
- Default-Konfiguration in `clutch/config/` paketiert, damit Wheel-Installationen die Routing-Defaults enthalten.
- Pytest-Konfiguration auf `tests/` begrenzt, damit manuelle Provider-Smokes im Repo-Root nicht als Unit-Tests gesammelt werden.
- `TODO.md` um einen aktuellen Public-Readiness-Status ergänzt und `.gitignore` um ein explizites `*.pyc`-Muster erweitert.
- `llms.txt` um `Last-checked`, Audience und Suchphrasen für LLM-/Crawler-Discovery ergänzt.

## [0.3.0-rc1] -- 2026-03-15

### Changed
- Repo-Referenzen auf `ellmos-ai/clutch` aktualisiert
- BACH-interne Dokumente (BACH_EINHAENGEPUNKTE.md, BACH_INTEGRATION.md) entfernt
- Personenbezogene Daten bereinigt

### Fixed
- `.gitignore` um BACH-Dateien ergänzt

## [0.3.0] -- 2026-03-12

Erster öffentlicher Release als `ellmos-ai/clutch`.

### Added
- Provider-neutrale LLM-Orchestration mit Auto-Metapher (Fahrer, Getriebe, Kupplung, etc.)
- Multi-Provider-Support: Anthropic (Claude), Google (Gemini), Ollama (lokal), Claude Code
- Streckenanalyse (Task-Klassifikation) mit 10 Streckentypen (Feldweg bis Langstrecke)
- Getriebe: Modell-Registry mit 8 vordefinierten Gängen (G1--G5)
- Kupplung: Automatischer Modellwechsel basierend auf Strecke, Budget und Health
- Gas/Bremse: Reasoning-Level-Steuerung (0%--100%)
- Tankuhr: Budget-Tracking mit 4-Zonen-System (green/yellow/orange/red)
- Bordcomputer: Health-Monitor mit Circuit-Breaker pro Modell
- Fahrtenbuch: SQLite-basierte Metrik-Speicherung
- Fahrschule: Lernengine mit Epsilon-Greedy Exploration und Fitness-Scoring
- Tacho: Metriken-Erfassung während der Laufzeit
- Execution Patterns: Einzelfahrt, Kolonne (Chain), Team (Parallel), Schwarm (Bulk), Hybrid
- JSON-basierte Konfiguration (getriebe.json, strecken.json, kupplung.json, fitness_criteria.json)
- 13 initiale Unit-Tests (`tests/test_clutch.py`)
- README mit Architektur-Diagramm und Quick Start
- MIT-Lizenz
