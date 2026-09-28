"""Tests für explizite Modellwahl (--model) in clutch (run, chat, route, webapp)."""

from __future__ import annotations

import json
from unittest.mock import patch
import pytest

from clutch.execution import resolve_model
from clutch.fahrer import Fahrer
from clutch.getriebe import Getriebe
from clutch.kupplung import FahrtConfig
from clutch.motorblock import MotorErgebnis
from clutch.strecke import StreckenAnalyse
import clutch.cli as cli


# ---------------------------------------------------------------------------
# 1. resolve_model Tests
# ---------------------------------------------------------------------------

def test_resolve_model_exact_gang_name():
    g = Getriebe()
    gang = resolve_model("ollama-glm-5.3", g)
    assert gang.name == "ollama-glm-5.3"
    assert gang.provider == "ollama"

    gang2 = resolve_model("claude-sonnet", g)
    assert gang2.name == "claude-sonnet"
    assert gang2.provider == "anthropic"


def test_resolve_model_model_id():
    g = Getriebe()
    gang = resolve_model("glm-5.3:cloud", g)
    assert gang.name == "ollama-glm-5.3"

    gang2 = resolve_model("gpt-5.6-terra", g)
    assert gang2.name == "openai-gpt-5.6-terra"


def test_resolve_model_execution_selector():
    g = Getriebe()
    # gpt5 resolves via family profile
    gang = resolve_model("gpt5", g)
    assert gang.provider == "openai"
    assert "gpt-5" in gang.model_id

    # claude profile resolves to an anthropic model
    gang2 = resolve_model("claude", g)
    assert gang2.provider in {"anthropic", "claude-code"}


def test_resolve_model_unknown_fails_closed():
    g = Getriebe()
    with pytest.raises(ValueError, match="Unbekanntes Modell / Selektor"):
        resolve_model("dieses-modell-gibt-es-nicht", g)

    with pytest.raises(ValueError, match="Modell-Selektor darf nicht leer sein"):
        resolve_model("", g)


def test_resolve_model_disabled_fails_closed(tmp_path, monkeypatch):
    # Simulate a disabled model in user overrides
    overrides_file = tmp_path / "user_overrides.json"
    overrides_file.write_text(json.dumps({"disabled_models": ["claude-sonnet"]}), encoding="utf-8")
    monkeypatch.setenv("CLUTCH_OVERRIDES_PATH", str(overrides_file))

    g = Getriebe(overrides_path=overrides_file)
    with pytest.raises(ValueError, match="deaktiviert"):
        resolve_model("claude-sonnet", g)


# ---------------------------------------------------------------------------
# 2. Kupplung / Fahrer Integration
# ---------------------------------------------------------------------------

def test_kuppeln_with_model_override():
    fahrer = Fahrer()
    profil = StreckenAnalyse().analysiere("Schreibe ein kurzes Python-Skript")
    config = fahrer.kuppeln(profil, model_override="ollama-glm-5.3")

    assert config.gang.name == "ollama-glm-5.3"
    assert config.entscheidungs_grund == "explizite Modellwahl: ollama-glm-5.3"
    assert config.ist_erkundung is False
    assert config.alternativen == []


def test_kuppeln_model_override_ignores_budget_zone_downshift():
    fahrer = Fahrer()
    profil = StreckenAnalyse().analysiere("Sehr schwere Aufgabe")
    # Even in a restrictive budget zone, model_override maintains the requested model
    config = fahrer.kupplungs_mechanik.einlegen(profil, model_override="openai-gpt-5.6-terra", budget_zone="sparmodus")
    assert config.gang.name == "openai-gpt-5.6-terra"
    assert config.entscheidungs_grund == "explizite Modellwahl: openai-gpt-5.6-terra"


def test_kuppeln_blocked_model_fails_closed():
    fahrer = Fahrer()
    profil = StreckenAnalyse().analysiere("Aufgabe")
    # If the model is in gesperrte_modelle, kuppeln must raise RuntimeError (no fallback)
    with pytest.raises(RuntimeError, match="deaktiviert oder gesperrt"):
        fahrer.kupplungs_mechanik.einlegen(
            profil,
            gesperrte_modelle=["ollama-glm-5.3"],
            model_override="ollama-glm-5.3",
        )


def test_fahren_with_model_override():
    fahrer = Fahrer()
    recorded_configs = []

    def mock_handler(config: FahrtConfig, task: str) -> MotorErgebnis:
        recorded_configs.append(config)
        return MotorErgebnis(text="Erfolg", erfolg=True, model_id=config.model_id, provider=config.provider)

    res = fahrer.fahren("Test-Prompt", handler=mock_handler, kontext={"model_override": "ollama-glm-5.3"})
    assert res.erfolg is True
    assert len(recorded_configs) == 1
    assert recorded_configs[0].gang.name == "ollama-glm-5.3"
    assert res.config.gang.name == "ollama-glm-5.3"


