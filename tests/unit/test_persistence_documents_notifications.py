"""Unit tests for persistence, documents, reminders and job-description analysis."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from kompas.container import AppContainer
from kompas.core.exceptions import NotFoundError, ValidationError
from kompas.domain.enums import DocumentFormat, EvaluationType, FormType
from kompas.domain.evaluation import EvaluationOutcome, IndicatorAssessment
from kompas.domain.people import Employee
from kompas.persistence.repository import InMemoryRepository, JsonFileRepository


def test_in_memory_and_json_file_repositories(tmp_path: Path) -> None:
    emp = Employee(
        id="e-tmp",
        first_name="A",
        last_name="B",
        org_unit="BDG",
        position="Specjalista",
        supervisor_id="sup-1",
        employment_start=date(2025, 1, 1),
    )
    mem = InMemoryRepository(Employee, "employees")
    mem.add(emp)
    assert mem.get("e-tmp").first_name == "A"
    with pytest.raises(ValidationError):
        mem.add(emp)

    repo = JsonFileRepository(Employee, "employees", tmp_path)
    repo.upsert(emp)
    emp.first_name = "Zmienione"
    repo.upsert(emp)

    reloaded = JsonFileRepository(Employee, "employees", tmp_path)
    assert reloaded.get("e-tmp").first_name == "Zmienione"
    reloaded.delete("e-tmp")
    with pytest.raises(NotFoundError):
        reloaded.get("e-tmp")


def test_job_analysis_detects_manager_and_recommends_criteria(container: AppContainer) -> None:
    res = container.job_analysis.analyze(
        "Naczelnik wydziału kieruje pracą 8 podległych pracowników, analizuje ryzyko i sytuacje kryzysowe."
    )
    assert res.recommended_form is FormType.B
    assert any(
        item["competency_id"] == "radzenie_sobie_w_kryzysie" for item in res.recommended_additional_criteria
    )


def test_documents_and_reminders(container: AppContainer) -> None:
    supervisor, _ = container.auth.authenticate("przelozony", "demo-password-1")
    ev = container.evaluation_service.create("emp-1", EvaluationType.FIRST, supervisor)
    ev = container.evaluation_service.record_first_eval_facts(
        ev.id, supervisor, report_submitted_on_time=True, exam_passed=True
    )
    for cid in ev.criteria:
        comp = container.competency_model.get(cid)
        ev = container.evaluation_service.assess_criterion(
            ev.id,
            supervisor,
            cid,
            [IndicatorAssessment(indicator_id=i.id, observed_points=5) for i in comp.indicators],
            final_points=5,
        )
    ev, outcome = container.evaluation_service.compute_outcome(
        ev.id, supervisor, justification="Poprawna praca"
    )
    assert isinstance(outcome, EvaluationOutcome) and outcome.positive is True

    html_bytes, mime_h, _, _ = container.evaluation_service.export_document(
        ev.id, supervisor, fmt=DocumentFormat.HTML
    )
    assert mime_h.startswith("text/html") and b"Jan Kowalski" in html_bytes

    pdf_bytes, mime_p, _, ref = container.evaluation_service.export_document(
        ev.id, supervisor, fmt=DocumentFormat.PDF, archive_copy=True
    )
    assert mime_p == "application/pdf" and pdf_bytes.startswith(b"%PDF")
    assert ref and Path(ref).is_file()

    # Reminders around the initial interview deadline
    due = ev.deadlines[0].due_date
    sent = container.monitoring.send_reminders(as_of=due - timedelta(days=2), lead_days=7)
    assert len(sent) >= 1
