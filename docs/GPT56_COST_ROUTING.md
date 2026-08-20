# GPT-5.6 cost and empirical routing

Data status: **official catalog and price facts, checked 2026-08-20**. Performance status: **not measured by this document**. The generated [price-facts chart](gpt56_price_facts.svg) is derived from `clutch/config/getriebe.json`; regenerate it with:

```powershell
python docs/generate_gpt56_price_facts.py
```

## Catalog and API transport

clutch catalogs `gpt-5.6-luna`, `gpt-5.6-terra`, and `gpt-5.6-sol`. Each supports `none`, `low`, `medium` (default), `high`, `xhigh`, and `max`. OpenAI calls use the Responses API. `FahrtConfig.effort` records the requested value, and `effective_effort` records the value sent. `max-delegate` is a clutch orchestration marker, never an API value: it maps to `max` only for a call explicitly marked `is_delegate=True`; otherwise the call fails closed.

Higher effort allows more reasoning. It does **not** guarantee monotonically more visible tokens or universally better results. Treat each model/effort pair as an empirical candidate for a specific task class.

## Versioned price calculation

The single source of truth is the nested `pricing` object for each catalog entry. Rates are USD per one million tokens:

| Model | Input | Cached input | Output |
|---|---:|---:|---:|
| GPT-5.6 Luna | $0.20 | $0.02 | $1.20 |
| GPT-5.6 Terra | $2.00 | $0.20 | $12.00 |
| GPT-5.6 Sol | $5.00 | $0.50 | $30.00 |

Cache writes cost 1.25 times uncached input. Above 272,000 input tokens, the whole request uses 2 times input rates and 1.5 times output rates. Standard/default uses multiplier 1; Fast/priority uses multiplier 2 for model tokens. Tool fees remain separate. Reasoning tokens are included in output tokens and are never billed again.

Provider-returned usage is `observed`; calculator inputs are `assumed` by default. If usage is missing, `usage_status=unknown` and `cost_usd=null`—never a fabricated zero.

```powershell
clutch cost --model gpt-5.6-terra --input 100000 --cached-input 20000 --output 10000 --json
clutch cost --model gpt-5.6-sol --input 300000 --output 20000 --service-tier fast --data-status assumed --json
```

Runtime, SQLite telemetry, Tankuhr, CLI JSON, web model JSON, and stats use this same calculator or its persisted result. Stored records include model, requested/effective effort, mode, service tier, task class/eval case, all token categories, tool fees, price version, cost, and usage status.

## Empirical route selection

`clutch/config/eval_profiles.json` defines reproducible cases, gates, and the complete candidate grid without inventing quality scores. Only externally labelled runs with observed usage and known cost enter empirical routing. Selection proceeds in this order:

1. require the configured sample size, minimum quality/pass rate, and latency gate;
2. include retry and fallback spend in expected cost per successful task;
3. form the non-dominated quality/cost/latency Pareto frontier;
4. choose the lowest expected cost per success on that frontier.

Without enough data, the decision is labelled `cold_start` and uses OpenAI's published roles: Luna for volume/cost-sensitive work, Terra for balance, and Sol for complex professional work. Sol is called evidence-required only when adequately sampled non-Sol candidates fail the gate and Sol passes it. There is no static model/effort intelligence matrix and no polling of launch-page benchmark snapshots.

## Refresh routine

1. Verify the live OpenAI model pages and latest-model guide, plus the official price update.
2. Update rates, `version`, `effective_at`, `checked_at`, and `source_url` together in `getriebe.json`.
3. Regenerate the SVG and run `pytest`, `ruff check .`, `python -m compileall -q clutch`, and `git diff --check`.
4. Inspect `clutch models --no-discovery --json`; `pricing_stale=true` is the fail-visible signal once the configured freshness period expires.

Official sources: [model catalog](https://developers.openai.com/api/docs/models), [latest-model guide](https://developers.openai.com/api/docs/guides/latest-model), [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), and the [official price-performance update](https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/).

## Historical user-supplied images

The following basenames are references only and were not imported as production data:

- `kosten leistung gpt 5.6 modell und effort.png` — SHA-256 `2649c2caa1b9cc041db97c9edd2734d1ada7c5e9a4f98ade04d112781e40366c`; unverified historical input.
- `Äquivalenzstufen gpt 5.6.png` — SHA-256 `6450f373a9e1ec9b842cd2a6fce4cdcdffa4d6496fb46c0f5bea1fa47bd8bd8c`; unverified historical input.

No private absolute path is stored.
