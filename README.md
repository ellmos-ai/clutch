<p align="center">
  <img src="docs/assets/banner.svg" alt="clutch banner" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

> Provider-neutral LLM orchestration engine and model router with auto-learning

[![Version 0.6.2](https://img.shields.io/badge/Version-0.6.2-orange.svg)](https://github.com/ellmos-ai/clutch/releases)
[![CI](https://img.shields.io/badge/CI-passing-brightgreen.svg)](https://github.com/ellmos-ai/clutch/actions)
[![Pytest](https://img.shields.io/badge/Pytest-387%20passed-brightgreen.svg)](https://github.com/ellmos-ai/clutch)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Platforms](https://img.shields.io/badge/Platforms-Linux%20%7C%20Windows%20%7C%20macOS-blue.svg)](https://github.com/ellmos-ai/clutch)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Providers](https://img.shields.io/badge/Providers-Anthropic%20%7C%20Gemini%20%7C%20OpenAI%20%7C%20Ollama%20%7C%20Kimi-purple.svg)](https://github.com/ellmos-ai/clutch)
[![Security SLA: 48h](https://img.shields.io/badge/Security%20SLA-48h%20Response%20%7C%205d%20Triage-blue.svg)](SECURITY.md)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Security: Local-First](https://img.shields.io/badge/Security-Local--First-green.svg)](SECURITY.md)
[![Privacy: Zero-Egress](https://img.shields.io/badge/Privacy-Zero--Egress-success.svg)](SECURITY.md)
[![Non-Elevation](https://img.shields.io/badge/Elevation-User--Mode-informational.svg)](SECURITY.md)
[![Ecosystem: ellmos-ai](https://img.shields.io/badge/Ecosystem-ellmos--ai-blue.svg)](https://github.com/ellmos-ai)
[![Umbrella: open-bricks](https://img.shields.io/badge/Umbrella-open--bricks-purple.svg)](https://github.com/open-bricks)
[![Discovery: llms.txt](https://img.shields.io/badge/Discovery-llms.txt-blue.svg)](llms.txt)

**clutch** (German: *Kupplung*) uses an intuitive automotive driving metaphor to intelligently route tasks to optimal LLM models across multiple providers. It analyzes task complexity and purpose, selects the right model gear and reasoning level, tracks budgets with a four-zone fuel gauge, enforces persistent circuit breakers, and learns from experience. Use it as a **library**, a **CLI**, or a **local web app**.

> [!NOTE]
> For AI agents, crawlers, and automated indexers, machine-readable summary metadata and discovery context are available in [llms.txt](llms.txt).

---

## Quick Navigation
1. [Features & Highlights](#features)
2. [Architecture & Metaphor Mapping](#architecture)
3. [Dual Mermaid Diagrams](#dual-mermaid-diagrams)
4. [Governance & Runtime Invariants](#governance--runtime-invariants)
5. [Road Types & Task Classification](#road-types)
6. [Installation & Requirements](#installation)
7. [Quick Start](#quick-start)
8. [Command-Line Interface](#command-line-interface)
9. [API Keys & Credentials](#api-keys--credentials)
10. [Configuration & User Overlays](#configuration)
11. [Supported Providers & Model Tiers](#supported-providers)
12. [Execution Patterns](#execution-patterns)
13. [Ecosystem & Sibling Tools](#ecosystem--sibling-tools)
14. [Security Policy & Liability](#security-policy--liability)

---

## Features

- **Provider-neutral** -- Anthropic (Claude), Google (Gemini), OpenAI (GPT/Codex), Ollama (local & remote), Claude Code, **agy via companion-for-agy**, and **Kimi** (Moonshot API / CLI / Ollama Cloud)
- **Auto-routing** -- analyzes task complexity *and purpose* (coding, vision, research, bulk) and picks the optimal model + reasoning level
- **Purpose & vision aware** -- routes image/document input to vision-capable models; matches tasks to model strengths
- **CLI + Web UI** -- `clutch route/run/chat/models/stats`, plus an optional FastAPI web chat (`clutch serve --web`)
- **Credential store** -- keep API keys in `~/.clutch/credentials.json` (`clutch keys ...`); env vars take precedence
- **Model discovery** -- auto-detect installed Ollama models (local/remote) and OpenAI-compatible `/v1/models`
- **Budget tracking** -- four-zone fuel gauge (green/yellow/orange/red) with daily and monthly limits
- **Learning engine** -- fitness scoring and epsilon-greedy exploration that improves routing over time
- **Execution patterns** -- single tasks, chains (convoy), parallel teams, and swarm processing
- **Persistent availability** -- circuit breakers and quota blocks survive one-shot processes; red Anthropic 5h/7d windows, `notaus`, and provider rate-limit failures are routed around until reset
- **Update-safe user overlay** -- disable models, prefer models/providers, cap model tiers, define aliases, and override model costs in `~/.clutch/user_overrides.json`
- **Per-call routing wishes** -- prefer or exclude gears, override purpose/effort, and receive two ranked fallback alternatives
- **Health monitoring** -- persistent circuit breakers, latency tracking, overkill/token-explosion alerts, provider failover
- **SQLite metrics** -- persistent trip log, chat sessions, prompt library, and profiles

---

## Architecture

The entire system follows a **car/driving metaphor**:

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

| Component | Role | Module |
|-----------|------|--------|
| **Fahrer** (Driver) | Orchestrator -- picks model, reasoning, pattern | `fahrer.py` |
| **Strecke** (Road) | Task analysis and classification | `strecke.py` |
| **Getriebe** (Gearbox) | Provider-neutral model registry | `getriebe.py` |
| **Gang** (Gear) | A specific model (G1--G5) | `getriebe.py` |
| **Gas/Bremse** (Throttle/Brake) | Reasoning level (0--100%) | `gas_bremse.py` |
| **Kupplung** (Clutch) | Model switching mechanism | `kupplung.py` |
| **MotorBlock** (Engine) | Unified API call layer | `motorblock.py` |
| **Tacho** (Speedometer) | Metrics collection | `tacho.py` |
| **Tankuhr** (Fuel Gauge) | Budget tracking (4 zones) | `tankuhr.py` |
| **Bordcomputer** (Onboard Computer) | Health monitor, circuit breaker | `bordcomputer.py` |
| **Fahrtenbuch** (Trip Log) | SQLite metrics storage | `fahrtenbuch.py` |
| **Fahrschule** (Driving School) | Learning / evolution engine | `fahrschule.py` |
| **Token-Throughput** (Shadow zone, Stage 1) | Anthropic 5h/7d rate-limit window as a second, display-only zone alongside Tankuhr's USD zones -- see [`docs/STAGED-MIGRATION.md`](docs/STAGED-MIGRATION.md) | `token_throughput.py` |

---

## Dual Mermaid Diagrams

### 1. System Architecture Topology

```mermaid
flowchart TD
    subgraph CLIENTS["Clients & Control Surfaces"]
        CLI["clutch CLI (route / run / chat / stats)"]
        Web["FastAPI Web UI (clutch serve --web)"]
        API["OpenAI-Compatible /v1/chat/completions"]
        Lib["Python SDK (from clutch import Fahrer)"]
    end

    subgraph ORCHESTRATION["Core Orchestration Layer"]
        Fahrer["FAHRER (Orchestrator)"]
        Strecke["STRECKE (Task & Purpose Classifier)"]
        GasBremse["GAS / BREMSE (Reasoning Effort 0-100%)"]
        Kupplung["KUPPLUNG (Model Switcher & Failover)"]
    end

    subgraph REGISTRY["Model Registry & Governance"]
        Getriebe["GETRIEBE (Gearbox G1-G5 & Local Ollama)"]
        Bordcomputer["BORDCOMPUTER (Circuit Breaker & Availability)"]
        Tankuhr["TANKUHR (4-Zone Fuel Gauge & Shadow Window)"]
        UserOverrides["User Overrides (~/.clutch/user_overrides.json)"]
    end

    subgraph ENGINES["Unified MotorBlock Provider Layer"]
        MotorBlock["MOTORBLOCK (Unified API Adapter)"]
        Anthropic["Anthropic (Claude Sonnet / Opus / Haiku)"]
        Gemini["Google (Gemini 3.7 Flash / 3.5 Fallback / Pro)"]
        OpenAI["OpenAI (GPT-5.6 / Codex)"]
        Ollama["Ollama (Local & Remote Models)"]
        Agy["agy (companion-for-agy)"]
        Kimi["Kimi (Moonshot API & CLI)"]
    end

    subgraph TELEMETRY["Telemetry, Ledger & Learning"]
        Tacho["TACHO (Latency & Token Throughput)"]
        Fahrtenbuch[("FAHRTENBUCH (SQLite Trip Ledger)")]
        Fahrschule["FAHRSCHULE (Auto-Learning & Fitness Engine)"]
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
    Fahrschule -. Fitness Feedback .-> Getriebe
```

### 2. End-to-End Task & Routing Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User as User / Agent
    participant Fahrer as Fahrer (Orchestrator)
    participant Strecke as Strecke (Classifier)
    participant Getriebe as Getriebe (Registry)
    participant Bord as Bordcomputer (Health/Quota)
    participant Motor as MotorBlock (Unified Engine)
    participant Provider as Model Provider (API/Local)
    participant Tacho as Tacho & Tankuhr (Telemetry)
    participant Ledger as Fahrtenbuch (SQLite)
    participant School as Fahrschule (Learning)

    User->>Fahrer: Submit task (prompt, preferences, exclusions, zweck, effort)
    Fahrer->>Strecke: strecke_analysieren(prompt)
    Strecke-->>Fahrer: StreckenProfil (road_type, difficulty, purpose, vision_needed)
    Fahrer->>Getriebe: get_candidates(profile, zweck)
    Getriebe->>Bord: pruefe_verfuegbarkeit(candidates, user_overrides)
    Bord-->>Getriebe: Filter active red quota windows & tripped circuit breakers
    Getriebe-->>Fahrer: FahrtConfig (primary gear + 2 ranked fallback alternatives)
    Fahrer->>Motor: ausfuehren(task, primary_gear, effort)
    alt Primary Execution Success
        Motor->>Provider: Dispatch API call
        Provider-->>Motor: Stream completion tokens & usage metadata
    else Provider Error / Rate Limit (429 / Quota)
        Motor->>Bord: Trigger temporary quota block (persisted in availability.json)
        Motor->>Provider: Failover to ranked alternative gear
        Provider-->>Motor: Stream completion from fallback provider
    end
    Motor->>Tacho: Record tokens, latency & token throughput EMA
    Tacho->>Fahrer: Update budget zones (Tankuhr) and speed metrics
    Fahrer->>Ledger: record_trip(trip_log, duration, fitness)
    Ledger->>School: Trigger learning update
    School-->>Getriebe: Update epsilon-greedy fitness weights
    Fahrer-->>User: MotorErgebnis (content, config, telemetry, alternatives)
```

---

## Governance & Runtime Invariants

| # | Invariant | Scope | Operational Guarantee |
|---|-----------|-------|-----------------------|
| **1** | **Provider Agnosticism & Zero Lock-in** | Engine | No mandatory vendor dependency; seamless hot-swapping between Anthropic, Google Gemini, OpenAI, Ollama, and Kimi. |
| **2** | **100% Local-First & Zero Egress** | Network | No analytics, tracking, or telemetry egress; network calls connect strictly to user-configured LLM provider endpoints. |
| **3** | **Non-Elevation User Mode** | Process | All CLI commands, background processes, and FastAPI web servers execute within unprivileged user-space permissions. |
| **4** | **Fail-Closed Circuit Breaker** | Reliability | Quota blocks, red windows, and API failures trigger persistent circuit breakers in `~/.clutch/availability.json` rather than looping. |
| **5** | **Update-Safe User Overlays** | Configuration | User preferences, model exclusions, aliases, and cost overrides live in `~/.clutch/user_overrides.json` and persist across package updates. |
| **6** | **Dual-Alternative Ranked Fallbacks** | Routing | Every routing resolution produces a primary gear plus two ranked alternative fallbacks (`alternativen`). |
| **7** | **Two-Dimensional Telemetry** | Budget | Combines financial USD consumption zones (`Tankuhr`) with real-time token throughput burn rates (`token_throughput.py`). |
| **8** | **Purpose & Vision Alignment** | Classification | Multimodal and vision inputs are strictly routed to vision-capable models; code tasks match specialized coding gears. |
| **9** | **Transactional SQLite Audit Ledger** | Persistence | All trips, execution records, chat sessions, and prompt library entries are safely stored in local SQLite databases with ACID guarantees. |
| **10** | **Cross-Platform Multi-OS Parity** | Platform | Identical behavior, CLI ergonomics, test coverage, and routing semantics across Linux, Windows, and macOS. |

---

## Road Types

| Road | Difficulty | Default Gear | Throttle | Pattern |
|------|-----------|-------------|----------|---------|
| Feldweg (Dirt road) | Trivial | Haiku (G1) | 30% | Single |
| Landstrasse (Country road) | Standard | Sonnet (G3) | 50% | Single |
| Bundesstrasse (Highway) | Bugfix | Sonnet (G3) | 70% | Single |
| Autobahn (Motorway) | Architecture | Opus (G5) | 90% | Single |
| Rallye (Rally) | Bulk ops | Haiku (G1) | 30% | Swarm |
| Konvoi (Convoy) | Pipeline | Sonnet (G3) | 50% | Chain |
| Teamfahrt (Team drive) | Multi-file | Sonnet (G3) | 50% | Team |
| Langstrecke (Long distance) | Complex | Opus (G5) | 90% | Hybrid |

---

## Installation

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
pip install -e .
```

### Optional Web UI
```bash
pip install -e .[web]
```

### Requirements
- Python 3.10+
- API keys for your desired providers (set as environment variables or via `clutch keys set`):
  - `ANTHROPIC_API_KEY` for Claude models
  - `GOOGLE_API_KEY` for Gemini models
  - `OPENAI_API_KEY` for GPT and Codex models
  - `MOONSHOT_API_KEY` for Kimi API models
  - Ollama running locally for local models

---

## Quick Start

```python
from clutch import Fahrer

# Create a driver (uses all configured providers)
fahrer = Fahrer()

# Describe your task -- the driver handles everything
result = fahrer.fahren(
    "Fix the authentication bug in the login module",
    handler=my_handler,
)

# Inspect what was chosen
print(result.config.gang.name)       # "claude-sonnet"
print(result.config.gang.provider)   # "anthropic"
print(result.config.gas.wert)        # 0.7

# Dashboard
status = fahrer.status()
print(status["tankuhr"]["zone"])     # "green"
print(status["getriebe"])            # "Getriebe[haiku(G1), flash(G2), ...]"

# Learn from past runs
fahrer.trainieren()
```

---

## Command-Line Interface

After `pip install -e .` the `clutch` command is available:

```bash
clutch route "Fix the auth bug"      # show the routing decision (dry-run, no LLM call)
clutch route "..." --prefer codex --exclude claude-sonnet --zweck coding --effort high
clutch "Explain quantum computing"    # one-shot: route + execute, print the answer
clutch run "..." --json               # machine-readable output (for other agents)
clutch chat                           # interactive REPL
clutch models [--status] [--json]     # models plus optional availability/reset reason
clutch models disable claude-sonnet   # persistent, update-safe user override
clutch models enable claude-sonnet
clutch config prefer openai           # prefer a model or provider persistently
clutch stats                          # usage / budget / health dashboard
clutch config <key> [value]           # read/set CLI settings
clutch keys set MOONSHOT_API_KEY      # store an API key (hidden input; values never shown)
clutch keys list                      # list stored key names (not values)
clutch serve --web                    # start the web UI (needs: pip install clutch[web])
```

Three usage modes: **console** (humans), **web UI** (humans, graphical), and **CLI/API**
(other LLMs/agents routing tasks via `--json` or the OpenAI-compatible web endpoint).

---

## API Keys & Credentials

clutch resolves keys in this order (first non-empty wins):

1. Environment variable (e.g. `MOONSHOT_API_KEY`) -- preferred for CI/servers
2. clutch store `~/.clutch/credentials.json` (via `clutch keys set`, file mode 0600)
3. `~/.credentials/<name>` files (interop with sibling tools)

Values are never printed, logged, or committed.

---

## Configuration

Default config lives in `clutch/config/` so editable installs and wheels use the
same bundled routing defaults. Pass a custom `base_dir` with its own `config/`
folder to `Fahrer` if you want project-specific overrides.

| File | Purpose |
|------|---------|
| `kupplung.json` | Global settings (driver defaults, swarm limits, budget) |
| `getriebe.json` | All gears + provider mappings |
| `strecken.json` | Road type to gear/throttle/effort mapping |
| `fitness_criteria.json` | Learning engine thresholds |

Bundled files remain immutable defaults. User choices are layered over them
from `~/.clutch/user_overrides.json` with these fields:

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

`~/.clutch/availability.json` is runtime-owned state. It persists model circuit
states and provider quota blocks with `until`/`resets_at`; every
`Bordcomputer.pruefe()` reloads it, so separate CLI processes share the same
availability decision. Missing or stale token-budget input never creates a new
block, while a previously evidenced red block remains active until its reset.

### Per-call routing wishes

The library accepts the same routing wishes as the CLI:

```python
profile = fahrer.strecke_analysieren("Implement the parser")
config = fahrer.kuppeln(
    profile,
    zweck="coding",
    effort_override="high",
    ausschluss=["claude-sonnet"],
    praeferenz=["codex", "openai"],
)
print(config.gang.name)
print(config.alternativen)  # two ranked fallback gears
```

Hard constraints (disabled/unavailable/excluded gears, budget, trust, and
required vision capability) are applied before preferences. Route JSON always
contains `alternativen`.

### Reasoning Effort

Model choice and reasoning effort are orthogonal: clutch decides **which
model** (gear) and records **how deeply** a compatible agent should work in the
optional `effort` field. Road classes in `strecken.json` can use:

- `high` for routine, bounded work
- `xhigh` as the normal thorough session level
- `max-delegate` for a transparent, targeted max worker on the hardest single
  step; it does not enable a persistent max mode

Callers may override the recommendation for one invocation with
`kontext={"effort": "high"}`. `ultracode` is intentionally not an effort
value: it describes breadth (team/swarm fan-out), not deeper reasoning, and
expensive fan-out still needs explicit confirmation. Split long compute into
observable steps; when one step is expected to take about 10--15 minutes or
more, route that step to the Mac Studio compute path.

### Budget Zones

| Zone | Usage | Allowed Gears |
|------|-------|--------------|
| Green | 0--30% | All (G1--G5) |
| Yellow | 30--60% | G1--G3 |
| Orange | 60--80% | G1--G2 only |
| Red | 80--100% | None (budget exhausted) |

`clutch/config/fitness_criteria.json` is the single runtime source for these
limits. Both the onboard computer and the clutch read the same policy; a red
zone stops routing before an LLM is selected.

---

## Supported Providers

| Provider | Models | Local |
|----------|--------|-------|
| **Anthropic** | Claude Fable 5, Haiku, Sonnet, Opus | No |
| **Google** | Gemini 3.7 Flash (preferred), Gemini 3.5 Flash fallback, Gemini 3.1 Pro Preview | No |
| **OpenAI** | GPT-5.6 Luna/Terra/Sol via Responses API, GPT-5.3-Codex | No |
| **Ollama** | Qwen, Mistral, and more (local & remote) | Yes |
| **Claude Code** | Via subprocess (CLI session) | Yes |
| **agy** | Live-discovered Gemini, Claude and GPT-OSS catalog via `companion-for-agy` | CLI session |
| **Kimi (Moonshot)** | `kimi-k2.7-code`, `kimi-k2.6` via OpenAI-compatible API; `kimi-cli`/`kimi-code` CLI; Ollama Cloud | API / CLI |
| **OpenAI-compatible** | Any `/v1/chat/completions` endpoint (set `base_url`) | No |

### GPT-5.6 Cost and Empirical Routing

GPT-5.6 pricing is versioned in the model catalog and shared by runtime telemetry, Tankuhr, CLI/API JSON, and stats. The calculator distinguishes observed, assumed, and unknown usage; missing provider usage is unmetered (`cost_usd=null`), not zero. It accounts for cached input, cache writes, the >272k long-context multipliers, Standard/Fast service, tool fees, and reasoning tokens exactly once.

```bash
clutch cost --model gpt-5.6-terra --input 100000 --cached-input 20000 --output 10000 --json
```

All three GPT-5.6 models expose efforts `none`, `low`, `medium`, `high`, `xhigh`, and `max`. Higher effort allows more reasoning but does not guarantee monotonically more visible tokens or universally better outcomes. Routing therefore applies per-task quality/latency gates and expected cost per successful task on a Pareto frontier; without enough labelled observations it reports a role-based cold start rather than fabricating scores.

See [GPT-5.6 cost and routing](docs/GPT56_COST_ROUTING.md), the [example input](docs/gpt56_cost_example.json), and the generated [price-facts chart](docs/gpt56_price_facts.svg).

---

## Execution Patterns

- **Single** -- one model, one task
- **Convoy (Kolonne)** -- sequential chain, output N feeds input N+1
- **Team** -- parallel specialized workers, results merged
- **Swarm** -- massively parallel micro-tasks (e.g., 20x Haiku), then aggregation

---

## Project Structure

```
clutch/
+-- clutch/
|   +-- __init__.py
|   +-- fahrer.py          # Orchestrator
|   +-- strecke.py         # Task analysis
|   +-- getriebe.py        # Model registry
|   +-- kupplung.py        # Model switching
|   +-- motorblock.py      # Unified API layer
|   +-- gas_bremse.py      # Reasoning level
|   +-- fahrtenbuch.py     # SQLite metrics
|   +-- bordcomputer.py    # Health monitor
|   +-- tankuhr.py         # Budget tracking
|   +-- tacho.py           # Metrics
|   +-- fahrschule.py      # Learning engine
|   +-- token_throughput.py# Anthropic 5h/7d throughput
|   +-- patterns/
|       +-- kolonne.py     # Chain pattern
|       +-- team.py        # Parallel pattern
|       +-- schwarm.py     # Swarm pattern
|       +-- hybrid.py      # Hybrid pattern
|   +-- config/
|       +-- kupplung.json
|       +-- getriebe.json
|       +-- strecken.json
|       +-- fitness_criteria.json
+-- tests/
|   +-- test_clutch.py
|   +-- test_learning.py
|   +-- test_patterns.py
|   +-- test_route.py
|   +-- test_metadata.py   # Automated parity contract tests
+-- data/                  # Runtime data (not tracked)
```

---

## Tests

```bash
pip install -e . pytest
pytest -q
```

Pytest is configured to collect only `tests/`. Root-level smoke scripts such as
`demo.py`, `live_test.py`, and `claude_code_test.py` are manual provider checks.

---

## Ecosystem & Sibling Tools

Part of the [ellmos-ai](https://github.com/ellmos-ai) multi-agent infrastructure and the overarching [open-bricks](https://github.com/open-bricks) open-source software ecosystem:

| Tool | Organization | Description |
|------|--------------|-------------|
| [coma](https://github.com/ellmos-ai/coma) | ellmos-ai | Single-binary multi-agent orchestrator & execution coordinator |
| [swarm-ai](https://github.com/ellmos-ai/swarm-ai) | ellmos-ai | Swarm intelligence and autonomous agent consensus engine |
| [system-explorer](https://github.com/ellmos-ai/system-explorer) | ellmos-ai | Local system discovery and hardware resource monitor |
| [policy-registry](https://github.com/ellmos-ai/policy-registry) | ellmos-ai | Unified agent permission and policy management engine |
| [sqlite-transit-sync](https://github.com/ellmos-ai/sqlite-transit-sync) | ellmos-ai | Multi-agent state synchronization via SQLite WAL journals |
| [workflowhooker](https://github.com/ellmos-ai/workflowhooker) | ellmos-ai | Event hooks and agent workflow automation triggers |
| [memoryhooker](https://github.com/ellmos-ai/memoryhooker) | ellmos-ai | Transparent SQLite/FTS5 working memory capture for agents |
| [agent-ops-stack](https://github.com/ellmos-ai/agent-ops-stack) | ellmos-ai | Composed operational sidecar stack for autonomous agents |
| [convergence-reconciler](https://github.com/ellmos-ai/convergence-reconciler) | ellmos-ai | Cross-model convergence validation & consensus engine |
| [DevCenter](https://github.com/dev-bricks/DevCenter) | dev-bricks | Developer control plane, repository dashboard & environment manager |
| [CodeBox](https://github.com/dev-bricks/CodeBox) | dev-bricks | Polyglot code snippet manager & developer workbench |
| [open-bricks](https://github.com/open-bricks) | open-bricks | Umbrella open-source organization for autonomous tools & infrastructure |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
For the German automotive API terms, see [GLOSSARY.md](GLOSSARY.md).

---

## Security Policy & Liability

See [SECURITY.md](SECURITY.md) for supported versions, response SLAs, and vulnerability reporting procedures.

### Haftungsausschluss / Liability Disclaimer

Dieses Projekt ist eine **unentgeltliche Open-Source-Schenkung** im Sinne der §§ 516 ff. BGB. Die Haftung des Urhebers ist gemäß **§ 521 BGB** auf **Vorsatz und grobe Fahrlässigkeit** beschränkt. Ergänzend gelten die Haftungsausschlüsse der MIT-Lizenz.

Nutzung auf eigenes Risiko. Keine Wartungszusage, keine Verfügbarkeitsgarantie, keine Gewähr für Fehlerfreiheit oder Eignung für einen bestimmten Zweck.

This project is an unpaid open-source donation. Liability is limited to intent and gross negligence (§ 521 German Civil Code). Use at your own risk. No warranty, no maintenance guarantee, no fitness-for-purpose assumed.
