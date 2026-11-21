"""Unit tests for Phase 2: OSP upload, ReportDetails, RankPromotionMotion and deadline extensions."""

from __future__ import annotations

import io
from datetime import timedelta

import docx
import pytest
from fpdf import FPDF

from kompas.container import AppContainer
from kompas.core.exceptions import ValidationError
from kompas.domain.enums import DocumentFormat, EvaluationType, FormType
from kompas.domain.evaluation import IndicatorAssessment, ReportDetails


def _make_docx(paragraphs: list[str]) -> bytes:
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def _make_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, text)
    return bytes(pdf.output())


def test_osp_file_extraction_for_docx_pdf_and_invalid(container: AppContainer) -> None:
    docx_bytes = _make_docx(
        [
            "Naczelnik wydziału pełni funkcję bezpośredniego przełożonego, zarządzając zespołem.",
            "Organizuje konferencje i spotkania międzynarodowe.",
        ]
    )
    res_docx = container.job_analysis.analyze_file("osp_naczelnik.docx", docx_bytes)
    assert res_docx.recommended_form is FormType.B

    pdf_bytes = _make_pdf("Analizuje przepisy prawa oraz zarzadzania kryzysowego.")
    res_pdf = container.job_analysis.analyze_file("osp_radca.pdf", pdf_bytes)
    assert res_pdf.recommended_form is FormType.C

    with pytest.raises(ValidationError, match="Nieobsługiwany format"):
        container.job_analysis.analyze_file("osp.xlsx", b"123")


def test_first_eval_report_details_validation_and_export(container: AppContainer) -> None:
    supervisor, _ = container.auth.authenticate("przelozony", "demo-password-1")
    ev = container.evaluation_service.create("emp-1", EvaluationType.FIRST, supervisor)

    with pytest.raises(ValidationError, match="7 miesięcy"):
        container.evaluation_service.record_first_eval_facts(
            ev.id,
            supervisor,
            report_submitted_on_time=True,
            exam_passed=True,
            report_details=ReportDetails(tasks_performed="Zadania", period_months=5),
        )

    ev = container.evaluation_service.record_first_eval_facts(
        ev.id,
        supervisor,
        report_submitted_on_time=True,
        exam_passed=True,
        report_details=ReportDetails(
            tasks_performed="Analiza wniosków i przygotowanie projektów pism.",
            problems_and_solutions="Niejednoznaczne przepisy – konsultacja z radcą.",
            new_skills_and_knowledge="Obsługa EZD RP.",
            period_months=8,
        ),
    )
    html, _, _, _ = container.evaluation_service.export_document(ev.id, supervisor, fmt=DocumentFormat.HTML)
    assert b"Sprawozdanie ocenianego" in html
    assert b"Obs\xc5\x82uga EZD RP" in html


def test_rank_promotion_motion_and_deadline_extension(container: AppContainer) -> None:
    supervisor, _ = container.auth.authenticate("przelozony", "demo-password-1")
    # emp-2 is a civil servant (is_civil_servant=True)
    ev = container.evaluation_service.create("emp-2", EvaluationType.PERIODIC, supervisor)

    # Cannot request promotion before positive outcome
    with pytest.raises(ValidationError, match="pozytywnej oceny"):
        container.evaluation_service.set_rank_promotion_motion(
            ev.id, supervisor, "III", "Wyróżniające wyniki."
        )

    for cid in ev.criteria:
        comp = container.competency_model.get(cid)
        ev = container.evaluation_service.assess_criterion(
            ev.id,
            supervisor,
            cid,
            [IndicatorAssessment(indicator_id=i.id, observed_points=7) for i in comp.indicators],
            final_points=7,
        )
    ev, _ = container.evaluation_service.compute_outcome(ev.id, supervisor, development_plan="IPRZ")
    ev = container.evaluation_service.set_rank_promotion_motion(
        ev.id, supervisor, requested_rank="III stopień służbowy", rationale="Wysoka jakość analiz AI."
    )

    new_due = ev.deadlines[0].due_date + timedelta(days=30)
    ev = container.evaluation_service.extend_deadline(
        ev.id,
        supervisor,
        step_id=ev.deadlines[0].step_id,
        new_due_date=new_due,
        reason="Usprawiedliwiona nieobecność",
    )
    assert ev.deadlines[0].due_date == new_due
    assert len(ev.deadline_extensions) == 1

    html, _, _, _ = container.evaluation_service.export_document(ev.id, supervisor, fmt=DocumentFormat.HTML)
    assert b"III stopie" in html
    assert b"sprzeciw do dyrektora generalnego" in html
