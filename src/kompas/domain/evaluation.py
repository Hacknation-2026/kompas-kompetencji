"""Evaluation aggregate – the central entity of both evaluation paths."""

from __future__ import annotations

from datetime import UTC, date, datetime

from pydantic import BaseModel, Field

from kompas.domain.enums import DeadlineKind, EvaluationStatus, EvaluationType, FormType


def utcnow() -> datetime:
    return datetime.now(UTC)


class IndicatorAssessment(BaseModel):
    """Supervisor's choice of the behaviour that best matches observations.

    ``observed_points`` is ``None`` when there was no opportunity to observe the behaviour
    ("brak podstaw do oceny" – guidance from the competency model).
    """

    indicator_id: str
    observed_points: int | None = None
    evidence: str | None = Field(default=None, description="Sytuacja – działanie – rezultat")


class LevelSuggestion(BaseModel):
    """System recommendation – advisory only."""

    points: int | None
    mean: float | None
    coverage: float = Field(description="Share of indicators assessed (0..1)")
    strategy: str
    message: str


class CriterionAssessment(BaseModel):
    """Assessment of one criterion (competency) on the sheet."""

    competency_id: str
    indicators: list[IndicatorAssessment] = Field(default_factory=list)
    suggestion: LevelSuggestion | None = None
    final_points: int | None = Field(default=None, description="Decision of the supervisor")
    justification: str | None = None
    decided_at: datetime | None = None


class EvaluationOutcome(BaseModel):
    """Result computed by the legal scoring policy."""

    average: float
    overall_points: int | None = None
    overall_label: str | None = None
    positive: bool
    reasons: list[str] = Field(default_factory=list)
    computed_at: datetime = Field(default_factory=utcnow)


class Deadline(BaseModel):
    """Deadline attached to a workflow step."""

    step_id: str
    label: str
    due_date: date
    kind: DeadlineKind = DeadlineKind.DUE
    legal_basis: str | None = None


class StepEvent(BaseModel):
    """Audit trail entry."""

    step_id: str
    completed_at: datetime = Field(default_factory=utcnow)
    completed_by: str
    note: str | None = None


class ReportDetails(BaseModel):
    """Sprawozdanie ocenianego – Załącznik nr 3 rozporządzenia z 23.07.2015 r."""

    tasks_performed: str
    problems_and_solutions: str = ""
    new_skills_and_knowledge: str = ""
    improvement_proposals: str = ""
    period_months: int | None = Field(default=None, ge=1, le=24)


class RankPromotionMotion(BaseModel):
    """Część III arkusza B/C – wniosek o kolejny stopień służbowy (art. 89 ust. 1)."""

    requested_rank: str
    rationale: str


class DeadlineExtension(BaseModel):
    """Zmiana terminu oceny / złożenia sprawozdania (§ 5 rozp. 2015 / art. 81 ust. 8)."""

    step_id: str
    previous_due_date: date
    new_due_date: date
    reason: str
    notified_at: datetime = Field(default_factory=utcnow)


class Evaluation(BaseModel):
    """Evaluation aggregate root."""

    id: str
    type: EvaluationType
    form: FormType
    employee_id: str
    evaluator_id: str
    status: EvaluationStatus = EvaluationStatus.IN_PROGRESS
    current_step: str
    completed_steps: list[str] = Field(default_factory=list)
    anchors: dict[str, date] = Field(default_factory=dict)
    deadlines: list[Deadline] = Field(default_factory=list)
    is_post_negative_reevaluation: bool = False
    mandatory_criteria: list[str] = Field(default_factory=list)
    additional_criteria: list[str] = Field(default_factory=list)
    criteria_confirmed: bool = False
    goals: list[str] = Field(default_factory=list)
    assessments: dict[str, CriterionAssessment] = Field(default_factory=dict)
    # first-evaluation specifics (§ 10 rozporządzenia z 2015 r.)
    exam_passed: bool | None = None  # None = not applicable
    exam_status_recorded: bool = False
    report_submitted_on_time: bool | None = None
    report_details: ReportDetails | None = None
    outcome: EvaluationOutcome | None = None
    justification: str | None = None
    development_plan: str | None = None  # wnioski do IPRZ / rozwoju zawodowego
    rank_promotion_motion: RankPromotionMotion | None = None
    deadline_extensions: list[DeadlineExtension] = Field(default_factory=list)
    history: list[StepEvent] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def criteria(self) -> list[str]:
        """Mandatory followed by additional criteria (sheet order)."""
        return [*self.mandatory_criteria, *self.additional_criteria]

    def final_points(self) -> dict[str, int]:
        """Decided partial scores (criterion -> points)."""
        return {
            cid: a.final_points
            for cid, a in self.assessments.items()
            if cid in self.criteria and a.final_points is not None
        }

    def touch(self) -> None:
        self.updated_at = utcnow()
