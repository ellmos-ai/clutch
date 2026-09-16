# Sicherheitsrichtlinie / Security Policy

## Deutsch

### Unterstützte Versionen

| Version | Unterstützt | Anmerkung |
|---------|-------------|-----------|
| **0.6.x** | :white_check_mark: Aktiv | Aktuelle Haupt- und Wartungsversion |
| < 0.6.0 | :x: Veraltet | Bitte auf die aktuelle Version aktualisieren |

### Sicherheitslücken melden

Wenn Sie eine Sicherheitslücke in **clutch** finden, melden Sie diese bitte verantwortungsvoll:

1. **Kein öffentliches Issue eröffnen**
2. **GitHub Private Vulnerability Reporting verwenden** ([Security Advisories](https://github.com/ellmos-ai/clutch/security/advisories/new))
3. Beschreibung, Reproduktionsschritte und potenzielle Auswirkungen angeben

### So melden Sie ein Problem

1. Öffnen Sie im Repository: `Security` → `Advisories` → `New`
2. Tragen Sie Titel, Beschreibung, Schweregrad und betroffene Versionen ein
3. Reichen Sie die Meldung privat ein

Falls Private Vulnerability Reporting im Repository noch nicht aktiviert ist, kontaktieren Sie das Sicherheitsteam direkt per E-Mail unter `security@open-bricks.org`, `security@ellmos.ai`, `support@lukasgeiger.com` oder `lukas@open-bricks.org` und veröffentlichen Sie keine Details in einem öffentlichen Issue.

### Reaktionszeit & SLA

- **Erstreaktion:** Innerhalb von **48 Stunden** an Werktagen.
- **Triage & Statusmeldung:** Innerhalb von **5 Werktagen** mit Bestätigung oder Einstufung.
- **Patch-Bereitstellung:** Kritische Sicherheitsbehebungen werden schnellstmöglich als Patch-Release bereitgestellt.

### Sicherheitsprinzipien & Laufzeit-Invarianten

- **Local-First Routing:** Alle Orchestrierungsentscheidungen, Sitzungsverläufe, Prompt-Bibliotheken und Lernzustände verbleiben lokal auf dem Rechner des Nutzers (`~/.clutch/`).
- **Sichere Credential-Verwaltung:** API-Schlüssel werden über Dateiberechtigungen (0600), Umgebungsvariablen oder OS-Keyring verwaltet; niemals Speicherung im Klartext im Repository oder Commit-Verlauf.
- **Null Telemetrie & Zero-Egress:** Es werden keinerlei Telemetrie-, Nutzungs- oder Tracking-Daten an externe Dritte übertragen. Netzwerkverkehr entsteht ausschließlich zu den vom Nutzer explizit konfigurierten Provider-Endpunkten (Anthropic, Google, Ollama, Kimi, OpenAI-kompatibel).
- **Prozessisolierung & Non-Elevation (`RunAsInvoker`):** CLI- und Web-App-Routinen operieren ausschließlich im Benutzerkontext ohne erhöhte Rechte (Non-Elevation).
- **Fail-Closed Circuit Breaker:** Überlastete, ratenlimitierte oder gesperrte Modelle werden vorab blockiert und niemals unkontrolliert wiederholt.
- **Audit-Integrität:** Fahrtenbuch und Routing-Historie werden lokal in einer transaktionssicheren SQLite-Datenbank persistiert.
- **Multi-OS Parität:** Sicherheits- und Isolationseigenschaften gelten gleichermaßen unter Linux, Windows und macOS.

| Invariante | Kategorie | Beschreibung |
|---|---|---|
| `INV-LOCAL-01` | Provider-Agnostizismus & Zero Lock-in | Nahtloses Hot-Swapping zwischen Anthropic, Google Gemini, OpenAI, Ollama und Kimi ohne Herstellerbindung. |
| `INV-LOCAL-02` | 100% Local-First & Zero Egress | Alle Routing-Entscheidungen, Sitzungsverläufe und Metriken verbleiben lokal; null Telemetrie oder Datenabfluss. |
| `INV-UNPRIV-03` | Unprivilegierter Benutzermodus (`RunAsInvoker`) | CLI, Hintergrundprozesse und Web-App laufen vollständig im unprivilegierten Benutzerkontext ohne Administrator- oder Root-Rechte. |
| `INV-CIRCUIT-04` | Fail-Closed Circuit Breaker | Persistente Circuit-Breaker überdauern Prozesse in `~/.clutch/availability.json` und verhindern Quota-Hämmern. |
| `INV-OVERLAY-05` | Update-sichere Benutzer-Overlays | Benutzereinstellungen, Ausschlüsse und Aliase liegen in `~/.clutch/user_overrides.json` und überstehen Paket-Updates. |
| `INV-FALLBACK-06` | Rangierte Zwei-Alternativen-Fallbacks | Jede Routing-Entscheidung liefert einen primären Gang plus zwei gerankte Ausweich-Alternativen. |
| `INV-BUDGET-07` | Zweidimensionale Telemetrie & Budget | Verbindet finanzielle Dollar-Verbrauchszonen (`Tankuhr`) mit Echtzeit-Token-Durchsatzüberwachung. |
| `INV-PURPOSE-08` | Zweck- & Vision-Ausrichtung | Bild- und multimodale Aufgaben werden strikt an vision-fähige Modelle geleitet; Code-Aufgaben an Coding-Gänge. |
| `INV-LEDGER-09` | Transaktionssicheres SQLite-Audit-Ledger | Fahrtenbuch, Sitzungsverläufe und Prompts werden sicher in lokalen SQLite-Datenbanken mit ACID-Garantie persistiert. |
| `INV-SLA-10` | Plattformübergreifende Multi-OS-Parität & SLA | Identisches Verhalten unter Linux, Windows und macOS mit 48-Stunden-Sicherheits-Reaktions-SLA. |

---

## English

### Supported Versions

| Version | Supported | Notes |
|---------|-----------|-------|
| **0.6.x** | :white_check_mark: Active | Current stable release line |
| < 0.6.0 | :x: Unsupported | Please upgrade to the latest release |

### Reporting a Vulnerability

If you discover a security vulnerability in **clutch**, please report it responsibly:

1. **Do not open a public issue**
2. **Use GitHub Private Vulnerability Reporting** ([Security Advisories](https://github.com/ellmos-ai/clutch/security/advisories/new))
3. Include a detailed description, reproduction steps, and potential impact

### How to Report

1. Open in the repository: `Security` → `Advisories` → `New`
2. Fill in title, description, severity rating, and affected versions
3. Submit the advisory privately

If private vulnerability reporting is not yet active, contact the security team directly via email at `security@open-bricks.org`, `security@ellmos.ai`, `support@lukasgeiger.com`, or `lukas@open-bricks.org` without posting confidential details publicly.

### Response SLA & Timeline

- **Initial Response:** Within **48 hours** on business days.
- **Triage & Assessment:** Within **5 business days** with confirmed reproduction and severity score.
- **Patch Availability:** Critical security fixes are prioritized for immediate patch release.

### Security Principles & Runtime Invariants

- **Local-First Routing:** All orchestration routing logic, session histories, prompt library entries, and learning states remain strictly local on the user's filesystem (`~/.clutch/`).
- **Secure Credential Storage:** API keys and credentials are handled via strict file permissions (0600), environment variables, or local configuration; never hardcoded, leaked, or tracked in git.
- **Zero Telemetry & Zero Egress:** No analytics, tracking, or telemetry data is transmitted to any third party. Outbound network traffic connects solely to user-configured LLM provider endpoints (Anthropic, Google, Ollama, Kimi, OpenAI-compatible).
- **Process Isolation & Non-Elevation (`RunAsInvoker`):** CLI and web interfaces operate strictly within unprivileged user-level permissions without requiring administrative elevation.
- **Fail-Closed Circuit Breaker:** Exhausted, rate-limited, or blocked models fail safely and are routed around rather than repeatedly hammered.
- **Audit Integrity:** Trip logs and routing metrics are safely recorded in a transaction-protected local SQLite ledger.
- **Multi-OS Parity:** Security guarantees and permission boundaries apply consistently across Linux, Windows, and macOS.

| Invariant | Category | Description |
|---|---|---|
| `INV-LOCAL-01` | Provider Agnosticism & Zero Lock-in | Seamless hot-swapping across Anthropic, Google Gemini, OpenAI, Ollama, and Kimi without vendor lock-in. |
| `INV-LOCAL-02` | 100% Local-First & Zero Egress | All routing decisions, session history, and metrics remain on local disk; zero tracking or telemetry egress. |
| `INV-UNPRIV-03` | Non-Elevation User Mode (`RunAsInvoker`) | All CLI commands, web apps, and background routines operate strictly in unprivileged user space without admin/root. |
| `INV-CIRCUIT-04` | Fail-Closed Circuit Breakers | Persistent circuit breakers survive one-shot CLI processes and avoid hammering rate-limited providers. |
| `INV-OVERLAY-05` | Update-Safe User Overlays | User preferences, model exclusions, and aliases live in `~/.clutch/user_overrides.json` across package updates. |
| `INV-FALLBACK-06` | Dual-Alternative Ranked Fallbacks | Every routing decision provides a primary model plus two ranked alternatives for instantaneous failover. |
| `INV-BUDGET-07` | Two-Dimensional Telemetry & Budget | Combines financial USD consumption zones (`Tankuhr`) with real-time token throughput tracking. |
| `INV-PURPOSE-08` | Purpose & Vision Alignment | Vision and multimodal tasks are strictly routed to vision-capable models; code tasks match coding gears. |
| `INV-LEDGER-09` | Transactional SQLite Audit Ledger | All trips, execution records, chat sessions, and prompt library entries are safely stored in local ACID SQLite databases. |
| `INV-SLA-10` | Cross-Platform Multi-OS Parity & SLA | Identical behavior across Linux, Windows, and macOS with committed 48h security response SLA. |
