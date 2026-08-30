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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from clutch.strecke import StreckenProfil, Tempo
from clutch.getriebe import Getriebe, Gang
from clutch.gas_bremse import GasBremse, GasStellung

# Agentische CLI-Motoren fuehren Tools mit Auto-Approve (--yolo) auf dem Host aus.
# Aus untrusted Quellen (Web/API) duerfen sie NICHT automatisch gewaehlt werden.
AGENTIC_CLI_PROVIDERS = {"claude-code", "kimi-cli", "kimi-code", "agy"}
OPENAI_EFFORTS = {"none", "low", "medium", "high", "xhigh", "max"}
ERLAUBTE_EFFORTS = OPENAI_EFFORTS | {"max-delegate"}


@dataclass
class FahrtConfig:
    """Komplette Konfiguration fuer eine Fahrt (Task-Ausfuehrung)."""
    gang: Gang                    # Welches Modell
    gas: GasStellung              # Reasoning-Level
    muster: str                   # "einzelfahrt" | "kolonne" | "team" | "schwarm" | "hybrid"
    ist_erkundung: bool = False   # Epsilon-Greedy Exploration?
    entscheidungs_grund: str = ""
    effort: Optional[str] = None  # Orthogonal zur Modellwahl; max nur als gezielter Delegate
    effective_effort: Optional[str] = None
    reasoning_mode: str = "standard"
    service_tier: str = "default"
    is_delegate: bool = False
    task_class: Optional[str] = None
    eval_case: Optional[str] = None
    alternativen: list[str] = field(default_factory=list)

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
            "requested_effort": self.effort,
            "effort": self.effort,
            "effective_effort": self.effective_effort,
            "reasoning_mode": self.reasoning_mode,
            "service_tier": self.service_tier,
            "is_delegate": self.is_delegate,
            "task_class": self.task_class,
            "eval_case": self.eval_case,
            "ist_erkundung": self.ist_erkundung,
            "grund": self.entscheidungs_grund,
            "alternativen": list(self.alternativen),
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
        self.config_dir = config_dir or Path(__file__).parent / "config"
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
        zweck: Optional[str] = None,
        vertrauenswuerdig: bool = True,
        effort_override: Optional[str] = None,
        ausschluss: Optional[list[str]] = None,
        praeferenz: Optional[list[str]] = None,
    ) -> FahrtConfig:
        """Bestimmt die optimale FahrtConfig fuer ein StreckenProfil.

        Das ist der Kupplungsvorgang: Gang waehlen + Gas einstellen.
        """
        gesperrte = list(gesperrte_modelle or [])
        ausgeschlossen = {
            self.getriebe.resolve_name(name)
            for name in (ausschluss or [])
            if isinstance(name, str) and name.strip()
        }
        blockiert = set(gesperrte) | ausgeschlossen

        # 1. Strecken-Lookup
        strecken_key = profil.typ.value
        if strecken_key in self._overrides:
            basis = self._overrides[strecken_key].copy()
        elif strecken_key in self._strecken_config.get("strecken", {}):
            basis = self._strecken_config["strecken"][strecken_key].copy()
        else:
            basis = self._standard.copy()

        # Effort ist eine eigene Routing-Dimension neben Modell/Gang und Gas.
        # "max-delegate" ist bewusst nur ein Delegationshinweis, kein
        # persistenter Session-Modus.
        effort = self._effort_waehlen(
            effort_override if effort_override is not None else basis.get("effort")
        )

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
        limit = max_gang if max_gang is not None else 5
        if budget_zone:
            # SSOT: identisch zu bordcomputer._budget_zonen / README (orange = G1-G2).
            zone_max = {"green": 5, "yellow": 3, "orange": 2, "red": 0}
            limit = min(limit, zone_max.get(budget_zone, 5))
            if gang and gang.gang > limit:
                guenstigere = self.getriebe.filter(max_gang=limit)
                if guenstigere:
                    gang = guenstigere[-1]  # Hoechster erlaubter Gang
                elif limit == 0:
                    gang = None  # Budget erschoepft

        # 6b. Zweck-Refinement: Gang nach Zweck/Modalitaet anpassen (staerken-Match).
        #     Bildbewusst: zweck="vision" erzwingt ein vision-faehiges Modell (M2).
        if gang and zweck and zweck != "general":
            passend = self._zweck_gang(zweck, gang, limit, list(blockiert))
            if passend and passend.name != gang.name:
                gang = passend

        # 7. Gesperrte Modelle
        if gang and gang.name in blockiert:
            alternativen = [
                g for g in self.getriebe.alle_gaenge()
                if g.name not in blockiert and g.gang <= (gang.gang if gang else 5)
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
        gang_vor_erkundung = gang  # Referenz fuer Mindest-Qualitaet (10a)
        if random.random() < self._erkundungsrate:
            gang, gas_wert, ist_erkundung = self._erkunden(gang, gas_wert)

        # 10a. Harte Schranken nach Exploration wiederherstellen.
        #      Exploration darf weder Budget-Zone (limit) noch Strecken-Mindestqualitaet
        #      (min_gang = Strecken-Basis-Gang) noch eilig-Gas-Kappung verletzen.
        if ist_erkundung:
            min_gang_erkundung = gang_vor_erkundung.gang if gang_vor_erkundung else 1
            if gang and gang.gang > limit:
                guenstigere = self.getriebe.filter(max_gang=limit)
                if guenstigere:
                    gang = guenstigere[-1]
            if gang and gang.gang < min_gang_erkundung:
                teurere = self.getriebe.filter(min_gang=min_gang_erkundung, max_gang=limit)
                if teurere:
                    gang = teurere[0]
            if profil.tempo == Tempo.EILIG:
                gas_wert = min(gas_wert, 0.5)
            if gang.name in blockiert:
                gang = gang_vor_erkundung
                ist_erkundung = False

        # 10b. Harte Modalitaet: vision darf NICHT durch Exploration gebrochen werden
        #      (ein Nicht-Vision-Modell kann das Bild nicht sehen). Wiederherstellen.
        zusatz_grund = ""
        if zweck == "vision" and gang and "vision" not in gang.staerken:
            passend = self._zweck_gang("vision", gang, limit, list(blockiert))
            if passend:
                gang = passend
                ist_erkundung = False
            else:
                # Kein vision-faehiges Modell verfuegbar -- transparent machen.
                zusatz_grund += " | WARN: kein vision-Modell verfuegbar"

        # 10c. Untrusted (Web/API): keine agentischen CLI-Motoren mit Auto-Approve.
        if not vertrauenswuerdig and gang and gang.provider in AGENTIC_CLI_PROVIDERS:
            sicher = [g for g in self.getriebe.filter(max_gang=limit)
                      if g.provider not in AGENTIC_CLI_PROVIDERS and g.name not in blockiert]
            if sicher:
                gang = sicher[-1]
                ist_erkundung = False
                zusatz_grund += " | untrusted: agentische CLI ausgeschlossen"

        # 10d. Aufruf- und Nutzerpraeferenzen wirken nach allen harten Gates.
        # Explizite Aufrufpraeferenzen stehen vor dem update-festen Overlay.
        kandidaten = self._routing_kandidaten(
            gang,
            limit,
            blockiert,
            zweck=zweck,
            vertrauenswuerdig=vertrauenswuerdig,
        )
        if not kandidaten:
            raise RuntimeError("kein verfuegbarer Gang nach Ausschluss- und Verfuegbarkeitsfiltern")
        if gang.name not in {kandidat.name for kandidat in kandidaten}:
            gang = min(kandidaten, key=lambda kandidat: (abs(kandidat.gang - gang.gang), -kandidat.gang))
            ist_erkundung = False
        tokens = [*(praeferenz or []), *self.getriebe.preferred_models, *self.getriebe.preferred_providers]
        bevorzugt = self._bevorzugter_gang(tokens, kandidaten, gang)
        if bevorzugt is not None and bevorzugt.name != gang.name:
            gang = bevorzugt
            ist_erkundung = False
            zusatz_grund += f" | praeferenz={bevorzugt.name}"

        if ausgeschlossen:
            zusatz_grund += " | ausschluss=" + ",".join(sorted(ausgeschlossen))

        alternativen = [
            kandidat.name
            for kandidat in self._rangiere_alternativen(kandidaten, gang, zweck)
            if kandidat.name != gang.name
        ][:2]

        # Gas-Stellung berechnen
        gas_stellung = self.pedal.stellung(gas_wert)

        grund = self._grund_bauen(profil, gang, ist_erkundung) + zusatz_grund

        return FahrtConfig(
            gang=gang,
            gas=gas_stellung,
            muster=muster,
            ist_erkundung=ist_erkundung,
            entscheidungs_grund=grund,
            effort=effort,
            alternativen=alternativen,
        )

    def override(self, strecken_typ: str, config: dict) -> None:
        """Setzt eine manuelle Override-Konfiguration fuer einen Streckentyp."""
        self._overrides[strecken_typ] = config

    def set_erkundungsrate(self, rate: float) -> None:
        self._erkundungsrate = max(0.0, min(1.0, rate))

    # --- Private ---

    @staticmethod
    def _effort_waehlen(effort: Optional[str]) -> Optional[str]:
        """Validiert den optionalen Effort-Hinweis.

        Die sechs OpenAI-Werte werden unverändert transportiert.
        ``max-delegate`` bleibt ein Orchestrierungshinweis und darf erst im
        tatsächlich als Delegate markierten Aufruf zu API-``max`` werden.
        """
        if effort is None:
            return None
        if not isinstance(effort, str):
            raise ValueError("effort muss ein String oder null sein")
        normalisiert = effort.strip().lower()
        if normalisiert not in ERLAUBTE_EFFORTS:
            erlaubt = ", ".join(sorted(ERLAUBTE_EFFORTS))
            raise ValueError(f"ungueltiger effort '{effort}'; erlaubt: {erlaubt}")
        return normalisiert

    def _zweck_gang(self, zweck: str, aktuell: Gang, limit: int,
                    gesperrte: list[str]) -> Optional[Gang]:
        """Waehlt einen Gang dessen staerken den Zweck abdecken.

        Kandidaten: zweck in staerken, nicht gesperrt, gang <= limit. Wenn der
        aktuelle Gang bereits passt, bleibt er. Sonst der Kandidat mit der
        kleinsten Stufendifferenz (Tie-Break: hoehere Stufe = mehr Qualitaet).
        Gibt None zurueck, wenn kein passender Gang existiert (Aufrufer behaelt
        den aktuellen Gang -- z.B. wenn kein vision-Modell verfuegbar ist).
        """
        if zweck in aktuell.staerken:
            return aktuell
        kandidaten = [
            g for g in self.getriebe.filter(staerke=zweck, max_gang=limit)
            if g.name not in gesperrte
        ]
        if not kandidaten:
            return None
        return min(kandidaten, key=lambda g: (abs(g.gang - aktuell.gang), -g.gang))

    def _muster_waehlen(self, basis_muster: str, profil: StreckenProfil) -> str:
        """Bestimmt das Ausfuehrungsmuster basierend auf dem Profil."""
        if profil.etappen > 10:
            return "schwarm"
        elif profil.braucht_spezialisten and profil.etappen > 2:
            return "team"
        elif profil.ist_pipeline:
            return "kolonne"
        return basis_muster

    def _routing_kandidaten(
        self,
        aktuell: Gang,
        limit: int,
        blockiert: set[str],
        *,
        zweck: Optional[str],
        vertrauenswuerdig: bool,
    ) -> list[Gang]:
        kandidaten = [
            gang for gang in self.getriebe.filter(max_gang=limit)
            if gang.name not in blockiert
            and (vertrauenswuerdig or gang.provider not in AGENTIC_CLI_PROVIDERS)
        ]
        if zweck == "vision":
            vision_kandidaten = [gang for gang in kandidaten if "vision" in gang.staerken]
            if vision_kandidaten:
                kandidaten = vision_kandidaten
        aktuell_erlaubt = (
            aktuell.name not in blockiert
            and aktuell.gang <= limit
            and (vertrauenswuerdig or aktuell.provider not in AGENTIC_CLI_PROVIDERS)
        )
        if aktuell not in kandidaten and aktuell_erlaubt:
            kandidaten.append(aktuell)
        return kandidaten

    def _bevorzugter_gang(
        self,
        tokens: list[str],
        kandidaten: list[Gang],
        aktuell: Gang,
    ) -> Optional[Gang]:
        erlaubt = {gang.name: gang for gang in kandidaten}
        for token in tokens:
            if not isinstance(token, str) or not token.strip():
                continue
            _, matches = self.getriebe.passende_praeferenz(token.strip())
            passend = [gang for gang in matches if gang.name in erlaubt]
            if passend:
                return min(passend, key=lambda gang: (abs(gang.gang - aktuell.gang), -gang.gang))
        return None

    def _rangiere_alternativen(
        self,
        kandidaten: list[Gang],
        aktuell: Gang,
        zweck: Optional[str],
    ) -> list[Gang]:
        reihenfolge = {gang.name: index for index, gang in enumerate(self.getriebe.alle_gaenge())}
        return sorted(
            kandidaten,
            key=lambda gang: (
                0 if gang.name == aktuell.name else 1,
                0 if not zweck or zweck == "general" or zweck in gang.staerken else 1,
                abs(gang.gang - aktuell.gang),
                reihenfolge.get(gang.name, 10_000),
            ),
        )

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
