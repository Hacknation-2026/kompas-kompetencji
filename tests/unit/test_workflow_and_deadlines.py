"""Unit tests for Polish civil-law deadline calculations and workflow engine."""

from __future__ import annotations

from datetime import date

import pytest

from kompas.core.config import Settings
from kompas.core.exceptions import WorkflowError
from kompas.domain.enums import EvaluationType, FormType
from kompas.domain.evaluation import Evaluation, EvaluationOutcome
from kompas.workflow.deadlines import add_months, compute_anchors, compute_deadlines, next_working_day
from kompas.workflow.definitions import load_paths
from kompas.workflow.engine import WorkflowEngine


def test_add_months_and_next_working_day_art_112_115_kc() -> None:
    assert add_months(date(2025, 1, 31), 1) == date(2025, 2, 28)
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)  # leap year
    assert add_months(date(2024, 3, 15), 24) == date(2026, 3, 15)
    # 2025-11-01 is Saturday (All Saints' Day), 2025-11-02 is Sunday -> Monday 2025-11-03
    assert next_working_day(date(2025, 11, 2)) == date(2025, 11, 3)
    # 2026-05-03 is Constitution Day (Sunday) -> Monday 2026-05-04
    assert next_working_day(date(2026, 5, 3)) == date(2026, 5, 4)


def test_first_evaluation_deadlines(settings: Settings) -> None:
    paths = load_paths(settings.paths.workflows_file)
    path = paths[EvaluationType.FIRST]
    anchors = compute_anchors(path, {"employment_start": date(2026, 3, 2)})
    assert anchors["contract_end"] == date(2027, 3, 2)
    deadlines = {d.step_id: d.due_date for d in compute_deadlines(path, anchors)}
    assert deadlines["initial_interview"] == date(2026, 3, 23)
    assert deadlines["report"] == date(2026, 11, 2)
    assert deadlines["decision"] == date(2027, 2, 2)


def test_workflow_engine_enforces_order_and_requirements(settings: Settings) -> None:
    engine = WorkflowEngine(load_paths(settings.paths.workflows_file))
    ev = Evaluation(
        id="ev-1",
        type=EvaluationType.FIRST,
        form=FormType.FIRST,
        employee_id="emp-1",
        evaluator_id="sup-1",
        current_step="initial_interview",
        mandatory_criteria=["rzetelnosc"],
    )
    with pytest.raises(WorkflowError):
        engine.complete_step(ev, "report", "sup-1")  # out of order

    engine.complete_step(ev, "initial_interview", "sup-1")
    assert ev.current_step == "report"

    # Unmet requirement: report_status_recorded
    with pytest.raises(WorkflowError):
        engine.complete_step(ev, "report", "sup-1")

    ev.report_submitted_on_time = True
    engine.complete_step(ev, "report", "sup-1")
    assert ev.current_step == "competency_assessment"

    # Negative outcome requires justification
    ev.outcome = EvaluationOutcome(average=3.0, positive=False)
    assert len(engine.unmet_requirements(ev, "decision")) >= 1
