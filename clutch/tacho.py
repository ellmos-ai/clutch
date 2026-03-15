"""Tacho -- Metriken-Erfassung waehrend der Fahrt.

Misst Latenz, Tokens, Tool-Calls etc. und schreibt
ins Fahrtenbuch.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from clutch.fahrtenbuch import Fahrtenbuch, FahrtEintrag
from clutch.kupplung import FahrtConfig


@dataclass
class LaufendeMessung:
    fahrt_id: str
    start_zeit: float
    config: FahrtConfig
    strecken_typ: str
    total_tokens: int = 0
    thinking_tokens: int = 0
    tool_calls: int = 0
    files_read: int = 0
    files_changed: int = 0
    erfolg: bool = True
    wiederholungen: int = 0
    user_korrekturen: int = 0
    fehler_anzahl: int = 0


class Tacho:
    """Misst die Fahrt (Task-Ausfuehrung) und schreibt ins Fahrtenbuch."""

    def __init__(self, buch: Fahrtenbuch):
        self.buch = buch
        self._aktiv: dict[str, LaufendeMessung] = {}

    def start(self, strecken_typ: str, config: FahrtConfig) -> str:
        fahrt_id = f"f_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        self._aktiv[fahrt_id] = LaufendeMessung(
            fahrt_id=fahrt_id,
            start_zeit=time.time(),
            config=config,
            strecken_typ=strecken_typ,
        )
        return fahrt_id

    def update(self, fahrt_id: str, **kwargs) -> None:
        if fahrt_id in self._aktiv:
            messung = self._aktiv[fahrt_id]
            for key, value in kwargs.items():
                if hasattr(messung, key):
                    setattr(messung, key, value)

    def stop(self, fahrt_id: str, erfolg: bool = True) -> Optional[FahrtEintrag]:
        if fahrt_id not in self._aktiv:
            return None

        m = self._aktiv.pop(fahrt_id)
        latenz = time.time() - m.start_zeit

        eintrag = FahrtEintrag(
            fahrt_id=m.fahrt_id,
            strecken_typ=m.strecken_typ,
            gang=m.config.gang.name,
            provider=m.config.provider,
            gas=m.config.gas.wert,
            muster=m.config.muster,
            total_tokens=m.total_tokens,
            thinking_tokens=m.thinking_tokens,
            tool_calls=m.tool_calls,
            files_read=m.files_read,
            files_changed=m.files_changed,
            latenz_sekunden=latenz,
            erfolg=erfolg,
            wiederholungen=m.wiederholungen,
            user_korrekturen=m.user_korrekturen,
            fehler_anzahl=m.fehler_anzahl,
            ist_erkundung=m.config.ist_erkundung,
            entscheidungs_grund=m.config.entscheidungs_grund,
        )

        self.buch.eintragen(eintrag)
        return eintrag

    @contextmanager
    def messen(self, strecken_typ: str, config: FahrtConfig):
        """Context-Manager fuer einfache Messung."""
        fahrt_id = self.start(strecken_typ, config)
        result = {"fahrt_id": fahrt_id, "erfolg": True}
        try:
            yield result
        except Exception:
            result["erfolg"] = False
            raise
        finally:
            self.stop(fahrt_id, erfolg=result["erfolg"])

    def kpis(self) -> dict:
        total = self.buch.gesamte_fahrten()
        return {
            "gesamte_fahrten": total,
            "phase": "sammeln" if total < 200 else "routing",
            "aktive_messungen": len(self._aktiv),
        }
