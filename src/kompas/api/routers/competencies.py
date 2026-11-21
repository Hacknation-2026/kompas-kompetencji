"""Competency model, forms and job-description (OSP) analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from kompas.api.deps import get_container, get_current_user
from kompas.api.schemas import JobAnalysisRequest
from kompas.container import AppContainer
from kompas.domain.competency import Competency, CompetencyModel
from kompas.domain.enums import FormType
from kompas.domain.people import User
from kompas.services.job_analysis import JobAnalysisResult

router = APIRouter(prefix="/competencies", tags=["competencies"])


@router.get("/model", response_model=CompetencyModel)
def get_model(
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> CompetencyModel:
    return container.competency_model


@router.get("/forms")
def get_forms(
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    return {
        form.value: {
            "title": dfn.title,
            "evaluation_type": dfn.evaluation_type.value,
            "legal_basis": dfn.legal_basis,
            "scale": container.scales.describe(dfn.scale),
            "mandatory_criteria": dfn.mandatory_criteria,
            "allowed_additional_criteria": container.criteria_policy.allowed_additional(form),
            "max_additional_criteria": dfn.max_additional_criteria,
        }
        for form, dfn in container.criteria_policy.forms.items()
    }


@router.get("/{competency_id}", response_model=Competency)
def get_competency(
    competency_id: str,
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> Competency:
    return container.competency_model.get(competency_id)


@router.post("/analyze-job-description", response_model=JobAnalysisResult)
def analyze_job_description(
    body: JobAnalysisRequest,
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> JobAnalysisResult:
    return container.job_analysis.analyze(
        text=body.text,
        manages_people=body.manages_people,
        is_head_of_office=body.is_head_of_office,
    )


@router.post("/analyze-job-description/upload", response_model=JobAnalysisResult)
async def analyze_job_description_file(
    file: UploadFile = File(...),
    manages_people: bool | None = Form(default=None),
    is_head_of_office: bool = Form(default=False),
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> JobAnalysisResult:
    content = await file.read()
    return container.job_analysis.analyze_file(
        filename=file.filename or "osp.txt",
        content=content,
        manages_people=manages_people,
        is_head_of_office=is_head_of_office,
    )


@router.get("/forms/{form}/allowed-additional")
def allowed_additional(
    form: FormType,
    _user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> dict[str, object]:
    return {
        "form": form.value,
        "mandatory": container.criteria_policy.mandatory(form),
        "allowed_additional": container.criteria_policy.allowed_additional(form),
    }
