"""Kupplung -- Der Modellwechsel-Mechanismus.

Die Kupplung ist der Kern: Sie entscheidet WANN und WIE
zwischen Modellen (Gaengen) gewechselt wird.

Ablauf:
  1. Strecke analysieren
  2. Passenden Gang waehlen (Getriebe)
  3. Gas einstellen (Reasoning-Level)
  4. Bei Bedarf: Kuppeln (Modellwechsel)

Die Kupplung beruecksichtigt:
  - Budget-Zone (Tankuhr)
  - Health-Status (Bordcomputer)
  - Gelernte Erfahrungen (Fahrschule)
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from clutch.strecke import StreckenProfil, StreckenTyp, Tempo
from clutch.getriebe import Getriebe, Gang
from clutch.gas_bremse import GasBremse, GasStellung


@dataclass
class FahrtConfig:
    """Komplette Konfiguration fuer eine Fahrt (Task-Ausfuehrung)."""
    gang: Gang                    # Welches Modell
    gas: GasStellung              # Reasoning-Level
    muster: str                   # "einzelfahrt" | "kolonne" | "team" | "schwarm" | "hybrid"
    ist_erkundung: bool = False   # Epsilon-Greedy Exploration?
    entscheidungs_grund: str = ""

    @property
    def model_id(self) -> str:
        return self.gang.model_id

    @property
    def provider(self) -> str:
        return self.gang.provider

    def to_dict(self) -> dict:
        return {
            "gang": self.gang.name,
            "provider": self.gang.provider,
            "model_id": self.gang.model_id,
            "gas": self.gas.wert,
            "gas_strategie": self.gas.prompt_strategie,
            "token_multiplikator": self.gas.token_multiplikator,
            "muster": self.muster,
            "ist_erkundung": self.ist_erkundung,
            "grund": self.entscheidungs_grund,
        }


class Kupplung:
    """Der Modellwechsel-Mechanismus.

    Nimmt ein StreckenProfil und bestimmt die optimale FahrtConfig:
    welches Modell (Gang), wie viel Reasoning (Gas), welches Muster.

    Nutzung:
        getriebe = Getriebe()
        kupplung = Kupplung(getriebe)
        profil = StreckenAnalyse().analysiere("Fix den Bug")
        config = kupplung.einlegen(profil)
    """

    def __init__(
        self,
        getriebe: Getriebe,
        config_dir: Optional[Path] = None,
    ):
        self.getriebe = getriebe
        self.pedal = GasBremse()
        self.config_dir = config_dir or Path(__file__).parent.parent / "config"
        self._strecken_config = self._load_strecken()
        self._standard = self._strecken_config.get("standard", {})
        self._erkundungsrate = self._strecken_config.get("erkundungsrate", 0.10)
        self._overrides: dict[str, dict] = {}

    def einlegen(
        self,
        profil: StreckenProfil,
        budget_zone: Optional[str] = None,
        max_gang: Optional[int] = None,
        gesperrte_modelle: Optional[list[str]] = None,
    ) -> FahrtConfig:
        """Bestimmt die optimale FahrtConfig fuer ein StreckenProfil.

        Das ist der Kupplungsvorgang: Gang waehlen + Gas einstellen.
        """
        gesperrte = gesperrte_modelle or []

        # 1. Strecken-Lookup
        strecken_key = profil.typ.value
        if strecken_key in self._overrides:
            basis = self._overrides[strecken_key].copy()
        elif strecken_key in self._strecken_config.get("strecken", {}):
            basis = self._strecken_config["strecken"][strecken_key].copy()
        else:
            basis = self._standard.copy()

        # 2. Gang waehlen
        gang_name = basis.get("gang", "claude-sonnet")
        gang = self.getriebe.gang(gang_name)

        # 3. Tempo -> Gas anpassen
        basis_gas = basis.get("gas", 0.5)
        gas_wert = self.pedal.anpassen(
            basis_gas,
            profil.schwierigkeit,
            profil.tempo.value,
        )

        # 4. Tempo-Override: Bei "eilig" Gang runterschrauben
        if profil.tempo == Tempo.EILIG and gang and gang.gang >= 4:
            runtergeschaltet = self.getriebe.naechster_gang_runter(gang.name)
            if runtergeschaltet:
                gang = runtergeschaltet

        # 5. Schwierigkeit: Bei sehr schwierig Gang hochschalten
        if profil.schwierigkeit > 0.8 and gang:
            hochgeschaltet = self.getriebe.naechster_gang_hoch(gang.name)
            if hochgeschaltet:
                gang = hochgeschaltet

        # 6. Budget-Constraint
        if budget_zone:
            zone_max = {"green": 5, "yellow": 3, "orange": 1, "red": 0}
            limit = zone_max.get(budget_zone, 5)
            if max_gang is not None:
                limit = min(limit, max_gang)
            if gang and gang.gang > limit:
                guenstigere = self.getriebe.filter(max_gang=limit)
                if guenstigere:
                    gang = guenstigere[-1]  # Hoechster erlaubter Gang
                elif limit == 0:
                    gang = None  # Budget erschoepft

        # 7. Gesperrte Modelle
        if gang and gang.name in gesperrte:
            alternativen = [
                g for g in self.getriebe.alle_gaenge()
                if g.name not in gesperrte and g.gang <= (gang.gang if gang else 5)
            ]
            gang = alternativen[-1] if alternativen else None

        # 8. Fallback
        if not gang:
            alle = self.getriebe.alle_gaenge()
            gang = alle[0] if alle else Gang(
                name="fallback", provider="unknown", model_id="unknown",
                gang=1, leistung="basis", kosten_input_1k=0, kosten_output_1k=0,
            )

        # 9. Muster bestimmen
        muster = self._muster_waehlen(basis.get("muster", "einzelfahrt"), profil)

        # 10. Exploration (Epsilon-Greedy)
        ist_erkundung = False
        if random.random() < self._erkundungsrate:
            gang, gas_wert, ist_erkundung = self._erkunden(gang, gas_wert)

        # Gas-Stellung berechnen
        gas_stellung = self.pedal.stellung(gas_wert)

        grund = self._grund_bauen(profil, gang, ist_erkundung)

        return FahrtConfig(
            gang=gang,
            gas=gas_stellung,
            muster=muster,
            ist_erkundung=ist_erkundung,
            entscheidungs_grund=grund,
        )

    def override(self, strecken_typ: str, config: dict) -> None:
        """Setzt eine manuelle Override-Konfiguration fuer einen Streckentyp."""
        self._overrides[strecken_typ] = config

    def set_erkundungsrate(self, rate: float) -> None:
        self._erkundungsrate = max(0.0, min(1.0, rate))

    # --- Private ---

    def _muster_waehlen(self, basis_muster: str, profil: StreckenProfil) -> str:
        """Bestimmt das Ausfuehrungsmuster basierend auf dem Profil."""
        if profil.etappen > 10:
            return "schwarm"
        elif profil.braucht_spezialisten and profil.etappen > 2:
            return "team"
        elif profil.ist_pipeline:
            return "kolonne"
        return basis_muster

    def _erkunden(self, gang: Gang, gas: float) -> tuple[Gang, float, bool]:
        """Epsilon-Greedy: Zufaellige Alternative testen."""
        dimension = random.choice(["gang", "gas"])

        if dimension == "gang":
            alle = self.getriebe.alle_gaenge()
            alternativen = [g for g in alle if g.name != gang.name]
            if alternativen:
                gang = random.choice(alternativen)
        else:
            # Gas um +/- 0.2 variieren
            delta = random.uniform(-0.2, 0.2)
            gas = max(0.0, min(1.0, gas + delta))

        return gang, gas, True

    def _grund_bauen(self, profil: StreckenProfil, gang: Gang, erkundung: bool) -> str:
        parts = [f"strecke={profil.typ.value}"]
        parts.append(f"tempo={profil.tempo.value}")
        parts.append(f"schwierigkeit={profil.schwierigkeit:.2f}")
        parts.append(f"gang={gang.name}")
        if erkundung:
            parts.append("ERKUNDUNG")
        return " | ".join(parts)

    def _load_strecken(self) -> dict:
        path = self.config_dir / "strecken.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        return {"strecken": {}, "standard": {
            "gang": "claude-sonnet", "gas": 0.5, "muster": "einzelfahrt",
        }}
