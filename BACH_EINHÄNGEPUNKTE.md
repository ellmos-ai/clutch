# Kupplung x BACH -- Einhängepunkte-Analyse

**Wo kann die Kupplung in BACH eingehängt werden?**

Stand: 2026-03-09 | BACH v3.2+ | Kupplung v0.2.0

---

## Kurzfassung

BACH hat bereits 70-80% der Infrastruktur. Die Kupplung muss nicht parallel gebaut werden, sondern **an 4 Stellen eingehängt** werden:

```
User-Request
     │
     ▼
┌─────────────────────────────────┐
│  1. COMPLEXITY_SCORER           │  ← Strecken-Analyse einhängen
│     hub/_services/delegation/   │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  2. PARTNER.PY → _delegate()   │  ← Kupplung einhängen (Gangwahl)
│     hub/partner.py              │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  3. SCHWARM / CHAIN / AGENT     │  ← Muster-Wahl einhängen
│     hub/schwarm.py              │
│     hub/chain.py                │
│     hub/agent_launcher.py       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  4. TOKENS + FEEDBACK           │  ← Fahrtenbuch einhängen
│     hub/tokens.py               │
│     hub/meta_feedback_injector  │
│     hub/consolidation.py        │
└─────────────────────────────────┘
```

---

## Einhängepunkt 1: Strecken-Analyse → ComplexityScorer

### Aktuell in BACH
`hub/_services/delegation/complexity_scorer.py` (249 Zeilen)

- Score 0-100 basierend auf: Textlaenge, Keywords, Code-Patterns, Multi-Step, Tech-Terme
- Modell-Empfehlung: `<20=haiku`, `20-50=sonnet`, `50-80=opus`, `>=80=opus+extended`
- Singleton: `get_scorer()` / `score_task()`

### Was die Kupplung besser kann

| Aspekt | BACH ComplexityScorer | Kupplung StreckenAnalyse |
|--------|---------------------|--------------------------|
| Dimensionen | 1 (Score 0-100) | 4 (Typ, Tempo, Schwierigkeit, Etappen) |
| Task-Typen | Keine (nur Score) | 10 (Feldweg bis Langstrecke) |
| Urgency | Nicht beruecksichtigt | Eilig/Normal/Gemuetlich |
| Gas-Steuerung | Nicht vorhanden | 0-100% Reasoning-Level |
| Provider | Nur Claude | Claude, Gemini, Ollama, claude-code |

### Einhaenge-Strategie

```python
# hub/_services/delegation/complexity_scorer.py -- ERWEITERN

from kupplung.strecke import StreckenAnalyse

class ComplexityScorer:
    def __init__(self):
        self._strecke = StreckenAnalyse()  # Kupplung einhängen
        # ... bestehender Code bleibt

    def score_task(self, task: str, context: dict = None) -> dict:
        # Bestehender Score (Abwaertskompatibel)
        legacy_score = self._legacy_score(task)

        # Neuer Strecken-Score
        profil = self._strecke.analysiere(task, context)

        return {
            "score": legacy_score,                    # Alt (0-100)
            "strecke": profil.typ.value,              # Neu
            "tempo": profil.tempo.value,              # Neu
            "schwierigkeit": profil.schwierigkeit,    # Neu
            "etappen": profil.etappen,                # Neu
            "model_recommendation": self._recommend(profil),  # Erweitert
        }
```

**Aufwand:** Gering. `StreckenAnalyse` hat keine externen Abhaengigkeiten.

---

## Einhängepunkt 2: Kupplung → partner.py `_delegate()`

### Aktuell in BACH
`hub/partner.py` (525 Zeilen)

Die `_delegate()` Methode ist der KERN-Einhängepunkt:
1. Liest `complexity_scorer` Score
2. Prueft aktuelle Budget-Zone (Zone 1-4)
3. Prueft Partner-Erlaubnis via `delegation_rules`
4. Delegiert an Partner (API-Call)
5. Trackt in `delegation_logs`

### Was fehlt (und die Kupplung liefert)

| Feature | BACH partner.py | Kupplung |
|---------|----------------|----------|
| Multi-Provider Routing | Statisch (partner_recognition) | Dynamisch (Getriebe) |
| Reasoning-Level | Nicht steuerbar | Gas/Bremse (0-100%) |
| Speed-Dimension | Fehlt komplett | Tempo (eilig/normal/gemuetlich) |
| Lernende Policy | Nein | Fahrschule (Epsilon-Greedy) |
| Circuit-Breaker | Nein | Bordcomputer |
| Gangwechsel | Nicht moeglich | Kupplung (Upshift/Downshift) |

### Einhaenge-Strategie

