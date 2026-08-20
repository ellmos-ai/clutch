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
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

from clutch.kupplung import FahrtConfig
from clutch.gas_bremse import GasBremse
from clutch.credentials import get_api_key
from clutch.pricing import UsageRecord, cost_for_gang

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
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0
    usage_status: str = "unknown"
    requested_effort: Optional[str] = None
    effective_effort: Optional[str] = None
    reasoning_mode: str = "standard"
    service_tier: str = "default"
    tool_fees_usd: float = 0.0
    price_version: Optional[str] = None
    cost_usd: Optional[float] = None
    cost_breakdown: Optional[dict] = None

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
        self._api_key_override = api_key
        self._client = None
        self._client_key = None

    def _aktueller_api_key(self) -> str:
        if self._api_key_override is not None:
            return self._api_key_override
        return get_api_key("ANTHROPIC_API_KEY")

    def _get_client(self):
        api_key = self._aktueller_api_key()
        if self._client is None or self._client_key != api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                self._client_key = api_key
            except ImportError:
                raise RuntimeError(
                    "anthropic SDK nicht installiert. "
                    "Installiere mit: pip install anthropic"
                )
        return self._client

    def ist_verfuegbar(self) -> bool:
        return bool(self._aktueller_api_key())

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
        self._api_key_override = api_key
        self._client = None
        self._client_key = None

    def _aktueller_api_key(self) -> str:
        if self._api_key_override is not None:
            return self._api_key_override
        return get_api_key("GOOGLE_API_KEY")

    def _get_client(self):
        api_key = self._aktueller_api_key()
        if self._client is None or self._client_key != api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
                self._client_key = api_key
            except ImportError:
                raise RuntimeError(
                    "google-genai SDK nicht installiert. "
                    "Installiere mit: pip install google-genai"
                )
        return self._client

    def ist_verfuegbar(self) -> bool:
        return bool(self._aktueller_api_key())

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

    def __init__(self, basis_url: str = "http://localhost:11434",
                 timeout_basis: Optional[float] = None):
        super().__init__()
        self._basis_url = basis_url.rstrip("/")
        # Lokale Modelle (v.a. grosse, z.B. 30B+) brauchen beim Kaltstart
        # leicht laenger als der Cloud-orientierte 60s-Default. Konfigurierbar
        # via Parameter oder Env CLUTCH_OLLAMA_TIMEOUT (Sekunden), sonst 60.
        if timeout_basis is None:
            try:
                timeout_basis = float(os.environ.get("CLUTCH_OLLAMA_TIMEOUT", "60"))
            except (TypeError, ValueError):
                timeout_basis = 60.0
        self._timeout_basis = timeout_basis

    def _ziel_url(self, config: Optional[FahrtConfig] = None) -> str:
        """Basis-URL des Ziel-Hosts.

        Bevorzugt den ``endpoint`` des gewaehlten Gangs (z.B. ein per Discovery
        gefundener Remote-Ollama-Host im VPN) und faellt auf die bei der
        Konstruktion gesetzte Basis-URL zurueck. Ohne diese Aufloesung wuerde
        ein Remote-Gang stets gegen ``localhost`` laufen.
        """
        gang = getattr(config, "gang", None)
        endpoint = getattr(gang, "endpoint", None)
        return (endpoint or self._basis_url).rstrip("/")

    def ist_verfuegbar(self, config: Optional[FahrtConfig] = None) -> bool:
        try:
            import requests
            r = requests.get(f"{self._ziel_url(config)}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        timeout = self._timeout(config, basis=self._timeout_basis)

        try:
            import requests

            response = requests.post(
                f"{self._ziel_url(config)}/api/generate",
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
# Kimi CLI Motoren (CLI subprocess, Print-Modus)
# ---------------------------------------------------------------------------

class _KimiBasisMotor(Motor):
    """Gemeinsame Basis fuer die Kimi-CLI-Motoren (kimi-cli / kimi-code).

    Beide werden als Subprozess im nicht-interaktiven Print-Modus aufgerufen.
    Der Login laeuft ueber den Moonshot-Account (Device-Code-Flow) -- es gibt
    KEINEN API-Key. Der Print-Modus liefert KEINE Token-/Usage-Daten, daher
    bleiben input_tokens/output_tokens bewusst 0 (Budget-Tracking fuer
    Kimi-Gaenge = nicht gemessen). Sobald Kimi spaeter doch Usage liefert oder
    ein API-Zugang besteht, kann das hier nachgezogen werden.
    """

    binary: str = "kimi"

    def ist_verfuegbar(self) -> bool:
        try:
            result = subprocess.run(
                [self.binary, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _argv(self, vollprompt: str) -> list[str]:
        raise NotImplementedError

    def _stdin(self, vollprompt: str) -> Optional[str]:
        return None

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        timeout = self._timeout(config, basis=120.0)

        try:
            result = subprocess.run(
                self._argv(vollprompt),
                input=self._stdin(vollprompt),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"{self.binary} CLI exit code {result.returncode}: "
                    f"{result.stderr[:500]}"
                )

            # Print-Modus liefert reinen Text auf stdout, keine Usage-Daten.
            return MotorErgebnis(
                text=result.stdout.strip(),
                input_tokens=0,
                output_tokens=0,
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except subprocess.TimeoutExpired:
            logger.error(f"{self.__class__.__name__} Timeout nach {timeout}s")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=f"Timeout nach {timeout:.0f}s",
            )
        except Exception as e:
            logger.error(f"{self.__class__.__name__} Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


class KimiCliMotor(_KimiBasisMotor):
    """Motor fuer Kimi CLI (kimi-cli.exe, Python-Linie) im Print-Modus.

    Aufruf: prompt via stdin, `--print` aktiviert implizit `--yolo`
    (Auto-Approve), so dass tool-pflichtige Tasks nicht haengen bleiben.
    """

    provider_name = "kimi-cli"
    binary = "kimi-cli"

    def _argv(self, vollprompt: str) -> list[str]:
        return [self.binary, "--print", "--output-format", "text"]

    def _stdin(self, vollprompt: str) -> Optional[str]:
        return vollprompt


class KimiCodeMotor(_KimiBasisMotor):
    """Motor fuer Kimi Code CLI (kimi-code.exe, TS-Linie) im Print-Modus.

    Aufruf: `kimi-code -p <prompt> --output-format text -y`. Das `-y`/`--yolo`
    approved Tool-Aktionen automatisch, damit der nicht-interaktive Lauf nicht
    auf eine Bestaetigung wartet (analog zum ClaudeCodeMotor-Verhalten).
    """

    provider_name = "kimi-code"
    binary = "kimi-code"

    def _argv(self, vollprompt: str) -> list[str]:
        return [self.binary, "-p", vollprompt, "--output-format", "text", "-y"]


# ---------------------------------------------------------------------------
# OpenAI-kompatibler Motor (Moonshot/Kimi-API, Codex/GPT, OpenRouter, LM Studio)
# ---------------------------------------------------------------------------

class OpenAICompatibleMotor(Motor):
    """Motor fuer jede OpenAI-kompatible Chat-Completions-API.

    Generische Basis: base_url + Bearer-Key (aus Env). Subklassen setzen
    base_url/api_key_env/provider_name. Deckt Moonshot/Kimi-API, Codex/GPT,
    OpenRouter und LM Studio ab. Liefert volle Token-Usage (prompt_tokens/
    completion_tokens) -- anders als die Kimi-CLI-Motoren.
    """

    provider_name = "openai-compatible"
    base_url = "https://api.openai.com/v1"
    api_key_env = "OPENAI_API_KEY"
    max_tokens_parameter = "max_tokens"

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None,
                 api_key_env: Optional[str] = None):
        super().__init__()
        if base_url:
            self.base_url = base_url
        if api_key_env:
            self.api_key_env = api_key_env
        self._api_key_override = api_key

    def _aktueller_api_key(self) -> str:
        if self._api_key_override is not None:
            return self._api_key_override
        return get_api_key(self.api_key_env)

    def ist_verfuegbar(self) -> bool:
        return bool(self._aktueller_api_key())

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        max_tok = self._max_tokens(config)
        timeout = self._timeout(config)

        try:
            import requests

            api_key = self._aktueller_api_key()
            payload = {
                "model": config.model_id,
                "messages": [{"role": "user", "content": vollprompt}],
                self.max_tokens_parameter: max_tok,
            }
            response = requests.post(
                f"{self.base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
            data = response.json()

            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})

            return MotorErgebnis(
                text=text,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )

        except Exception as e:
            logger.error(f"{self.__class__.__name__} Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


class KimiApiMotor(OpenAICompatibleMotor):
    """Moonshot/Kimi-API (OpenAI-kompatibel). Key: MOONSHOT_API_KEY."""

    provider_name = "kimi-api"
    base_url = "https://api.moonshot.ai/v1"
    api_key_env = "MOONSHOT_API_KEY"


class OpenAIMotor(OpenAICompatibleMotor):
    """OpenAI Responses API mit überprüfbarem Effort- und Usage-Transport."""

    provider_name = "openai"
    base_url = "https://api.openai.com/v1"
    api_key_env = "OPENAI_API_KEY"

    @staticmethod
    def _effective_effort(config: FahrtConfig) -> Optional[str]:
        supported = list(getattr(config.gang, "efforts", []) or [])
        requested = config.effort
        if requested == "max-delegate":
            if not config.is_delegate:
                raise ValueError(
                    "max-delegate ist nur Orchestrierung; API-max erfordert is_delegate=True"
                )
            requested = "max"
        if requested is None and supported:
            requested = "medium"
        if requested is not None and requested not in supported:
            raise ValueError(
                f"effort '{requested}' wird von {config.model_id} nicht unterstützt"
            )
        return requested

    @staticmethod
    def _api_service_tier(service_tier: str) -> str:
        aliases = {"standard": "default", "fast": "priority"}
        return aliases.get(service_tier, service_tier)

    def _build_payload(self, config: FahrtConfig, prompt: str) -> dict:
        """Erzeugt den exakt an OpenAI gesendeten Payload (separat testbar)."""
        effective = self._effective_effort(config)
        config.effective_effort = effective
        payload = {
            "model": config.model_id,
            "input": prompt,
            "max_output_tokens": self._max_tokens(config),
            "service_tier": self._api_service_tier(config.service_tier),
        }
        if effective is not None:
            payload["reasoning"] = {"effort": effective}
        return payload

    @staticmethod
    def _response_text(data: dict) -> str:
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        teile = []
        for item in data.get("output", []):
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    teile.append(content["text"])
        return "".join(teile)

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        try:
            import requests

            payload = self._build_payload(config, self._prompt_mit_gas(config, prompt))
            response = requests.post(
                f"{self.base_url.rstrip('/')}/responses",
                headers={
                    "Authorization": f"Bearer {self._aktueller_api_key()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._timeout(config),
            )
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage")
            usage_known = isinstance(usage, dict)
            usage = usage or {}
            input_details = usage.get("input_tokens_details") or {}
            output_details = usage.get("output_tokens_details") or {}
            input_tokens = int(usage.get("input_tokens", 0) or 0)
            output_tokens = int(usage.get("output_tokens", 0) or 0)
            cached_tokens = int(input_details.get("cached_tokens", 0) or 0)
            cache_write_tokens = int(input_details.get("cache_write_tokens", 0) or 0)
            reasoning_tokens = int(output_details.get("reasoning_tokens", 0) or 0)
            service_tier = data.get("service_tier") or payload["service_tier"]

            breakdown = cost_for_gang(
                config.gang,
                UsageRecord(
                    input_tokens=input_tokens if usage_known else None,
                    cached_input_tokens=cached_tokens if usage_known else None,
                    cache_write_tokens=cache_write_tokens if usage_known else None,
                    output_tokens=output_tokens if usage_known else None,
                    reasoning_tokens=reasoning_tokens if usage_known else None,
                    service_tier=service_tier,
                    data_status="observed" if usage_known else "unknown",
                ),
            )
            return MotorErgebnis(
                text=self._response_text(data),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=cached_tokens,
                cache_write_tokens=cache_write_tokens,
                reasoning_tokens=reasoning_tokens,
                usage_status="observed" if usage_known else "unknown",
                requested_effort=config.effort,
                effective_effort=config.effective_effort,
                reasoning_mode=config.reasoning_mode,
                service_tier=service_tier,
                price_version=breakdown.pricing_version,
                cost_usd=breakdown.total_usd,
                cost_breakdown=breakdown.to_dict(),
                model_id=data.get("model") or config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )
        except Exception as e:
            logger.error(f"OpenAIMotor Fehler: {e}")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                requested_effort=config.effort,
                effective_effort=config.effective_effort,
                reasoning_mode=config.reasoning_mode,
                service_tier=config.service_tier,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=str(e),
            )


# ---------------------------------------------------------------------------
# agy Companion Motor (CLI subprocess)
# ---------------------------------------------------------------------------

class AgyCompanionMotor(Motor):
    """agy-Modelle ueber den nicht-interaktiven companion-for-agy-Wrapper."""

    provider_name = "agy"

    def __init__(self, binary: Optional[str] = None):
        super().__init__()
        self.binary = (
            binary
            or os.environ.get("CLUTCH_AGY_COMPANION")
            or shutil.which("companion-for-agy")
            or "companion-for-agy"
        )

    def ist_verfuegbar(self) -> bool:
        try:
            result = subprocess.run(
                [self.binary, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def _effort(config: FahrtConfig) -> Optional[str]:
        erlaubt = list(getattr(config.gang, "efforts", []) or [])
        if not erlaubt:
            return None
        angefordert = (config.effort or "").lower()
        if angefordert in erlaubt:
            return angefordert
        if angefordert in {"high", "xhigh", "max-delegate"} and "high" in erlaubt:
            return "high"
        for kandidat in ("high", "thinking", "medium", "low"):
            if kandidat in erlaubt:
                return kandidat
        return None

    def _argv(self, config: FahrtConfig, vollprompt: str) -> list[str]:
        argv = [
            self.binary,
            "--json",
            "--sandbox",
            "--model",
            config.model_id,
        ]
        effort = self._effort(config)
        if effort:
            argv.extend(["--effort", effort])
        argv.extend(["--", vollprompt])
        return argv

    def ausfuehren(self, config: FahrtConfig, prompt: str) -> MotorErgebnis:
        t0 = time.time()
        vollprompt = self._prompt_mit_gas(config, prompt)
        timeout = self._timeout(config, basis=150.0)

        try:
            result = subprocess.run(
                self._argv(config, vollprompt),
                capture_output=True,
                text=True,
                timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"companion-for-agy exit code {result.returncode}: "
                    f"{result.stderr[:500]}"
                )
            data = json.loads(result.stdout)
            return MotorErgebnis(
                text=data.get("response", ""),
                input_tokens=0,
                output_tokens=0,
                model_id=data.get("model") or config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
            )
        except subprocess.TimeoutExpired:
            logger.error(f"AgyCompanionMotor Timeout nach {timeout}s")
            return MotorErgebnis(
                text="",
                model_id=config.model_id,
                provider=self.provider_name,
                latenz_sekunden=time.time() - t0,
                erfolg=False,
                fehler=f"Timeout nach {timeout:.0f}s",
            )
        except Exception as e:
            logger.error(f"AgyCompanionMotor Fehler: {e}")
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
            "kimi-cli": KimiCliMotor(),
            "kimi-code": KimiCodeMotor(),
            "kimi-api": KimiApiMotor(),
            "openai": OpenAIMotor(),
            "agy": AgyCompanionMotor(),
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

        # Ollama-Verfuegbarkeit gegen den Ziel-Host des Gangs pruefen (Remote),
        # nicht stur gegen localhost. Andere Motoren: Signatur ohne config.
        verfuegbar = (
            motor.ist_verfuegbar(config)
            if config.provider == "ollama"
            else motor.ist_verfuegbar()
        )
        if not verfuegbar:
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
