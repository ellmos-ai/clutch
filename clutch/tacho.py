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
    model_id: str = ""
    requested_effort: Optional[str] = None
    effective_effort: Optional[str] = None
    mode: str = "standard"
    service_tier: str = "default"
    task_class: Optional[str] = None
    eval_case: Optional[str] = None
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    tool_fees_usd: float = 0.0
    usage_status: str = "unknown"
    price_version: Optional[str] = None
    cost_usd: Optional[float] = None


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
            model_id=config.model_id,
            requested_effort=config.effort,
            effective_effort=config.effective_effort,
            mode=config.reasoning_mode,
            service_tier=config.service_tier,
            task_class=config.task_class or strecken_typ,
            eval_case=config.eval_case,
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
            model_id=m.model_id,
            requested_effort=m.requested_effort,
            effective_effort=m.effective_effort,
            mode=m.mode,
            service_tier=m.service_tier,
            task_class=m.task_class,
            eval_case=m.eval_case,
            input_tokens=m.input_tokens,
            cached_input_tokens=m.cached_input_tokens,
            cache_write_tokens=m.cache_write_tokens,
            output_tokens=m.output_tokens,
            reasoning_tokens=m.reasoning_tokens,
            tool_fees_usd=m.tool_fees_usd,
            usage_status=m.usage_status,
            price_version=m.price_version,
            cost_usd=m.cost_usd,
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
