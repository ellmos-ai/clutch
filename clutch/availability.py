"""Prozessuebergreifender Verfuegbarkeitszustand fuer Modelle und Provider."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from clutch.user_overrides import clutch_home


DEFAULT_RETRY_SECONDS = 300.0
RED_QUOTA_PCT = 90.0
STALE_AFTER_SECONDS = 1800.0


def availability_path() -> Path:
    return clutch_home() / "availability.json"


def _read_json(path: Path) -> Optional[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


@contextmanager
def _exclusive_file_lock(path: Path, timeout: float = 10.0) -> Iterator[None]:
    """Serialisiert Mutationen auch zwischen unabhaengigen CLI-Prozessen."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + timeout
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Lock nicht verfuegbar: {path}")
                    time.sleep(0.05)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            while True:
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Lock nicht verfuegbar: {path}")
                    time.sleep(0.05)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return None
    return None


class AvailabilityStore:
    """Atomar gespeicherte Circuit- und Kontingentsperren.

    Die Datei wird nur angelegt, wenn tatsaechlich Zustand persistiert werden
    muss. Reine Statusabfragen ohne Signal veraendern das Nutzerverzeichnis nicht.
    """

    def __init__(
        self,
        path: Optional[Path] = None,
        token_budget_path: Optional[Path] = None,
        sparmodus_path: Optional[Path] = None,
    ):
        self.path = Path(path) if path is not None else availability_path()
        state_dir = Path.home() / ".claude" / "state"
        self.token_budget_path = Path(token_budget_path) if token_budget_path else state_dir / "token_budget.json"
        self.sparmodus_path = Path(sparmodus_path) if sparmodus_path else state_dir / "sparmodus_state.json"

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {"version": 1, "circuits": {}, "provider_blocks": {}}

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"Ungueltige Verfuegbarkeitsdatei: {self.path}") from error
        if not isinstance(data, dict):
            raise ValueError(f"Ungueltige Verfuegbarkeitsdatei: {self.path}")
        data.setdefault("version", 1)
        data.setdefault("circuits", {})
        data.setdefault("provider_blocks", {})
        if not isinstance(data["circuits"], dict) or not isinstance(data["provider_blocks"], dict):
            raise ValueError(f"Ungueltige Verfuegbarkeitsdatei: {self.path}")
        return data

    @property
    def lock_path(self) -> Path:
        return self.path.with_name(self.path.name + ".lock")

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        data["version"] = 1
        data["updated_at"] = time.time()
        text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        fd, tmp_name = tempfile.mkstemp(prefix=self.path.name + ".", suffix=".tmp", dir=str(self.path.parent))
        try:
            try:
                os.chmod(tmp_name, 0o600)
            except OSError:
                pass
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_name, self.path)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def _mutate(self, mutation: Callable[[dict[str, Any]], bool]) -> None:
        with _exclusive_file_lock(self.lock_path):
            data = self.read()
            if mutation(data):
                self._write_unlocked(data)

    def circuits(self) -> dict[str, dict[str, Any]]:
        return self.read()["circuits"]

    def save_circuit(self, model: str, circuit: dict[str, Any]) -> None:
        def save(data: dict[str, Any]) -> bool:
            data["circuits"][model] = circuit
            return True

        self._mutate(save)

    def set_provider_block(
        self,
        provider: str,
        source: str,
        reason: str,
        *,
        until: Optional[float],
        resets_at: Any = None,
        now: Optional[float] = None,
    ) -> None:
        new_block = {
            "reason": reason,
            "source": source,
            "until": until,
            "resets_at": resets_at,
            "updated_at": time.time() if now is None else now,
        }
        def set_block(data: dict[str, Any]) -> bool:
            blocks = data["provider_blocks"].setdefault(provider, {})
            current = blocks.get(source)
            if isinstance(current, dict) and all(
                current.get(key) == new_block.get(key)
                for key in ("reason", "source", "until", "resets_at")
            ):
                return False
            blocks[source] = new_block
            return True

        self._mutate(set_block)

    def clear_provider_block(self, provider: str, source: str) -> None:
        def clear_block(data: dict[str, Any]) -> bool:
            provider_blocks = data["provider_blocks"].get(provider)
            if not isinstance(provider_blocks, dict) or source not in provider_blocks:
                return False
            del provider_blocks[source]
            if not provider_blocks:
                data["provider_blocks"].pop(provider, None)
            return True

        self._mutate(clear_block)

    def refresh_external(self, now: Optional[float] = None) -> None:
        """Spiegelt nur harte rote/notaus-Signale; keine EMA-Routingpolitik."""
        now = time.time() if now is None else now
        budget = _read_json(self.token_budget_path)
        budget_fresh = False
        red_windows: list[tuple[str, Any, Optional[float]]] = []
        if budget:
            written_at = _timestamp(budget.get("written_at"))
            budget_fresh = written_at is not None and now - written_at <= STALE_AFTER_SECONDS
            if budget_fresh:
                for key, label in (("five_hour", "5h"), ("seven_day", "7d")):
                    window = budget.get(key) if isinstance(budget.get(key), dict) else {}
                    used = window.get("used_percentage")
                    try:
                        is_red = float(used) >= RED_QUOTA_PCT
                    except (TypeError, ValueError):
                        is_red = False
                    if is_red:
                        raw_reset = window.get("resets_at")
                        red_windows.append((label, raw_reset, _timestamp(raw_reset)))

        if red_windows:
            labels = "/".join(item[0] for item in red_windows)
            valid_resets = [item[2] for item in red_windows if item[2] is not None]
            until = max(valid_resets) if valid_resets else now + DEFAULT_RETRY_SECONDS
            resets = max(valid_resets) if valid_resets else None
            if until <= now:
                until = now + DEFAULT_RETRY_SECONDS
                resets = until
            self.set_provider_block(
                "anthropic",
                "token_budget",
                f"Anthropic-Kontingent {labels} rot",
                until=until,
                resets_at=resets,
                now=now,
            )
        elif budget_fresh:
            # Nur ein frisches, nicht-rotes Signal hebt die persistierte Sperre auf.
            # Fehlende/veraltete Bridge behaelt den letzten Beleg bis ``until``.
            self.clear_provider_block("anthropic", "token_budget")

        sparmodus = _read_json(self.sparmodus_path) or {}
        if sparmodus.get("mode") == "notaus":
            raw_reset = sparmodus.get("resets_at") or sparmodus.get("wake_at")
            until = _timestamp(raw_reset) or now + DEFAULT_RETRY_SECONDS
            self.set_provider_block(
                "anthropic",
                "sparmodus",
                "sparmodus mode=notaus",
                until=until,
                resets_at=raw_reset or until,
                now=now,
            )
        elif sparmodus:
            self.clear_provider_block("anthropic", "sparmodus")

    def record_provider_failure(
        self,
        provider: str,
        reason: str,
        *,
        now: Optional[float] = None,
        retry_seconds: float = DEFAULT_RETRY_SECONDS,
    ) -> None:
        now = time.time() if now is None else now
        self.set_provider_block(
            provider,
            "provider_error",
            reason,
            until=now + retry_seconds,
            resets_at=now + retry_seconds,
            now=now,
        )

    def active_provider_blocks(self, now: Optional[float] = None) -> dict[str, list[dict[str, Any]]]:
        now = time.time() if now is None else now
        active: dict[str, list[dict[str, Any]]] = {}

        def expire(data: dict[str, Any]) -> bool:
            changed = False
            for provider, sources in list(data["provider_blocks"].items()):
                if not isinstance(sources, dict):
                    data["provider_blocks"].pop(provider, None)
                    changed = True
                    continue
                for source, block in list(sources.items()):
                    until = _timestamp(block.get("until")) if isinstance(block, dict) else None
                    if until is not None and until <= now:
                        del sources[source]
                        changed = True
                    elif isinstance(block, dict):
                        active.setdefault(provider, []).append(block)
                if not sources:
                    data["provider_blocks"].pop(provider, None)
            return changed

        self._mutate(expire)
        return active


_QUOTA_PATTERN = re.compile(
    r"(?:\b429\b|quota|rate[ -]?limit|usage[ -]?limit|out of usage|resource exhausted)",
    re.IGNORECASE,
)


def provider_failure_reason(provider: str, error: Any = None, output_text: Any = None) -> Optional[str]:
    """Erkennt die im Ticket benannten Kontingent-Fehlermuster."""
    message = str(error or "").strip()
    if message and _QUOTA_PATTERN.search(message):
        return f"{provider}: {message[:300]}"
    if provider == "agy" and not message and not str(output_text or "").strip():
        return "agy: Exit 0 ohne Ausgabe"
    return None