```python
# hub/partner.py -- _delegate() ERWEITERN

from kupplung.fahrer import Fahrer as KupplungsFahrer

class PartnerHandler(BaseHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._kupplung = None  # Lazy init

    @property
    def kupplung(self):
        if self._kupplung is None:
            try:
                self._kupplung = KupplungsFahrer()
            except Exception:
                pass  # Fallback: ohne Kupplung
        return self._kupplung

    def _delegate(self, task, partner_name=None, **kwargs):
        # BESTEHENDE Zone-Logik bleibt
        zone = self._get_current_zone()

        if self.kupplung and not partner_name:
            # KUPPLUNG ENTSCHEIDET
            profil = self.kupplung.strecke_analysieren(task)
            config = self.kupplung.kuppeln(profil)

            # Kupplung-Gang → BACH-Partner Mapping
            partner_name = self._gang_zu_partner(config.gang)

            # Gas als Prompt-Prefix injizieren
            if config.gas.prompt_strategie != "ausgewogen":
                task = config.gas.prompt_prefix + "\n\n" + task

        # ... bestehende Delegation-Logik mit partner_name
```

### Gang → Partner Mapping

```python
def _gang_zu_partner(self, gang):
    """Mappt Kupplung-Gang auf BACH partner_recognition."""
    # DB: SELECT name FROM partner_recognition
    #     WHERE partner_type = gang.provider
    #     AND model_id LIKE gang.model_id
    mapping = {
        "claude-opus":    "claude",      # BACH Partner "claude"
        "claude-sonnet":  "claude",      # Gleicher Partner, anderes Modell
        "claude-haiku":   "claude",
        "gemini-pro":     "gemini",
        "gemini-flash":   "gemini",
        "ollama-qwen3":   "ollama",
        "ollama-mistral": "ollama",
        "claude-code":    None,          # Kein Delegation, self-execute
    }
    return mapping.get(gang.name)
```

**Aufwand:** Mittel. Bestehende `_delegate()` Logik muss erweitert, nicht ersetzt werden.

---

## Einhängepunkt 3: Muster-Wahl → schwarm.py / chain.py / agent_launcher.py

### Aktuell in BACH

3 getrennte Systeme fuer Ausfuehrungsmuster:

| System | Handler | Muster |
|--------|---------|--------|
| `schwarm.py` | `SchwarmHandler` | Epstein, Konsensus, Hierarchie, Stigmergy, Spezialist |
| `chain.py` | `ChainHandler` | Toolchains (DB), llmauto-Ketten (JSON) |
| `agent_launcher.py` | `AgentLauncherHandler` | Agent-Start mit PID-Management |

**Problem:** Kein zentraler Entscheider der das RICHTIGE Muster waehlt.

### Was die Kupplung liefert

Die Kupplung bestimmt das `muster` automatisch basierend auf dem Task-Profil:

| Kupplung-Muster | BACH-Pendant | Wann |
|-----------------|-------------|------|
| `einzelfahrt` | Direkte Delegation | 1 Task, 1 Modell |
| `kolonne` | `chain.py` Toolchain | Pipeline, sequentiell |
| `team` | `agent_launcher.py` multi-agent | Parallel, spezialisiert |
| `schwarm` | `schwarm.py` Epstein | Bulk, viele Mikrotasks |
| `hybrid` | Kombination | Phasenweise anders |

### Einhaenge-Strategie

```python
# NEUER Service: hub/_services/kupplung_bridge.py

class KupplungBridge:
    """Verbindet Kupplung-Muster mit BACH-Execution-Engines."""

    def __init__(self, db, schwarm_handler, chain_handler, agent_handler):
        self.db = db
        self.schwarm = schwarm_handler
        self.chain = chain_handler
        self.agent = agent_handler

    def ausfuehren(self, config: FahrtConfig, task: str):
        muster = config.muster

        if muster == "einzelfahrt":
            # Direkt an Partner delegieren
            return self._direkt(config, task)

        elif muster == "kolonne":
            # BACH ChainHandler nutzen
            return self.chain._run_chain(task, steps=config.etappen)

        elif muster == "team":
            # BACH AgentLauncher: Mehrere Agents parallel
            return self._team_launch(config, task)

        elif muster == "schwarm":
            # BACH SchwarmHandler: Epstein-Pattern
            return self.schwarm._run_epstein(task, config.gang.model_id)

        elif muster == "hybrid":
            # Phasenweise: Analyse(Opus) → Umsetzung(Sonnet) → Tests(Haiku)
            return self._hybrid(config, task)
```

**Aufwand:** Mittel-Hoch. Braucht Zugriff auf alle 3 Handler.

