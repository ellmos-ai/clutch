# Dirigent -- BACH Integration Map

Analyse der bestehenden BACH-Mechanismen die fuer den Dirigent relevant sind.
**Stand:** 2026-03-08 | **BACH Version:** 3.2.0+

---

## Fazit vorweg

**BACH bietet bereits 70-80% der notwendigen Infrastruktur.**
Der Dirigent muss kein Parallelsystem aufbauen, sondern BACH erweitern.

---

## Direkt nutzbare BACH-Komponenten

### 1. Token-Budget & Delegation Zones (hub/partner.py)

Bereits implementiert: 4-Zonen-System basierend auf Token-Verbrauch.

| Zone | Budget-% | Erlaubte Partner | Dirigent-Mapping |
|------|----------|------------------|------------------|
| Zone 1 | 0-30% | Alle | Opus/High erlaubt |
| Zone 2 | 30-60% | Nur guenstige | Sonnet/Medium max |
| Zone 3 | 60-80% | Nur lokal (Ollama) | Haiku/Low oder lokal |
| Zone 4 | 80-100% | Nur Human | Kein LLM-Einsatz |

**Reuse:** Logik 1:1, nur Model-Tier-Zuordnung erweitern.

### 2. Complexity Scorer (hub/_services/delegation/complexity_scorer.py)

Bewertet Task-Komplexitaet -> steuert Partner-Auswahl.

**Fuer Dirigent:** Task-Complexity -> Model/Level Entscheidung.
- Low Complexity -> Haiku/Low
- Medium -> Sonnet/Medium
- High -> Opus/Medium oder Opus/High

### 3. Token-Tracking (hub/tokens.py)

Vollstaendiges Bilanzierungssystem:
- Input/Output/Total Tokens pro Task
- USD + EUR Kosten (mit Exchange-Rate)
- Delegations suggested/accepted/savings
- Budget-Warnungen (95%+)

**DB-Tabelle:** `monitor_tokens`

### 4. Success-Rate Tracking

**DB-Tabelle:** `monitor_success`
- Attempts, Successes, Failures pro Entity
- Success-Rate (Real), avg_duration_seconds
- User-Rating, Notes

**Fuer Dirigent:** Leistungs-Metriken pro Model x Level x TaskType.

### 5. Process Monitoring

**DB-Tabelle:** `monitor_processes`
- Actor-Status (idle/working/error)
- Tasks completed, Error count
- Uptime tracking

### 6. Meta-Feedback-Injector (hub/meta_feedback_injector.py)

Pattern-basiertes Korrektur-System:
- Erkennt wiederkehrende LLM-Ticks (Sprache, Emojis, etc.)
- Frequency-Tracking mit Hit/Miss Recording
- Auto-Deaktivierung nach max inactive_count
- Injection in Prompts vor Agent-Aufruf

**Fuer Dirigent:** Grundgeruest fuer adaptives Prompt-Tuning pro Modell.

### 7. Consolidation Handler (hub/consolidation.py)

Memory-Konsolidierung mit Lernmechanismus:
- Gewichtungs-System (WEIGHT_THRESHOLD_ARCHIVE = 0.2)
- Decay-Rate: 5% taeglich (DECAY_RATE_DEFAULT = 0.95)
- Boost bei Zugriff: +0.1 Gewicht
- Operationen: weight, archive, compress, forget, reclassify

**Fuer Dirigent:** Welche Routing-Entscheidungen bewähren sich ueber Zeit?

### 8. Schwarm-Patterns (hub/schwarm.py)

5 implementierte Muster:
1. **Epstein** -- Parallelisierte Chunk-Verarbeitung (ThreadPoolExecutor)
2. **Hierarchie** -- Manager-Worker mit Task-Delegation
3. **Stigmergy** -- Indirekte Koordination ueber geteilten Zustand
4. **Konsensus** -- Mehrere LLMs abstimmen (Majority-Vote)
5. **Spezialist** -- Aufgabe an spezialisierten Agenten routen

**Fuer Dirigent:** Swarm-Pattern direkt aus BACH nutzen.

### 9. Shared Memory (hub/shared_memory.py)

Multi-Agent-faehiges Memory-System:
- 6 Tabellen: facts, lessons, sessions, working, consolidation, triggers
- Visibility: private | team | global
- Conflict-Resolution fuer Multi-Agent Locks
- Decay-Mechanismus fuer Working Memory
- Delta-Abfragen: `changes-since <timestamp>`

**Fuer Dirigent:** Zentrale Koordination zwischen Dirigent und Workern.

### 10. Reflection Agent (agents/reflection/)

SelfReflection-Klasse:
- `log_metric(task, latency_ms, success, details)` -- Metriken tracken
- `review_performance(days)` -- N-Tages-Statistiken
- Gap-Analyse (Schwachstellen identifizieren)

### 11. Multi-Model-Support (partners/)

