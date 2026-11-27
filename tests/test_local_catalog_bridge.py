"""Tests for the OCEAN model-tuning-catalog.v1 -> Clutch local gear bridge."""

from __future__ import annotations

import json
from pathlib import Path

from clutch.getriebe import Getriebe
from clutch.local_catalog_bridge import (
    OCEAN_TUNING_SCHEMA,
    build_local_gears_from_catalog,
)


def _sample_catalog() -> dict:
    return {
        "schema": OCEAN_TUNING_SCHEMA,
        "schema_version": 1,
        "updated_at": "2026-11-27",
        "models": [
            {
                "model_id": "inkling-2-mini:latest",
                "quantization": "nvfp4",
                "backends": ["mlx", "ollama"],
                "tool_calling_verified": True,
                "confidence_tier": "measured_live",
                "clutch_gang": 3,
                "clutch_leistung": "hoch",
                "ram_tiers": [
                    {
                        "min_ram_gib": 0,
                        "supported": False,
                        "num_ctx_safe": 4096,
                        "recommended_max_tool_rounds": 15,
                    },
                    {
                        "min_ram_gib": 32,
                        "supported": True,
                        "num_ctx_safe": 16384,
                        "recommended_max_tool_rounds": 40,
                    },
                    {
                        "min_ram_gib": 64,
                        "supported": True,
                        "num_ctx_safe": 32768,
                        "recommended_max_tool_rounds": 50,
                    },
                ],
            },
            {
                "model_id": "gemma4:12b",
                "quantization": "q4_k_m",
                "backends": ["mlx", "gguf", "ollama"],
                "tool_calling_verified": True,
                "confidence_tier": "curated",
                "clutch_gang": 2,
                "clutch_leistung": "mittel",
                "ram_tiers": [
                    {
                        "min_ram_gib": 16,
                        "supported": True,
                        "num_ctx_safe": 16384,
                        "recommended_max_tool_rounds": 30,
                    }
                ],
            },
        ],
    }


def test_build_local_gears_filters_by_host_ram_tier(tmp_path: Path) -> None:
    cat_file = tmp_path / "model-tuning-catalog.v1.json"
    cat_file.write_text(json.dumps(_sample_catalog()), encoding="utf-8")

    gears_16 = build_local_gears_from_catalog(host_ram_gib=16.0, catalog_path=cat_file)
    assert "ollama-gemma4-12b" in gears_16
    assert "ollama-inkling-2-mini" not in gears_16

    gears_32 = build_local_gears_from_catalog(host_ram_gib=32.0, catalog_path=cat_file)
    assert "ollama-inkling-2-mini" in gears_32
    ink = gears_32["ollama-inkling-2-mini"]
    assert ink["num_ctx_safe"] == 16384
    assert ink["max_context"] == 16384
    assert ink["recommended_max_tool_rounds"] == 40
    assert ink["confidence_tier"] == "measured_live"
    assert ink["catalog_source"] == OCEAN_TUNING_SCHEMA


def test_getriebe_apply_local_tuning_catalog_preserves_cloud_gears() -> None:
    getriebe = Getriebe()
    before_count = len(getriebe.filter())
    added = getriebe.apply_local_tuning_catalog(
        host_ram_gib=32.0,
        catalog_data=_sample_catalog(),
    )
    assert "ollama-inkling-2-mini" in added
    assert "ollama-gemma4-12b" in added
    assert len(getriebe.filter()) >= before_count

    ink = getriebe.gang("ollama-inkling-2-mini")
    assert ink is not None
    assert ink.ist_lokal is True
    assert ink.ist_kostenlos is True
    assert ink.max_context == 16384
    assert ink.num_ctx_safe == 16384
    assert ink.recommended_max_tool_rounds == 40
    assert ink.confidence_tier == "measured_live"
