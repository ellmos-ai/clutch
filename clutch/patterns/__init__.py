"""Fahrt-Muster: Kolonne (sequentiell), Team (parallel), Schwarm (massiv), Hybrid (kombiniert)."""

from clutch.patterns.kolonne import Kolonne, KolonnenSchritt
from clutch.patterns.team import TeamFahrt, TeamMitglied
from clutch.patterns.schwarm import Schwarm, SchwarmAufgabe
from clutch.patterns.hybrid import HybridFahrt, HybridErgebnis

__all__ = [
    "Kolonne", "KolonnenSchritt",
    "TeamFahrt", "TeamMitglied",
    "Schwarm", "SchwarmAufgabe",
    "HybridFahrt", "HybridErgebnis",
]
