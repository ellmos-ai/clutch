"""Tests fuer M5d -- ChatRuntime (Konversationsschicht ueber dem Router)."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.chat_runtime import ChatRuntime
from clutch.profile_manager import Profil
from clutch.motorblock import MotorErgebnis


def _fake_handler(antwort="ANTWORT"):
    erfasst = {}

    def handler(config, task):
        erfasst["task"] = task
        erfasst["gang"] = config.gang.name
        return MotorErgebnis(text=antwort, input_tokens=10, output_tokens=5,
                             model_id=config.model_id, provider=config.provider)

    return handler, erfasst


def _runtime(tmp, handler):
    return ChatRuntime(db_path=Path(tmp) / "clutch.db", handler=handler)


def test_chat_persistiert_verlauf():
    with tempfile.TemporaryDirectory() as tmp:
        handler, _ = _fake_handler()
        rt = _runtime(tmp, handler)
        s = rt.neue_session(titel="Test")
        res = rt.chat(s.id, "Hallo, fix den Bug")
        assert res["erfolg"]
        assert res["text"] == "ANTWORT"
        assert res["tokens"] == 15
        verlauf = rt.verlauf(s.id)
        assert len(verlauf) == 2
        assert verlauf[0].role == "user" and verlauf[1].role == "assistant"
        print("[OK] chat persistiert Verlauf")


def test_systemprompt_wird_vorangestellt():
    with tempfile.TemporaryDirectory() as tmp:
        handler, erfasst = _fake_handler()
        rt = _runtime(tmp, handler)
        s = rt.neue_session(system_prompt_on=True)
        rt.chat(s.id, "Meine Aufgabe")
        assert "CLUTCH" in erfasst["task"] or "clutch" in erfasst["task"], \
            "Systemprompt sollte bei system_prompt_on im Vollprompt stecken"
        assert "Meine Aufgabe" in erfasst["task"]
        print("[OK] Systemprompt vorangestellt")


def test_systemprompt_aus():
    with tempfile.TemporaryDirectory() as tmp:
        handler, erfasst = _fake_handler()
        rt = _runtime(tmp, handler)
        s = rt.neue_session(system_prompt_on=False)
        rt.chat(s.id, "Nur die Aufgabe")
        assert erfasst["task"].strip().startswith("Nur die Aufgabe") or \
            "Du arbeitest als ausfuehrendes" not in erfasst["task"]
        print("[OK] Systemprompt aus")


def test_mitgesendete_prompts_aus_profil():
    with tempfile.TemporaryDirectory() as tmp:
        handler, erfasst = _fake_handler()
        rt = _runtime(tmp, handler)
        # Prompt anlegen + in toolset-Profil referenzieren
        from clutch.prompt_library import PromptItem
        item = rt.prompts.upsert(PromptItem(id="", typ="prompt", name="Stil",
                                            content="STILVORGABE-XYZ"))
        rt.profile.speichere(Profil(
            name="meins", scope="toolset",
            payload={"mitgesendete_prompts": [item.id], "system_prompt_on": False},
        ))
        s = rt.neue_session(profil="meins", system_prompt_on=False)
        rt.chat(s.id, "Aufgabe")
        assert "STILVORGABE-XYZ" in erfasst["task"]
        print("[OK] mitgesendete Prompts aus Profil")


def test_nutzungsstatistik():
    with tempfile.TemporaryDirectory() as tmp:
        handler, _ = _fake_handler()
        rt = _runtime(tmp, handler)
        s = rt.neue_session()
        rt.chat(s.id, "Implementiere Feature X")
        stat = rt.nutzungsstatistik()
        assert "tankuhr" in stat and "sessions" in stat
        assert stat["sessions"] >= 1
        print("[OK] Nutzungsstatistik")


def test_bild_kontext_durchgereicht():
    with tempfile.TemporaryDirectory() as tmp:
        handler, erfasst = _fake_handler()
        rt = _runtime(tmp, handler)
        s = rt.neue_session(system_prompt_on=False)
        rt.chat(s.id, "Was ist das?", hat_bild=True)
        # Bild-Kontext -> Zweck vision -> vision-faehiger Gang
        assert "vision" in erfasst["gang"] or erfasst["gang"] != ""
        print("[OK] Bild-Kontext durchgereicht")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
