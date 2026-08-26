"""Token-Durchsatz -- Anthropic-5h/7d-Fenster als Schatten-Dimension (Stufe 1).

T-20260825-939511775 (T1E, User-Entscheidung, Stufenplan siehe
docs/STAGED-MIGRATION.md): Stufe 1 = SCHATTENMODUS. Dieses Modul liest die
Bridge-Datei, die der bestehende Claude-Code-Statusline-Hook
(~/.claude/hooks/token_budget_statusline.py) bereits schreibt, fuehrt ein
eigenes Rolling-Log und berechnet eine EMA-geglaettete Durchsatzrate --
Vorbild: Antigravity token_analytics_engine (7d-Burn-Rate).

WICHTIG -- Schattenmodus-Grenze (nicht ueberschreiten):
  * Dieses Modul SCHREIBT NICHTS in ~/.claude/hooks/, ~/.claude/settings.json
    oder eine der bestehenden Hook-Zustandsdateien (token_budget_guard_state.json,
    sparmodus_state.json). Es liest sie hoechstens (read-only), niemals schreibend.
  * Es TRIFFT keine Boost-/Drossel-Entscheidung und aendert kein Verhalten von
    clutch selbst -- record_point() liefert nur Messwerte, classify_zone() nur
    eine informative Einordnung. Die bestehende sparmodus/notaus-Schwellenlogik
    bleibt in Stufe 1 die einzig wirksame Steuerung.
  * Alle Dateien, die dieses Modul anlegt, sind NEU (token_throughput_log.jsonl,
    clutch_shadow_protocol.jsonl) -- keine bestehende Datei wird angefasst.

Fail-open wie die bestehenden Hooks: fehlt die Bridge-Datei oder ist sie
unlesbar, liefert record_point() None statt einen Fehler zu werfen.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STATE_DIR = Path(os.path.expanduser("~")) / ".claude" / "state"
BRIDGE_PATH = STATE_DIR / "token_budget.json"
THROUGHPUT_LOG_PATH = STATE_DIR / "token_throughput_log.jsonl"
SHADOW_PROTOCOL_PATH = STATE_DIR / "clutch_shadow_protocol.jsonl"
SPARMODUS_STATE_PATH = STATE_DIR / "sparmodus_state.json"
TOKEN_BUDGET_CONFIG_PATH = Path(os.path.expanduser("~")) / ".claude" / "hooks" / "token_budget_config.json"

#: Wie viele Rolling-Log-Punkte maximal behalten werden (Pruning bei jedem
#: Schreiben) -- verhindert unbegrenztes Wachstum, ohne dass Stufe 2
#: (Beobachtungsfenster) zu wenig Historie vorfindet.
MAX_LOG_POINTS = 2000

#: EMA-Glaettungskonstante fuer die Rate (Prozentpunkte/Stunde). 0.3 gewichtet
#: die letzten ~3-4 Messpunkte am staerksten, ohne auf einen einzelnen
#: Ausreisser ueberzureagieren.
DEFAULT_EMA_ALPHA = 0.3

#: Bridge-Daten aelter als das gelten als "stale" (deckt sich mit dem
#: stale_after_seconds-Default aus token_budget_config.json).
DEFAULT_STALE_AFTER_SECONDS = 1800

#: Zonenschwellen, identisch zu den sparmodus/notaus-Default-Schwellen in
#: token_budget_config.json -- absichtlich dieselben Zahlen, damit die
#: Schatten-Zone direkt mit der realen sparmodus-Stufe vergleichbar ist.
DEFAULT_ZONE_THRESHOLDS = {"kurztext": 50.0, "sparmodus": 80.0, "notaus": 90.0}


@dataclass
class ThroughputSnapshot:
    """Ergebnis eines record_point()-Aufrufs -- reine Messwerte, keine Entscheidung."""

    five_hour_pct: Optional[float]
    five_hour_rate_ema_per_hour: Optional[float]
    seven_day_pct: Optional[float]
    seven_day_rate_ema_per_hour: Optional[float]
    written_at: Optional[float]
    stale: bool
    sample_count: int


def _read_json(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def _read_log() -> list[dict]:
    if not THROUGHPUT_LOG_PATH.exists():
        return []
    points = []
    try:
        with THROUGHPUT_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    points.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return points


def _write_log(points: list[dict]) -> None:
    trimmed = points[-MAX_LOG_POINTS:]
    text = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in trimmed)
    _atomic_write_text(THROUGHPUT_LOG_PATH, text)


def _load_zone_thresholds() -> dict:
    config = _read_json(TOKEN_BUDGET_CONFIG_PATH)
    thresholds = (config or {}).get("thresholds") or {}
    return {
        "kurztext": float(thresholds.get("kurztext_used_pct", DEFAULT_ZONE_THRESHOLDS["kurztext"])),
        "sparmodus": float(thresholds.get("sparmodus_used_pct", DEFAULT_ZONE_THRESHOLDS["sparmodus"])),
        "notaus": float(thresholds.get("notaus_used_pct", DEFAULT_ZONE_THRESHOLDS["notaus"])),
    }


def classify_zone(five_hour_pct: Optional[float]) -> str:
    """Rein informative Einordnung -- KEINE Entscheidung, keine Modusaenderung.

    Nutzt dieselben Schwellen wie token_budget_config.json (50/80/90 Default),
    damit die Schatten-Zone direkt mit dem realen sparmodus-Modus vergleichbar
    ist (siehe record_shadow_decision)."""
    if five_hour_pct is None:
        return "unknown"
    thresholds = _load_zone_thresholds()
    if five_hour_pct >= thresholds["notaus"]:
        return "red"
    if five_hour_pct >= thresholds["sparmodus"]:
        return "orange"
    if five_hour_pct >= thresholds["kurztext"]:
        return "yellow"
    return "green"


def _ema_rate(log: list[dict], key: str, alpha: float) -> Optional[float]:
    """EMA ueber die Rate (Prozentpunkte/Stunde) zwischen aufeinanderfolgenden
    Punkten. Ueberspringt Uebergaenge, bei denen resets_at sich geaendert hat
    (Fenster-Reset) oder der Wert stark gefallen ist -- ein Reset ist kein
    negativer 'Verbrauch', sondern ein neuer Startpunkt."""
    ema: Optional[float] = None
    prev = None
    for point in log:
        pct = point.get(key)
        ts = point.get("t")
        resets_at = point.get(f"{key}_resets_at")
        if pct is None or ts is None:
            continue
        if prev is not None:
            prev_pct, prev_ts, prev_resets_at = prev
            reset_happened = resets_at is not None and prev_resets_at is not None and resets_at != prev_resets_at
            dropped_sharply = pct < prev_pct - 5.0
            dt_hours = (ts - prev_ts) / 3600.0
            if not reset_happened and not dropped_sharply and dt_hours > 0:
                rate = (pct - prev_pct) / dt_hours
                ema = rate if ema is None else (alpha * rate + (1 - alpha) * ema)
        prev = (pct, ts, resets_at)
    return ema


def record_point(alpha: float = DEFAULT_EMA_ALPHA) -> Optional[ThroughputSnapshot]:
    """Liest die Bridge-Datei, haengt einen Punkt ans Rolling-Log an (falls neu)
    und liefert die aktuelle EMA-Rate. Fail-open: liefert None, wenn die
    Bridge-Datei fehlt oder unlesbar ist -- schreibt in dem Fall auch nichts."""
    bridge = _read_json(BRIDGE_PATH)
    if not bridge:
        return None

    written_at = bridge.get("written_at")
    five_hour = bridge.get("five_hour") or {}
    seven_day = bridge.get("seven_day") or {}
    five_pct = five_hour.get("used_percentage")
    seven_pct = seven_day.get("used_percentage")

    log = _read_log()
    already_logged = bool(log) and log[-1].get("t") == written_at
    if not already_logged and written_at is not None:
        log.append(
            {
                "t": written_at,
                "five_hour_pct": five_pct,
                "five_hour_pct_resets_at": five_hour.get("resets_at"),
                "seven_day_pct": seven_pct,
                "seven_day_pct_resets_at": seven_day.get("resets_at"),
            }
        )
        try:
            _write_log(log)
        except OSError:
            pass  # Fail-open: ein Log-Schreibfehler darf die Messung nicht abbrechen

    five_hour_rate = _ema_rate(log, "five_hour_pct", alpha)
    seven_day_rate = _ema_rate(log, "seven_day_pct", alpha)

    stale = True
    if written_at is not None:
        stale = (time.time() - written_at) > DEFAULT_STALE_AFTER_SECONDS

    return ThroughputSnapshot(
        five_hour_pct=five_pct,
        five_hour_rate_ema_per_hour=five_hour_rate,
        seven_day_pct=seven_pct,
        seven_day_rate_ema_per_hour=seven_day_rate,
        written_at=written_at,
        stale=stale,
        sample_count=len(log),
    )


def _current_sparmodus_mode() -> str:
    """Read-only. Liefert 'off' falls die Datei fehlt (identischer Default wie
    token_budget_guard.py._default_sparmodus_state())."""
    state = _read_json(SPARMODUS_STATE_PATH)
    if not state or "mode" not in state:
        return "off"
    return state.get("mode") or "off"


def record_shadow_decision(snapshot: Optional[ThroughputSnapshot] = None) -> Optional[dict]:
    """Schatten-Protokoll (Punkt 3 des Tickets): haengt eine Zeile an, die
    festhaelt, was die neue Schatten-Zone WUERDE vorschlagen vs. was
    sparmodus REAL gerade tut. Reine Beobachtung fuer Stufe 2 -- greift in
    nichts ein, aendert keinen Modus. Gibt den geschriebenen Datensatz zurueck
    (oder None, wenn keine Bridge-Daten verfuegbar sind)."""
    snap = snapshot if snapshot is not None else record_point()
    if snap is None:
        return None

    shadow_zone = classify_zone(snap.five_hour_pct)
    real_mode = _current_sparmodus_mode()
    record = {
        "t": time.time(),
        "five_hour_pct": snap.five_hour_pct,
        "five_hour_rate_ema_per_hour": snap.five_hour_rate_ema_per_hour,
        "shadow_zone": shadow_zone,
        "real_sparmodus_mode": real_mode,
        "agreement": _zone_matches_mode(shadow_zone, real_mode),
    }

    log = []
    if SHADOW_PROTOCOL_PATH.exists():
        try:
            with SHADOW_PROTOCOL_PATH.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if line:
                        try:
                            log.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except OSError:
            log = []
    log.append(record)
    try:
        text = "".join(json.dumps(p, ensure_ascii=False) + "\n" for p in log[-MAX_LOG_POINTS:])
        _atomic_write_text(SHADOW_PROTOCOL_PATH, text)
    except OSError:
        pass  # Fail-open

    return record


def _zone_matches_mode(zone: str, mode: str) -> bool:
    """Grobe Uebereinstimmungspruefung fuer die spaetere Auswertung in Stufe 2
    -- KEINE normative Aussage, nur ein Hinweis, wie oft Schatten-Zone und
    realer Modus auseinanderlaufen."""
    expected = {
        "green": {"off"},
        "yellow": {"off", "manual-spar", "auto-spar"},
        "orange": {"manual-spar", "auto-spar", "notaus"},
        "red": {"notaus"},
        "unknown": {"off", "manual-spar", "auto-spar", "notaus"},
    }
    return mode in expected.get(zone, set())
