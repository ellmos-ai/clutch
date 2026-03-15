"""Strecke -- Task-Analyse und Klassifikation.

Analysiert die "Strecke" (den Task) und bestimmt:
- Streckentyp (Feldweg bis Langstrecke)
- Tempo (Urgency)
- Schwierigkeitsgrad
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class StreckenTyp(Enum):
    FELDWEG = "feldweg"              # Trivial: Typos, Formatierung
    LANDSTRASSE = "landstrasse"      # Standard-Entwicklung
    BUNDESSTRASSE = "bundesstrasse"  # Bugfix, tiefere Analyse
    AUTOBAHN = "autobahn"            # Architektur, System-Design
    PRUEFSTRECKE = "pruefstrecke"    # Code-Review
    RALLYE = "rallye"                # Bulk-Operationen
    KONVOI = "konvoi"                # Pipeline/Sequentiell
    TEAMFAHRT = "teamfahrt"          # Multi-File parallel
    LANGSTRECKE = "langstrecke"      # Komplexe Grossprojekte
    TESTFAHRT = "testfahrt"          # Test-Generierung
    UNBEKANNT = "unbekannt"


class Tempo(Enum):
    """Wie schnell soll gefahren werden?"""
    GEMUETLICH = "gemuetlich"    # Gruendlich, keine Eile
    NORMAL = "normal"
    EILIG = "eilig"              # Schnell bitte!


@dataclass
class StreckenProfil:
    """Vollstaendige Analyse einer Strecke (eines Tasks)."""
    typ: StreckenTyp
    tempo: Tempo
    schwierigkeit: float  # 0.0 - 1.0
    etappen: int = 1      # Anzahl Teilaufgaben
    braucht_spezialisten: bool = False
    ist_pipeline: bool = False
    konfidenz: float = 0.0
    erkannte_keywords: list[str] = field(default_factory=list)


_STRECKEN_KEYWORDS: dict[StreckenTyp, list[str]] = {
    StreckenTyp.FELDWEG: [
        r"\b(typo|rename|format|indent|whitespace|comment|docstring)\b",
        r"\b(einfach|simpel|klein|minor|trivial)\b",
    ],
    StreckenTyp.BUNDESSTRASSE: [
        r"\b(bug|fix|fehler|error|crash|broken|kaputt|defect|issue)\b",
        r"\b(debug|traceback|exception|stacktrace)\b",
    ],
    StreckenTyp.AUTOBAHN: [
        r"\b(architektur|architecture|design|refactor|restructure|migration)\b",
        r"\b(pattern|abstraktion|interface|api.?design)\b",
    ],
    StreckenTyp.PRUEFSTRECKE: [
        r"\b(review|pruef|check|audit|inspect|qualit)\b",
    ],
    StreckenTyp.RALLYE: [
        r"\b(bulk|batch|mass|alle.?dateien|all.?files|format.?all)\b",
    ],
    StreckenTyp.TEAMFAHRT: [
        r"\b(multi.?file|mehrere.?dateien|cross.?module|uebergreifend)\b",
    ],
    StreckenTyp.KONVOI: [
        r"\b(pipeline|workflow|chain|sequen|step.?by.?step)\b",
    ],
    StreckenTyp.TESTFAHRT: [
        r"\b(test|tests|unittest|pytest|spec|coverage)\b",
    ],
}

_TEMPO_KEYWORDS = {
    Tempo.EILIG: [
        r"\b(schnell|quick|fast|asap|eilig|urgent|sofort|immediately)\b",
    ],
    Tempo.GEMUETLICH: [
        r"\b(gruendlich|thorough|careful|sorgfaeltig|keine.?eile|take.?time)\b",
    ],
}

_SCHWIERIGKEITS_SIGNALE = {
    "hoch": [
        r"\b(komplex|complex|schwierig|difficult|tricky|challenging)\b",
        r"\b(system|global|ueberall|everywhere|entire|ganz)\b",
    ],
    "niedrig": [
        r"\b(einfach|simple|klein|small|quick|one.?liner)\b",
    ],
}


class StreckenAnalyse:
    """Analysiert Tasks und bestimmt den Streckentyp.

    Phase 1: Regelbasiert (Keywords).
    Phase 2: ML-basiert wenn genuegend Daten vorhanden (spaeter).
    """

    def analysiere(self, beschreibung: str, kontext: Optional[dict] = None) -> StreckenProfil:
        text = beschreibung.lower()
        kontext = kontext or {}

        typ, konfidenz, keywords = self._typ_erkennen(text)
        tempo = self._tempo_erkennen(text, kontext)
        schwierigkeit = self._schwierigkeit_schaetzen(text, kontext)
        etappen = self._etappen_schaetzen(text, kontext)

        return StreckenProfil(
            typ=typ,
            tempo=tempo,
            schwierigkeit=schwierigkeit,
            etappen=etappen,
            braucht_spezialisten=typ in (
                StreckenTyp.AUTOBAHN, StreckenTyp.PRUEFSTRECKE,
            ),
            ist_pipeline=typ == StreckenTyp.KONVOI,
            konfidenz=konfidenz,
            erkannte_keywords=keywords,
        )

    def _typ_erkennen(self, text: str) -> tuple[StreckenTyp, float, list[str]]:
        scores: dict[StreckenTyp, tuple[float, list[str]]] = {}

        for typ, patterns in _STRECKEN_KEYWORDS.items():
            matched = []
            for pattern in patterns:
                found = re.findall(pattern, text, re.IGNORECASE)
                matched.extend(found)
            if matched:
                scores[typ] = (len(matched) / len(patterns), matched)

        if not scores:
            return StreckenTyp.LANDSTRASSE, 0.3, []

        best = max(scores, key=lambda k: scores[k][0])
        konfidenz, keywords = scores[best]
        return best, min(konfidenz, 1.0), keywords

    def _tempo_erkennen(self, text: str, kontext: dict) -> Tempo:
        if kontext.get("tempo"):
            return Tempo(kontext["tempo"])

        for tempo, patterns in _TEMPO_KEYWORDS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return tempo

        return Tempo.NORMAL

    def _schwierigkeit_schaetzen(self, text: str, kontext: dict) -> float:
        if "schwierigkeit" in kontext:
            return float(kontext["schwierigkeit"])

        score = 0.5

        for pattern in _SCHWIERIGKEITS_SIGNALE["hoch"]:
            if re.search(pattern, text, re.IGNORECASE):
                score += 0.15
        for pattern in _SCHWIERIGKEITS_SIGNALE["niedrig"]:
            if re.search(pattern, text, re.IGNORECASE):
                score -= 0.15

        word_count = len(text.split())
        if word_count > 100:
            score += 0.1
        elif word_count < 15:
            score -= 0.1

        return max(0.0, min(1.0, score))

    def _etappen_schaetzen(self, text: str, kontext: dict) -> int:
        if "etappen" in kontext:
            return int(kontext["etappen"])

        bullets = len(re.findall(r"^\s*[-*\d+\.]\s+", text, re.MULTILINE))
        if bullets > 1:
            return bullets

        conjunctions = len(re.findall(
            r"\b(und|and|sowie|plus|ausserdem|additionally)\b", text,
        ))
        return max(1, 1 + conjunctions)
