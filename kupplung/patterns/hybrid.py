"""Hybrid-Fahrt -- Kombination aus Kolonne (sequentiell) und Team (parallel).

Typischer Ablauf: Erst sequentielle Vorbereitungsschritte (Kolonne),
dann parallele Ausfuehrung (Team), dann sequentielle Nachbereitung.

Beispiel: Pipeline "Analysiere Code -> (Refactore Module A | Module B | Module C) -> Teste alles"
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from kupplung.kupplung import FahrtConfig
from kupplung.patterns.kolonne import Kolonne, KolonnenSchritt
from kupplung.patterns.team import TeamFahrt, TeamMitglied


@dataclass
class HybridPhase:
    """Eine Phase in der Hybrid-Fahrt."""
    name: str
    typ: str  # "kolonne" | "team"


@dataclass
class HybridErgebnis:
    """Ergebnis einer kompletten Hybrid-Fahrt."""
    erfolg: bool
    phasen_ergebnisse: dict[str, Any] = field(default_factory=dict)
    fehler: list[str] = field(default_factory=list)
    latenz: float = 0.0
    phasen_fertig: int = 0
    phasen_gesamt: int = 0


class HybridFahrt:
    """Kombiniert sequentielle und parallele Phasen.

    Nutzung:
        hybrid = HybridFahrt()

        # Phase 1: Sequentielle Vorbereitung
        hybrid.kolonne_phase("vorbereitung", [
            KolonnenSchritt("analyse", config_a, analyse_handler),
            KolonnenSchritt("plan", config_b, plan_handler),
        ])

        # Phase 2: Parallele Ausfuehrung
        hybrid.team_phase("umsetzung", [
            TeamMitglied("modul_a", config_c, refactor_a),
            TeamMitglied("modul_b", config_c, refactor_b),
        ])

        # Phase 3: Sequentielle Nachbereitung
        hybrid.kolonne_phase("nachbereitung", [
            KolonnenSchritt("test", config_d, test_handler),
            KolonnenSchritt("review", config_e, review_handler),
        ])

        ergebnis = hybrid.fahren()
    """

    def __init__(self):
        self._phasen: list[tuple[HybridPhase, Any]] = []

    def kolonne_phase(
        self,
        name: str,
        schritte: list[KolonnenSchritt],
    ) -> "HybridFahrt":
        """Fuegt eine sequentielle Phase hinzu."""
        kolonne = Kolonne()
        for s in schritte:
            kolonne.schritt(s)
        self._phasen.append((HybridPhase(name=name, typ="kolonne"), kolonne))
        return self

    def team_phase(
        self,
        name: str,
        mitglieder: list[TeamMitglied],
        max_parallel: int = 5,
    ) -> "HybridFahrt":
        """Fuegt eine parallele Phase hinzu."""
        team = TeamFahrt(max_parallel=max_parallel)
        for m in mitglieder:
            team.mitglied(m)
        self._phasen.append((HybridPhase(name=name, typ="team"), team))
        return self

    def fahren(self, start_input: Any = None) -> HybridErgebnis:
        """Fuehrt alle Phasen in Reihenfolge aus.

        Der Output der letzten Kolonne-Phase wird als Kontext
        an die naechste Phase weitergegeben.
        """
        result = HybridErgebnis(
            erfolg=True,
            phasen_gesamt=len(self._phasen),
        )
        t0 = time.time()
        aktueller_kontext = start_input

        for phase, executor in self._phasen:
            try:
                if phase.typ == "kolonne":
                    phase_ergebnis = executor.fahren(start_input=aktueller_kontext)
                    result.phasen_ergebnisse[phase.name] = phase_ergebnis

                    if not phase_ergebnis.erfolg:
                        result.erfolg = False
                        result.fehler.append(
                            f"Kolonne '{phase.name}' fehlgeschlagen: "
                            f"{phase_ergebnis.fehler}"
                        )
                        break

                    # Letzter Output wird Kontext fuer naechste Phase
                    if phase_ergebnis.outputs:
                        aktueller_kontext = phase_ergebnis.outputs[-1]

                elif phase.typ == "team":
                    phase_ergebnis = executor.fahren(kontext=aktueller_kontext)
                    result.phasen_ergebnisse[phase.name] = phase_ergebnis

                    if not phase_ergebnis.erfolg:
                        result.erfolg = False
                        result.fehler.append(
                            f"Team '{phase.name}' fehlgeschlagen: "
                            f"{phase_ergebnis.fehler}"
                        )
                        break

                    # Team-Ergebnisse als Dict werden Kontext
                    aktueller_kontext = phase_ergebnis.ergebnisse

                result.phasen_fertig += 1

            except Exception as e:
                result.erfolg = False
                result.fehler.append(f"Phase '{phase.name}': {e}")
                break

        result.latenz = time.time() - t0
        return result
