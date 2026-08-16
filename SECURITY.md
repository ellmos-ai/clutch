# Sicherheitsrichtlinie / Security Policy

## Deutsch

### Sicherheitslücken melden

Wenn Sie eine Sicherheitslücke in **clutch** finden, melden Sie diese bitte verantwortungsvoll:

1. **Kein öffentliches Issue eröffnen**
2. **GitHub Private Vulnerability Reporting verwenden** ([Security Advisories](https://github.com/ellmos-ai/clutch/security/advisories/new))
3. Beschreibung, Reproduktionsschritte und potenzielle Auswirkungen angeben

### So melden Sie ein Problem

1. Öffnen Sie im Repository: `Security` → `Advisories` → `New`
2. Tragen Sie Titel, Beschreibung, Schweregrad und betroffene Versionen ein
3. Reichen Sie die Meldung privat ein

Falls Private Vulnerability Reporting im Repository noch nicht aktiviert ist, kontaktieren Sie die Maintainer direkt über GitHub und veröffentlichen Sie keine Details in einem öffentlichen Issue.

### Sicherheitsprinzipien & Geltungsbereich

- **Local-First Routing:** Alle Orchestrierungsentscheidungen, Sitzungsverläufe, Prompt-Bibliotheken und Lernzustände verbleiben lokal auf dem Rechner des Nutzers (`~/.clutch/`).
- **Sichere Credential-Verwaltung:** API-Schlüssel werden über das OS-Keyring-Backend oder lokale Umgebungsvariablen verwaltet; keine Speicherung im Klartext im Repository.
- **Null Telemetrie:** Es werden keine Telemetrie- oder Tracking-Daten an externe Server gesendet. API-Aufrufe erfolgen ausschließlich direkt an die vom Nutzer konfigurierten LLM-Provider (Anthropic, Google, Ollama, Kimi, OpenAI-kompatibel).
- **Prozessisolierung:** CLI- und Web-App-Routinen operieren im Benutzerkontext ohne erhöhte Rechte (Non-Elevation).

### Reaktionszeit

Kritische Sicherheitsmeldungen werden vorrangig bearbeitet. Bitte geben Sie angemessene Zeit zur Behebung, bevor Details öffentlich diskutiert werden.

---

## English

### Reporting a Vulnerability

If you discover a security vulnerability in **clutch**, please report it responsibly:

1. **Do not open a public issue**
2. **Use GitHub Private Vulnerability Reporting** ([Security Advisories](https://github.com/ellmos-ai/clutch/security/advisories/new))
3. Include a detailed description, reproduction steps, and potential impact

### How to Report

1. Open in the repository: `Security` → `Advisories` → `New`
2. Fill in title, description, severity rating, and affected versions
3. Submit the advisory privately

If private vulnerability reporting is not yet active, contact the maintainers directly through GitHub without posting confidential details publicly.

### Security Principles & Scope

- **Local-First Routing:** All orchestration routing logic, session histories, prompt library entries, and learning states remain local on the user's filesystem (`~/.clutch/`).
- **Secure Credential Storage:** API keys and credentials are handled via the native OS keyring backend or environment variables; never hardcoded or tracked in git.
- **Zero Telemetry:** No analytics, tracking, or telemetry data is transmitted. Outbound requests connect solely to user-configured LLM provider endpoints (Anthropic, Google, Ollama, Kimi, OpenAI-compatible).
- **Process Isolation & Non-Elevation:** CLI and web interfaces operate strictly within user-level permissions without requiring administrative privileges.

### Response Timeline

Critical vulnerabilities are handled with top priority. Please allow reasonable coordination time before any public disclosure.
