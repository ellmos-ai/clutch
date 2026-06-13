"""Tests fuer die Kimi-CLI-Motoren (kimi-cli / kimi-code).

Diese Tests rufen NICHT die echten Binaries auf (Login via Moonshot-Account
noetig). Stattdessen wird subprocess.run gemockt, um Argv-Bau und
Output-Parsing zu pruefen. Zusaetzlich wird geprueft, dass die neuen Gaenge in
der Getriebe-Config geladen werden und die Factory die richtigen Motoren liefert.
"""

import sys
import subprocess
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.getriebe import Getriebe
from clutch.gas_bremse import GasBremse
from clutch.kupplung import FahrtConfig
from clutch.motorblock import (
    MotorBlock,
    KimiCliMotor,
    KimiCodeMotor,
)


def _config(getriebe: Getriebe, gang_name: str) -> FahrtConfig:
    gang = getriebe.gang(gang_name)
    assert gang is not None, f"Gang {gang_name} fehlt im Getriebe"
    gas = GasBremse().stellung(0.5)
    return FahrtConfig(gang=gang, gas=gas, muster="einzelfahrt")


def test_kimi_gaenge_in_getriebe():
    """Die beiden Kimi-Gaenge sind registriert, kostenlos und korrekt gemappt."""
    g = Getriebe()

    cli = g.gang("kimi-cli")
    code = g.gang("kimi-code")
    assert cli is not None and code is not None

    assert cli.provider == "kimi-cli"
    assert code.provider == "kimi-code"
    assert cli.ist_kostenlos and code.ist_kostenlos

    provider_set = {gang.provider for gang in g.alle_gaenge()}
    assert "kimi-cli" in provider_set
    assert "kimi-code" in provider_set
    print("[OK] Kimi-Gaenge im Getriebe")


def test_ollama_kimi_cloud_gang():
    """Kimi K2.7 Code via Ollama Cloud: provider=ollama (nutzt vorhandenen
    OllamaMotor), aber NICHT als kostenlos/lokal getaggt."""
    g = Getriebe()
    gang = g.gang("ollama-kimi-k2")
    assert gang is not None
    assert gang.provider == "ollama"
    assert gang.model_id == "kimi-k2.7-code:cloud"
    # Cloud-Modell: NICHT kostenlos (Abgrenzung zu echten lokalen Ollama-Gaengen)
    assert not gang.ist_kostenlos
    print("[OK] Ollama-Kimi-Cloud-Gang")


def test_factory_liefert_kimi_motoren():
    """MotorBlock kennt beide Kimi-Provider und liefert die passenden Klassen."""
    block = MotorBlock()
    assert isinstance(block.motor_fuer("kimi-cli"), KimiCliMotor)
    assert isinstance(block.motor_fuer("kimi-code"), KimiCodeMotor)

    # ist_verfuegbar liefert einen bool (True wenn lokal installiert, sonst False)
    verf = block.verfuegbare_motoren()
    assert isinstance(verf["kimi-cli"], bool)
    assert isinstance(verf["kimi-code"], bool)
    print("[OK] Factory liefert Kimi-Motoren")


def test_kimi_code_argv_und_parsing(monkeypatch):
    """kimi-code: -p <prompt> --output-format text -y, stdout wird zu text."""
    g = Getriebe()
    cfg = _config(g, "kimi-code")
    aufgerufen = {}

    def fake_run(argv, **kwargs):
        aufgerufen["argv"] = argv
        aufgerufen["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="PONG\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    motor = KimiCodeMotor()
    ergebnis = motor.ausfuehren(cfg, "Sag PONG")

    assert ergebnis.erfolg
    assert ergebnis.text == "PONG"
    assert ergebnis.provider == "kimi-code"
    assert ergebnis.input_tokens == 0 and ergebnis.output_tokens == 0
    assert aufgerufen["argv"][0] == "kimi-code"
    assert "-p" in aufgerufen["argv"]
    assert "-y" in aufgerufen["argv"]
    assert aufgerufen["input"] is None  # kimi-code uebergibt den Prompt als Argument
    print("[OK] kimi-code argv + parsing")


def test_kimi_cli_stdin_und_parsing(monkeypatch):
    """kimi-cli: --print --output-format text, Prompt via stdin."""
    g = Getriebe()
    cfg = _config(g, "kimi-cli")
    aufgerufen = {}

    def fake_run(argv, **kwargs):
        aufgerufen["argv"] = argv
        aufgerufen["input"] = kwargs.get("input")
        return SimpleNamespace(returncode=0, stdout="  Antwort  \n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    motor = KimiCliMotor()
    ergebnis = motor.ausfuehren(cfg, "Frage")

    assert ergebnis.erfolg
    assert ergebnis.text == "Antwort"
    assert ergebnis.provider == "kimi-cli"
    assert aufgerufen["argv"][0] == "kimi-cli"
    assert "--print" in aufgerufen["argv"]
    assert aufgerufen["input"] is not None  # kimi-cli bekommt den Prompt via stdin
    print("[OK] kimi-cli stdin + parsing")


def test_kimi_fehler_bei_exit_code(monkeypatch):
    """Nicht-Null-Exit-Code fuehrt zu erfolg=False mit Fehlertext."""
    g = Getriebe()
    cfg = _config(g, "kimi-code")

    def fake_run(argv, **kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="No model configured")

    monkeypatch.setattr(subprocess, "run", fake_run)

    ergebnis = KimiCodeMotor().ausfuehren(cfg, "x")
    assert not ergebnis.erfolg
    assert "No model configured" in (ergebnis.fehler or "")
    print("[OK] kimi Fehlerpfad")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
