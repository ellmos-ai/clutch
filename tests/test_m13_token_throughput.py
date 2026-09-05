"""Tests fuer Stufe 1 (Schattenmodus) T1E -- token_throughput + Tankuhr-Erweiterung.

T-20260825-939511775. Alle Tests arbeiten gegen eine temporaere Bridge-/Log-
Umgebung (monkeypatch der Modul-Pfade) -- niemals gegen die echte
~/.claude/state/-Umgebung dieses Hosts.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch import token_throughput as tt
from clutch.tankuhr import Tankuhr


def _isolate(tmp_path, monkeypatch):
    """Richtet eine isolierte Bridge-/Log-/Config-Umgebung fuer einen Test ein."""
    bridge = tmp_path / "token_budget.json"
    log = tmp_path / "token_throughput_log.jsonl"
    shadow = tmp_path / "clutch_shadow_protocol.jsonl"
    sparmodus = tmp_path / "sparmodus_state.json"
    config = tmp_path / "token_budget_config.json"

    monkeypatch.setattr(tt, "BRIDGE_PATH", bridge)
    monkeypatch.setattr(tt, "THROUGHPUT_LOG_PATH", log)
    monkeypatch.setattr(tt, "SHADOW_PROTOCOL_PATH", shadow)
    monkeypatch.setattr(tt, "SPARMODUS_STATE_PATH", sparmodus)
    monkeypatch.setattr(tt, "TOKEN_BUDGET_CONFIG_PATH", config)
    return bridge, log, shadow, sparmodus, config


def _write_bridge(bridge_path, five_pct, seven_pct=None, resets_at=1000, written_at=None):
    payload = {
        "written_at": written_at if written_at is not None else time.time(),
        "five_hour": {"used_percentage": five_pct, "resets_at": resets_at},
        "seven_day": {"used_percentage": seven_pct if seven_pct is not None else five_pct, "resets_at": resets_at + 1000},
    }
    bridge_path.write_text(json.dumps(payload), encoding="utf-8")


def test_record_point_missing_bridge_returns_none(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert tt.record_point() is None
    print("[OK] record_point() fail-open ohne Bridge-Datei")


def test_record_point_appends_and_reads(tmp_path, monkeypatch):
    bridge, log, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 10.0, written_at=1000.0)
    snap = tt.record_point()
    assert snap is not None
    assert snap.five_hour_pct == 10.0
    assert snap.sample_count == 1
    assert log.exists()
    print("[OK] record_point() legt ersten Punkt an")


def test_record_point_does_not_duplicate_same_snapshot(tmp_path, monkeypatch):
    bridge, log, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 10.0, written_at=1000.0)
    tt.record_point()
    tt.record_point()  # gleicher written_at -> darf nicht doppelt geloggt werden
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    print("[OK] identischer Bridge-Snapshot wird nicht doppelt geloggt")


def test_ema_rate_positive_between_two_rising_points(tmp_path, monkeypatch):
    bridge, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 10.0, written_at=1000.0)
    tt.record_point()
    _write_bridge(bridge, 20.0, written_at=1000.0 + 3600)  # +10pp in 1h
    snap = tt.record_point()
    assert snap.five_hour_rate_ema_per_hour is not None
    assert abs(snap.five_hour_rate_ema_per_hour - 10.0) < 1e-6
    print(f"[OK] EMA-Rate nach 2 Punkten = {snap.five_hour_rate_ema_per_hour} pp/h")


def test_reset_boundary_is_not_treated_as_negative_rate(tmp_path, monkeypatch):
    """Ein Fenster-Reset (resets_at aendert sich) ist kein Verbrauch-Sturz."""
    bridge, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 85.0, resets_at=1000, written_at=1000.0)
    tt.record_point()
    _write_bridge(bridge, 5.0, resets_at=2000, written_at=1000.0 + 60)  # neues Fenster
    snap = tt.record_point()
    # Kein Punkt aus dem Reset-Uebergang darf in die EMA einfliessen -> None,
    # solange noch kein voller (nicht-resetteter) Uebergang vorliegt.
    assert snap.five_hour_rate_ema_per_hour is None
    print("[OK] Fenster-Reset wird nicht als negative Rate gewertet")


def test_classify_zone_uses_configured_thresholds(tmp_path, monkeypatch):
    _, _, _, _, config = _isolate(tmp_path, monkeypatch)
    config.write_text(
        json.dumps({"thresholds": {"kurztext_used_pct": 40, "sparmodus_used_pct": 70, "notaus_used_pct": 95}}),
        encoding="utf-8",
    )
    assert tt.classify_zone(10.0) == "green"
    assert tt.classify_zone(45.0) == "yellow"
    assert tt.classify_zone(80.0) == "orange"
    assert tt.classify_zone(96.0) == "red"
    assert tt.classify_zone(None) == "unknown"
    print("[OK] classify_zone() respektiert konfigurierte Schwellen")


def test_classify_zone_default_thresholds_without_config(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert tt.classify_zone(10.0) == "green"
    assert tt.classify_zone(60.0) == "yellow"
    assert tt.classify_zone(85.0) == "orange"
    assert tt.classify_zone(95.0) == "red"
    print("[OK] classify_zone() Default-Schwellen (50/80/90) ohne Config-Datei")


def test_record_shadow_decision_defaults_to_off_without_sparmodus_file(tmp_path, monkeypatch):
    bridge, _, shadow, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 10.0, written_at=1000.0)
    record = tt.record_shadow_decision()
    assert record is not None
    assert record["real_sparmodus_mode"] == "off"
    assert record["shadow_zone"] == "green"
    assert record["agreement"] is True
    assert shadow.exists()
    print("[OK] Schatten-Protokoll: Default 'off' ohne sparmodus_state.json")


def test_record_shadow_decision_flags_disagreement(tmp_path, monkeypatch):
    bridge, _, shadow, sparmodus, _ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 95.0, written_at=1000.0)  # Schatten-Zone waere "red"
    sparmodus.write_text(json.dumps({"mode": "off"}), encoding="utf-8")  # real: nichts aktiv
    record = tt.record_shadow_decision()
    assert record["shadow_zone"] == "red"
    assert record["real_sparmodus_mode"] == "off"
    assert record["agreement"] is False
    print("[OK] Schatten-Protokoll erkennt Abweichung Schatten-Zone vs. realer Modus")


def test_log_is_pruned_to_max_points(tmp_path, monkeypatch):
    bridge, log, *_ = _isolate(tmp_path, monkeypatch)
    monkeypatch.setattr(tt, "MAX_LOG_POINTS", 5)
    for i in range(10):
        _write_bridge(bridge, float(i), written_at=1000.0 + i)
        tt.record_point()
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 5
    print("[OK] Rolling-Log wird auf MAX_LOG_POINTS gekuerzt")


def test_tankuhr_anthropic_schatten_stand_is_additive_and_optional(tmp_path, monkeypatch):
    """Kernanforderung des Tickets: die neue Methode aendert nichts an
    stand()/zone()/verbrauch_pct() und ist nur bei explizitem Aufruf aktiv."""
    bridge, *_ = _isolate(tmp_path, monkeypatch)
    tank = Tankuhr()

    stand_before = tank.stand()
    assert stand_before.zone == "green"  # unveraendertes bestehendes Verhalten

    # Ohne Bridge-Datei: fail-open, liefert None, aendert nichts.
    assert tank.anthropic_schatten_stand() is None

    _write_bridge(bridge, 92.0, written_at=1000.0)
    schatten = tank.anthropic_schatten_stand()
    assert schatten is not None
    assert schatten.zone == "red"
    assert schatten.five_hour_pct == 92.0

    # stand()/zone() bleiben von der Schatten-Abfrage vollstaendig unberuehrt.
    stand_after = tank.stand()
    assert stand_after.zone == stand_before.zone == "green"
    print("[OK] anthropic_schatten_stand() ist additiv, stand()/zone() unveraendert")


def test_tankuhr_shadow_log_only_written_when_requested(tmp_path, monkeypatch):
    bridge, _, shadow, *_ = _isolate(tmp_path, monkeypatch)
    _write_bridge(bridge, 30.0, written_at=1000.0)
    tank = Tankuhr()

    tank.anthropic_schatten_stand()  # record_shadow_log=False (Default)
    assert not shadow.exists()

    tank.anthropic_schatten_stand(record_shadow_log=True)
    assert shadow.exists()
    print("[OK] Schatten-Protokoll wird nur bei record_shadow_log=True geschrieben")


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
