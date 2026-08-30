"""Fahrer -- Der Orchestrator.

Der Fahrer sitzt am Steuer und koordiniert alles:
  1. Strecke analysieren (was ist der Task?)
  2. Kupplung betaetigen (welches Modell, welches Gas?)
  3. Losfahren (Task ausfuehren)
  4. Tacho ablesen (Metriken erfassen)
  5. Fahrtenbuch fuehren (Ergebnis speichern)
  6. Fahrschule besuchen (aus Ergebnissen lernen)

Der Fahrer selbst kann JEDES Modell sein -- nicht nur Claude Opus.
Er trifft die Entscheidungen, die Worker fuehren aus.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Optional

from clutch.strecke import StreckenAnalyse, StreckenProfil
from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung, FahrtConfig
from clutch.fahrtenbuch import Fahrtenbuch
from clutch.bordcomputer import Bordcomputer
from clutch.tankuhr import Tankuhr
from clutch.tacho import Tacho
from clutch.fahrschule import Fahrschule
from clutch.scorer import get_scorer
from clutch.pricing import UsageRecord, cost_for_gang
from clutch.user_overrides import clutch_home

logger = logging.getLogger("clutch")


@dataclass
class FahrtErgebnis:
    """Ergebnis einer abgeschlossenen Fahrt."""
    fahrt_id: str
    erfolg: bool
    output: Any = None
    config: Optional[FahrtConfig] = None
    latenz_sekunden: float = 0.0
    total_tokens: int = 0
    cost_usd: Optional[float] = None
    usage_status: str = "unknown"
    requested_effort: Optional[str] = None
    effective_effort: Optional[str] = None
    warnungen: list[str] = None

    def __post_init__(self):
        if self.warnungen is None:
            self.warnungen = []


class Fahrer:
    """Der Orchestrator -- sitzt am Steuer.

    Nutzung:
        # Einfach: Task beschreiben, Fahrer entscheidet alles
        fahrer = Fahrer()
        ergebnis = fahrer.fahren("Fix den Bug in auth.py", handler=mein_handler)

        # Fortgeschritten: Strecke vorab analysieren
        profil = fahrer.strecke_analysieren("Refaktoriere alles")
        config = fahrer.kuppeln(profil)
        ergebnis = fahrer.ausfuehren(config, handler=mein_handler)

        # Status
        print(fahrer.status())
    """

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
        overrides_path: Optional[Path] = None,
        availability_path: Optional[Path] = None,
        token_budget_path: Optional[Path] = None,
        sparmodus_path: Optional[Path] = None,
    ):
        self.base_dir = base_dir or Path(__file__).parent
        config_dir = self.base_dir / "config"

        # DB-Pfad: NICHT ins Repo/OneDrive schreiben. Default = User-Home.
        if db_path is None:
            db_path = clutch_home() / "clutch.db"
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Kern-Komponenten (Auto-Teile)
        self.analyse = StreckenAnalyse()
        self.getriebe = Getriebe(config_dir=config_dir, overrides_path=overrides_path)
        self.kupplungs_mechanik = Kupplung(self.getriebe, config_dir=config_dir)
        self.buch = Fahrtenbuch(db_path=db_path)
        self.bordcomputer = Bordcomputer(
            self.buch,
            config_dir=config_dir,
            availability_path=availability_path,
            token_budget_path=token_budget_path,
            sparmodus_path=sparmodus_path,
            model_provider={
                gang.name: gang.provider
                for gang in self.getriebe.alle_gaenge(einschliesslich_deaktiviert=True)
            },
        )
        self.tankuhr = Tankuhr(config_dir=config_dir, buch=self.buch)
        self.tacho = Tacho(self.buch)
        self.fahrschule = Fahrschule(self.buch, self.kupplungs_mechanik, config_dir=config_dir)
        self.scorer = get_scorer()

        # Fahrer-Config
        self._config = self._load_config(config_dir)
        self._bypass_feldwege = self._config.get("einfache_strecken_bypass", True)
        self._logge_alles = self._config.get("alle_entscheidungen_loggen", True)

        logger.info(f"Fahrer bereit. Getriebe: {self.getriebe}")

    def strecke_analysieren(self, beschreibung: str, kontext: Optional[dict] = None) -> StreckenProfil:
        """Analysiert die Strecke (den Task)."""
        return self.analyse.analysiere(beschreibung, kontext)

    def kuppeln(self, profil: StreckenProfil, zweck: Optional[str] = None,
                vertrauenswuerdig: bool = True,
                effort_override: Optional[str] = None,
                ausschluss: Optional[list[str]] = None,
                praeferenz: Optional[list[str]] = None) -> FahrtConfig:
        """Kuppelt: Waehlt Gang und Gas basierend auf Strecke + Systemzustand.

        zweck (coding/vision/research/...) steuert das Zweck-Routing (M2):
        Gaenge werden nach passenden staerken-Tags ausgewaehlt.
        vertrauenswuerdig=False (z.B. Web/API) schliesst agentische CLI-Motoren
        mit Auto-Approve aus.
        effort_override setzt optional high/xhigh/max-delegate fuer genau
        diesen Aufruf; max-delegate bleibt ein transparenter Delegationshinweis.
        """

        # Bordcomputer checken
        verbrauch_pct = self.tankuhr.verbrauch_pct()
        system_status = self.bordcomputer.pruefe(verbrauch_pct)

        config = self.kupplungs_mechanik.einlegen(
            profil,
            budget_zone=system_status.budget_zone,
            gesperrte_modelle=system_status.gesperrte_modelle,
            zweck=zweck,
            vertrauenswuerdig=vertrauenswuerdig,
            effort_override=effort_override,
            ausschluss=ausschluss,
            praeferenz=praeferenz,
        )

        # Gesperrtes Modell Fallback
        if config.gang.name in system_status.gesperrte_modelle:
            runter = self.getriebe.naechster_gang_runter(config.gang.name)
            if runter:
                config = replace(
                    config,
                    gang=runter,
                    entscheidungs_grund=config.entscheidungs_grund + " | fallback",
                )

        if self._logge_alles:
            logger.info(
                f"Kupplung: {profil.typ.value} -> "
                f"{config.gang.name} (G{config.gang.gang}) / "
                f"Gas {config.gas.wert:.0%} / {config.muster} "
                f"[{config.entscheidungs_grund}]"
            )

        return config

    def fahren(
        self,
        beschreibung: str,
        handler: Callable[[FahrtConfig, str], Any],
        kontext: Optional[dict] = None,
    ) -> FahrtErgebnis:
        """Komplette Fahrt: Analysieren -> Kuppeln -> Ausfuehren -> Lernen.

        Args:
            beschreibung: Natuerlichsprachliche Task-Beschreibung
            handler: Funktion die den Task ausfuehrt.
                     Signatur: handler(config: FahrtConfig, task: str) -> Any
            kontext: Zusaetzlicher Kontext
        """
        start = time.time()

        # 1. Strecke analysieren
        profil = self.strecke_analysieren(beschreibung, kontext)

        # 1b. Zweck/Modalitaet erkennen (M2) -- Bild-Anhang erzwingt vision
        hat_bild = bool(kontext and kontext.get("hat_bild"))
        zweck = self.scorer.erkenne_zweck(beschreibung, hat_bild=hat_bild)
        vertrauenswuerdig = bool(kontext.get("vertrauenswuerdig", True)) if kontext else True
        effort_override = kontext.get("effort") if kontext else None
        ausschluss = kontext.get("ausschluss") if kontext else None
        praeferenz = kontext.get("praeferenz") if kontext else None

        # 2. Kuppeln (zweck-bewusst)
        config = self.kuppeln(
            profil,
            zweck=zweck,
            vertrauenswuerdig=vertrauenswuerdig,
            effort_override=effort_override,
            ausschluss=ausschluss,
            praeferenz=praeferenz,
        )
        config.task_class = (
            str(kontext.get("task_class")) if kontext and kontext.get("task_class")
            else profil.typ.value
        )
        config.eval_case = str(kontext.get("eval_case")) if kontext and kontext.get("eval_case") else None
        config.reasoning_mode = str(kontext.get("reasoning_mode", "standard")) if kontext else "standard"
        config.service_tier = str(kontext.get("service_tier", "default")) if kontext else "default"
        config.is_delegate = bool(kontext.get("is_delegate", False)) if kontext else False
        if kontext and kontext.get("task_class") and kontext.get("empirical_routing", True):
            try:
                decision = self.fahrschule.empirisch_routen(config.task_class)
                gang = next(
                    (g for g in self.getriebe.alle_gaenge() if g.model_id == decision.model_id),
                    None,
                )
                if gang is not None:
                    task_fields = {
                        "task_class": config.task_class,
                        "eval_case": config.eval_case,
                        "reasoning_mode": config.reasoning_mode,
                        "service_tier": config.service_tier,
                        "is_delegate": config.is_delegate,
                    }
                    empirical_preferences = [*(praeferenz or []), gang.name]
                    routed = self.kuppeln(
                        profil,
                        zweck=zweck,
                        vertrauenswuerdig=vertrauenswuerdig,
                        effort_override=decision.effort,
                        ausschluss=ausschluss,
                        praeferenz=empirical_preferences,
                    )
                    config = replace(
                        routed,
                        **task_fields,
                        entscheidungs_grund=(
                            routed.entscheidungs_grund
                            + f" | empirical:{decision.status}:{decision.reason}"
                        ),
                    )
            except ValueError as error:
                logger.info(f"Kein Eval-Profil für {config.task_class}: {error}")

        # 3. Fahren + messen
        fahrt_id = self.tacho.start(profil.typ.value, config)

        fehlertext = None
        try:
            output = handler(config, beschreibung)
            erfolg = bool(getattr(output, "erfolg", True))
            fehlertext = getattr(output, "fehler", None)
        except Exception as e:
            output = None
            erfolg = False
            fehlertext = str(e)
            logger.error(f"Fahrt {fahrt_id} gescheitert: {e}")

        # 3b. Tokens + Kosten verbuchen (falls Handler ein MotorErgebnis lieferte)
        self._verbuchen(fahrt_id, config, output)

        # 4. Tacho stoppen
        eintrag = self.tacho.stop(fahrt_id, erfolg=erfolg)

        # 5. Bordcomputer informieren
        warnungen = []
        if eintrag:
            warnungen = self.bordcomputer.fahrt_auswerten(
                eintrag,
                fehlertext=fehlertext,
                output_text=getattr(output, "text", None),
            )

        return FahrtErgebnis(
            fahrt_id=fahrt_id,
            erfolg=erfolg,
            output=output,
            config=config,
            latenz_sekunden=time.time() - start,
            total_tokens=eintrag.total_tokens if eintrag else 0,
            cost_usd=eintrag.cost_usd if eintrag else None,
            usage_status=eintrag.usage_status if eintrag else "unknown",
            requested_effort=eintrag.requested_effort if eintrag else config.effort,
            effective_effort=eintrag.effective_effort if eintrag else config.effective_effort,
            warnungen=warnungen,
        )

    def ausfuehren(
        self,
        config: FahrtConfig,
        handler: Callable[[FahrtConfig], Any],
        strecken_typ: str = "unbekannt",
    ) -> FahrtErgebnis:
        """Fuehrt einen Task mit gegebener Config aus."""
        start = time.time()
        fahrt_id = self.tacho.start(strecken_typ, config)

        fehlertext = None
        try:
            output = handler(config)
            erfolg = bool(getattr(output, "erfolg", True))
            fehlertext = getattr(output, "fehler", None)
        except Exception as e:
            output = None
            erfolg = False
            fehlertext = str(e)
            logger.error(f"Fahrt {fahrt_id} gescheitert: {e}")

        self._verbuchen(fahrt_id, config, output)
        eintrag = self.tacho.stop(fahrt_id, erfolg=erfolg)
        warnungen = self.bordcomputer.fahrt_auswerten(
            eintrag,
            fehlertext=fehlertext,
            output_text=getattr(output, "text", None),
        ) if eintrag else []

        return FahrtErgebnis(
            fahrt_id=fahrt_id,
            erfolg=erfolg,
            output=output,
            config=config,
            latenz_sekunden=time.time() - start,
            total_tokens=eintrag.total_tokens if eintrag else 0,
            cost_usd=eintrag.cost_usd if eintrag else None,
            usage_status=eintrag.usage_status if eintrag else "unknown",
            requested_effort=eintrag.requested_effort if eintrag else config.effort,
            effective_effort=eintrag.effective_effort if eintrag else config.effective_effort,
            warnungen=warnungen,
        )

    def _verbuchen(self, fahrt_id: str, config: Optional[FahrtConfig], output: Any) -> None:
        """Uebernimmt Tokens/Kosten aus einem MotorErgebnis (Duck-Typing).

        Verdrahtet den Token-Fluss in Tacho (Metriken) und Tankuhr (Budget) --
        zuvor blieben beide auf Null (Fahrtenbuch/Fahrschule lernten auf Nulldaten).
        Handler die kein MotorErgebnis liefern, bleiben unberuehrt.
        """
        in_tok = getattr(output, "input_tokens", None)
        out_tok = getattr(output, "output_tokens", None)
        if in_tok is None and out_tok is None:
            return
        in_tok = int(in_tok or 0)
        out_tok = int(out_tok or 0)
        cached = int(getattr(output, "cached_input_tokens", 0) or 0)
        cache_write = int(getattr(output, "cache_write_tokens", 0) or 0)
        reasoning = int(getattr(output, "reasoning_tokens", 0) or 0)
        tool_fees = float(getattr(output, "tool_fees_usd", 0.0) or 0.0)
        usage_status = getattr(output, "usage_status", "unknown") or "unknown"
        cost_usd = getattr(output, "cost_usd", None)
        price_version = getattr(output, "price_version", None)
        service_tier = getattr(output, "service_tier", None) or config.service_tier
        effective_effort = getattr(output, "effective_effort", None) or config.effective_effort
        model_id = getattr(output, "model_id", None) or config.model_id

        if config and getattr(config, "gang", None):
            try:
                if cost_usd is None and usage_status != "unknown":
                    breakdown = cost_for_gang(
                        config.gang,
                        UsageRecord(
                            input_tokens=in_tok,
                            cached_input_tokens=cached,
                            cache_write_tokens=cache_write,
                            output_tokens=out_tok,
                            reasoning_tokens=reasoning,
                            tool_fees_usd=tool_fees,
                            service_tier=service_tier,
                            data_status=usage_status,
                        ),
                    )
                    cost_usd = breakdown.total_usd
                    price_version = breakdown.pricing_version
            except Exception as e:  # Budget-Buchung darf die Fahrt nie kippen
                logger.warning(f"Kostenberechnung fehlgeschlagen: {e}")
                cost_usd = None
                usage_status = "unknown"
        self.tacho.update(
            fahrt_id,
            total_tokens=in_tok + out_tok,
            thinking_tokens=reasoning,
            model_id=model_id,
            requested_effort=config.effort,
            effective_effort=effective_effort,
            mode=config.reasoning_mode,
            service_tier=service_tier,
            task_class=config.task_class,
            eval_case=config.eval_case,
            input_tokens=in_tok,
            cached_input_tokens=cached,
            cache_write_tokens=cache_write,
            output_tokens=out_tok,
            reasoning_tokens=reasoning,
            tool_fees_usd=tool_fees,
            usage_status=usage_status,
            price_version=price_version,
            cost_usd=cost_usd,
        )

    def trainieren(self) -> dict:
        """Fahrschule: Lernt aus bisherigen Fahrten."""
        return self.fahrschule.trainieren()

    def empirisch_routen(self, task_class: str) -> dict:
        """Gibt die gelabelte GPT-5.6-Evalentscheidung nachvollziehbar zurück."""
        return self.fahrschule.empirisch_routen(task_class).to_dict()

    def status(self) -> dict:
        """Aktueller System-Status (Armaturenbrett)."""
        system = self.bordcomputer.pruefe(self.tankuhr.verbrauch_pct())
        tank = self.tankuhr.stand()
        kpis = self.tacho.kpis()

        return {
            "bordcomputer": {
                "gesund": system.gesund,
                "warnungen": system.warnungen,
                "gesperrte_modelle": system.gesperrte_modelle,
                "verfuegbarkeit": system.verfuegbarkeit,
            },
            "tankuhr": {
                "zone": tank.zone,
                "kosten_heute_usd": tank.kosten_heute_usd,
                "verbrauch_pct": tank.tages_verbrauch_pct,
                "nachricht": tank.zone_nachricht,
                "unmetered_fahrten_heute": tank.unmetered_fahrten_heute,
            },
            "tacho": kpis,
            "getriebe": str(self.getriebe),
        }

    def feedback(
        self,
        fahrt_id: str,
        bewertung: str,
        notiz: str = "",
        quality_score: Optional[float] = None,
        passed: Optional[bool] = None,
    ) -> None:
        """User-Feedback zu einer Fahrt.

        bewertung: "gut" | "schlecht" | "overkill" | "zu_langsam"
        """
        logger.info(f"Feedback fuer {fahrt_id}: {bewertung} -- {notiz}")
        if quality_score is not None and passed is not None:
            self.buch.eval_label_setzen(fahrt_id, quality_score, passed)

    def _load_config(self, config_dir: Path) -> dict:
        path = config_dir / "kupplung.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f).get("fahrer", {})
        return {}
