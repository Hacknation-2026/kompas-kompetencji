"""Maps an :class:`Evaluation` + employee + competency model into a flat document view."""

from __future__ import annotations

from pydantic import BaseModel, Field

from kompas.competency.criteria import FormDefinition
from kompas.domain.competency import CompetencyModel
from kompas.domain.evaluation import Evaluation
from kompas.domain.people import Employee, User
from kompas.scoring.scales import RatingScales


class CriterionRow(BaseModel):
    name: str
    kind: str  # "Obowiązkowe" | "Dodatkowe"
    suggested_points: int | None = None
    final_points: int | None = None
    final_label: str = "-"
    justification: str | None = None


class EvaluationDocumentData(BaseModel):
    evaluation_id: str
    office_name: str
    form_title: str
    legal_basis: str
    employee_name: str
    employee_position: str
    employee_org_unit: str
    evaluator_name: str
    evaluator_position: str
    status: str
    criteria_rows: list[CriterionRow] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    exam_status: str | None = None
    report_status: str | None = None
    average: float | None = None
    overall_label: str | None = None
    positive: bool | None = None
    justification: str | None = None
    development_plan: str | None = None
    deadlines: list[tuple[str, str]] = Field(default_factory=list)


def build_document_data(
    evaluation: Evaluation,
    employee: Employee,
    evaluator: User | None,
    form_def: FormDefinition,
    model: CompetencyModel,
    scales: RatingScales,
    office_name: str,
) -> EvaluationDocumentData:
    mandatory_set = set(evaluation.mandatory_criteria)
    rows: list[CriterionRow] = []
    for cid in evaluation.criteria:
        comp = model.get(cid)
        assess = evaluation.assessments.get(cid)
        final_pts = assess.final_points if assess else None
        suggested_pts = assess.suggestion.points if assess and assess.suggestion else None
        rows.append(
            CriterionRow(
                name=comp.name,
                kind="Obowiązkowe" if cid in mandatory_set else "Dodatkowe",
                suggested_points=suggested_pts,
                final_points=final_pts,
                final_label=scales.label(final_pts) if final_pts is not None else "-",
                justification=assess.justification if assess else None,
            )
        )

    exam_status: str | None = None
    if evaluation.exam_status_recorded:
        if evaluation.exam_passed is None:
            exam_status = "Nie dotyczy"
        else:
            exam_status = "Zaliczony" if evaluation.exam_passed else "Niezaliczony"

    report_status: str | None = None
    if evaluation.report_submitted_on_time is not None:
        report_status = "W terminie" if evaluation.report_submitted_on_time else "Po terminie / brak"

    return EvaluationDocumentData(
        evaluation_id=evaluation.id,
        office_name=office_name,
        form_title=form_def.title,
        legal_basis=form_def.legal_basis,
        employee_name=employee.full_name,
        employee_position=employee.position,
        employee_org_unit=employee.org_unit,
        evaluator_name=evaluator.full_name if evaluator else evaluation.evaluator_id,
        evaluator_position=(evaluator.position or "-") if evaluator else "-",
        status=evaluation.status.value,
        criteria_rows=rows,
        goals=list(evaluation.goals),
        exam_status=exam_status,
        report_status=report_status,
        average=evaluation.outcome.average if evaluation.outcome else None,
        overall_label=evaluation.outcome.overall_label if evaluation.outcome else None,
        positive=evaluation.outcome.positive if evaluation.outcome else None,
        justification=evaluation.justification,
        development_plan=evaluation.development_plan,
        deadlines=[(d.label, d.due_date.isoformat()) for d in evaluation.deadlines],
    )