# ---------------------------------------------------------------------------
# 3. CLI Tests (route, run, chat)
# ---------------------------------------------------------------------------

def test_cli_route_with_model(capsys):
    rc = cli.main(["route", "Schreibe Code", "--model", "ollama-glm-5.3", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["gang"] == "ollama-glm-5.3"
    assert out["grund"] == "explizite Modellwahl: ollama-glm-5.3"
    assert out["alternativen"] == []


def test_cli_route_unknown_model_fails_closed(capsys):
    rc = cli.main(["route", "Schreibe Code", "--model", "unbekanntes-modell-xyz"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Unbekanntes Modell" in err


def test_cli_run_unknown_model_fails_closed(capsys):
    rc = cli.main(["run", "Hallo", "--model", "unbekanntes-modell-xyz"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Modell-Fehler" in err
    assert "Unbekanntes Modell" in err


def test_cli_run_unavailable_model_fails_closed(capsys):
    # Testing with a provider whose motor is unavailable
    with patch("clutch.motorblock.OllamaMotor.ist_verfuegbar", return_value=False):
        rc = cli.main(["run", "Hallo", "--model", "ollama-glm-5.3"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "nicht verfügbar" in err or "not available" in err


def test_cli_run_with_model_success(capsys):
    with patch("clutch.motorblock.Motor.ist_verfuegbar", return_value=True), \
         patch("clutch.motorblock.MotorBlock.ausfuehren") as mock_ausfuehren:
        mock_ausfuehren.return_value = MotorErgebnis(
            text="Antwort von GLM",
            erfolg=True,
            model_id="glm-5.3:cloud",
            provider="ollama",
        )
        rc = cli.main(["run", "Hallo", "--model", "ollama-glm-5.3", "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["output"] == "Antwort von GLM"
        assert out["gang"] == "ollama-glm-5.3"


def test_cli_positional_prompt_with_model(capsys):
    with patch("clutch.motorblock.Motor.ist_verfuegbar", return_value=True), \
         patch("clutch.motorblock.MotorBlock.ausfuehren") as mock_ausfuehren:
        mock_ausfuehren.return_value = MotorErgebnis(
            text="Antwort von GLM",
            erfolg=True,
            model_id="glm-5.3:cloud",
            provider="ollama",
        )
        rc = cli.main(["--model", "ollama-glm-5.3", "Hallo Welt"])
        assert rc == 0
        out = capsys.readouterr().out.strip()
        assert out == "Antwort von GLM"


def test_cli_chat_unknown_model_fails_closed(capsys):
    rc = cli.main(["chat", "--model", "unbekanntes-modell-xyz"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Modell-Fehler" in err


# ---------------------------------------------------------------------------
# 4. ChatRuntime & WebApp Integration
# ---------------------------------------------------------------------------

def test_chat_runtime_with_model():
    from clutch.chat_runtime import ChatRuntime

    with patch("clutch.motorblock.Motor.ist_verfuegbar", return_value=True), \
         patch("clutch.motorblock.MotorBlock.ausfuehren") as mock_ausfuehren:
        mock_ausfuehren.return_value = MotorErgebnis(
            text="Chat Antwort",
            erfolg=True,
            model_id="glm-5.3:cloud",
            provider="ollama",
        )
        rt = ChatRuntime()
        res = rt.chat("session-1", "Hallo", model="ollama-glm-5.3")
        assert res["erfolg"] is True
        assert res["text"] == "Chat Antwort"
        assert res["gang"] == "ollama-glm-5.3"


def test_webapp_chat_with_model():
    from fastapi.testclient import TestClient
    from clutch.webapp import create_app
    from clutch.chat_runtime import ChatRuntime

    with patch("clutch.motorblock.Motor.ist_verfuegbar", return_value=True), \
         patch("clutch.motorblock.MotorBlock.ausfuehren") as mock_ausfuehren:
        mock_ausfuehren.return_value = MotorErgebnis(
            text="Web Antwort",
            erfolg=True,
            model_id="glm-5.3:cloud",
            provider="ollama",
        )
        rt = ChatRuntime()
        app = create_app(runtime=rt)
        client = TestClient(app, base_url="http://127.0.0.1")

        # Successful chat with valid model
        response = client.post("/api/chat", json={"text": "Hi", "model": "ollama-glm-5.3"})
        assert response.status_code == 200
        data = response.json()
        assert data["gang"] == "ollama-glm-5.3"

        # Invalid model returns 400
        bad_response = client.post("/api/chat", json={"text": "Hi", "model": "ungueltiges-modell"})
        assert bad_response.status_code == 400
        assert "Unbekanntes Modell" in bad_response.json()["detail"]
