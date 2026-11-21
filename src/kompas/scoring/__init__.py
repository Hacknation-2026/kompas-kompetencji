"""Scoring: indicator->competency suggestion strategies and legal outcome policies."""

from kompas.scoring.aggregation import (
    IndicatorAggregationStrategy,
    MeanNearestStrategy,
    MedianStrategy,
    aggregation_registry,
)
from kompas.scoring.policies import (
    EvaluationContext,
    FirstEvaluationPolicy,
    OutcomePolicy,
    PeriodicEvaluationPolicy,
    policy_registry,
)
from kompas.scoring.scales import RatingScales, load_scales

__all__ = [
    "EvaluationContext",
    "FirstEvaluationPolicy",
    "IndicatorAggregationStrategy",
    "MeanNearestStrategy",
    "MedianStrategy",
    "OutcomePolicy",
    "PeriodicEvaluationPolicy",
    "RatingScales",
    "aggregation_registry",
    "load_scales",
    "policy_registry",
]
