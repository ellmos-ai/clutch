"""Regression: OllamaMotor muss den Endpoint des Gangs treffen (Remote-Host),
nicht stur localhost. Vorher wurde ``Gang.endpoint`` (per Discovery gesetzt)
bei der Ausfuehrung und beim Verfuegbarkeitscheck ignoriert.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.gas_bremse import GasBremse
from clutch.getriebe import Gang
from clutch.kupplung import FahrtConfig
from clutch.motorblock import MotorBlock, OllamaMotor

REMOTE = "http://mac-im-vpn:11434"


def _remote_cfg():
    gang = Gang(
        name="remote-qwen", provider="ollama", model_id="qwen3:4b", gang=2,
        leistung="mittel", kosten_input_1k=0.0, kosten_output_1k=0.0,
        endpoint=REMOTE,
    )
    return FahrtConfig(gang=gang, gas=GasBremse().stellung(0.5), muster="einzelfahrt")


def test_ausfuehren_trifft_gang_endpoint(monkeypatch):
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "ok", "prompt_eval_count": 2, "eval_count": 3}

    def fake_post(url, json=None, timeout=None):
        erfasst["url"] = url
        return FakeResp()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    # Motor mit localhost-Default konstruiert -- der Gang-Endpoint muss gewinnen.
    erg = OllamaMotor().ausfuehren(_remote_cfg(), "hi")

    assert erg.erfolg
    assert erg.text == "ok"
    assert erfasst["url"].startswith(REMOTE), erfasst["url"]
    assert "localhost" not in erfasst["url"]
    print("[OK] ausfuehren trifft Gang-Endpoint")


def test_ist_verfuegbar_prueft_gang_endpoint(monkeypatch):
    erfasst = {}

    def fake_get(url, timeout=None):
        erfasst["url"] = url
        return SimpleNamespace(status_code=200)

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(get=fake_get))

    assert OllamaMotor().ist_verfuegbar(_remote_cfg()) is True
    assert erfasst["url"].startswith(REMOTE), erfasst["url"]
    print("[OK] ist_verfuegbar prueft Gang-Endpoint")


def test_motorblock_routet_zum_gang_endpoint(monkeypatch):
    """Voller Pfad ueber MotorBlock: Verfuegbarkeit + Ausfuehrung am Remote-Host."""
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "pong", "prompt_eval_count": 1, "eval_count": 1}

    def fake_get(url, timeout=None):
        erfasst["get"] = url
        return SimpleNamespace(status_code=200)

    def fake_post(url, json=None, timeout=None):
        erfasst["post"] = url
        return FakeResp()

    monkeypatch.setitem(sys.modules, "requests",
                        SimpleNamespace(get=fake_get, post=fake_post))

    erg = MotorBlock().ausfuehren(_remote_cfg(), "ping")

    assert erg.erfolg and erg.text == "pong"
    assert erfasst["get"].startswith(REMOTE)
    assert erfasst["post"].startswith(REMOTE)
    print("[OK] MotorBlock routet zum Gang-Endpoint")


def test_default_bleibt_localhost(monkeypatch):
    """Ohne Gang-Endpoint bleibt das bisherige Verhalten (localhost) erhalten."""
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "x"}

    def fake_post(url, json=None, timeout=None):
        erfasst["url"] = url
        return FakeResp()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))

    gang = Gang(name="lokal", provider="ollama", model_id="mistral", gang=1,
                leistung="basis", kosten_input_1k=0.0, kosten_output_1k=0.0,
                endpoint=None)
    cfg = FahrtConfig(gang=gang, gas=GasBremse().stellung(0.5), muster="einzelfahrt")

    OllamaMotor().ausfuehren(cfg, "hi")
    assert erfasst["url"].startswith("http://localhost:11434")
    print("[OK] Default bleibt localhost")


def _capture_timeout(monkeypatch):
    erfasst = {}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "ok"}

    def fake_post(url, json=None, timeout=None):
        erfasst["timeout"] = timeout
        return FakeResp()

    monkeypatch.setitem(sys.modules, "requests", SimpleNamespace(post=fake_post))
    return erfasst


def test_timeout_basis_parameter(monkeypatch):
    """Grosse Lokalmodelle: Timeout-Basis per Parameter erhöhbar (Default 60)."""
    erfasst = _capture_timeout(monkeypatch)
    OllamaMotor(timeout_basis=300).ausfuehren(_remote_cfg(), "hi")
    assert erfasst["timeout"] >= 300, erfasst["timeout"]
    print("[OK] timeout_basis Parameter")


def test_timeout_basis_env(monkeypatch):
    """Env CLUTCH_OLLAMA_TIMEOUT überschreibt den Default."""
    monkeypatch.setenv("CLUTCH_OLLAMA_TIMEOUT", "200")
    erfasst = _capture_timeout(monkeypatch)
    OllamaMotor().ausfuehren(_remote_cfg(), "hi")
    assert erfasst["timeout"] >= 200, erfasst["timeout"]
    print("[OK] CLUTCH_OLLAMA_TIMEOUT Env")


def test_timeout_default_unveraendert(monkeypatch):
    """Ohne Konfiguration bleibt der bisherige 60s-Basis-Default."""
    monkeypatch.delenv("CLUTCH_OLLAMA_TIMEOUT", raising=False)
    erfasst = _capture_timeout(monkeypatch)
    OllamaMotor().ausfuehren(_remote_cfg(), "hi")
    # 60 * gas.timeout_multiplikator (gas 0.5 -> ~1.0–1.2); jedenfalls < 100.
    assert 50 <= erfasst["timeout"] < 100, erfasst["timeout"]
    print("[OK] Default-Timeout unverändert")


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
