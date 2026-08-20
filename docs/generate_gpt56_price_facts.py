"""Generate the GPT-5.6 price-facts SVG from clutch's versioned catalog."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clutch.getriebe import Getriebe  # noqa: E402


MODELS = (
    "openai-gpt-5.6-luna",
    "openai-gpt-5.6-terra",
    "openai-gpt-5.6-sol",
)


def render() -> str:
    models = [Getriebe().gang(name) for name in MODELS]
    checked = {model.pricing.checked_at for model in models}
    effective = {model.pricing.effective_at for model in models}
    version = {model.pricing.version for model in models}
    if len(checked) != 1 or len(effective) != 1 or len(version) != 1:
        raise ValueError("GPT-5.6 catalog facts must share one checked/effective/version state")

    colors = {"input": "#38bdf8", "cached": "#34d399", "output": "#f59e0b"}
    max_rate = max(model.pricing.output_per_million for model in models)
    rows = []
    for index, model in enumerate(models):
        y = 158 + index * 112
        rows.append(
            f'<text x="36" y="{y}" class="model">{model.model_id}</text>'
            f'<text x="265" y="{y}" class="value">'
            f'input ${model.pricing.input_per_million:g} · cached ${model.pricing.cached_input_per_million:g} · '
            f'output ${model.pricing.output_per_million:g}</text>'
        )
        for offset, (kind, rate) in enumerate((
            ("input", model.pricing.input_per_million),
            ("cached", model.pricing.cached_input_per_million),
            ("output", model.pricing.output_per_million),
        )):
            width = max(2.0, 520 * rate / max_rate)
            bar_y = y + 15 + offset * 18
            rows.append(
                f'<rect x="265" y="{bar_y}" width="{width:.2f}" height="10" '
                f'fill="{colors[kind]}" rx="3"/><text x="796" y="{bar_y + 9}" class="legend">{kind}</text>'
            )

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="540" viewBox="0 0 920 540">
<title>GPT-5.6 official price facts</title>
<desc>Generated from clutch/config/getriebe.json. This is not a performance evaluation.</desc>
<style>
  .title {{ font: 700 24px system-ui, sans-serif; fill: #e2e8f0; }}
  .meta {{ font: 14px system-ui, sans-serif; fill: #94a3b8; }}
  .model {{ font: 700 16px ui-monospace, monospace; fill: #e2e8f0; }}
  .value {{ font: 14px system-ui, sans-serif; fill: #cbd5e1; }}
  .legend {{ font: 11px system-ui, sans-serif; fill: #94a3b8; }}
</style>
<rect width="920" height="540" fill="#0f172a" rx="16"/>
<text x="36" y="48" class="title">GPT-5.6 token price facts (USD / 1M tokens)</text>
<text x="36" y="78" class="meta">data status: official price facts · not a performance evaluation</text>
<text x="36" y="101" class="meta">effective: {next(iter(effective))} · checked: {next(iter(checked))} · version: {next(iter(version))}</text>
<text x="36" y="124" class="meta">confidence: source-verified tariff; empirical quality sample: n/a</text>
{''.join(rows)}
<text x="36" y="511" class="meta">Long context &gt;272k: input ×2, output ×1.5 · cache write: uncached input ×1.25 · Fast: token price ×2</text>
</svg>
'''


def main() -> int:
    output = Path(__file__).with_name("gpt56_price_facts.svg")
    output.write_text(render(), encoding="utf-8", newline="\n")
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