---

## Einhängepunkt 4: Fahrtenbuch → tokens.py + meta_feedback + consolidation

### 4a. Token-Tracking (tokens.py)

**Aktuell:** `monitor_tokens` Tabelle mit Input/Output/Total/Cost pro Aufruf.

**Was fehlt:** Aufschluesselung nach Routing-Entscheidung (welcher Gang wurde gewaehlt und warum).

```sql
-- MIGRATION: Neue Spalten in monitor_tokens
ALTER TABLE monitor_tokens ADD COLUMN kupplung_gang TEXT;
ALTER TABLE monitor_tokens ADD COLUMN kupplung_gas REAL;
ALTER TABLE monitor_tokens ADD COLUMN kupplung_strecke TEXT;
ALTER TABLE monitor_tokens ADD COLUMN kupplung_muster TEXT;
ALTER TABLE monitor_tokens ADD COLUMN kupplung_erkundung INTEGER DEFAULT 0;
```

**Alternative:** Kupplung-Fahrtenbuch (`kupplung.db`) separat fuehren und per View joinen:

```sql
-- View: Vereinigte Sicht
CREATE VIEW v_fahrt_komplett AS
SELECT
    mt.timestamp, mt.model, mt.tokens_total, mt.cost_eur,
    fe.strecken_typ, fe.gang, fe.gas, fe.muster, fe.ist_erkundung
FROM monitor_tokens mt
LEFT JOIN kupplung_fahrten fe ON mt.call_id = fe.fahrt_id;
```

**Empfehlung:** Separates Fahrtenbuch (Kupplung bleibt standalone-faehig), JOIN per View.

### 4b. Meta-Feedback-Injector

**Aktuell:** Erkennt LLM-Ticks (Sprache, Emojis) und injiziert Korrekturen.

**Kupplung-Erweiterung:** Gas-Stellung als Prompt-Prefix injizieren:

```python
# hub/meta_feedback_injector.py -- ERWEITERN

class MetaFeedbackInjector:
    def inject_corrections(self, prompt, context=None):
        corrections = []

        # BESTEHEND: LLM-Ticks
        corrections.extend(self._check_existing_patterns(prompt))

        # NEU: Kupplung Gas-Prefix
        if context and "kupplung_gas" in context:
            gas = context["kupplung_gas"]
            if gas.prompt_strategie == "direkt":
                corrections.append(
                    "Antworte direkt und knapp. "
                    "Keine ausfuehrliche Analyse, nur das Ergebnis."
                )
            elif gas.prompt_strategie == "gruendlich":
                corrections.append(
                    "Analysiere gruendlich. Pruefe mehrere Ansaetze. "
                    "Erklaere dein Vorgehen Schritt fuer Schritt."
                )

        return self._format_corrections(corrections)
```

### 4c. Consolidation (Lernmechanismus)

**Aktuell:** Weight-Decay (0.95/Tag), Archive/Forget/Reclassify fuer Memory.

**Kupplung-Erweiterung:** Fahrschule-Ergebnisse als Lessons speichern:

```python
# Nach jedem Fahrschule.trainieren() Zyklus:
for update in training_result["updates"]:
    # Als BACH Lesson speichern
    db.execute_write(
        """INSERT INTO memory_lessons
        (category, problem, solution, weight, source)
        VALUES (?, ?, ?, ?, ?)""",
        (
            "kupplung_routing",
            f"Strecke {update['strecke']}: Welcher Gang?",
            f"Bester Gang: {update['neuer_gang']} ({update['neuer_provider']}) "
            f"mit Fitness {update['fitness']:.3f} ({update['stichproben']} Fahrten)",
            0.8,
            "kupplung_fahrschule",
        )
    )
```

**Aufwand:** Gering pro Sub-Punkt, mittel gesamt.

---

## Integrations-Architektur (Gesamtbild)