Bereits integriert:
- `partners/claude/` -- Anthropic Claude (Hauptmodell)
- `partners/gemini/` -- Google Gemini
- `partners/ollama/` -- Lokale Modelle

**DB-Tabelle:** `partner_recognition`
- partner_name, partner_type (api|local|human)
- capabilities (JSON), cost_tier (1-3)
- token_zone (zone_1 bis zone_4)
- priority, status, success_rate

### 12. Chain/Agent-Orchestrierung

3-Schichten Execution Stack:
1. **SchedulerService** -- Zeitgesteuerte Jobs (cron)
2. **ChainHandler** -- Toolchains + llmauto-Ketten mit bach:// URL-Resolution
3. **AgentLauncherHandler** -- Startet Claude/Gemini/Ollama-Sessions

---

## Ueberschneidungs-Matrix

| Dirigent-Funktion | In BACH? | BACH-Quelle | Gap |
|-------------------|----------|-------------|-----|
| Dynamic Model Routing | Teilweise | partner.py + complexity_scorer | Speed-Dimension fehlt |
| Level-basierte Delegation | Ja | Delegation Zones | Reasoning-Level != Token-Zone |
| Speed-Aware Routing | Nein | -- | Muss implementiert werden |
| Learning Loop | Ja | meta_feedback, consolidation, reflection | Fehlt: Model-Performance-Feedback |
| Performance Tracking | Ja | monitor_tokens/success/processes | Fehlt: Model x Level Aufschluesselung |
| Multi-Agent Coordination | Ja | shared_memory, USMC bridge | Reicht aus |
| Task Routing | Ja | ChainHandler, AgentLauncher | Fehlt: Dynamische Routing-Logik |
| Prompt Management | Ja | prompt_templates, prompt_boards | Reicht aus |
| Self-Assessment | Ja | Reflection Agent, Consolidation | Fehlt: Model-Vergleich |

---

## Was der Dirigent NEU implementieren muss

### 1. Speed-Dimension
BACH hat cost_tier aber kein speed_tier.
-> `partner_recognition` um `speed_tier` und `reasoning_level` erweitern.

### 2. Model-Performance-Vorhersage
BACH trackt Erfolg pro Entity, aber nicht pro Model x Level x TaskType.
-> Neue Tabelle `dirigent_routing_log` mit allen 3 Dimensionen.

### 3. Dynamische Entscheidungslogik
BACH hat statische Zones (30/60/80%).
-> Dirigent braucht lernende Routing-Tabelle die sich anpasst.

### 4. A/B-Testing Framework
BACH hat kein Experiment-System.
-> Epsilon-Greedy Exploration (10% der Tasks mit alternativer Kombination).

### 5. Feedback-Loop fuer Routing-Entscheidungen
BACH misst Erfolg, aber korreliert nicht mit der Routing-Entscheidung.
-> Nach jedem Task: "War diese Model-Wahl optimal?" erfassen.

---

## Empfohlene Implementierungsstrategie

### Option A: Dirigent als BACH-Skill (empfohlen)

```
BACH/system/
├── hub/dirigent.py              # Neuer Handler
├── hub/_services/dirigent/
│   ├── router.py                # Model/Level/Speed Router
│   ├── learner.py               # Feedback -> Policy Update
│   └── experiment.py            # A/B-Testing
├── agents/dirigent/             # Boss-Agent (Opus/Med)
└── skills/dirigent/             # Skill-Definition
```

**Vorteile:**
- Nutzt alle bestehenden BACH-Handler direkt
- DB-Zugriff ueber bewährte API
- Sofortige Integration mit Token-Tracking, Monitoring, etc.

### Option B: Dirigent als Standalone (MODULAR_AGENTS)

```
MODULAR_AGENTS/Dirigent/
├── dirigent/
│   ├── orchestrator.py
│   ├── ...
└── bach_bridge.py               # Optional: BACH-Anbindung
```

**Vorteile:**
- Unabhaengig von BACH nutzbar
- Leichter zu testen und zu publishen

### Option C: Hybrid (empfohlen fuer Start)

Entwicklung in MODULAR_AGENTS/Dirigent/ mit optionaler BACH-Bridge.
Spaeter als BACH-Skill integrieren wenn stabil.

---

## Relevante BACH-Dateipfade

| Datei | Zweck |
|-------|-------|
| `hub/partner.py` | Delegation Zones, Partner-Auswahl |
| `hub/tokens.py` | Token-Budget-Tracking |
| `hub/consolidation.py` | Learning Loop mit Weight-Decay |
| `hub/shared_memory.py` | Multi-Agent State |
| `hub/schwarm.py` | Parallelisierungs-Patterns |
| `hub/meta_feedback_injector.py` | Adaptives Feedback |
| `hub/_services/delegation/complexity_scorer.py` | Task-Scoring |
| `agents/reflection/reflection_analyzer.py` | Performance-Analyse |
| `data/schema/schema.sql` | Datenbank-Schema |

---

*Erstellt: 2026-03-08*
