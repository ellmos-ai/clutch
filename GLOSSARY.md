# Glossary

clutch keeps its German automotive terms as a deliberate domain language. This
glossary maps the code terms to English so contributors can read the API without
renaming stable identifiers.

| Code term | English term | Meaning |
|---|---|---|
| `Fahrer` | Driver | Main orchestrator that analyzes tasks, selects routes, and executes work. |
| `Strecke` | Road / route | Task profile derived from a natural-language request. |
| `StreckenTyp` | Road type | Classification such as `feldweg`, `autobahn`, or `teamfahrt`. |
| `Getriebe` | Gearbox | Model registry across providers. |
| `Gang` | Gear | A concrete model option with tier, provider, cost, and strengths. |
| `Kupplung` | Clutch | Selection mechanism for model, reasoning level, and execution pattern. |
| `Gas` | Throttle | Higher reasoning effort and token budget. |
| `Bremse` | Brake | Lower reasoning effort and tighter response style. |
| `MotorBlock` | Engine block | Provider execution layer for Anthropic, Google, Ollama, and Claude Code. |
| `Tacho` | Speedometer | Runtime metrics collector. |
| `Tankuhr` | Fuel gauge | Cost and budget tracker. |
| `Bordcomputer` | Onboard computer | Health monitor and circuit breaker. |
| `Fahrtenbuch` | Trip log | SQLite-backed history of runs and metrics. |
| `Fahrschule` | Driving school | Learning engine that improves routing from historical results. |
| `Kolonne` | Convoy | Sequential chain execution. |
| `Teamfahrt` | Team drive | Parallel specialized-worker execution. |
| `Schwarm` | Swarm | Bulk parallel execution for many small tasks. |
| `HybridFahrt` | Hybrid drive | Mixed sequential and parallel execution phases. |
