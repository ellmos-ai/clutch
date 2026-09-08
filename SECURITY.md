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

Falls Private Vulnerability Reporting im Repository noch nicht aktiviert ist, kontaktieren Sie das Sicherheitsteam direkt per E-Mail unter `security@ellmos.ai`, `support@lukasgeiger.com` oder `lukas@open-bricks.org` und veröffentlichen Sie keine Details in einem öffentlichen Issue.

### Reaktionszeit & SLA

- **Erstreaktion:** Innerhalb von **48 Stunden** an Werktagen.
- **Triage & Statusmeldung:** Innerhalb von **5 Werktagen** mit Bestätigung oder Einstufung.
- **Patch-Bereitstellung:** Kritische Sicherheitsbehebungen werden schnellstmöglich als Patch-Release bereitgestellt.

### Sicherheitsprinzipien & Laufzeit-Invarianten

- **Local-First Routing:** Alle Orchestrierungsentscheidungen, Sitzungsverläufe, Prompt-Bibliotheken und Lernzustände verbleiben lokal auf dem Rechner des Nutzers (`~/.clutch/`).
- **Sichere Credential-Verwaltung:** API-Schlüssel werden über Dateiberechtigungen (0600), Umgebungsvariablen oder OS-Keyring verwaltet; niemals Speicherung im Klartext im Repository oder Commit-Verlauf.
- **Null Telemetrie & Zero-Egress:** Es werden keinerlei Telemetrie-, Nutzungs- oder Tracking-Daten an externe Dritte übertragen. Netzwerkverkehr entsteht ausschließlich zu den vom Nutzer explizit konfigurierten Provider-Endpunkten (Anthropic, Google, Ollama, Kimi, OpenAI-kompatibel).
- **Prozessisolierung & Non-Elevation:** CLI- und Web-App-Routinen operieren ausschließlich im Benutzerkontext ohne erhöhte Rechte (Non-Elevation).
- **Fail-Closed Circuit Breaker:** Überlastete, ratenlimitierte oder gesperrte Modelle werden vorab blockiert und niemals unkontrolliert wiederholt.
- **Audit-Integrität:** Fahrtenbuch und Routing-Historie werden lokal in einer transaktionssicheren SQLite-Datenbank persistiert.
- **Multi-OS Parität:** Sicherheits- und Isolationseigenschaften gelten gleichermaßen unter Linux, Windows und macOS.

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

If private vulnerability reporting is not yet active, contact the security team directly via email at `security@ellmos.ai`, `support@lukasgeiger.com`, or `lukas@open-bricks.org` without posting confidential details publicly.

### Response SLA & Timeline

- **Initial Response:** Within **48 hours** on business days.
- **Triage & Assessment:** Within **5 business days** with confirmed reproduction and severity score.
- **Patch Availability:** Critical security fixes are prioritized for immediate patch release.

### Security Principles & Runtime Invariants

- **Local-First Routing:** All orchestration routing logic, session histories, prompt library entries, and learning states remain strictly local on the user's filesystem (`~/.clutch/`).
- **Secure Credential Storage:** API keys and credentials are handled via strict file permissions (0600), environment variables, or local configuration; never hardcoded, leaked, or tracked in git.
- **Zero Telemetry & Zero Egress:** No analytics, tracking, or telemetry data is transmitted to any third party. Outbound network traffic connects solely to user-configured LLM provider endpoints (Anthropic, Google, Ollama, Kimi, OpenAI-compatible).
- **Process Isolation & Non-Elevation:** CLI and web interfaces operate strictly within unprivileged user-level permissions without requiring administrative elevation.
- **Fail-Closed Circuit Breaker:** Exhausted, rate-limited, or blocked models fail safely and are routed around rather than repeatedly hammered.
- **Audit Integrity:** Trip logs and routing metrics are safely recorded in a transaction-protected local SQLite ledger.
- **Multi-OS Parity:** Security guarantees and permission boundaries apply consistently across Linux, Windows, and macOS.
