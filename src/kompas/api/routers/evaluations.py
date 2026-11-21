"""Evaluation lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from kompas.api.deps import get_container, get_current_user
from kompas.api.schemas import (
    AdvanceStepRequest,
    AssessCriterionRequest,
    ComputeOutcomeRequest,
    ConfigureCriteriaRequest,
    CreateEvaluationRequest,
    ExtendDeadlineRequest,
    FirstEvalFactsRequest,
    RankPromotionRequest,
)
from kompas.container import AppContainer
from kompas.domain.enums import DocumentFormat
from kompas.domain.evaluation import Evaluation, EvaluationOutcome
from kompas.domain.people import Employee, User

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


@router.get("/employees", response_model=list[Employee])
def list_employees(
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> list[Employee]:
    if user.role.value in ("hr", "admin"):
        return container.employees.list()
    return container.employees.list(lambda e: e.supervisor_id == user.id)


@router.get("", response_model=list[Evaluation])
def list_evaluations(
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> list[Evaluation]:
    return container.evaluation_service.list_for_user(user)


@router.post("", response_model=Evaluation, status_code=201)
def create_evaluation(
    body: CreateEvaluationRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.create(
        employee_id=body.employee_id,
        evaluation_type=body.evaluation_type,
        user=user,
        form_override=body.form_override,
        period_anchor=body.period_anchor,
        is_post_negative_reevaluation=body.is_post_negative_reevaluation,
    )


@router.get("/{evaluation_id}", response_model=Evaluation)
def get_evaluation(
    evaluation_id: str,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.get(evaluation_id, user)


@router.get("/{evaluation_id}/progress")
def get_progress(
    evaluation_id: str,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    ev = container.evaluation_service.get(evaluation_id, user)
    return {
        "evaluation_id": ev.id,
        "status": ev.status.value,
        "current_step": ev.current_step,
        "unmet_requirements": container.workflow.unmet_requirements(ev),
        "steps": container.workflow.progress(ev),
    }


@router.put("/{evaluation_id}/criteria", response_model=Evaluation)
def configure_criteria(
    evaluation_id: str,
    body: ConfigureCriteriaRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.configure_criteria(
        evaluation_id=evaluation_id,
        user=user,
        additional_criteria=body.additional_criteria,
        goals=body.goals,
        confirm=body.confirm,
    )


@router.put("/{evaluation_id}/criteria/{competency_id}/assessment", response_model=Evaluation)
def assess_criterion(
    evaluation_id: str,
    competency_id: str,
    body: AssessCriterionRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.assess_criterion(
        evaluation_id=evaluation_id,
        user=user,
        competency_id=competency_id,
        indicators=body.indicators,
        final_points=body.final_points,
        justification=body.justification,
    )


@router.put("/{evaluation_id}/first-eval-facts", response_model=Evaluation)
def record_first_eval_facts(
    evaluation_id: str,
    body: FirstEvalFactsRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.record_first_eval_facts(
        evaluation_id=evaluation_id,
        user=user,
        report_submitted_on_time=body.report_submitted_on_time,
        exam_passed=body.exam_passed,
        exam_applicable=body.exam_applicable,
        report_details=body.report_details,
    )


@router.put("/{evaluation_id}/rank-promotion", response_model=Evaluation)
def set_rank_promotion(
    evaluation_id: str,
    body: RankPromotionRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.set_rank_promotion_motion(
        evaluation_id=evaluation_id,
        user=user,
        requested_rank=body.requested_rank,
        rationale=body.rationale,
    )


@router.post("/{evaluation_id}/deadlines/extend", response_model=Evaluation)
def extend_deadline(
    evaluation_id: str,
    body: ExtendDeadlineRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.extend_deadline(
        evaluation_id=evaluation_id,
        user=user,
        step_id=body.step_id,
        new_due_date=body.new_due_date,
        reason=body.reason,
    )


@router.post("/{evaluation_id}/outcome", response_model=EvaluationOutcome)
def compute_outcome(
    evaluation_id: str,
    body: ComputeOutcomeRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> EvaluationOutcome:
    _, outcome = container.evaluation_service.compute_outcome(
        evaluation_id=evaluation_id,
        user=user,
        justification=body.justification,
        development_plan=body.development_plan,
    )
    return outcome


@router.post("/{evaluation_id}/steps/complete", response_model=Evaluation)
def complete_step(
    evaluation_id: str,
    body: AdvanceStepRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Evaluation:
    return container.evaluation_service.advance_step(
        evaluation_id=evaluation_id,
        user=user,
        step_id=body.step_id,
        note=body.note,
    )


@router.get("/{evaluation_id}/document")
def export_document(
    evaluation_id: str,
    fmt: DocumentFormat = Query(default=DocumentFormat.PDF),
    archive: bool = Query(default=False),
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Response:
    content, media_type, filename, archive_ref = container.evaluation_service.export_document(
        evaluation_id=evaluation_id,
        user=user,
        fmt=fmt,
        archive_copy=archive,
    )
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if archive_ref:
        headers["X-Archive-Ref"] = archive_ref
    return Response(content=content, media_type=media_type, headers=headers)
