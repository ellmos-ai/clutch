"""Scorer -- Komplexitaets- und Zweck-Bewertung von Tasks.

Portiert und provider-neutral angepasst aus BACHs ComplexityScorer
(hub/_services/delegation/complexity_scorer.py). Liefert:

- score(task) -> (0-100, breakdown): numerischer Komplexitaets-Score.
- gang_level_fuer_score(score) -> 1..5: provider-neutrale Gang-Stufe.
- erkenne_zweck(task) -> str: Zweck/Modalitaet des Tasks
  (coding | vision | research | bulk | creative | general).

Der Zweck speist das Zweck-Routing (Plan M2): Gaenge werden nach ihren
`staerken`-Tags gefiltert, der Score bestimmt die Stufe innerhalb des Zwecks.
Zero-Dependency (nur stdlib `re`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Komplexitaets-Indikatoren (aus BACH portiert)
# ---------------------------------------------------------------------------

SIMPLE_KEYWORDS = {
    "zeige", "liste", "anzeige", "status", "info", "check", "pruefe", "prüfe",
    "lies", "oeffne", "öffne", "schliesse", "schließe", "starte", "stoppe", "restart",
}
MEDIUM_KEYWORDS = {
    "analysiere", "vergleiche", "finde", "suche", "filter", "sortiere",
    "berechne", "formatiere", "konvertiere", "update", "aktualisiere",
}
COMPLEX_KEYWORDS = {
    "entwickle", "implementiere", "erstelle", "designe", "optimiere",
    "refactore", "refaktoriere", "migriere", "integriere", "debugge", "behebe",
}
VERY_COMPLEX_KEYWORDS = {
    "architektur", "framework", "system", "migration", "multi-agent",
    "distributed", "microservice", "security", "performance-optimierung",
}

CODE_INDICATORS = [
    r"\bdef\s+\w+", r"\bclass\s+\w+", r"\bimport\s+\w+",
    r"\{[\s\S]*\}", r"function\s+\w+", r"async\s+\w+", r"```[\s\S]*```",
]
MULTI_STEP_INDICATORS = [
    r"\d+\.\s+", r"schritt\s+\d+", r"dann\s+", r"danach\s+",
    r"zuerst\s+.*\s+dann", r"ausserdem", r"außerdem", r"zusaetzlich", r"zusätzlich",
    r"phase\s+\d+", r"teil\s+\d+",
]
TECH_TERMS = [
    "api", "endpoint", "database", "sql", "rest", "graphql",
    "authentication", "authorization", "cache", "redis",
    "docker", "kubernetes", "ci/cd", "deployment",
]

# ---------------------------------------------------------------------------
# Zweck-/Modalitaets-Indikatoren (neu, Plan M2)
# ---------------------------------------------------------------------------

PURPOSE_KEYWORDS = {
    "coding": {
        "code", "coden", "programmier", "implementiere", "refactor", "refaktor",
        "bug", "debug", "funktion", "function", "klasse", "class", "api",
        "test", "kompil", "compile", "script", "pyproject", "git", "merge",
    },
    "vision": {
        "bild", "image", "foto", "screenshot", "diagramm", "grafik", "ocr",
        "sieh dir", "auf dem bild", "im bild", "visuell", "video", "screen",
    },
    "research": {
        "recherch", "research", "quelle", "studie", "paper", "literatur",
        "suche im web", "websuche", "finde heraus", "untersuche", "vergleiche studien",
    },
    "bulk": {
        "alle dateien", "batch", "massen", "stapel", "jede datei", "fuer jeden",
        "fuer jede", "durchlaufe", "iteriere ueber", "tausend", "hunderte",
    },
    "creative": {
        "schreibe einen", "geschichte", "gedicht", "kreativ", "brainstorm",
        "idee", "slogan", "marketing", "erzaehl", "story", "name fuer",
    },
}


@dataclass
class ScoreErgebnis:
    score: int = 0
    breakdown: dict = field(default_factory=dict)
    zweck: str = "general"
    gang_level: int = 3


class Scorer:
    """Bewertet Task-Komplexitaet und -Zweck."""

    def __init__(self):
        self._code = [re.compile(p, re.IGNORECASE) for p in CODE_INDICATORS]
        self._steps = [re.compile(p, re.IGNORECASE) for p in MULTI_STEP_INDICATORS]

    # -- Komplexitaet ------------------------------------------------------

    def score(self, task: str) -> tuple[int, dict]:
        text = task.lower()
        bd: dict[str, int] = {}

        n = len(task)
        bd["length"] = 5 if n < 50 else 10 if n < 150 else 15 if n < 300 else 20

        kw = 0
        if any(k in text for k in SIMPLE_KEYWORDS):
            kw = 5
        if any(k in text for k in MEDIUM_KEYWORDS):
            kw = 15
        if any(k in text for k in COMPLEX_KEYWORDS):
            kw = 25
        if any(k in text for k in VERY_COMPLEX_KEYWORDS):
            kw = 30
        bd["keywords"] = kw

        code_hits = sum(1 for p in self._code if p.search(task))
        bd["code"] = min(25, code_hits * 8) if code_hits else 0

        step_hits = sum(1 for p in self._steps if p.search(task))
        bd["multi_step"] = min(20, step_hits * 5) if step_hits else 0

        bd["technical"] = min(10, sum(3 for t in TECH_TERMS if t in text))

        return min(100, sum(bd.values())), bd

    @staticmethod
    def gang_level_fuer_score(score: int) -> int:
        """Provider-neutrale Gang-Stufe 1..5 aus dem Score."""
        if score < 20:
            return 1
        if score < 40:
            return 2
        if score < 60:
            return 3
        if score < 80:
            return 4
        return 5

    # -- Zweck / Modalitaet ------------------------------------------------

    def erkenne_zweck(self, task: str, hat_bild: bool = False) -> str:
        """Erkennt den Zweck/die Modalitaet eines Tasks.

        hat_bild=True (Bild-/Dokument-Anhang) erzwingt 'vision', damit das
        Routing ein vision-faehiges Modell waehlt (Plan M2, bildbewusst).
        """
        if hat_bild:
            return "vision"
        text = task.lower()
        treffer: dict[str, int] = {}
        for zweck, kws in PURPOSE_KEYWORDS.items():
            n = sum(1 for k in kws if k in text)
            if n:
                treffer[zweck] = n
        if not treffer:
            return "general"
        return max(treffer.items(), key=lambda x: x[1])[0]

    # -- Komplettbewertung -------------------------------------------------

    def bewerte(self, task: str, hat_bild: bool = False) -> ScoreErgebnis:
        score, bd = self.score(task)
        return ScoreErgebnis(
            score=score,
            breakdown=bd,
            zweck=self.erkenne_zweck(task, hat_bild=hat_bild),
            gang_level=self.gang_level_fuer_score(score),
        )


_scorer: Optional[Scorer] = None


def get_scorer() -> Scorer:
    global _scorer
    if _scorer is None:
        _scorer = Scorer()
    return _scorer
