"""Tests fuer M7 -- Toolsets + Permission-Durchsetzung (default-deny)."""

import sys
import json
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.toolsets import (
    Tool, Toolset, filter_tools, export_toolset, lade_katalog, ToolsetManager,
)
from clutch.profile_manager import ProfileManager, Profil


def _tools():
    return [
        Tool("read_file", "fc"), Tool("delete_file", "fc"),
        Tool("run_shell", "fc"), Tool("search", "cc"),
    ]


def test_filter_default_deny():
    ts = Toolset("safe", erlaubte_tools=["read_file", "search"])
    erlaubt = filter_tools(_tools(), ts)
    namen = {t.name for t in erlaubt}
    assert namen == {"read_file", "search"}
    # Sicherheitskern: verbotene Tools rutschen NICHT durch
    assert "delete_file" not in namen and "run_shell" not in namen
    print("[OK] Permission default-deny")


def test_leere_whitelist_blockt_alles():
    ts = Toolset("none", erlaubte_tools=[])
    assert filter_tools(_tools(), ts) == []
    print("[OK] leere Whitelist blockt alles")


def test_export_enthaelt_nur_erlaubte():
    ts = Toolset("safe", erlaubte_tools=["read_file"], tool_infos={"read_file": "liest Datei"})
    paket = export_toolset(ts, _tools())
    assert [t["name"] for t in paket["tools"]] == ["read_file"]
    assert paket["tool_infos"]["read_file"] == "liest Datei"
    # Kein verbotenes Tool im Paket
    assert all(t["name"] == "read_file" for t in paket["tools"])
    print("[OK] Export nur erlaubte")


def test_lade_katalog_servers_format():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "katalog.json"
        p.write_text(json.dumps({
            "servers": [
                {"packageName": "fc", "tools": [
                    {"name": "read_file", "description": "liest"},
                    {"name": "delete_file", "description": "loescht"},
                ]},
            ]
        }), encoding="utf-8")
        tools = lade_katalog(p)
        assert {t.name for t in tools} == {"read_file", "delete_file"}
        assert all(t.server == "fc" for t in tools)
        print("[OK] Katalog servers-Format")


def test_lade_katalog_fehlt_graceful():
    assert lade_katalog(Path("nicht/da.json")) == []
    print("[OK] Katalog fehlt -> []")


def test_manager_toolset_aus_profil():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProfileManager(db_path=Path(tmp) / "c.db")
        pm.speichere(Profil(name="safe", scope="toolset", payload={
            "erlaubte_tools": ["read_file", "search"],
            "tool_infos": {"read_file": "info"},
        }))
        kat = Path(tmp) / "k.json"
        kat.write_text(json.dumps({"tools": [
            {"name": "read_file", "server": "fc"},
            {"name": "delete_file", "server": "fc"},
            {"name": "search", "server": "cc"},
        ]}), encoding="utf-8")

        mgr = ToolsetManager(profile_manager=pm, katalog_pfad=kat)
        paket = mgr.aufgeloest("safe")
        namen = {t["name"] for t in paket["tools"]}
        assert namen == {"read_file", "search"}
        assert "delete_file" not in namen
        print("[OK] Manager Toolset aus Profil + Katalog-Filter")


def test_manager_unbekanntes_profil():
    with tempfile.TemporaryDirectory() as tmp:
        pm = ProfileManager(db_path=Path(tmp) / "c.db")
        mgr = ToolsetManager(profile_manager=pm)
        paket = mgr.aufgeloest("gibtsnicht")
        assert paket["tools"] == [] and paket["erlaubte_tools"] == []
        print("[OK] Manager unbekanntes Profil")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
