"""Fahrt-Muster: Kolonne (sequentiell), Team (parallel), Schwarm (massiv), Hybrid (kombiniert)."""

from kupplung.patterns.kolonne import Kolonne, KolonnenSchritt
from kupplung.patterns.team import TeamFahrt, TeamMitglied
from kupplung.patterns.schwarm import Schwarm, SchwarmAufgabe
from kupplung.patterns.hybrid import HybridFahrt, HybridErgebnis

__all__ = [
    "Kolonne", "KolonnenSchritt",
    "TeamFahrt", "TeamMitglied",
    "Schwarm", "SchwarmAufgabe",
    "HybridFahrt", "HybridErgebnis",
]
