"""Tests fuer die Google-Gemini-4-Modellfamilie (Direct API & agy) im Getriebe."""

from clutch.execution import resolve_execution_selector
from clutch.gas_bremse import GasBremse
from clutch.getriebe import Getriebe
from clutch.kupplung import FahrtConfig
from clutch.motorblock import AgyCompanionMotor


def test_google_api_gemini_4_models_registered():
    g = Getriebe()

    expected = {
        "gemini-4-carbon": (5, "max", ["low", "medium", "high"]),
        "gemini-4-neon": (5, "max", ["low", "medium", "high", "xhigh"]),
        "gemini-4-argon": (4, "hoch", ["low", "medium", "high"]),
        "gemini-4-hydrogen": (2, "mittel", ["low", "medium", "high", "xhigh"]),
    }
    for name, (stufe, leistung, efforts) in expected.items():
        gang = g.gang(name)
        assert gang is not None, f"{name} fehlt im Getriebe"
        assert gang.provider == "google"
        assert gang.model_id == name
        assert gang.gang == stufe
        assert gang.leistung == leistung
        assert gang.max_context == 1_048_576
        assert gang.efforts == efforts
        assert gang.catalog_checked_at == "2026-11-23"
        assert gang.catalog_source == "https://ai.google.dev/gemini-api/docs/models"


def test_gemini_4_hydrogen_is_preferred_g2_and_argon_leads_g4():
    g = Getriebe()

    hoch = g.naechster_gang_hoch("claude-haiku")
    assert hoch is not None and hoch.name == "gemini-4-hydrogen"

    runter = g.naechster_gang_runter("claude-sonnet")
    assert runter is not None and runter.name == "gemini-4-hydrogen"

    google_g2 = [x.name for x in g.filter(provider="google", max_gang=2)]
    assert google_g2 == ["gemini-4-hydrogen", "gemini-3.7-flash", "gemini-flash"]

    google_g4 = [x.name for x in g.filter(provider="google", min_gang=4, max_gang=4)]
    assert google_g4 == ["gemini-4-argon", "gemini-pro"]

    # Budget-Downshift-Ziel bleibt unveraendert.
    assert g.filter(max_gang=2)[-1].name == "ollama-mistral"


def test_agy_gemini_4_models_and_effort_mapping():
    g = Getriebe()
    motor = AgyCompanionMotor(binary="companion-for-agy")

    for name, model_id, stufe in (
        ("agy-gemini-4-carbon", "gemini-4-carbon", 5),
        ("agy-gemini-4-neon", "gemini-4-neon", 5),
        ("agy-gemini-4-argon", "gemini-4-argon", 4),
        ("agy-gemini-4-hydrogen", "gemini-4-hydrogen", 3),
    ):
        gang = g.gang(name)
        assert gang is not None
        assert gang.provider == "agy"
        assert gang.model_id == model_id
        assert gang.gang == stufe
        assert gang.max_context == 1_048_576
        assert gang.catalog_checked_at == "2026-11-23"

    neon_cfg = FahrtConfig(
        gang=g.gang("agy-gemini-4-neon"),
        gas=GasBremse().stellung(0.8),
        muster="einzelfahrt",
        effort="xhigh",
    )
    assert motor._effort(neon_cfg) == "xhigh"

    carbon_cfg = FahrtConfig(
        gang=g.gang("agy-gemini-4-carbon"),
        gas=GasBremse().stellung(0.9),
        muster="einzelfahrt",
        effort="xhigh",
    )
    assert motor._effort(carbon_cfg) == "high"


def test_gemini_4_selector_disambiguates_google_vs_agy():
    g = Getriebe()

    ambiguous = resolve_execution_selector("gemini-4-carbon", registry=g)
    assert not ambiguous["resolved"]
    assert ambiguous["reason"] == "ambiguous-exact-selector"

    via_api = resolve_execution_selector("gemini-4-carbon", runner="clutch", registry=g)
    assert via_api["resolved"]
    assert via_api["registry_name"] == "gemini-4-carbon"

    via_agy = resolve_execution_selector("gemini-4-carbon", runner="agy", registry=g)
    assert via_agy["resolved"]
    assert via_agy["registry_name"] == "agy-gemini-4-carbon"
