"""Empirisches GPT-5.6-Routing auf Qualitätsgates und Pareto-Frontier.

Das Modul enthält bewusst keine vorgegebenen Intelligence-Scores. Es akzeptiert
nur extern gelabelte Eval-Beobachtungen mit bekannten Kosten. Retry- und
Fallback-Kosten gehören zur Kostenbasis des jeweiligen Eval-Laufs.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass(frozen=True)
class EvalObservation:
    task_class: str
    eval_case: str
    model_id: str
    effort: str
    quality_score: float
    passed: bool
    cost_usd: float
    latency_seconds: float
    retry_fallback_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.quality_score <= 1.0:
            raise ValueError("quality_score muss zwischen 0 und 1 liegen")
        if min(self.cost_usd, self.latency_seconds, self.retry_fallback_cost_usd) < 0:
            raise ValueError("Kosten und Latenz dürfen nicht negativ sein")


@dataclass(frozen=True)
class CandidateMetrics:
    model_id: str
    effort: str
    samples: int
    pass_rate: float
    pass_rate_lower_95: float
    avg_quality: float
    avg_latency_seconds: float
    total_cost_usd: float
    retry_fallback_cost_usd: float
    expected_cost_per_success_usd: float
    confidence: str
    eligible: bool
    on_pareto_frontier: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RoutingDecision:
    task_class: str
    model_id: str
    effort: str
    status: str
    reason: str
    sol_required_by_evidence: bool
    candidates: tuple[CandidateMetrics, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["candidates"] = [c.to_dict() for c in self.candidates]
        return data


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def _dominates(a: CandidateMetrics, b: CandidateMetrics) -> bool:
    no_worse = (
        a.expected_cost_per_success_usd <= b.expected_cost_per_success_usd
        and a.avg_latency_seconds <= b.avg_latency_seconds
        and a.avg_quality >= b.avg_quality
        and a.pass_rate >= b.pass_rate
    )
    strictly_better = (
        a.expected_cost_per_success_usd < b.expected_cost_per_success_usd
        or a.avg_latency_seconds < b.avg_latency_seconds
        or a.avg_quality > b.avg_quality
        or a.pass_rate > b.pass_rate
    )
    return no_worse and strictly_better


def _cold_start(task_class: str) -> tuple[str, str, str]:
    normalized = task_class.lower()
    if any(tag in normalized for tag in ("bulk", "volume", "latency", "klassifikation")):
        return "gpt-5.6-luna", "medium", "offizielle Rolle: kosten- und volumenorientiert"
    if any(tag in normalized for tag in ("safety", "critical", "frontier", "hard")):
        return "gpt-5.6-sol", "medium", "offizielle Rolle: komplexe professionelle Arbeit"
    return "gpt-5.6-terra", "medium", "offizielle Rolle: ausgewogenes Preis-Leistungs-Profil"


class EmpiricalRouter:
    """Wählt nach Gate zuerst, danach auf der nicht-dominierten Frontier."""

    def __init__(self, min_samples: int = 5):
        if min_samples < 1:
            raise ValueError("min_samples muss positiv sein")
        self.min_samples = min_samples

    def evaluate(
        self,
        task_class: str,
        observations: Iterable[EvalObservation],
        *,
        min_quality: float,
        min_pass_rate: float,
        max_latency_seconds: Optional[float] = None,
    ) -> RoutingDecision:
        rows = [row for row in observations if row.task_class == task_class]
        groups: dict[tuple[str, str], list[EvalObservation]] = {}
        for row in rows:
            groups.setdefault((row.model_id, row.effort), []).append(row)

        metrics = []
        for (model_id, effort), group in sorted(groups.items()):
            samples = len(group)
            successes = sum(1 for row in group if row.passed)
            total_cost = sum(row.cost_usd + row.retry_fallback_cost_usd for row in group)
            retry_cost = sum(row.retry_fallback_cost_usd for row in group)
            pass_rate = successes / samples
            avg_quality = sum(row.quality_score for row in group) / samples
            avg_latency = sum(row.latency_seconds for row in group) / samples
            expected_cost = total_cost / successes if successes else math.inf
            sufficiently_sampled = samples >= self.min_samples
            latency_ok = max_latency_seconds is None or avg_latency <= max_latency_seconds
            eligible = (
                sufficiently_sampled
                and pass_rate >= min_pass_rate
                and avg_quality >= min_quality
                and latency_ok
            )
            metrics.append(CandidateMetrics(
                model_id=model_id,
                effort=effort,
                samples=samples,
                pass_rate=pass_rate,
                pass_rate_lower_95=_wilson_lower(successes, samples),
                avg_quality=avg_quality,
                avg_latency_seconds=avg_latency,
                total_cost_usd=total_cost,
                retry_fallback_cost_usd=retry_cost,
                expected_cost_per_success_usd=expected_cost,
                confidence="measured" if sufficiently_sampled else "insufficient",
                eligible=eligible,
            ))

        eligible = [candidate for candidate in metrics if candidate.eligible]
        if not eligible:
            model_id, effort, role = _cold_start(task_class)
            return RoutingDecision(
                task_class=task_class,
                model_id=model_id,
                effort=effort,
                status="cold_start",
                reason=f"keine ausreichend belegte Route; {role}",
                sol_required_by_evidence=False,
                candidates=tuple(metrics),
            )

        frontier = [
            candidate for candidate in eligible
            if not any(_dominates(other, candidate) for other in eligible if other is not candidate)
        ]
        frontier_keys = {(candidate.model_id, candidate.effort) for candidate in frontier}
        metrics = [
            CandidateMetrics(
                **{
                    **candidate.to_dict(),
                    "on_pareto_frontier": (candidate.model_id, candidate.effort) in frontier_keys,
                }
            )
            for candidate in metrics
        ]
        selected = min(
            frontier,
            key=lambda candidate: (
                candidate.expected_cost_per_success_usd,
                candidate.avg_latency_seconds,
                -candidate.avg_quality,
                -candidate.pass_rate,
            ),
        )
        adequately_tested_non_sol = any(
            candidate.samples >= self.min_samples and candidate.model_id != "gpt-5.6-sol"
            for candidate in metrics
        )
        eligible_non_sol = any(
            candidate.eligible and candidate.model_id != "gpt-5.6-sol" for candidate in metrics
        )
        sol_required = (
            selected.model_id == "gpt-5.6-sol"
            and adequately_tested_non_sol
            and not eligible_non_sol
        )
        return RoutingDecision(
            task_class=task_class,
            model_id=selected.model_id,
            effort=selected.effort,
            status="measured",
            reason=(
                "Sol erfüllt als einzige ausreichend getestete Route das Qualitäts-/Latenz-Gate"
                if sol_required
                else "günstigste Route pro Erfolg auf der Pareto-Frontier nach Qualitätsgate"
            ),
            sol_required_by_evidence=sol_required,
            candidates=tuple(metrics),
        )


def load_eval_profiles(path: Optional[Path] = None) -> dict:
    """Lädt die versionierte Aufgabenklassen-Matrix ohne erfundene Messwerte."""
    path = path or Path(__file__).parent / "config" / "eval_profiles.json"
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)
