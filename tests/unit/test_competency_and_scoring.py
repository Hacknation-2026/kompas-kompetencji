"""Unit tests for competency model, form selection, criteria validation and scoring."""

from __future__ import annotations

from datetime import date

import pytest

from kompas.competency.criteria import CriteriaPolicy, FormSelector, load_forms
from kompas.competency.loader import YamlCompetencyModelLoader
from kompas.core.config import Settings
from kompas.core.exceptions import NotFoundError, ValidationError
from kompas.domain.enums import EvaluationType, FormType
from kompas.domain.people import Employee
from kompas.scoring.aggregation import MeanNearestStrategy, MedianStrategy
from kompas.scoring.policies import EvaluationContext, FirstEvaluationPolicy, PeriodicEvaluationPolicy
from kompas.scoring.scales import load_scales


def _emp(**kwargs: object) -> Employee:
    defaults: dict[str, object] = {
        "id": "e1",
        "first_name": "Jan",
        "last_name": "Test",
        "org_unit": "DSI",
        "position": "Specjalista",
        "supervisor_id": "sup-1",
        "employment_start": date(2025, 1, 1),
    }
    defaults.update(kwargs)
    return Employee(**defaults)  # type: ignore[arg-type]


def test_loaded_competency_model_has_14_competencies_49_indicators(settings: Settings) -> None:
    model = YamlCompetencyModelLoader(settings.paths.competency_model_file).load()
    assert len(model.competencies) == 14
    assert model.indicator_count == 49
    assert model.get("rzetelnosc").indicator("rzetelnosc.1").describe(5)
    with pytest.raises(NotFoundError):
        model.get("nonexistent")


def test_form_selector_and_criteria_policy(settings: Settings) -> None:
    model = YamlCompetencyModelLoader(settings.paths.competency_model_file).load()
    policy = CriteriaPolicy(load_forms(settings.paths.forms_file), model)
    selector = FormSelector()

    assert selector.select(EvaluationType.FIRST, _emp()) is FormType.FIRST
    assert selector.select(EvaluationType.PERIODIC, _emp(is_head_of_office=True)) is FormType.A
    assert selector.select(EvaluationType.PERIODIC, _emp(manages_people=True)) is FormType.B
    assert selector.select(EvaluationType.PERIODIC, _emp()) is FormType.C

    assert policy.validate_additional(FormType.C, ["kreatywnosc", "myslenie_analityczne"]) == [
        "kreatywnosc",
        "myslenie_analityczne",
    ]
    with pytest.raises(ValidationError):
        policy.validate_additional(FormType.C, ["kreatywnosc", "kreatywnosc"])
    with pytest.raises(ValidationError):
        policy.validate_additional(FormType.C, ["rzetelnosc"])  # already mandatory
    with pytest.raises(ValidationError):
        policy.validate_additional(
            FormType.C, ["kreatywnosc", "negocjowanie", "myslenie_analityczne", "wystapienia_publiczne"]
        )


def test_indicator_aggregation_strategies() -> None:
    mean_strat = MeanNearestStrategy(tie_break="lower", min_coverage=0.5)
    sug = mean_strat.suggest([5, 7, None, 7], [1, 3, 5, 7, 9])
    assert sug.points == 7
    assert sug.coverage == 0.75

    low_cov = mean_strat.suggest([5, None, None, None], [1, 3, 5, 7, 9])
    assert low_cov.points is None

    tie = mean_strat.suggest([5, 7], [1, 3, 5, 7, 9])
    assert tie.points == 5  # conservative tie_break="lower"

    med_strat = MedianStrategy(min_coverage=0.5)
    assert med_strat.suggest([1, 5, 9], [1, 3, 5, 7, 9]).points == 5


def test_periodic_evaluation_policy_legal_rules(settings: Settings) -> None:
    scales, policies = load_scales(settings.paths.scoring_file)
    policy = PeriodicEvaluationPolicy(scales=scales, **policies["periodic"]["params"])

    ok = policy.compute({"a": 5, "b": 5, "c": 7, "d": 5, "e": 5})
    assert ok.positive is True
    assert ok.overall_points == 5

    # Even with high average, a single partial == 1 forces negative (§ 11 ust. 1 pkt 4)
    neg_by_partial = policy.compute({"a": 9, "b": 9, "c": 9, "d": 9, "e": 1})
    assert neg_by_partial.positive is False

    neg_by_avg = policy.compute({"a": 3, "b": 3, "c": 5, "d": 3, "e": 3})
    assert neg_by_avg.positive is False
    assert neg_by_avg.overall_points == 3


def test_first_evaluation_policy_legal_rules(settings: Settings) -> None:
    scales, policies = load_scales(settings.paths.scoring_file)
    policy = FirstEvaluationPolicy(scales=scales, **policies["first"]["params"])

    pos = policy.compute(
        {"a": 5, "b": 5, "c": 5, "d": 3, "e": 7},
        EvaluationContext(exam_passed=True, report_submitted_on_time=True),
    )
    assert pos.positive is True
    assert pos.average == 5.0

    # Two partials == 3 -> negative (§ 10 ust. 1 pkt 3)
    two_threes = policy.compute(
        {"a": 3, "b": 3, "c": 7, "d": 7, "e": 7},
        EvaluationContext(exam_passed=True, report_submitted_on_time=True),
    )
    assert two_threes.positive is False

    # Failed exam -> negative (§ 10 ust. 1 pkt 1)
    failed_exam = policy.compute(
        {"a": 7, "b": 7, "c": 7, "d": 7, "e": 7},
        EvaluationContext(exam_passed=False, report_submitted_on_time=True),
    )
    assert failed_exam.positive is False
