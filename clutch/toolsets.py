"""Toolsets -- Tool-Erlaubnisse + Tool-Infos als versendbare Profile.

clutch-Seite der ControlCenter-Anbindung (Plan M7). Ein Toolset legt fest,
WELCHE Tools einem Modell mitgesendet werden duerfen (Whitelist, default-deny)
und welche Tool-Infos beigelegt werden. Die Permission-Durchsetzung ist
sicherheitskritisch: was nicht ausdruecklich erlaubt ist, wird entfernt.

Anbindung an ellmos-ControlCenter (MCP, TypeScript):
- ControlCenter liefert Server-/Tool-Kataloge + Capability-Bundles
  (`controlcenter_build_catalog` / `data/capability-bundles.json`).
- clutch liest einen exportierten Katalog (JSON) via `lade_katalog()`.
- OFFEN (ControlCenter-Seite, anderes Repo, ~1-2 Tage TS): per-Tool-Whitelist
  pro Profil + MCP-Tool `controlcenter_export_toolset`. Bis dahin pflegt clutch
  die Whitelist selbst (ueber toolset-Profile im ProfileManager).

Zero-Dependency (stdlib).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Tool:
    name: str
    server: str = ""
    beschreibung: str = ""
    bundle: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "server": self.server,
                "beschreibung": self.beschreibung, "bundle": self.bundle}


@dataclass
class Toolset:
    """Ein versendbares Tool-Profil: erlaubte Tools + Infos.

    erlaubte_tools = Whitelist (default-deny). tool_infos = optionale
    Zusatzinfos je Toolname (z.B. Kurzbeschreibung), die mitgesendet werden.
    """
    name: str
    erlaubte_tools: list[str] = field(default_factory=list)
    tool_infos: dict = field(default_factory=dict)
    quelle: str = "profil"

    def erlaubt(self, tool_name: str) -> bool:
        return tool_name in self.erlaubte_tools

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "erlaubte_tools": list(self.erlaubte_tools),
            "tool_infos": dict(self.tool_infos),
            "quelle": self.quelle,
        }


def filter_tools(tools: list[Tool], toolset: Toolset) -> list[Tool]:
    """Default-deny: nur Tools auf der Whitelist passieren.

    Sicherheitskern (M7): kein nicht-erlaubtes Tool darf durchrutschen --
    auch nicht bei leerer/fehlender Whitelist (dann passiert NICHTS).
    """
    erlaubt = set(toolset.erlaubte_tools)
    return [t for t in tools if t.name in erlaubt]


def export_toolset(toolset: Toolset, tools: Optional[list[Tool]] = None) -> dict:
    """Versendbares Toolset-Paket (JSON-serialisierbar).

    Enthaelt NUR erlaubte Tools (bereits gefiltert), plus tool_infos.
    """
    gefiltert = filter_tools(tools, toolset) if tools else []
    return {
        "toolset": toolset.name,
        "erlaubte_tools": list(toolset.erlaubte_tools),
        "tools": [t.to_dict() for t in gefiltert],
        "tool_infos": dict(toolset.tool_infos),
    }


def lade_katalog(pfad: Path) -> list[Tool]:
    """Liest einen ControlCenter-Katalog (JSON) und gibt Tools zurueck.

    Erwartet ein robustes, tolerantes Format: entweder
    {"servers": [{"packageName": str, "tools": [{"name","description"}]}]}
    oder {"tools": [{"name","server","description","bundle"}]}.
    Fehlende Datei / unlesbares JSON -> leere Liste (graceful).
    """
    pfad = Path(pfad)
    if not pfad.exists():
        return []
    try:
        data = json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    tools: list[Tool] = []
    if isinstance(data, dict) and "servers" in data:
        for srv in data.get("servers", []):
            server = srv.get("packageName") or srv.get("name", "")
            for t in srv.get("tools", []) or []:
                tools.append(Tool(
                    name=t.get("name", ""), server=server,
                    beschreibung=t.get("description", t.get("beschreibung", "")),
                    bundle=t.get("bundle", ""),
                ))
    elif isinstance(data, dict) and "tools" in data:
        for t in data.get("tools", []):
            tools.append(Tool(
                name=t.get("name", ""), server=t.get("server", ""),
                beschreibung=t.get("description", t.get("beschreibung", "")),
                bundle=t.get("bundle", ""),
            ))
    return [t for t in tools if t.name]


class ToolsetManager:
    """Verbindet toolset-Profile (ProfileManager) mit dem Tool-Katalog."""

    def __init__(self, profile_manager=None, katalog_pfad: Optional[Path] = None):
        self.profile = profile_manager
        self._katalog = lade_katalog(katalog_pfad) if katalog_pfad else []

    def verfuegbare_tools(self) -> list[Tool]:
        return list(self._katalog)

    def toolset_aus_profil(self, profil_name: str) -> Optional[Toolset]:
        """Baut ein Toolset aus einem toolset-Profil des ProfileManagers."""
        if not self.profile:
            return None
        p = self.profile.lade(profil_name, "toolset")
        if not p:
            return None
        return Toolset(
            name=profil_name,
            erlaubte_tools=list(p.payload.get("erlaubte_tools", [])),
            tool_infos=dict(p.payload.get("tool_infos", {})),
        )

    def aufgeloest(self, profil_name: str) -> dict:
        """Versendbares Paket fuer ein toolset-Profil (gefiltert gegen Katalog)."""
        ts = self.toolset_aus_profil(profil_name)
        if ts is None:
            return {"toolset": profil_name, "erlaubte_tools": [], "tools": [], "tool_infos": {}}
        return export_toolset(ts, self._katalog)
