"""End-to-end smoke test exercising both evaluation paths, AI assistant and PDF export."""

from __future__ import annotations

import sys

from kompas.container import build_container
from kompas.domain.enums import AssistantMode, DocumentFormat, EvaluationType
from kompas.domain.evaluation import IndicatorAssessment


def main() -> int:
    container = build_container()
    supervisor, _ = container.auth.authenticate("przelozony", "demo-password-1")
    hr_user, _ = container.auth.authenticate("kadry", "demo-password-hr")

    # 1. Periodic evaluation (Form C) for emp-2
    ev = container.evaluation_service.create("emp-2", EvaluationType.PERIODIC, supervisor)
    ev = container.evaluation_service.advance_step(ev.id, supervisor, "job_description_analysis")
    ev = container.evaluation_service.configure_criteria(
        ev.id,
        supervisor,
        additional_criteria=["myslenie_analityczne"],
        goals=["Opracowanie opinii dot. AI Act"],
    )
    ev = container.evaluation_service.advance_step(ev.id, supervisor, "criteria_setting")

    for cid in ev.criteria:
        comp = container.competency_model.get(cid)
        observations = [
            IndicatorAssessment(indicator_id=ind.id, observed_points=7) for ind in comp.indicators
        ]
        ev = container.evaluation_service.assess_criterion(
            ev.id, supervisor, cid, observations, final_points=7
        )

    ev = container.evaluation_service.advance_step(ev.id, supervisor, "competency_assessment")
    prep = container.assistant.prepare_conversation(ev, container.competency_model, container.scales)
    ev = container.evaluation_service.advance_step(ev.id, supervisor, "evaluation_interview")
    ev, outcome = container.evaluation_service.compute_outcome(
        ev.id, supervisor, development_plan="Szkolenie z AI Act oraz wymiana dobrych praktyk."
    )
    ev = container.evaluation_service.advance_step(ev.id, supervisor, "decision")
    ev = container.evaluation_service.advance_step(ev.id, supervisor, "acknowledgement")

    pdf_bytes, _, filename, archive_ref = container.evaluation_service.export_document(
        ev.id, supervisor, fmt=DocumentFormat.PDF, archive_copy=True
    )
    answer = container.assistant.ask(
        "Ile kryteriów dodatkowych można wybrać w ocenie okresowej?", mode=AssistantMode.FORMAL
    )
    dashboard = container.monitoring.dashboard()

    assert outcome.positive is True
    assert len(pdf_bytes) > 500
    assert answer.grounded is True
    assert prep.opening_questions
    assert hr_user.role.value == "hr"
    print(f"OK: {ev.id} ({ev.status.value}), PDF={filename} ({len(pdf_bytes)} B), archive={archive_ref}")
    print(f"OK: Assistant grounded={answer.grounded}, citations={len(answer.citations)}")
    print(f"OK: Monitoring total={dashboard.total_evaluations}, completed={dashboard.completed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
