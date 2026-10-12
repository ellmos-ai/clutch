# Security Policy

This policy describes the current source tree for clutch-router 0.6.3. It is not a support or maintenance commitment for a particular installed package or release.

## Reporting a vulnerability

Please do not publish exploit details, credentials, or private user data in a public issue. Use [GitHub Private Vulnerability Reporting](https://github.com/ellmos-ai/clutch/security/advisories/new). If that route is unavailable, contact the maintainers at security@open-bricks.org, security@ellmos.ai, support@lukasgeiger.com, or lukas@open-bricks.org.

Maintainers aim to acknowledge a report within 48 hours on business days and to provide a status update within five business days. These are response targets, not guaranteed service levels. Investigation and remediation depend on the report, reproduction, severity, and maintainer availability.

## Data and execution boundaries

- Routing requests sent to a remote model provider may contain prompts and context supplied by the caller. The selected provider's API, account configuration, and terms determine how that service handles the request.
- Configuration, credentials, history, and related state use the user's ~/.clutch directory by default; commands that accept explicit paths may use other locations.
- API keys saved in credentials.json are unencrypted text. The application attempts to apply POSIX mode 0600 where supported, but this is best effort and is not encryption or a cross-platform ACL guarantee.
- Some execution paths start provider or coding-agent command-line programs. Child processes inherit the invoking account's permissions and environment.
- Budget zones represent configured local thresholds and estimates. They do not cap provider billing.
- FastAPI and Uvicorn are optional web dependencies. The web interface is intended for local use; clutch does not provide a general outbound-network block, an execution sandbox, or a public-hosting security certification.

For project terms, see [LICENSE](LICENSE). For the direct dependency scope and upstream license references, see [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

# Sicherheitsrichtlinie

Diese Richtlinie beschreibt den aktuellen Quellstand von clutch-router 0.6.3. Sie ist keine Support- oder Wartungszusage für ein bestimmtes installiertes Paket oder Release.

## Sicherheitslücke melden

Veröffentliche keine Details zu einem möglichen Angriff, Zugangsdaten oder privaten Nutzerdaten in einem öffentlichen Issue. Nutze [GitHub Private Vulnerability Reporting](https://github.com/ellmos-ai/clutch/security/advisories/new). Falls dieser Weg nicht verfügbar ist, kontaktiere die Maintainer unter security@open-bricks.org, security@ellmos.ai, support@lukasgeiger.com oder lukas@open-bricks.org.

Die Maintainer bemühen sich, Meldungen innerhalb von 48 Stunden an Werktagen zu bestätigen und innerhalb von fünf Werktagen einen Status mitzuteilen. Das sind Reaktionsziele, keine garantierten Service-Level. Prüfung und Behebung hängen von Meldung, Reproduktion, Schweregrad und Verfügbarkeit der Maintainer ab.

## Daten- und Ausführungsgrenzen

- Anfragen an entfernte Modell-Provider können Prompts und vom Aufrufer übergebenen Kontext enthalten. Die API, Kontoeinstellungen und Bedingungen des ausgewählten Providers bestimmen dessen Verarbeitung.
- Konfiguration, Zugangsdaten, Verlauf und weitere Zustandsdaten liegen standardmäßig im Verzeichnis ~/.clutch des Nutzers. Befehle mit expliziter Pfadangabe können andere Orte verwenden.
- In credentials.json gespeicherte API-Schlüssel sind unverschlüsselter Text. Die Anwendung versucht, soweit unterstützt, POSIX-Modus 0600 zu setzen. Das ist eine Best-Effort-Maßnahme, keine Verschlüsselung und keine plattformübergreifende ACL-Garantie.
- Manche Ausführungspfade starten Provider- oder Coding-Agent-Kommandozeilenprogramme. Kindprozesse übernehmen Berechtigungen und Umgebung des aufrufenden Kontos.
- Budget-Zonen bilden konfigurierte lokale Schwellenwerte und Schätzungen ab. Sie begrenzen keine Provider-Abrechnung.
- FastAPI und Uvicorn sind optionale Web-Abhängigkeiten. Die Weboberfläche ist für lokale Nutzung gedacht; clutch bietet keine allgemeine Sperre ausgehender Netzwerkverbindungen, keine Ausführungs-Sandbox und keine Sicherheitszertifizierung für öffentliches Hosting.

Die Projektbedingungen stehen in [LICENSE](LICENSE). Umfang direkter Abhängigkeiten und Verweise auf Upstream-Lizenzdateien stehen in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).
