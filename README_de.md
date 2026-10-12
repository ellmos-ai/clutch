> Diese kurze Einstiegsseite folgt der Archivierungsregel für Projektdokumentation. Direkter Vorgänger: die ausführliche `README_de.md` zum Ausgangscommit `67c5b72fd2ea6d1e91e47f363d8ab9f951b9fd44`. Sie ist mit korrigierten aktuellen Aussagen im [Archiv unter docs/archive/README_de-2026-10-12.md](docs/archive/README_de-2026-10-12.md) erhalten.

<p align="center">
  <img src="docs/assets/banner.svg" alt="clutch banner" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

![Version 0.6.3](https://img.shields.io/badge/version-0.6.3-blue)
[![CI](https://github.com/ellmos-ai/clutch/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ellmos-ai/clutch/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**clutch** ist eine Python-Bibliothek und CLI, die Aufgaben an konfigurierte Modellanbieter weiterleitet. Zusätzlich gibt es eine optionale FastAPI-Weboberfläche für die lokale Nutzung. Die Version bleibt 0.6.3.

## Installation und Start

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
python -m pip install -e .
clutch --help
```

Für die optionale Weboberfläche installiere zusätzlich `python -m pip install -e ".[web]"`. Die Entwicklungs- und Testumgebung steht in [CONTRIBUTING.md](CONTRIBUTING.md).

## Laufzeit- und Datengrenzen

Konfiguration, Zugangsdaten und Verlauf werden standardmäßig lokal gespeichert; einzelne Befehle können andere Pfade annehmen. An einen entfernten Anbieter gesendete Anfragen und Kontexte verlassen den lokalen Rechner und unterliegen dessen Bedingungen und Kontoeinstellungen. Gespeicherte API-Schlüssel sind unverschlüsselter Text; POSIX-Modus 0600 wird, soweit unterstützt, bestmöglich gesetzt. CLI-Kindprozesse übernehmen Berechtigungen und Umgebung des aufrufenden Kontos. Lokale Budgetzonen sind Schwellenwerte oder Schätzungen, keine Abrechnungsgrenzen des Anbieters. Die optionale Weboberfläche ist für lokale Nutzung gedacht; clutch bietet keine allgemeine Egress-Sperre, Prozess-Sandbox oder Zertifizierung für öffentliches Hosting. Die aktuelle HTTP-App liefert die HTML-Seite am Wurzelpfad aus, hat aber keine Routen für die darin referenzierten lokalen statischen Ressourcen; die vollständige Browseroberfläche ist daher nicht verifiziert.

Siehe [SECURITY.md](SECURITY.md), [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), [LICENSE](LICENSE) und die maschinenlesbare [llms.txt](llms.txt). Verwandte Werkzeuge sind eigenständige Repositories; Links im ausführlichen Archiv beschreiben belegte Beziehungen und behaupten keine Integration.

## Ausführliche Dokumentation und erhaltene Navigation

Der frühere Leitfaden mit 18 Abschnitten ist im [datierten Archiv](docs/archive/README_de-2026-10-12.md) erhalten. Die ursprünglichen Abschnittslinks bleiben hier verfügbar:

1. <a id="1-features"></a><a id="features"></a><a id="funktionen"></a>[Funktionen & Highlights](docs/archive/README_de-2026-10-12.md#1-features)
2. <a id="2-architecture"></a><a id="architecture"></a><a id="architektur"></a>[Architektur & Metaphern-Abbildung](docs/archive/README_de-2026-10-12.md#2-architecture)
3. <a id="3-target-personas--discoverability"></a><a id="target-personas--discoverability"></a><a id="zielgruppen--auffindbarkeit"></a>[Typische Einsatzbereiche](docs/archive/README_de-2026-10-12.md#3-target-personas--discoverability)
4. <a id="4-comparative-matrix-vs-alternatives"></a><a id="comparative-matrix-vs-alternatives"></a><a id="vergleichsmatrix-gegenueber-alternativen"></a>[Nutzungsarten & Grenzen](docs/archive/README_de-2026-10-12.md#4-comparative-matrix-vs-alternatives)
5. <a id="5-dual-mermaid-diagrams"></a><a id="dual-mermaid-diagrams"></a><a id="duale-mermaid-diagramme"></a>[Duale Mermaid-Diagramme](docs/archive/README_de-2026-10-12.md#5-dual-mermaid-diagrams)
6. <a id="6-governance--runtime-invariants"></a><a id="governance--runtime-invariants"></a><a id="governance--laufzeit-invarianten"></a>[Laufzeitumfang & Datengrenzen](docs/archive/README_de-2026-10-12.md#6-governance--runtime-invariants)
7. <a id="7-road-types"></a><a id="road-types"></a><a id="streckentypen"></a>[Streckentypen & Aufgabenklassifikation](docs/archive/README_de-2026-10-12.md#7-road-types)
8. <a id="8-installation"></a><a id="installation"></a>[Installation & Voraussetzungen](docs/archive/README_de-2026-10-12.md#8-installation)
9. <a id="9-quick-start"></a><a id="quick-start"></a><a id="kurzanleitung"></a>[Schnellstart & Kurzanleitung](docs/archive/README_de-2026-10-12.md#9-quick-start)
10. <a id="10-command-line-interface"></a><a id="command-line-interface"></a><a id="kommandozeilen-schnittstelle"></a>[Kommandozeilen-Schnittstelle](docs/archive/README_de-2026-10-12.md#10-command-line-interface)
11. <a id="11-api-keys--credentials"></a><a id="api-keys--credentials"></a><a id="api-keys--zugangsdaten"></a>[API-Keys & Zugangsdaten](docs/archive/README_de-2026-10-12.md#11-api-keys--credentials)
12. <a id="12-configuration"></a><a id="configuration"></a><a id="konfiguration"></a>[Konfiguration & Benutzer-Overlays](docs/archive/README_de-2026-10-12.md#12-configuration)
13. <a id="13-supported-providers"></a><a id="supported-providers"></a><a id="unterstuetzte-provider"></a>[Unterstützte Provider & Modell-Gänge](docs/archive/README_de-2026-10-12.md#13-supported-providers)
14. <a id="14-execution-patterns"></a><a id="execution-patterns"></a><a id="ausfuehrungsmuster"></a>[Ausführungsmuster](docs/archive/README_de-2026-10-12.md#14-execution-patterns)
15. <a id="15-ecosystem--sibling-tools"></a><a id="ecosystem--sibling-tools"></a><a id="verwandte-tools--oekosystem"></a>[Verwandte Tools & Ökosystem](docs/archive/README_de-2026-10-12.md#15-ecosystem--sibling-tools)
16. <a id="16-third-party-licenses--transparency"></a><a id="third-party-licenses--transparency"></a><a id="drittanbieter-lizenzen--transparenz"></a>[Deklarierte Abhängigkeiten & Lizenzumfang](docs/archive/README_de-2026-10-12.md#16-third-party-licenses--transparency)
17. <a id="17-security-policy--liability"></a><a id="security-policy--liability"></a><a id="sicherheitsrichtlinie--haftung"></a>[Sicherheitshinweise & rechtlicher Rahmen](docs/archive/README_de-2026-10-12.md#17-security-policy--liability)
18. <a id="18-verification--test-suite"></a><a id="verification--test-suite"></a><a id="verifikation--testsuite"></a>[Prüfungen & Testbefehle](docs/archive/README_de-2026-10-12.md#18-verification--test-suite)
