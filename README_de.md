<p align="center">
  <img src="docs/assets/banner.svg" alt="clutch banner" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

> Provider-neutrale LLM-Orchestrierungsengine und Modell-Router mit automatischem Lernen

[![Version 0.6.3](https://img.shields.io/badge/Version-0.6.3-orange.svg)](https://github.com/ellmos-ai/clutch/releases)
[![CI](https://img.shields.io/badge/CI-bestanden-brightgreen.svg)](https://github.com/ellmos-ai/clutch/actions)
[![Pytest](https://img.shields.io/badge/Pytest-415%20bestanden-brightgreen.svg)](https://github.com/ellmos-ai/clutch)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Plattformen](https://img.shields.io/badge/Plattformen-Linux%20%7C%20Windows%20%7C%20macOS-blue.svg)](https://github.com/ellmos-ai/clutch)
[![Lizenz: MIT](https://img.shields.io/badge/Lizenz-MIT-green.svg)](LICENSE)
[![Provider](https://img.shields.io/badge/Provider-Anthropic%20%7C%20Gemini%20%7C%20OpenAI%20%7C%20Ollama%20%7C%20Kimi-purple.svg)](https://github.com/ellmos-ai/clutch)
[![Drittanbieter-Lizenzen: Geprüft](https://img.shields.io/badge/Drittanbieter--Lizenzen-Gepr%C3%BCft-brightgreen.svg)](THIRD_PARTY_LICENSES.md)
[![Marketing-Log: Aktiv](https://img.shields.io/badge/Marketing--Log-Aktiv-blue.svg)](MARKETING-LOG.txt)
[![Sicherheits-SLA: 48h](https://img.shields.io/badge/Sicherheits--SLA-48h%20Antwort%20%7C%205d%20Triage-blue.svg)](SECURITY.md)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Sicherheit: Local-First](https://img.shields.io/badge/Sicherheit-Local--First-green.svg)](SECURITY.md)
[![Privatsphäre: Zero-Egress](https://img.shields.io/badge/Privatsph%C3%A4re-Zero--Egress-success.svg)](SECURITY.md)
[![Non-Elevation](https://img.shields.io/badge/Elevation-User--Mode-informational.svg)](SECURITY.md)
[![Ökosystem: ellmos-ai](https://img.shields.io/badge/%C3%96kosystem-ellmos--ai-blue.svg)](https://github.com/ellmos-ai)
[![Dachorganisation: open-bricks](https://img.shields.io/badge/Dachorganisation-open--bricks-purple.svg)](https://github.com/open-bricks)
[![Discovery: llms.txt](https://img.shields.io/badge/Discovery-llms.txt-blue.svg)](llms.txt)

**clutch** (deutsch: *Kupplung*) verwendet eine intuitive automobile Fahrmetapher, um Aufgaben intelligent an optimale LLM-Modelle verschiedener Anbieter weiterzuleiten. Das System analysiert Aufgabenkomplexität und -zweck, wählt die passende Gangstufe und das ideale Reasoning-Level, verfolgt Budgets mit einer Vier-Zonen-Tankuhr, setzt persistente Circuit-Breaker durch und lernt aus Erfahrungen. Verwendbar als **Bibliothek**, **CLI** oder **lokale Web-App**.

> [!NOTE]
> Für KI-Agenten, Crawler und automatisierte Indexierer stehen maschinenlesbare Metadaten und Entdeckungskontexte in [llms.txt](llms.txt) bereit.

---

## Schnellnavigation

1. [Funktionen & Highlights](#1-features)
2. [Architektur & Metaphern-Abbildung](#2-architecture)
3. [Zielgruppen & Auffindbarkeit](#3-target-personas--discoverability)
4. [Vergleichsmatrix gegenüber Alternativen](#4-comparative-matrix-vs-alternatives)
5. [Duale Mermaid-Diagramme](#5-dual-mermaid-diagrams)
6. [Governance- & Laufzeit-Invarianten](#6-governance--runtime-invariants)
7. [Streckentypen & Aufgabenklassifikation](#7-road-types)
8. [Installation & Voraussetzungen](#8-installation)
9. [Schnellstart & Kurzanleitung](#9-quick-start)
10. [Kommandozeilen-Schnittstelle (CLI)](#10-command-line-interface)
11. [API-Keys & Zugangsdaten](#11-api-keys--credentials)
12. [Konfiguration & Benutzer-Overlays](#12-configuration)
13. [Unterstützte Provider & Modell-Gänge](#13-supported-providers)
14. [Ausführungsmuster](#14-execution-patterns)
15. [Verwandte Tools & Ökosystem](#15-ecosystem--sibling-tools)
16. [Drittanbieter-Lizenzen & Transparenz](#16-third-party-licenses--transparency)
17. [Sicherheitsrichtlinie & Haftung](#17-security-policy--liability)
18. [Verifikation & Testsuite](#18-verification--test-suite)

---

<a id="1-features"></a>
<a id="features"></a>
<a id="funktionen"></a>
## 1. Funktionen & Highlights

- **Provider-neutral** -- Anthropic (Claude), Google (Gemini), OpenAI (GPT/Codex), Ollama (lokal & remote), Claude Code, **agy via companion-for-agy** sowie **Kimi** (Moonshot API / CLI / Ollama Cloud)
- **Automatisches Routing** -- analysiert Aufgabenkomplexität *und Zweck* (Coding, Vision, Recherche, Bulk) und wählt optimales Modell + Reasoning-Level
- **Zweck- und Vision-bewusst** -- leitet Bild-/Dokumenteingaben an vision-fähige Modelle weiter; passt Aufgaben an Modellstärken an
- **CLI + Web-UI** -- `clutch route/run/chat/models/stats`, plus optionale FastAPI-Web-Chat-Oberfläche (`clutch serve --web`)
- **Credential-Speicher** -- API-Keys sicher in `~/.clutch/credentials.json` ablegen (`clutch keys ...`); Umgebungsvariablen haben Vorrang
- **Modell-Erkennung** -- automatische Erkennung installierter Ollama-Modelle (lokal/remote) und OpenAI-kompatibler `/v1/models`-Endpunkte
- **Budget-Tracking** -- Tankuhr mit vier Zonen (grün/gelb/orange/rot) mit täglichen und monatlichen Limits
- **Lernengine** -- Fitness-Scoring und Epsilon-Greedy-Exploration, die das Routing im Laufe der Zeit verbessert
- **Ausführungsmuster** -- Einzelaufgaben, Ketten (Kolonne), parallele Teams und Schwarm-Verarbeitung
- **Persistente Verfügbarkeit** -- Circuit-Breaker und Kontingentsperren überleben One-Shot-Prozesse; rote Anthropic-5h/7d-Fenster, `notaus` und Provider-Rate-Limits werden bis zum Reset umgangen
- **Update-festes Nutzer-Overlay** -- Modelle deaktivieren, Modelle/Provider bevorzugen, Gangstufen begrenzen, Aliase und Modellkosten in `~/.clutch/user_overrides.json` pflegen
- **Beleggestützte Ausführungsselektoren** -- Runner-, Familien- und exakte Modellbindungen ohne stille Ersetzung auflösen; Provider-Adapter halten fünf Verfügbarkeitsstufen getrennt
- **Routing-Wünsche pro Aufruf** -- Gänge bevorzugen oder ausschließen, Zweck/Effort überschreiben und zwei gerankte Fallback-Alternativen erhalten
- **Gesundheitsüberwachung** -- persistente Circuit-Breaker, Latenz-Tracking, Overkill/Token-Explosion-Alarme, Provider-Failover
- **SQLite-Metriken** -- persistentes Fahrtenbuch, Chat-Sitzungen, Prompt-Bibliothek und Profile

---

<a id="2-architecture"></a>
<a id="architecture"></a>
<a id="architektur"></a>
## 2. Architektur & Metaphern-Abbildung

Das gesamte System folgt einer **Auto-/Fahrmetapher**:

```
                    +----------------------------------+
                    |            FAHRER                 |
                    |        (Driver / Orchestrator)    |
                    |     Any LLM: Opus, Gemini, ...   |
                    +--------+----------+--------------+
                             |          |
                +------------+          +-------------+
                |                                     |
        +-------v--------+                   +--------v-------+
        |    STRECKE      |                   |    GETRIEBE    |
        | (Road / Task    |                   | (Gearbox /     |
        |  Analysis)      |                   |  Model Registry|
        +----------------+                   |                |
                                              | G1: Haiku      |
        +----------------+                   | G2: Flash      |
        |   GAS / BREMSE  |                   | G3: Sonnet     |
        | (Throttle/Brake |                   | G4: Gemini Pro |
        |  Reasoning Lvl) |                   | G5: Opus       |
        +----------------+                   | + Ollama local |
                                              +----------------+
        +----------------+
        |    KUPPLUNG     |    +------------+    +-------------+
        | (Clutch / Model |    |   TACHO    |    |  TANKUHR    |
        |  Switching)     |    | (Metrics)  |    | (Budget)    |
        +----------------+    +------------+    +-------------+
```

| Komponente | Rolle | Modul |
|-----------|------|--------|
| **Fahrer** (Driver) | Orchestrator -- wählt Modell, Reasoning und Ausführungsmuster | `fahrer.py` |
| **Strecke** (Road) | Aufgabenanalyse und -klassifikation | `strecke.py` |
| **Getriebe** (Gearbox) | Provider-neutrale Modell-Registry | `getriebe.py` |
| **Gang** (Gear) | Ein konkretes Modell (G1--G5) | `getriebe.py` |
| **Gas / Bremse** (Throttle/Brake) | Reasoning-Level (0--100%) | `gas_bremse.py` |
| **Kupplung** (Clutch) | Schaltmechanismus zwischen Modellen | `kupplung.py` |
| **MotorBlock** (Engine) | Einheitliche API-Aufrufschicht | `motorblock.py` |
| **Tacho** (Speedometer) | Metriken-Erfassung | `tacho.py` |
| **Tankuhr** (Fuel Gauge) | Budget-Tracking (4 Zonen) | `tankuhr.py` |
| **Bordcomputer** (Onboard Computer) | Health-Monitor, Circuit-Breaker | `bordcomputer.py` |
| **Fahrtenbuch** (Trip Log) | SQLite-Metrikspeicher | `fahrtenbuch.py` |
| **Fahrschule** (Driving School) | Lernengine / Auto-Tuning | `fahrschule.py` |
| **Token-Throughput** (Schattenzone) | Anthropic 5h/7d-Rate-Limit-Fenster als zweite Zone -- siehe [`docs/STAGED-MIGRATION.md`](docs/STAGED-MIGRATION.md) | `token_throughput.py` |

---

<a id="3-target-personas--discoverability"></a>
<a id="target-personas--discoverability"></a>
<a id="zielgruppen--auffindbarkeit"></a>
## 3. Zielgruppen & Auffindbarkeit

`clutch` wurde für vier technische Zielgruppen konzipiert, die präzise Kontrolle über Modelldispatch, Kostenkalkulation und strikte Null-Telemetrie benötigen:

### `[PERSONA-01]` Autonome KI-Agenten-Entwickler & Multi-Agenten-Architekten
- **Kontext:** Aufbau von Multi-Agenten-Systemen, kontinuierlichen Hintergrund-Workern und werkzeuggestützten Agenten-Schleifen (z. B. LangGraph, CrewAI, AutoGen oder native CLI-Agenten).
- **Herausforderung:** Statisches Hardcoding teurer Frontier-Modelle führt zu explodierenden Token-Kosten; starre SDKs crashen bei Quotenlimits oder 429-Rate-Limits.
- **Lösung durch clutch:** Dynamisches Provider-Hot-Swapping (Anthropic, Gemini, OpenAI, Ollama, Kimi), orthogonale Steuerung des Reasoning-Aufwands, prozessübergreifende Circuit-Breaker und deterministische Fallback-Ketten.

### `[PERSONA-02]` Multi-Host- & Edge-Infrastruktur-Systemingenieure
- **Kontext:** Betrieb heterogener Rechenumgebungen bestehend aus lokalen GPU-Workstations, Laptops, Edge-Knoten und Cloud-APIs.
- **Herausforderung:** Ungleichmäßige Hardware-Verfügbarkeit macht starre Konfigurationen fragil; zentrale Cloud-Gateways erhöhen die Latenz und bilden Single Points of Failure.
- **Lösung durch clutch:** Automatische Erkennung lokaler/entfernter Ollama-Instanzen neben Cloud-Providern, belegte Selektor-Auflösung ohne verdeckte Ersetzungen und saubere Host-Isolation.

### `[PERSONA-03]` Solo-Entwickler & Tool-Builder
- **Kontext:** Entwicklung von Individualsoftware, Entwickler-Werkzeugen und CLI-Tools, die KI-Funktionalität ohne aufwendige Gateway-Infrastruktur benötigen.
- **Herausforderung:** Das Aufsetzen schwergewichtiger Docker-Proxys (LiteLLM, Portkey) ist Overkill; eigene Skripte entbehren oft Metriken und Budget-Sicherungen.
- **Lösung durch clutch:** Direkte Python-Bibliothek (`from clutch import Fahrer`) und CLI (`clutch run`) mit intuitiver Auto-Metapher, Vier-Zonen-Tankuhr, SQLite-Fahrtenbuch und ohne Hintergrund-Dämonen.

### `[PERSONA-04]` Datenschutz- & Compliance-Verantwortliche
- **Kontext:** Gewährleistung von DSGVO-, HIPAA- und IP-Schutzanforderungen in KI-gestützten Unternehmens- und Entwicklungs-Pipelines.
- **Herausforderung:** SaaS-Gateways leiten vertrauliche Prompts über fremde Server; unklare Lizenzen oder administrative Berechtigungen stellen ein Audit-Risiko dar.
- **Lösung durch clutch:** 100% Local-First-Architektur ohne Telemetrie-Egress (Verbindungen ausschließlich zu konfigurierten Provider-Endpunkten), unprivilegierte Benutzerrechte (`RunAsInvoker`), permissive MIT-Lizenz und transparente SPDX-Lizenzübersicht.

### High-Intent-Suchbegriffe & KI-Auffindbarkeit
Zur semantischen Erkennung durch Entwicklerverzeichnisse und KI-Suchmaschinen:
- `provider-neutral LLM orchestration engine and model router` -- Open-Source Python-Routing-Bibliothek für Anthropic, Gemini, OpenAI, Ollama und Kimi.
- `local-first zero-egress LLM budget tracking fuel gauge` -- 4-Zonen-Budgetkontrolle mit Token-Throughput-Schattenfenster.
- `automotive metaphor LLM routing Anthropic Gemini OpenAI Ollama Kimi` -- Intuitive Steuerung über Fahrer, Strecke, Getriebe, Gas/Bremse und Kupplung.
- `persistent circuit breaker quota failover multi-agent system` -- Prozessüberdauernde Sperren zur Vermeidung von Quotenschleifen.
- `adaptive reasoning effort throttle brake model switching` -- Entkopplung von Denkintensität und Modellwahl.
- `evidence-bearing execution selector model resolution` -- Fünfstufige Nachweiserbringung ohne unbemerkte Modellsubstitution.
- `unprivileged user-mode LLM router RunAsInvoker MIT license` -- Sichere Ausführung im unprivilegierten Benutzermodus mit permissiver Software-Inventur.

---

<a id="4-comparative-matrix-vs-alternatives"></a>
<a id="comparative-matrix-vs-alternatives"></a>
<a id="vergleichsmatrix-gegenueber-alternativen"></a>
## 4. Vergleichsmatrix gegenüber Alternativen

Die folgende Matrix vergleicht `clutch` mit etablierten Routing- und Gateway-Paradigmen anhand von 10 technischen Dimensionen, die direkt auf unsere Governance-Invarianten abgestimmt sind:

| Technische Dimension | Governance-Invariante | clutch | Klassische Einzel-Provider-SDKs | Cloud-Modell-Gateways (LiteLLM / OpenRouter) | Agenten-Framework-Router (CrewAI / AutoGen) | Ad-Hoc Skripte & Prompt-Router |
|---|:---:|:---:|:---:|:---:|:---:|
| **1. Multi-Provider-Neutralität** | `INV-LOCAL-01` | **Vollständiges Hot-Swapping (Anthropic, Gemini, OpenAI, Ollama, Kimi)** | Keine (Vendor-Lock-in) | Hoch (Multi-Provider API-Wrapper) | Mittel (Framework-spezifische Adapter) | Gering (Manueller Aufwand pro API) |
| **2. Offline-First & Zero Egress** | `INV-LOCAL-02` | **100% Lokal (Lokale Daten, keine Telemetrie)** | Hoch (Direkte API-Aufrufe) | Gering (Zentrale Cloud-Telemetrie / SaaS) | Gering (Oft integrierte Cloud-Telemetrie) | Hoch (Eigener Code) |
| **3. Unprivilegierte Ausführung** | `INV-UNPRIV-03` | **Strikter RunAsInvoker (User-Mode, kein Daemon)** | Hoch (User-Space-Bibliothek) | Erfordert oft Hintergrund-Dienst / Docker | Hoch (User-Space-Bibliothek) | Hoch (User-Space-Skript) |
| **4. Persistente Circuit-Breaker** | `INV-CIRCUIT-04` | **Persistente `availability.json` (Überlebt Neustart)** | Keine (Bricht bei 429 direkt ab) | Ephemer / Im Arbeitsspeicher (Nach Neustart verloren) | Ephemer (Mit Workflow-Ende verloren) | Keine (Skript stürzt ab oder schleift) |
| **5. Update-sichere Benutzer-Overlays** | `INV-OVERLAY-05` | **Persistente `user_overrides.json` & Aliase** | Keine (Code-Anpassung nötig) | Basis (Konfigurationsdatei / DB) | Code-Konfiguration | Hardcodierte Variablen |
| **6. Zweifache gerankte Fallback-Gänge** | `INV-FALLBACK-06` | **Primärer Gang + 2 gerankte Alternativen** | Keine | Basis (Lineare Wiederholungsliste) | Partiell (Pauschale Fehlerabfangung) | Keine (Harter Abbruch) |
| **7. 4-Zonen-Budget-Tankuhr** | `INV-BUDGET-07` | **Tankuhr (Grün/Gelb/Orange/Rot + Durchsatz)** | Keine (Nur externes Billing-Dashboard) | Basis (Ausgabenlimits / Guthabenprüfung) | Keine (Keine nativen Budget-Schranken) | Keine (Unkontrollierte API-Kosten) |
| **8. Zweck- & Vision-Ausrichtung** | `INV-PURPOSE-08` | **Automatische Modalitäts-Zuordnung (Vision/Code)** | Manuell | Manuelle Modellauswahl | Partiell (Rollen-Prompts) | Keine |
| **9. Transaktionssicheres Audit-Ledger** | `INV-LEDGER-09` | **ACID SQLite Fahrtenbuch & Chat-Historie** | Keine (Zustandslos) | Cloud-Logging-Dashboard | Ephemer im Arbeitsspeicher | Keine / Reine Textdateien |
| **10. Plattform-Parität & Sicherheits-SLA** | `INV-SLA-10` | **48h SLA / Multi-OS CI / Zero-Copyleft MIT** | Enterprise-Vertragsbedingungen | Gemischte / Proprietäre Bedingungen | Unterschiedlich je Open-Source-Projekt | Keine (Ungepflegte Skripte) |

---

<a id="5-dual-mermaid-diagrams"></a>
<a id="dual-mermaid-diagrams"></a>
<a id="duale-mermaid-diagramme"></a>
## 5. Duale Mermaid-Diagramme

### 1. Systemarchitektur-Topologie

```mermaid
flowchart TD
    subgraph CLIENTS["Clients & Steuerungs-Oberflächen"]
        CLI["clutch CLI (route / run / chat / stats)"]
        Web["FastAPI Web-UI (clutch serve --web)"]
        API["OpenAI-kompatibler /v1/chat/completions Endpunkt"]
        Lib["Python SDK (from clutch import Fahrer)"]
    end

    subgraph ORCHESTRATION["Kern-Orchestrierungsschicht"]
        Fahrer["FAHRER (Orchestrator)"]
        Strecke["STRECKE (Aufgaben- & Zweck-Klassifikator)"]
        GasBremse["GAS / BREMSE (Reasoning-Aufwand 0-100%)"]
        Kupplung["KUPPLUNG (Modellwechsler & Failover)"]
    end

    subgraph REGISTRY["Modell-Registry & Governance"]
        Getriebe["GETRIEBE (Modell-Gänge G1-G5 & Lokales Ollama)"]
        Bordcomputer["BORDCOMPUTER (Circuit Breaker & Verfügbarkeit)"]
        Tankuhr["TANKUHR (4-Zonen-Budget & Schattenfenster)"]
        UserOverrides["Benutzer-Overlays (~/.clutch/user_overrides.json)"]
    end

    subgraph ENGINES["Einheitliche MotorBlock-Provider-Schicht"]
        MotorBlock["MOTORBLOCK (Einheitlicher API-Adapter)"]
        Anthropic["Anthropic (Claude Sonnet / Opus / Haiku)"]
        Gemini["Google (Gemini 3.7 Flash / 3.5 Fallback / Pro)"]
        OpenAI["OpenAI (GPT-5.6 / Codex)"]
        Ollama["Ollama (Lokale & Remote Modelle)"]
        Agy["agy (companion-for-agy)"]
        Kimi["Kimi (Moonshot API & CLI)"]
    end

    subgraph TELEMETRY["Telemetrie, Ledger & Lernsystem"]
        Tacho["TACHO (Latenz & Token-Durchsatz)"]
        Fahrtenbuch[("FAHRTENBUCH (SQLite Fahrten-Ledger)")]
        Fahrschule["FAHRSCHULE (Lernengine & Fitness-Optimierung)"]
    end

    CLIENTS --> Fahrer
    Fahrer --> Strecke
    Strecke --> Getriebe
    Fahrer --> GasBremse
    Fahrer --> Kupplung
    Getriebe <--> Bordcomputer
    Getriebe <--> UserOverrides
    Bordcomputer <--> Tankuhr
    Kupplung --> MotorBlock
    MotorBlock --> Anthropic
    MotorBlock --> Gemini
    MotorBlock --> OpenAI
    MotorBlock --> Ollama
    MotorBlock --> Agy
    MotorBlock --> Kimi
    MotorBlock --> Tacho
    Tacho --> Fahrtenbuch
    Fahrtenbuch --> Fahrschule
    Fahrschule -. Fitness-Feedback .-> Getriebe
```

### 2. End-to-End Task- & Routing-Lebenszyklus

```mermaid
sequenceDiagram
    autonumber
    actor User as Nutzer / Agent
    participant Fahrer as Fahrer (Orchestrator)
    participant Strecke as Strecke (Klassifikator)
    participant Getriebe as Getriebe (Registry)
    participant Bord as Bordcomputer (Health/Quota)
    participant Motor as MotorBlock (Einheitliche Engine)
    participant Provider as Modell-Provider (API/Lokal)
    participant Tacho as Tacho & Tankuhr (Telemetrie)
    participant Ledger as Fahrtenbuch (SQLite)
    participant School as Fahrschule (Lernengine)

    User->>Fahrer: Aufgabe übergeben (Prompt, Präferenzen, Ausschluss, Zweck, Effort)
    Fahrer->>Strecke: strecke_analysieren(prompt)
    Strecke-->>Fahrer: StreckenProfil (Streckentyp, Schwierigkeit, Zweck, Vision-Bedarf)
    Fahrer->>Getriebe: get_candidates(profil, zweck)
    Getriebe->>Bord: pruefe_verfuegbarkeit(kandidaten, user_overrides)
    Bord-->>Getriebe: Aktive rote Quota-Fenster & ausgelöste Circuit-Breaker herausfiltern
    Getriebe-->>Fahrer: FahrtConfig (Hauptgang + 2 gerankte Fallback-Alternativen)
    Fahrer->>Motor: ausfuehren(task, hauptgang, effort)
    alt Reguläre Ausführung erfolgreich
        Motor->>Provider: API-Aufruf absetzen
        Provider-->>Motor: Antwort-Tokens & Verbrauchsmetadaten streamen
    else Provider-Fehler / Rate-Limit (429 / Quota)
        Motor->>Bord: Temporäre Provider-Sperre setzen (in availability.json persistiert)
        Motor->>Provider: Automatischer Wechsel auf gerankte Fallback-Alternative
        Provider-->>Motor: Antwort über Fallback-Modell streamen
    end
    Motor->>Tacho: Tokens, Latenz & Token-Durchsatz (EMA) aufzeichnen
    Tacho->>Fahrer: Budget-Zonen (Tankuhr) und Tacho-Messwerte aktualisieren
    Fahrer->>Ledger: record_trip(trip_log, dauer, fitness)
    Ledger->>School: Lernzyklus anstoßen
    School-->>Getriebe: Epsilon-Greedy-Fitnessgewichte anpassen
    Fahrer-->>User: MotorErgebnis (Antwortinhalt, Konfiguration, Telemetrie, Alternativen)
```

---

<a id="6-governance--runtime-invariants"></a>
<a id="governance--runtime-invariants"></a>
<a id="governance--laufzeit-invarianten"></a>
## 6. Governance- & Laufzeit-Invarianten

| # | Invariante | Geltungsbereich | Betriebliche Garantie |
|---|------------|-----------------|-----------------------|
| **1** | **Provider-Agnostizismus & Zero Lock-in** | Engine | Keine feste Herstellerbindung; nahtloses Umschalten zwischen Anthropic, Google Gemini, OpenAI, Ollama und Kimi. |
| **2** | **100% Local-First & Zero Egress** | Netzwerk | Keine Tracking-, Analyse- oder Telemetrie-Abflüsse; Netzwerkverkehr entsteht ausschließlich zu konfigurierten Providern. |
| **3** | **Non-Elevation User Mode** | Prozess | Alle CLI-Befehle, Hintergrund-Worker und FastAPI-Server laufen strikt im unprivilegierten Benutzerkontext. |
| **4** | **Fail-Closed Circuit Breaker** | Zuverlässigkeit | Erschöpfte Quotas, rote Fenster und API-Fehler führen zu persistenten Sperren in `~/.clutch/availability.json` statt Endlosschleifen. |
| **5** | **Update-feste Nutzer-Overlays** | Konfiguration | Nutzerpräferenzen, Modellausschlüsse, Aliase und Kostenanpassungen in `~/.clutch/user_overrides.json` überleben Paket-Updates. |
| **6** | **Zwei gerankte Fallback-Alternativen** | Routing | Jede Routing-Entscheidung liefert verlässlich einen Hauptgang sowie zwei gerankte Fallback-Alternativen (`alternativen`). |
| **7** | **Zweidimensionale Telemetrie** | Budget | Kombiniert finanzielle USD-Verbrauchszonen (`Tankuhr`) mit realen Token-Durchsatz-Raten (`token_throughput.py`). |
| **8** | **Zweck- und Vision-Passgenauigkeit** | Klassifikation | Bild- und Dokumentaufgaben werden strikt an vision-fähige Modelle geroutet; Coding-Tasks erhalten spezialisierte Coding-Gänge. |
| **9** | **Transaktionssicheres SQLite-Ledger** | Persistenz | Alle Fahrten, Ausführungsdaten, Chat-Sitzungen und Prompt-Vorlagen werden ACID-konform lokal in SQLite gespeichert. |
| **10** | **Plattformübergreifende Multi-OS Parität** | Plattform | Vollständig identisches Verhalten, CLI-Ergonomie, Testabdeckung und Routing-Semantik unter Linux, Windows und macOS. |

---

<a id="7-road-types"></a>
<a id="road-types"></a>
<a id="streckentypen"></a>
## 7. Streckentypen & Aufgabenklassifikation

| Strecke | Schwierigkeit | Standard-Gang | Gas/Throttle | Muster |
|---------|--------------|---------------|--------------|--------|
| **Feldweg** | Trivial | Haiku (G1) | 30% | Single |
| **Landstrasse** | Standard | Sonnet (G3) | 50% | Single |
| **Bundesstrasse** | Bugfix | Sonnet (G3) | 70% | Single |
| **Autobahn** | Architektur | Opus (G5) | 90% | Single |
| **Rallye** | Bulk ops | Haiku (G1) | 30% | Swarm |
| **Konvoi** | Pipeline | Sonnet (G3) | 50% | Chain |
| **Teamfahrt** | Multi-File | Sonnet (G3) | 50% | Team |
| **Langstrecke** | Komplex | Opus (G5) | 90% | Hybrid |

---

<a id="8-installation"></a>
<a id="installation"></a>
## 8. Installation & Voraussetzungen

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
pip install -e .
```

### Optionale Web-Oberfläche
```bash
pip install -e .[web]
```

### Voraussetzungen
- Python 3.10+
- API-Schlüssel für gewünschte Provider (als Umgebungsvariablen oder via `clutch keys set`):
  - `ANTHROPIC_API_KEY` für Claude-Modelle
  - `GOOGLE_API_KEY` für Gemini-Modelle
  - `OPENAI_API_KEY` für GPT- und Codex-Modelle
  - `MOONSHOT_API_KEY` für Kimi-API-Modelle
  - Lokales Ollama für lokale Open-Source-Modelle

---

<a id="9-quick-start"></a>
<a id="quick-start"></a>
<a id="kurzanleitung"></a>
## 9. Schnellstart & Kurzanleitung

```python
from clutch import Fahrer

# Fahrer instanziieren (nutzt alle konfigurierten Provider)
fahrer = Fahrer()

# Aufgabe übergeben -- der Fahrer übernimmt Analyse und Ausführung
ergebnis = fahrer.fahren(
    "Fix den Authentifizierungsbug im Login-Modul",
    handler=mein_handler,
)

# Gewählte Konfiguration inspizieren
print(ergebnis.config.gang.name)       # "claude-sonnet"
print(ergebnis.config.gang.provider)   # "anthropic"
print(ergebnis.config.gas.wert)        # 0.7

# Dashboard abfragen
status = fahrer.status()
print(status["tankuhr"]["zone"])       # "green"
print(status["getriebe"])              # "Getriebe[haiku(G1), flash(G2), ...]"

# Aus bisherigen Fahrten lernen
fahrer.trainieren()
```

---

<a id="10-command-line-interface"></a>
<a id="command-line-interface"></a>
<a id="kommandozeilen-schnittstelle"></a>
## 10. Kommandozeilen-Schnittstelle (CLI)

Nach `pip install -e .` steht das `clutch`-Kommando bereit:

```bash
clutch route "Fix den Auth-Bug"        # Zeigt Routing-Entscheidung (Dry-Run, kein API-Call)
clutch route "..." --prefer codex --exclude claude-sonnet --zweck coding --effort high
clutch "Erkläre Quantencomputing"     # One-Shot: Route + Ausführung, gibt Antwort aus
clutch run "..." --json                # Maschinenlesbare Ausgabe (für KI-Agenten)
clutch chat                            # Interaktive REPL-Sitzung
clutch models [--status] [--json]      # Modelle inklusive Verfügbarkeit & Sperrgrund
clutch models disable claude-sonnet    # Persistentes, update-festes Nutzer-Overlay
clutch models enable claude-sonnet
clutch resolve gpt5 --runner codex --json  # nur auflösen; führt kein Modell aus
clutch config prefer openai            # Modell oder Provider dauerhaft bevorzugen
clutch stats                           # Nutzungs-, Budget- und Health-Dashboard
clutch config <key> [value]            # CLI-Einstellungen lesen/schreiben
clutch keys set MOONSHOT_API_KEY       # API-Key sicher speichern (Maskierte Eingabe)
clutch keys list                       # Gespeicherte Key-Namen auflisten (keine Werte)
clutch serve --web                     # Lokale Web-UI starten (benötigt: pip install clutch[web])
```

---

<a id="11-api-keys--credentials"></a>
<a id="api-keys--credentials"></a>
<a id="api-keys--zugangsdaten"></a>
## 11. API-Keys & Zugangsdaten

clutch löst Schlüssel in folgender Reihenfolge auf (der erste Treffer gewinnt):

1. Umgebungsvariable (z. B. `MOONSHOT_API_KEY`) -- bevorzugt für Server und CI
2. clutch-Store `~/.clutch/credentials.json` (via `clutch keys set`, Berechtigung 0600)
3. `~/.credentials/<name>`-Dateien (Interoperabilität mit Geschwistertools)

Schlüsselwerte werden niemals ausgegeben, geloggt oder in Git committet.

---

<a id="12-configuration"></a>
<a id="configuration"></a>
<a id="konfiguration"></a>
## 12. Konfiguration & Benutzer-Overlays

Standardkonfigurationen liegen in `clutch/config/`. Eigene Overlays werden in `~/.clutch/user_overrides.json` abgelegt:

```json
{
  "disabled_models": ["claude-sonnet"],
  "preferred_models": ["openai-codex"],
  "preferred_providers": ["openai"],
  "model_max_gang": {"openai-codex": 4},
  "aliases": {"codex": "openai-codex"},
  "model_cost_override": {
    "ollama-kimi-k2": {"kosten_input_1k": 0.001, "kosten_output_1k": 0.004}
  }
}
```

### Ausführungsselektoren und Provider-Evidenz

`resolve_execution_selector()` löst Runnerprofile (`claude`, `codex`, `agy`,
`clutch`, `ollama`, `kimi`), `self`, Familien wie `gpt5` sowie exakte
Registrynamen oder Modell-IDs auf. Exakte Selektoren werden niemals ersetzt.
Das JSON-Ergebnis trennt `resolved` (Selektor existiert) von `claimable` (alle
erforderlichen Belege liegen vor) und enthält einen deterministischen
Registry-Fingerprint.

Für Claimability müssen fünf unabhängige Stufen wahr sein:
`provider_documented`, `provider_api_listed`, `account_accessible`,
`runner_compatible` und `host_ready`. Gebündelte Katalogdaten leiten weder
Accountzugriff noch Hostbereitschaft ab und bleiben deshalb fail-closed, bis ein
Aufrufer einen belegten `ProviderCatalogSnapshot` anwendet.

Provider-I/O bleibt außerhalb des Kernpakets. Injizierte
`ProviderCatalogAdapter` liefern validierte Snapshots;
`refresh_provider_catalog()` weist den Diff aus und behält bei einem Fehler den
letzten belegten Snapshot. Das Anwenden eines Snapshots darf bestehende
kuratierte Gänge anreichern, aber niemals ein providerseitig gefundenes Modell
neu in die Registry aufnehmen.

---

Die Bibliothek akzeptiert dieselben Wünsche wie die CLI:

```python
profil = fahrer.strecke_analysieren("Implementiere den Parser")
config = fahrer.kuppeln(
    profil,
    zweck="coding",
    effort_override="high",
    ausschluss=["claude-sonnet"],
    praeferenz=["codex", "openai"],
)
print(config.gang.name)
print(config.alternativen)  # zwei gerankte Fallback-Gänge
```

Harte Grenzen (deaktivierte/nicht verfügbare/ausgeschlossene Gänge, Budget,
Vertrauen und erforderliche Vision-Fähigkeit) gelten vor Präferenzen. Das
Route-JSON enthält immer `alternativen`.

### Reasoning-Effort

Modellwahl und Reasoning-Effort sind orthogonal: clutch entscheidet **welches
Modell** (Gang) und hält im optionalen Feld `effort` fest, **wie tief** ein
kompatibler Agent arbeiten soll. Aufgabenklassen in `strecken.json` können
verwenden:

- `high` für routinemäßige, klar begrenzte Arbeit
- `xhigh` als reguläres gründliches Session-Level
- `max-delegate` für einen transparent angekündigten, gezielten Max-Worker beim
  härtesten Einzelschritt; dadurch entsteht kein dauerhafter Max-Modus

Aufrufer können die Empfehlung für genau einen Aufruf mit
`kontext={"effort": "high"}` überschreiben. `ultracode` ist bewusst kein
Effort-Wert: Es beschreibt Breite (Team-/Schwarm-Fan-out), nicht tiefere
Analyse; teure Fan-outs brauchen weiterhin eine ausdrückliche Bestätigung.
Lange Rechenarbeit wird in beobachtbare Schritte zerlegt. Dauert ein einzelner
Schritt voraussichtlich etwa 10--15 Minuten oder länger, gehört dieser Schritt
auf den Mac-Studio-Compute-Pfad.

### Budget-Zonen

| Zone | Auslastung | Erlaubte Gänge |
|------|-------|--------------|
| Grün | 0--30 % | Alle (G1--G5) |
| Gelb | 30--60 % | G1--G3 |
| Orange | 60--80 % | Nur G1--G2 |
| Rot | 80--100 % | Keine (Budget erschöpft) |

`clutch/config/fitness_criteria.json` ist die einzige Laufzeitquelle für diese
Grenzen. Bordcomputer und Kupplung lesen dieselbe Policy; bei Rot stoppt das
Routing, bevor ein LLM ausgewählt wird.

---

<a id="13-supported-providers"></a>
<a id="supported-providers"></a>
<a id="unterstuetzte-provider"></a>
## 13. Unterstützte Provider & Modell-Gänge

| Provider | Modelle | Lokal |
|----------|---------|-------|
| **Anthropic** | Claude Fable 5, Haiku, Sonnet, Opus | Nein |
| **Google** | Gemini 3.7 Flash (bevorzugt), Gemini 3.5 Flash als Fallback, Gemini 3.1 Pro Preview | Nein |
| **OpenAI** | GPT-5.6 Luna/Terra/Sol via Responses API, GPT-5.3-Codex | Nein |
| **Ollama** | Qwen, Mistral und weitere (lokal & remote); Kimi K3, GLM 5.3, K2.7 Code via Ollama Cloud | Ja / Cloud |
| **Claude Code** | Subprozess-CLI-Sitzung | Ja |
| **agy** | Live erkanntes Gemini-, Claude- und GPT-OSS-Inventar via `companion-for-agy` | CLI-Sitzung |
| **Kimi (Moonshot)** | `kimi-k2.7-code`, `kimi-k2.6` via OpenAI-kompatible API; `kimi-cli`/`kimi-code` CLI; Ollama Cloud | API / CLI |
| **OpenAI-kompatibel**| Beliebiger `/v1/chat/completions`-Endpunkt (`base_url` setzbar) | Nein / Lokal |

---

<a id="14-execution-patterns"></a>
<a id="execution-patterns"></a>
<a id="ausfuehrungsmuster"></a>
## 14. Ausführungsmuster

- **Einzelfahrt (Single)** -- Ein Modell, ein Task
- **Kolonne (Convoy)** -- Sequentiell, Ausgabe N wird Eingabe für N+1
- **Team** -- Parallele spezialisierte Worker, Ergebnisse zusammengeführt
- **Schwarm (Swarm)** -- Massiv parallele Mikrotasks (z. B. 20x Haiku), danach Aggregation
- **Hybrid** -- Kombination aus Kolonnen- und Team-Phasen

---

<a id="15-ecosystem--sibling-tools"></a>
<a id="ecosystem--sibling-tools"></a>
<a id="verwandte-tools--oekosystem"></a>
## 15. Verwandte Tools & Ökosystem

Teil der [ellmos-ai](https://github.com/ellmos-ai) Multi-Agenten-Infrastruktur und des übergeordneten [open-bricks](https://github.com/open-bricks) Open-Source-Ökosystems:

| Tool | Organisation | Beschreibung |
|------|--------------|-------------|
| [coma](https://github.com/ellmos-ai/coma) | ellmos-ai | Multi-Agenten-Orchestrator und Ausführungskoordinator |
| [swarm-ai](https://github.com/ellmos-ai/swarm-ai) | ellmos-ai | Schwarmintelligenz und autonomer Agentenkonsens |
| [system-explorer](https://github.com/ellmos-ai/system-explorer) | ellmos-ai | Lokale Systemerkennung und Ressourcen-Monitor |
| [policy-registry](https://github.com/ellmos-ai/policy-registry) | ellmos-ai | Einheitliche Berechtigungs- und Richtlinien-Engine |
| [sqlite-transit-sync](https://github.com/ellmos-ai/sqlite-transit-sync) | ellmos-ai | Multi-Agenten Zustandssynchronisation via SQLite WAL |
| [workflowhooker](https://github.com/ellmos-ai/workflowhooker) | ellmos-ai | Ereignis-Hooks und Agenten-Workflow-Trigger |
| [memoryhooker](https://github.com/ellmos-ai/memoryhooker) | ellmos-ai | Transparentes SQLite/FTS5-Arbeitsgedächtnis für Agenten |
| [agent-ops-stack](https://github.com/ellmos-ai/agent-ops-stack) | ellmos-ai | Operativer Sidecar-Stack für autonome Agenten |
| [convergence-reconciler](https://github.com/ellmos-ai/convergence-reconciler) | ellmos-ai | Modell-Konvergenzprüfung und Konsens-Engine |
| [DevCenter](https://github.com/dev-bricks/DevCenter) | dev-bricks | Entwickler-Leitstand, Repository-Dashboard und Umgebungsmanager |
| [CodeBox](https://github.com/dev-bricks/CodeBox) | dev-bricks | Polyglotter Code-Snippet-Manager und Entwickler-Werkbank |
| [open-bricks](https://github.com/open-bricks) | open-bricks | Dachorganisation für modulare Open-Source Softwarewerkzeuge |

---

<a id="16-third-party-licenses--transparency"></a>
<a id="third-party-licenses--transparency"></a>
<a id="drittanbieter-lizenzen--transparenz"></a>
## 16. Drittanbieter-Lizenzen & Transparenz

`clutch` verpflichtet sich zu absoluter Softwaretransparenz, Lizenz-Compliance und Schutz der Lieferkette:

- **Vollständige SPDX-Software-Inventur:** Jede zwingende Laufzeitabhängigkeit (`anthropic`, `google-genai`, `requests`), optionale Web-Abhängigkeit (`fastapi`, `uvicorn`, `python-multipart`) und Entwicklungswerkzeuge (`pytest`, `ruff`) sind mit exakten SPDX-Kennungen in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md) dokumentiert.
- **Zero-Copyleft-Garantie:** 100% aller Abhängigkeiten nutzen permissive, wirtschaftsfreundliche Open-Source-Lizenzen (MIT, Apache-2.0, BSD-3-Clause, PSF). Es existieren keinerlei GPL-, AGPL- oder virale Copyleft-Komponenten.
- **Unprivilegierter Benutzermodus (`RunAsInvoker`):** Alle CLI-Befehle, Web-Oberflächen und lokalen Datenbanken laufen im regulären Benutzerkontext ohne administrative Privilegienerweiterung.
- **Laufzeit-Governance-Invarianten:** Formale Bestätigung der 10 Governance- und Laufzeit-Invarianten (`INV-LOCAL-01` bis `INV-SLA-10`).

Vollständige Abhängigkeitstabellen, Lizenztexte und Urheberrechtshinweise finden sich in [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md).

---

<a id="17-security-policy--liability"></a>
<a id="security-policy--liability"></a>
<a id="sicherheitsrichtlinie--haftung"></a>
## 17. Sicherheitsrichtlinie & Haftung

Details zu unterstützten Versionen, Reaktionszeiten und Meldeverfahren finden sich in [SECURITY.md](SECURITY.md).

### Haftungsausschluss / Liability Disclaimer

Dieses Projekt ist eine **unentgeltliche Open-Source-Schenkung** im Sinne der §§ 516 ff. BGB. Die Haftung des Urhebers ist gemäß **§ 521 BGB** auf **Vorsatz und grobe Fahrlässigkeit** beschränkt. Ergänzend gelten die Haftungsausschlüsse der MIT-Lizenz.

Nutzung auf eigenes Risiko. Keine Wartungszusage, keine Verfügbarkeitsgarantie, keine Gewähr für Fehlerfreiheit oder Eignung für einen bestimmten Zweck.

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.

---

<a id="18-verification--test-suite"></a>
<a id="verification--test-suite"></a>
<a id="verifikation--testsuite"></a>
## 18. Verifikation & Testsuite

`clutch` verfügt über eine umfassende automatisierte Testsuite mit 100% Erfolgsquote unter Linux, Windows und macOS:

```bash
# Unit-, Vertrags- und Regressionstests ausführen
python -m pytest -ra -v

# Schneller Durchlauf
pytest -q

# Code-Stil und Linter prüfen
ruff check .

# Bytecode-Kompilierung validieren
python -m compileall clutch tests
```

Die Testsuite prüft:
- Routing-Mechanik, Aufgabenanalyse und Zweck-Zuordnung (`test_route.py`, `test_clutch.py`)
- Automobile Ausführungsmuster: Kolonne, Team, Schwarm und Hybrid (`test_patterns.py`)
- Lernengine, Epsilon-Greedy-Exploration und Fitness-Feedback (`test_learning.py`)
- Provider-Engines und Modellkatalog-Parität (`test_kimi_motoren.py`, `test_motorblock.py`)
- Metadaten-Verträge, zweisprachige Doku-Parität, CI-Timeouts, Gitignore-Hygiene und Lizenz-Integrität (`test_metadata.py`)
