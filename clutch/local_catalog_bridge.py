"""Bridge between OCEAN's hardware-/RAM-coupled model tuning catalog and Clutch gears.

Allows Clutch to ingest curated and live-measured local Ollama model defaults
from ``ocean.model-tuning-catalog.v1`` (e.g. ``ocean-resources``) filtered to
the host's physical RAM tier, without coupling Clutch to a hard runtime
dependency on ``ocean-resources``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from clutch.getriebe import Gang, Getriebe

OCEAN_TUNING_SCHEMA = "ocean.model-tuning-catalog.v1"


def _discover_catalog_path(catalog_path: Optional[Path] = None) -> Path:
    if catalog_path is not None:
        return Path(catalog_path).resolve()
    try:
        from ocean_resources.model_tuning_catalog import (  # type: ignore[import-not-found]
            DEFAULT_CATALOG_PATH,
        )

        return Path(DEFAULT_CATALOG_PATH).resolve()
    except ImportError as exc:
        raise FileNotFoundError(
            "No catalog_path provided and ocean_resources.model_tuning_catalog is not installed"
        ) from exc


def load_ocean_model_tuning_catalog(catalog_path: Optional[Path] = None) -> dict[str, Any]:
    """Load and validate an ``ocean.model-tuning-catalog.v1`` JSON catalog."""
    target = _discover_catalog_path(catalog_path)
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != OCEAN_TUNING_SCHEMA:
        raise ValueError(f"Unsupported local model tuning catalog schema in {target}")
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError(f"Local model tuning catalog contains no models: {target}")
    return data


def _select_tier(tiers: list[dict[str, Any]], host_ram_gib: float) -> dict[str, Any]:
    ordered = sorted(tiers, key=lambda item: float(item.get("min_ram_gib", 0)))
    chosen = ordered[0]
    for tier in ordered:
        if host_ram_gib + 0.5 >= float(tier.get("min_ram_gib", 0)):
            chosen = tier
    return chosen


def build_local_gears_from_catalog(
    *,
    host_ram_gib: float,
    catalog_path: Optional[Path] = None,
    catalog_data: Optional[dict[str, Any]] = None,
    endpoint: str = "http://localhost:11434",
    include_unsupported: bool = False,
) -> dict[str, dict[str, Any]]:
    """Project local Ollama gears for ``host_ram_gib`` from ``ocean.model-tuning-catalog.v1``."""
    data = catalog_data if catalog_data is not None else load_ocean_model_tuning_catalog(catalog_path)
    if data.get("schema") != OCEAN_TUNING_SCHEMA:
        raise ValueError("Unsupported local model tuning catalog schema")

    checked_at = str(data.get("updated_at") or "") or None
    gears: dict[str, dict[str, Any]] = {}
    for entry in data.get("models") or []:
        mid = str(entry["model_id"])
        tier = _select_tier(entry["ram_tiers"], float(host_ram_gib))
        supported = bool(tier.get("supported", True))
        if not include_unsupported and not supported:
            continue
        slug = mid.split(":", 1)[0].replace(".", "-").replace("/", "-")
        tag = mid.split(":", 1)[1] if ":" in mid else "latest"
        gear_name = f"ollama-{slug}" if tag == "latest" else f"ollama-{slug}-{tag.replace('.', '-')}"
        strengths = ["kostenlos", "lokal", "datenschutz"]
        if entry.get("tool_calling_verified"):
            strengths.append("tool_calling")
        if "mlx" in (entry.get("backends") or []):
            strengths.append("apple_silicon_mlx")
        gears[gear_name] = {
            "provider": "ollama",
            "model_id": mid,
            "gang": int(entry.get("clutch_gang", 2)),
            "leistung": str(entry.get("clutch_leistung", "mittel")),
            "kosten_input_1k": 0.0,
            "kosten_output_1k": 0.0,
            "staerken": strengths,
            "schwaechen": [] if supported else ["ram_zu_knapp"],
            "max_context": int(tier["num_ctx_safe"]),
            "num_ctx_safe": int(tier["num_ctx_safe"]),
            "recommended_max_tool_rounds": int(tier.get("recommended_max_tool_rounds", 25)),
            "min_ram_gib": int(tier.get("min_ram_gib", 0)),
            "confidence_tier": str(entry.get("confidence_tier", "curated")),
            "quantization": entry.get("quantization"),
            "catalog_checked_at": checked_at,
            "catalog_source": OCEAN_TUNING_SCHEMA,
            "endpoint": endpoint,
        }
    return gears


def sync_local_gears_into_getriebe(
    getriebe: Getriebe,
    *,
    host_ram_gib: float,
    catalog_path: Optional[Path] = None,
    catalog_data: Optional[dict[str, Any]] = None,
    endpoint: str = "http://localhost:11434",
    include_unsupported: bool = False,
) -> dict[str, Gang]:
    """Overlay RAM-matched local Ollama gears onto a ``Getriebe`` instance."""
    from clutch.getriebe import Gang

    projected = build_local_gears_from_catalog(
        host_ram_gib=host_ram_gib,
        catalog_path=catalog_path,
        catalog_data=catalog_data,
        endpoint=endpoint,
        include_unsupported=include_unsupported,
    )
    added: dict[str, Gang] = {}
    for name, cfg in projected.items():
        gang = Gang(
            name=name,
            provider=cfg["provider"],
            model_id=cfg["model_id"],
            gang=cfg["gang"],
            leistung=cfg["leistung"],
            kosten_input_1k=cfg["kosten_input_1k"],
            kosten_output_1k=cfg["kosten_output_1k"],
            staerken=list(cfg["staerken"]),
            schwaechen=list(cfg["schwaechen"]),
            max_context=cfg["max_context"],
            endpoint=cfg["endpoint"],
            catalog_checked_at=cfg["catalog_checked_at"],
            catalog_source=cfg["catalog_source"],
            quantization=cfg["quantization"],
            num_ctx_safe=cfg["num_ctx_safe"],
            recommended_max_tool_rounds=cfg["recommended_max_tool_rounds"],
            min_ram_gib=cfg["min_ram_gib"],
            confidence_tier=cfg["confidence_tier"],
        )
        getriebe._gaenge[name] = gang
        added[name] = gang
    return added
