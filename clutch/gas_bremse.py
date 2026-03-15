"""Gas & Bremse -- Reasoning-Level-Steuerung innerhalb eines Modells.

Gas  = Mehr Tokens, gruendlichere Analyse (Reasoning hoch)
Bremse = Weniger Tokens, direktere Antwort (Reasoning runter)

Der Gas-Wert ist ein Float von 0.0 (Vollbremsung) bis 1.0 (Vollgas).
Er beeinflusst Prompt-Strategie, Token-Budget und Timeout.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class GasStellung:
    """Aktuelle Gas/Bremse-Stellung fuer einen Task."""
    wert: float              # 0.0 - 1.0
    token_multiplikator: float
    timeout_multiplikator: float
    prompt_strategie: str    # "direkt" | "ausgewogen" | "gruendlich"
    beschreibung: str


# Vordefinierte Gas-Stellungen
_STELLUNGEN = {
    "leerlauf":   (0.0, 0.2, 0.3, "direkt",     "Minimaler Aufwand, nur das Noetigste"),
    "schleichen": (0.2, 0.4, 0.5, "direkt",     "Schnell und direkt, wenig Analyse"),
    "stadt":      (0.4, 0.7, 0.8, "ausgewogen", "Ausgewogene Analyse"),
    "land":       (0.5, 1.0, 1.0, "ausgewogen", "Standard-Betrieb"),
    "schnell":    (0.7, 1.3, 1.2, "gruendlich", "Gruendlichere Analyse"),
    "autobahn":   (0.8, 1.6, 1.5, "gruendlich", "Sehr gruendlich, mehrere Ansaetze"),
    "vollgas":    (1.0, 2.0, 2.0, "gruendlich", "Maximale Gruendlichkeit"),
}


class GasBremse:
    """Steuert das Reasoning-Level innerhalb eines Modells.

    Nutzung:
        pedal = GasBremse()
        stellung = pedal.stellung(0.7)  # 70% Gas
        print(stellung.prompt_strategie)  # "gruendlich"
        print(stellung.token_multiplikator)  # 1.3x
    """

    def stellung(self, gas: float) -> GasStellung:
        """Berechnet die Gas-Stellung fuer einen gegebenen Wert."""
        gas = max(0.0, min(1.0, gas))

        # Interpoliere zwischen den vordefinierten Stellungen
        if gas <= 0.1:
            s = _STELLUNGEN["leerlauf"]
        elif gas <= 0.3:
            s = _STELLUNGEN["schleichen"]
        elif gas <= 0.45:
            s = _STELLUNGEN["stadt"]
        elif gas <= 0.6:
            s = _STELLUNGEN["land"]
        elif gas <= 0.75:
            s = _STELLUNGEN["schnell"]
        elif gas <= 0.9:
            s = _STELLUNGEN["autobahn"]
        else:
            s = _STELLUNGEN["vollgas"]

        _, token_mult, timeout_mult, strategie, beschreibung = s

        # Feinere Interpolation fuer Multiplikatoren
        token_mult = 0.2 + gas * 1.8       # 0.2x bei 0.0, 2.0x bei 1.0
        timeout_mult = 0.3 + gas * 1.7     # 0.3x bei 0.0, 2.0x bei 1.0

        return GasStellung(
            wert=gas,
            token_multiplikator=round(token_mult, 2),
            timeout_multiplikator=round(timeout_mult, 2),
            prompt_strategie=strategie,
            beschreibung=beschreibung,
        )

    def gas_fuer_tempo(self, tempo: str) -> float:
        """Bestimmt Gas-Wert basierend auf Tempo (Urgency).

        eilig -> weniger Gas (schnell durchkommen)
        gemuetlich -> mehr Gas (gruendlicher)
        """
        return {
            "eilig": 0.3,
            "normal": 0.5,
            "gemuetlich": 0.8,
        }.get(tempo, 0.5)

    def anpassen(self, basis_gas: float, schwierigkeit: float, tempo: str) -> float:
        """Passt den Gas-Wert basierend auf Kontext an.

        - Hohe Schwierigkeit -> mehr Gas
        - Eilig -> weniger Gas
        - Gemuetlich -> mehr Gas
        """
        gas = basis_gas

        # Schwierigkeit: Schwierigere Tasks brauchen mehr Analyse
        if schwierigkeit > 0.7:
            gas += 0.15
        elif schwierigkeit < 0.3:
            gas -= 0.1

        # Tempo-Override
        if tempo == "eilig":
            gas = min(gas, 0.5)    # Kappung bei eilig
        elif tempo == "gemuetlich":
            gas = max(gas, 0.6)    # Mindestens 60% bei gruendlich

        return max(0.0, min(1.0, gas))

    def prompt_prefix(self, stellung: GasStellung) -> str:
        """Generiert einen Prompt-Prefix basierend auf der Gas-Stellung.

        Dieser Prefix wird vor den eigentlichen Task-Prompt gesetzt
        um das Reasoning-Verhalten zu steuern.
        """
        if stellung.prompt_strategie == "direkt":
            return (
                "Antworte direkt und knapp. "
                "Keine ausfuehrliche Analyse, nur das Ergebnis."
            )
        elif stellung.prompt_strategie == "gruendlich":
            return (
                "Analysiere gruendlich. Pruefe mehrere Ansaetze. "
                "Erklaere dein Vorgehen Schritt fuer Schritt."
            )
        else:
            return ""  # "ausgewogen" = kein Prefix noetig
