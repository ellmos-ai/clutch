"""Regressionstests für die explizit kuratierten aktuellen Modell-IDs."""

from clutch.getriebe import Getriebe


def test_fable_5_ist_hoechster_gang():
    fable = Getriebe().gang("claude-fable")

    assert fable is not None
    assert fable.provider == "anthropic"
    assert fable.model_id == "claude-fable-5"
    assert fable.gang == 5
    assert fable.leistung == "max"
    assert fable.kosten_input_1k == 0.010
    assert fable.kosten_output_1k == 0.050
    assert fable.max_context == 1_000_000


def test_gemini_katalog_verwendet_offizielle_aktuelle_ids():
    getriebe = Getriebe()
    flash = getriebe.gang("gemini-flash")
    pro = getriebe.gang("gemini-pro")

    assert flash is not None and pro is not None
    assert flash.model_id == "gemini-3.5-flash"
    assert pro.model_id == "gemini-3.1-pro-preview"
    assert flash.max_context == pro.max_context == 1_048_576
    assert "gemini-3.5-pro" not in {
        gang.model_id for gang in getriebe.alle_gaenge()
    }
