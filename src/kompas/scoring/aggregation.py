"""Strategies turning indicator choices into a *suggested* competency level.

The suggestion is purely advisory – the supervisor always picks the final level
(challenge requirement: "Rekomendacja ma pełnić funkcję pomocniczą").
"""

from __future__ import annotations

import statistics
from abc import ABC, abstractmethod
from collections.abc import Sequence

from kompas.core.exceptions import ConfigurationError
from kompas.core.registry import Registry
from kompas.domain.evaluation import LevelSuggestion


class IndicatorAggregationStrategy(ABC):
    """Template method: validates coverage, delegates the central-tendency measure."""

    name: str = "abstract"

    def __init__(self, tie_break: str = "lower", min_coverage: float = 0.5) -> None:
        if tie_break not in {"lower", "higher"}:
            raise ConfigurationError("tie_break must be 'lower' or 'higher'")
        if not 0.0 <= min_coverage <= 1.0:
            raise ConfigurationError("min_coverage must be within 0..1")
        self.tie_break = tie_break
        self.min_coverage = min_coverage

    def suggest(self, observed: Sequence[int | None], scale: Sequence[int]) -> LevelSuggestion:
        """Suggest a level on ``scale`` from indicator observations (``None`` = no basis)."""
        if not scale:
            raise ConfigurationError("Scale must not be empty")
        total = len(observed)
        values = [v for v in observed if v is not None]
        coverage = round(len(values) / total, 4) if total else 0.0
        if not values or coverage < self.min_coverage:
            return LevelSuggestion(
                points=None,
                mean=None,
                coverage=coverage,
                strategy=self.name,
                message=(
                    "Za mało ocenionych wskaźników, aby zasugerować poziom "
                    f"(ocenione {len(values)}/{total}, wymagane min. {self.min_coverage:.0%})."
                ),
            )
        center = self.central_value(values)
        points = self.snap(center, scale)
        return LevelSuggestion(
            points=points,
            mean=round(statistics.fmean(values), 2),
            coverage=coverage,
            strategy=self.name,
            message=(
                f"Sugerowany poziom na podstawie {len(values)}/{total} wskaźników. "
                "Decyzję o ocenie cząstkowej podejmuje przełożony."
            ),
        )

    @abstractmethod
    def central_value(self, values: Sequence[int]) -> float: ...

    def snap(self, value: float, scale: Sequence[int]) -> int:
        """Nearest scale point; ties resolved by ``tie_break``."""
        ordered = sorted(scale)
        best = min(abs(value - p) for p in ordered)
        candidates = [p for p in ordered if abs(abs(value - p) - best) < 1e-9]
        return candidates[0] if self.tie_break == "lower" else candidates[-1]


aggregation_registry: Registry[IndicatorAggregationStrategy] = Registry("indicator_aggregation")


@aggregation_registry.register("mean_nearest")
class MeanNearestStrategy(IndicatorAggregationStrategy):
    """Arithmetic mean snapped to the nearest level (mirrors the legal averaging logic)."""

    name = "mean_nearest"

    def central_value(self, values: Sequence[int]) -> float:
        return statistics.fmean(values)


@aggregation_registry.register("median")
class MedianStrategy(IndicatorAggregationStrategy):
    """Median – robust to a single outlying indicator."""

    name = "median"

    def central_value(self, values: Sequence[int]) -> float:
        return float(statistics.median(values))