```
                    ┌─────────────────────────────┐
                    │         USER REQUEST         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │      COMPLEXITY_SCORER       │
                    │  + StreckenAnalyse (Kupplung)│
                    │                              │
                    │  Score: 65                    │
                    │  Strecke: bundesstrasse      │
                    │  Tempo: eilig                │
                    │  Schwierigkeit: 0.65         │
                    └──────────────┬──────────────┘
                                   │
                    ┌──────────────▼──────────────┐
                    │       PARTNER._delegate()    │
                    │  + Kupplung.einlegen()       │
                    │                              │
                    │  Gang: claude-sonnet (G3)    │
                    │  Gas: 50%                    │
                    │  Muster: einzelfahrt         │
                    │  Budget-Zone: green          │
                    └──────────────┬──────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
   ┌──────────▼─────┐  ┌──────────▼─────┐  ┌──────────▼─────┐
   │   einzelfahrt   │  │    kolonne     │  │    schwarm     │
   │                 │  │                │  │                │
   │  partner.py     │  │  chain.py      │  │  schwarm.py    │
   │  → Claude API   │  │  → Toolchain   │  │  → Epstein     │
   │  → Gemini API   │  │  → llmauto     │  │  → Konsensus   │
   │  → Ollama       │  │                │  │                │
   └────────┬────────┘  └────────┬───────┘  └────────┬───────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │
                    ┌────────────▼────────────────┐
                    │       ERGEBNIS-TRACKING      │
                    │                              │
                    │  monitor_tokens (BACH)        │
                    │  + Fahrtenbuch (Kupplung)     │
                    │  + meta_feedback_injector     │
                    │  + consolidation → Lessons    │
                    └──────────────────────────────┘
```

---

## Implementations-Reihenfolge

### Phase 1: Standalone-Bridge (1-2 Tage)
- `hub/_services/kupplung_bridge.py` erstellen
- Kupplung als `import` einbinden (kein Code-Kopieren)
- ComplexityScorer erweitern (abwaertskompatibel)
- **Test:** `bach partner delegate "Fix den Bug"` nutzt Kupplung-Routing

### Phase 2: Partner-Integration (1 Tag)
- `partner.py._delegate()` um Kupplung-Logik erweitern
- Gang → Partner Mapping
- Gas-Prefix in Prompts injizieren
- **Test:** Verschiedene Tasks werden an verschiedene Provider geroutet

### Phase 3: Muster-Routing (1-2 Tage)
- KupplungBridge verbindet `schwarm.py` / `chain.py` / `agent_launcher.py`
- Automatische Muster-Wahl basierend auf Strecken-Profil
- **Test:** Bulk-Task → Schwarm, Pipeline → Chain, Multi-File → Team

### Phase 4: Tracking & Lernen (1 Tag)
- Fahrtenbuch an `monitor_tokens` anbinden
- Fahrschule-Ergebnisse als Lessons speichern
- Consolidation erkennt Routing-Patterns
- **Test:** Nach 50+ Fahrten empfiehlt Fahrschule bessere Gaenge

### Phase 5: Meta-Feedback (0.5 Tage)
- Gas-Stellung als Prompt-Strategie injizieren
- Kupplung-Feedback-Loop ueber meta_feedback_injector
- **Test:** Task mit Gas=30% bekommt "direkt"-Prefix, Gas=90% bekommt "gruendlich"

---

## Risiken & Mitigation

| Risiko | Impact | Mitigation |
|--------|--------|------------|
| Kupplung-Overhead bei simplen Tasks | Latenz +50ms | `bypass_feldwege=true` in Config |
| Doppelte Token-Zählung (BACH + Kupplung) | Verwirrende Zahlen | Ein System fuehrt, anderes referenziert |
| Kupplung-DB vs. BACH-DB Sync | Inkonsistenz | Separates Fahrtenbuch + SQL View |
| Breaking Changes bei BACH-Updates | Kupplung kaputt | Bridge-Pattern isoliert Kupplung |
| Circular Imports | ImportError | Lazy-Init + Optional-Import |

---

## Was NICHT getan werden sollte

1. **Kupplung-Code IN BACH kopieren** -- Import, nicht Copy-Paste
2. **BACH-Handler ersetzen** -- Erweitern, bestehende Logik bleibt
3. **Eigene DB-Tabellen in bach.db** -- Separates `kupplung.db`
4. **Alle Strecken sofort routen** -- Erst Phase 1 (Datensammlung)
5. **Partner-Tabelle aendern** -- Mapping-Layer stattdessen

---

## Dateien die angefasst werden

| Datei | Aenderung | Risiko |
|-------|-----------|--------|
| `hub/_services/delegation/complexity_scorer.py` | +30 Zeilen (StreckenAnalyse Import) | Gering |
| `hub/partner.py` | +50 Zeilen (_delegate Erweiterung) | Mittel |
| `hub/meta_feedback_injector.py` | +15 Zeilen (Gas-Prefix) | Gering |
| **NEU:** `hub/_services/kupplung_bridge.py` | ~200 Zeilen (Bridge) | Kein (neu) |
| **NEU:** `data/schema/migration_kupplung.sql` | ~10 Zeilen (View) | Gering |

**Gesamter BACH-Impact:** ~95 Zeilen geaendert, ~210 Zeilen neu. Minimal-invasiv.

---

*Erstellt: 2026-03-09 | Basierend auf BACH v3.2+ und Kupplung v0.2.0*
