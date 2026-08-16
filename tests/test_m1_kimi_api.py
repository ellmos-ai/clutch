"""Tests fuer M1 -- Kimi-API-Motor (OpenAI-kompatibel)."""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.getriebe import Getriebe
from clutch.gas_bremse import GasBremse
from clutch.kupplung import FahrtConfig
from clutch.motorblock import (
    KimiApiMotor,
    MotorBlock,
    OpenAICompatibleMotor,
    OpenAIMotor,
)


def _cfg(gang_name):
    g = Getriebe()
    gang = g.gang(gang_name)
    assert gang is not None, f"Gang {gang_name} fehlt"
    return FahrtConfig(gang=gang, gas=GasBremse().stellung(0.5), muster="einzelfahrt")


def test_kimi_api_gaenge_registriert():
    g = Getriebe()
    code = g.gang("kimi-api-code")
    vision = g.gang("kimi-api-vision")
    assert code and vision
    assert code.provider == "kimi-api" and vision.provider == "kimi-api"
    assert code.model_id == "kimi-k2.7-code"
    assert vision.model_id == "kimi-k2.6"
    # API-Modelle haben echte Kosten (kein 0-Tarif wie die CLI/Session-Gaenge)
    assert not code.ist_kostenlos
    print("[OK] Kimi-API-Gaenge registriert")


def test_factory_kennt_kimi_api():
    block = MotorBlock()
    assert isinstance(block.motor_fuer("kimi-api"), KimiApiMotor)
    print("[OK] Factory kennt kimi-api")


def test_kimi_api_motor_request_und_usage(monkeypatch):
    cfg = _cfg("kimi-api-code")
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{"message": {"content": "PONG"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        erfasst["url"] = url
        erfasst["headers"] = headers
        erfasst["json"] = json
        return FakeResp()

    fake_requests = SimpleNamespace(post=fake_post)
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    motor = KimiApiMotor(api_key="sk-test")
    erg = motor.ausfuehren(cfg, "Sag PONG")

    assert erg.erfolg
    assert erg.text == "PONG"
    assert erg.input_tokens == 12 and erg.output_tokens == 3
    assert erfasst["url"].endswith("/chat/completions")
    assert "api.moonshot.ai" in erfasst["url"]
    assert erfasst["headers"]["Authorization"] == "Bearer sk-test"
    assert erfasst["json"]["model"] == "kimi-k2.7-code"
    assert "max_tokens" in erfasst["json"]
    assert "max_completion_tokens" not in erfasst["json"]
    print("[OK] Kimi-API Request + Usage")


def test_kimi_api_nicht_verfuegbar_ohne_key(monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    assert KimiApiMotor(api_key="").ist_verfuegbar() is False
    assert KimiApiMotor(api_key="sk-x").ist_verfuegbar() is True
    print("[OK] Kimi-API Verfuegbarkeit haengt am Key")


def test_openai_kompatibel_base_url_konfigurierbar():
    m = OpenAICompatibleMotor(base_url="http://localhost:1234/v1", api_key="x")
    assert m.base_url == "http://localhost:1234/v1"
    print("[OK] OpenAI-kompatibel base_url konfigurierbar")


def test_openai_gaenge_und_factory_registriert():
    getriebe = Getriebe()
    codex = getriebe.gang("openai-codex")
    sol = getriebe.gang("openai-gpt-5.6-sol")
    terra = getriebe.gang("openai-gpt-5.6-terra")

    assert codex and sol and terra
    assert codex.provider == sol.provider == terra.provider == "openai"
    assert codex.model_id == "gpt-5.3-codex"
    assert sol.model_id == "gpt-5.6-sol"
    assert terra.model_id == "gpt-5.6-terra"
    assert isinstance(MotorBlock().motor_fuer("openai"), OpenAIMotor)


def test_openai_motor_nutzt_max_completion_tokens(monkeypatch):
    cfg = _cfg("openai-gpt-5.6-sol")
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [{"message": {"content": "OPENAI_OK"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        erfasst["url"] = url
        erfasst["headers"] = headers
        erfasst["json"] = json
        return FakeResp()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    ergebnis = OpenAIMotor(api_key="sk-test").ausfuehren(cfg, "Antworte kurz")

    assert ergebnis.erfolg
    assert ergebnis.text == "OPENAI_OK"
    assert ergebnis.provider == "openai"
    assert erfasst["url"] == "https://api.openai.com/v1/chat/completions"
    assert "max_completion_tokens" in erfasst["json"]
    assert "max_tokens" not in erfasst["json"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
