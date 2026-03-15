"""Motorblock -- Echte LLM-Provider-Handler.

Der Motorblock ist die Verbindung zwischen Kupplung (Routing-Entscheidung)
und den tatsaechlichen LLM-APIs. Jeder Motor implementiert den API-Call
fuer einen bestimmten Provider.

Motoren:
  AnthropicMotor  -- Claude-Modelle ueber Anthropic SDK
  GeminiMotor     -- Gemini-Modelle ueber Google GenAI SDK
  OllamaMotor     -- Lokale Modelle ueber Ollama HTTP API
  ClaudeCodeMotor -- Claude Code CLI als subprocess
  MotorBlock      -- Factory die den richtigen Motor waehlt
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Optional

from clutch.kupplung import FahrtConfig
from clutch.gas_bremse import GasBremse, GasStellung

logger = logging.getLogger("clutch.motorblock")


# ---------------------------------------------------------------------------
# Ergebnis-Datenklasse
# ---------------------------------------------------------------------------

@dataclass
class MotorErgebnis:
    """Ergebnis eines LLM-Calls."""
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    model_id: str = ""
    provider: str = ""
    latenz_sekunden: float = 0.0
    erfolg: bool = True
    fehler: Optional[str] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


# ---------------------------------------------------------------------------
# Basis-Motor
# ---------------------------------------------------------------------------

class Motor:
    """Abstrakte Basis fuer alle LLM-Motoren."""

    provider_name: str = "basis"

    def __init__(self):
        self._pedal = GasBremse()

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        """Fuehrt einen LLM-Call aus.

        Args:
            config: FahrtConfig mit Gang, Gas etc.
            prompt: Der eigentliche Task-Prompt.

        Returns:
            MotorErgebnis mit Text, Token-Counts etc.
        """
        raise NotImplementedError

    def _prompt_mit_gas(self, config: FahrtConfig, prompt: str) -> str:
        """Reichert den Prompt mit Gas-Prefix an."""
        prefix = self._pedal.prompt_prefix(config.gas)
        if prefix:
            return f"{prefix}\n\n{prompt}"
        return prompt

    def _max_tokens(self, config: FahrtConfig, basis: int = 4096) -> int:
        """Berechnet max_tokens basierend auf Gas-Stellung."""
        return int(basis * config.gas.token_multiplikator)

    def _timeout(self, config: FahrtConfig, basis: float = 30.0) -> float:
        """Berechnet Timeout basierend auf Gas-Stellung."""
        return basis * config.gas.timeout_multiplikator

    def ist_verfuegbar(self) -> bool:
        """Prueft ob dieser Motor einsatzbereit ist."""
        return False


# ---------------------------------------------------------------------------
# Anthropic Motor (Claude)
# ---------------------------------------------------------------------------

class AnthropicMotor(Motor):
    """Motor fuer Claude-Modelle ueber das Anthropic SDK."""

    provider_name = "anthropic"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                raise RuntimeError(
                    "anthropic SDK nicht installiert. "
                    "Installiere mit: pip install anthropic"
                )
        return self._client

    def ist_verfuegbar(self) -> bool:
        return bool(self._api_key)

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        max_tok = self._max_tokens(config)
        timeout = self._timeout(config)

        try:
            client = self._get_client()
            response = client.messages.create(
                model=config.model_id,
                max_tokens=max_tok,
                messages=[{"role": "user", "content": vollprompt}],
                timeout=timeout,
            )

            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            return MotorErgebnis(
                text=text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except Exception as e:
            logger.error(f"AnthropicMotor Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


# ---------------------------------------------------------------------------
# Gemini Motor (Google)
# ---------------------------------------------------------------------------

class GeminiMotor(Motor):
    """Motor fuer Gemini-Modelle ueber das Google GenAI SDK."""

    provider_name = "google"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self._api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self._api_key)
            except ImportError:
                raise RuntimeError(
                    "google-genai SDK nicht installiert. "
                    "Installiere mit: pip install google-genai"
                )
        return self._client

    def ist_verfuegbar(self) -> bool:
        return bool(self._api_key)

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        max_tok = self._max_tokens(config)

        try:
            from google.genai import types

            client = self._get_client()
            response = client.models.generate_content(
                model=config.model_id,
                contents=vollprompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tok,
                ),
            )

            text = response.text or ""

            # Token-Counts aus usage_metadata
            input_tokens = 0
            output_tokens = 0
            if response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            return MotorErgebnis(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except Exception as e:
            logger.error(f"GeminiMotor Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


# ---------------------------------------------------------------------------
# Ollama Motor (Lokal)
# ---------------------------------------------------------------------------

class OllamaMotor(Motor):
    """Motor fuer lokale Modelle ueber Ollama HTTP API."""

    provider_name = "ollama"

    def __init__(self, basis_url: str = "http://localhost:11434"):
        super().__init__()
        self._basis_url = basis_url.rstrip("/")

    def ist_verfuegbar(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self._basis_url}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        timeout = self._timeout(config, basis=60.0)

        try:
            import requests

            response = requests.post(
                f"{self._basis_url}/api/generate",
                json={
                    "model": config.model_id,
                    "prompt": vollprompt,
                    "stream": False,
                    "options": {
                        "num_predict": self._max_tokens(config),
                    },
                },
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            return MotorErgebnis(
                text=data.get("response", ""),
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except Exception as e:
            logger.error(f"OllamaMotor Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


# ---------------------------------------------------------------------------
# Claude Code Motor (CLI subprocess)
# ---------------------------------------------------------------------------

class ClaudeCodeMotor(Motor):
    """Motor der die Claude Code CLI als subprocess aufruft."""

    provider_name = "claude-code"

    def __init__(self):
        super().__init__()

    def ist_verfuegbar(self) -> bool:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        timeout = self._timeout(config, basis=120.0)

        try:
            result = subprocess.run(
                ["claude", "-p", vollprompt, "--output-format", "json"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"claude CLI exit code {result.returncode}: "
                    f"{result.stderr[:500]}"
                )

            # Claude Code gibt JSON mit result und usage zurueck
            try:
                data = json.loads(result.stdout)
                text = data.get("result", result.stdout)
                input_tokens = data.get("input_tokens", 0)
                output_tokens = data.get("output_tokens", 0)
            except json.JSONDecodeError:
                text = result.stdout
                input_tokens = 0
                output_tokens = 0

            return MotorErgebnis(
                text=text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"ClaudeCodeMotor Timeout nach {timeout}s")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=f"Timeout nach {timeout:.0f}s",
            )
        except Exception as e:
            logger.error(f"ClaudeCodeMotor Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


# ---------------------------------------------------------------------------
# MotorBlock -- Factory
# ---------------------------------------------------------------------------

class MotorBlock:
    """Factory die anhand des Providers den richtigen Motor waehlt.

    Nutzung:
        block = MotorBlock()
        ergebnis = block.ausfuehren(config, "Erklaere Quantenmechanik")

        # Oder Motor direkt holen
        motor = block.motor_fuer("anthropic")
        ergebnis = motor.ausfuehren(config, prompt)
    """

    def __init__(self):
        self._motoren: dict[str, Motor] = {
            "anthropic": AnthropicMotor(),
            "google": GeminiMotor(),
            "ollama": OllamaMotor(),
            "claude-code": ClaudeCodeMotor(),
        }

    def motor_fuer(self, provider: str) -> Motor:
        """Gibt den Motor fuer einen Provider zurueck."""
        motor = self._motoren.get(provider)
        if motor is None:
            raise ValueError(
                f"Kein Motor fuer Provider '{provider}'. "
                f"Verfuegbar: {list(self._motoren.keys())}"
            )
        return motor

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        """Fuehrt einen LLM-Call mit dem passenden Motor aus."""
        motor = self.motor_fuer(config.provider)

        if not motor.ist_verfuegbar():
            logger.warning(
                f"Motor '{config.provider}' nicht verfuegbar. "
                f"Fehlender API-Key oder Service offline."
            )
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=config.provider,
                erfolg=False,
                fehler=f"Motor '{config.provider}' nicht verfuegbar",
            )

        logger.info(
            f"MotorBlock: {config.provider}/{config.model_id} "
            f"Gas={config.gas.wert:.0%} MaxTokens={int(4096 * config.gas.token_multiplikator)}"
        )

        return motor.ausfuehren(config, prompt)

    def verfuegbare_motoren(self) -> dict[str, bool]:
        """Zeigt welche Motoren einsatzbereit sind."""
        return {name: m.ist_verfuegbar() for name, m in self._motoren.items()}

    def registriere_motor(self, provider: str, motor: Motor) -> None:
        """Registriert einen benutzerdefinierten Motor."""
        self._motoren[provider] = motor

    def handler(self) -> callable:
        """Gibt einen Handler zurueck der mit Fahrer.fahren() kompatibel ist.

        Nutzung:
            block = MotorBlock()
            fahrer = Fahrer()
            ergebnis = fahrer.fahren("Mein Task", handler=block.handler())
        """
        def _handler(config: FahrtConfig, task: str) -> MotorErgebnis:
            return self.ausfuehren(config, task)
        return _handler
