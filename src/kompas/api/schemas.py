"""Request/response Pydantic schemas for the HTTP API."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from kompas.domain.enums import AssistantMode, EvaluationType, FormType
from kompas.domain.evaluation import IndicatorAssessment


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str
    role: str


class CreateEvaluationRequest(BaseModel):
    employee_id: str
    evaluation_type: EvaluationType
    form_override: FormType | None = None
    period_anchor: date | None = None


class ConfigureCriteriaRequest(BaseModel):
    additional_criteria: list[str] = Field(default_factory=list)
    goals: list[str] | None = None
    confirm: bool = True


class AssessCriterionRequest(BaseModel):
    indicators: list[IndicatorAssessment]
    final_points: int | None = None
    justification: str | None = None


class FirstEvalFactsRequest(BaseModel):
    report_submitted_on_time: bool | None = None
    exam_passed: bool | None = None
    exam_applicable: bool = True


class ComputeOutcomeRequest(BaseModel):
    justification: str | None = None
    development_plan: str | None = None


class AdvanceStepRequest(BaseModel):
    step_id: str
    note: str | None = None


class JobAnalysisRequest(BaseModel):
    text: str = Field(min_length=10)
    manages_people: bool = False
    is_head_of_office: bool = False


class AssistantAskRequest(BaseModel):
    question: str = Field(min_length=2)
    mode: AssistantMode = AssistantMode.FORMAL
    evaluation_id: str | None = None

