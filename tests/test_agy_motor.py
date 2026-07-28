"""Tests fuer die agy-Registry und den companion-for-agy-Motor."""

import json
import subprocess
from types import SimpleNamespace

from clutch.gas_bremse import GasBremse
from clutch.getriebe import Getriebe
from clutch.kupplung import AGENTIC_CLI_PROVIDERS, FahrtConfig
from clutch.motorblock import AgyCompanionMotor, MotorBlock


def _config(name: str, effort: str | None = None) -> FahrtConfig:
    gang = Getriebe().gang(name)
    assert gang is not None
    return FahrtConfig(
        gang=gang,
        gas=GasBremse().stellung(0.5),
        muster="einzelfahrt",
        effort=effort,
    )


def test_agy_registry_has_live_catalog_metadata():
    getriebe = Getriebe()
    models = getriebe.filter(provider="agy")
    assert {gang.model_id for gang in models} == {
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.1-pro",
        "claude-sonnet-4.6",
        "claude-opus-4.6",
        "gpt-oss-120b",
    }
    assert all(gang.catalog_checked_at == "2026-07-28" for gang in models)
    assert all(gang.catalog_source == "agy-invalid-model-probe" for gang in models)
    assert getriebe.gang("agy-gemini-3.6-flash").efforts == ["high", "medium", "low"]


def test_agy_is_registered_as_agentic_cli():
    assert "agy" in AGENTIC_CLI_PROVIDERS
    assert isinstance(MotorBlock().motor_fuer("agy"), AgyCompanionMotor)


def test_agy_motor_builds_model_and_supported_effort(monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({
                "response": "PONG",
                "model": "gemini-3.6-flash",
            }),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = AgyCompanionMotor(binary="companion-for-agy").ausfuehren(
        _config("agy-gemini-3.6-flash", effort="xhigh"),
        "Sag PONG",
    )

    assert result.erfolg
    assert result.text == "PONG"
    assert result.provider == "agy"
    assert captured["argv"][:6] == [
        "companion-for-agy",
        "--json",
        "--sandbox",
        "--model",
        "gemini-3.6-flash",
        "--effort",
    ]
    assert captured["argv"][6] == "high"
    assert captured["argv"][-2] == "--"


def test_agy_motor_selects_thinking_and_reports_errors(monkeypatch):
    config = _config("agy-claude-sonnet-4.6", effort="high")
    motor = AgyCompanionMotor(binary="companion-for-agy")
    assert motor._effort(config) == "thinking"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=7,
            stdout="",
            stderr="model unavailable",
        ),
    )
    result = motor.ausfuehren(config, "x")
    assert not result.erfolg
    assert "model unavailable" in (result.fehler or "")
