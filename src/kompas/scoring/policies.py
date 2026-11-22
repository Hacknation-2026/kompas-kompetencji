"""Legal outcome policies for each evaluation type.

* :class:`PeriodicEvaluationPolicy` – § 11 rozporządzenia PRM z 4.04.2016 r.
* :class:`FirstEvaluationPolicy`    – § 7 i § 10 rozporządzenia PRM z 23.07.2015 r.

Numeric thresholds are injected from ``config/scoring.yaml``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from kompas.core.exceptions import ConfigurationError, ValidationError
from kompas.core.registry import Registry
from kompas.domain.evaluation import EvaluationOutcome
from kompas.scoring.scales import RatingScales


class EvaluationContext(BaseModel):
    """Facts beyond partial scores needed by some policies."""

    exam_passed: bool | None = None  # None = not applicable
    report_submitted_on_time: bool | None = None


class OutcomePolicy(ABC):
    """Computes the evaluation outcome from partial scores."""

    def __init__(self, scales: RatingScales, scale_name: str) -> None:
        self.scales = scales
        self.allowed = set(scales.scale(scale_name))

    def compute(
        self, partials: dict[str, int], context: EvaluationContext | None = None
    ) -> EvaluationOutcome:
        if not partials:
            raise ValidationError("At least one partial score is required to compute the outcome")
        invalid = {k: v for k, v in partials.items() if v not in self.allowed}
        if invalid:
            raise ValidationError(
                f"Partial scores outside allowed scale {sorted(self.allowed)}", details={"invalid": invalid}
            )
        return self._compute(partials, context or EvaluationContext())

    @abstractmethod
    def _compute(self, partials: dict[str, int], context: EvaluationContext) -> EvaluationOutcome: ...


policy_registry: Registry[OutcomePolicy] = Registry("outcome_policy")


@policy_registry.register("periodic_2016")
class PeriodicEvaluationPolicy(OutcomePolicy):
    def __init__(
        self,
        scales: RatingScales,
        overall_bands: list[dict[str, Any]],
        positive_min_overall_points: int = 5,
        negative_if_any_partial: int = 1,
        decimals: int = 2,
        scale_name: str = "periodic",
    ) -> None:
        super().__init__(scales, scale_name)
        if not overall_bands:
            raise ConfigurationError("overall_bands must not be empty")
        self.bands = sorted(
            ((float(b["up_to"]), int(b["points"])) for b in overall_bands), key=lambda x: x[0]
        )
        self.positive_min = positive_min_overall_points
        self.negative_partial = negative_if_any_partial
        self.decimals = decimals

    def overall_points(self, average: float) -> int:
        for upper, points in self.bands:
            if average <= upper + 1e-9:
                return points
        return self.bands[-1][1]

    def _compute(self, partials: dict[str, int], context: EvaluationContext) -> EvaluationOutcome:
        average = round(sum(partials.values()) / len(partials), self.decimals)
        overall = self.overall_points(average)
        reasons: list[str] = []
        positive = overall >= self.positive_min
        if not positive:
            lbl = self.scales.label(overall).lower()
            reasons.append(f"Ogólny poziom spełniania kryteriów: {lbl} (§ 11 ust. 1 pkt 4).")
        lowest = [cid for cid, p in partials.items() if p == self.negative_partial]
        if lowest:
            positive = False
            neg_lbl = self.scales.label(self.negative_partial).lower()
            reasons.append(f"Ocena cząstkowa „{neg_lbl}” dla: {', '.join(lowest)} (§ 11 ust. 1 pkt 4).")
        if positive:
            reasons.append("Spełnione warunki oceny pozytywnej (§ 11 ust. 1 pkt 3).")
        return EvaluationOutcome(
            average=average,
            overall_points=overall,
            overall_label=self.scales.label(overall),
            positive=positive,
            reasons=reasons,
        )


@policy_registry.register("first_2015")
class FirstEvaluationPolicy(OutcomePolicy):
    def __init__(
        self,
        scales: RatingScales,
        min_average: float = 5.0,
        lowest_partial: int = 3,
        max_lowest_partials: int = 1,
        decimals: int = 2,
        scale_name: str = "first",
    ) -> None:
        super().__init__(scales, scale_name)
        self.min_average = min_average
        self.lowest_partial = lowest_partial
        self.max_lowest = max_lowest_partials
        self.decimals = decimals

    def _compute(self, partials: dict[str, int], context: EvaluationContext) -> EvaluationOutcome:
        average = round(sum(partials.values()) / len(partials), self.decimals)
        reasons: list[str] = []
        positive = True
        if context.exam_passed is False:
            positive = False
            reasons.append("Niezaliczony egzamin ze służby przygotowawczej (§ 10 ust. 1 pkt 1).")
        if context.report_submitted_on_time is not True:
            positive = False
            reasons.append("Sprawozdanie nie zostało złożone w wyznaczonym terminie (§ 10 ust. 1 pkt 2).")
        lowest = [cid for cid, p in partials.items() if p == self.lowest_partial]
        if len(lowest) > self.max_lowest:
            positive = False
            reasons.append(
                f"Więcej niż {self.max_lowest} ocena cząstkowa w wysokości {self.lowest_partial} pkt: "
                f"{', '.join(lowest)} (§ 10 ust. 1 pkt 3)."
            )
        if average < self.min_average:
            positive = False
            reasons.append(
                f"Ocena łączna {average} pkt jest niższa niż {self.min_average} pkt (§ 10 ust. 1 pkt 4)."
            )
        if positive:
            reasons.append("Spełnione łącznie warunki pozytywnej pierwszej oceny (§ 10 ust. 1).")
        return EvaluationOutcome(average=average, positive=positive, reasons=reasons)
