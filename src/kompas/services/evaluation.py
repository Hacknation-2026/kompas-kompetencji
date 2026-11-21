"""Application service orchestrating the evaluation lifecycle."""

from __future__ import annotations

import uuid
from datetime import date

from kompas.competency.criteria import CriteriaPolicy, FormSelector
from kompas.core.exceptions import ValidationError
from kompas.documents.builder import build_document_data
from kompas.documents.renderer import DocumentRenderer
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import DocumentFormat, EvaluationType, FormType
from kompas.domain.evaluation import (
    CriterionAssessment,
    DeadlineExtension,
    Evaluation,
    EvaluationOutcome,
    IndicatorAssessment,
    RankPromotionMotion,
    ReportDetails,
    utcnow,
)
from kompas.domain.people import Employee, User
from kompas.integrations.ezd import ArchiveGateway
from kompas.persistence.repository import Repository
from kompas.scoring.aggregation import IndicatorAggregationStrategy
from kompas.scoring.policies import EvaluationContext, OutcomePolicy
from kompas.scoring.scales import RatingScales
from kompas.security.rbac import require_evaluation_access
from kompas.workflow.deadlines import compute_anchors, compute_deadlines
from kompas.workflow.engine import WorkflowEngine


class EvaluationService:
    """Use-cases for creating, assessing, computing and exporting evaluations."""

    def __init__(
        self,
        evaluations: Repository[Evaluation],
        employees: Repository[Employee],
        users: Repository[User],
        model: CompetencyModel,
        criteria_policy: CriteriaPolicy,
        form_selector: FormSelector,
        scales: RatingScales,
        aggregator: IndicatorAggregationStrategy,
        policies: dict[EvaluationType, OutcomePolicy],
        workflow: WorkflowEngine,
        renderers: dict[DocumentFormat, DocumentRenderer],
        archive: ArchiveGateway,
        office_name: str,
    ) -> None:
        self.evaluations = evaluations
        self.employees = employees
        self.users = users
        self.model = model
        self.criteria_policy = criteria_policy
        self.form_selector = form_selector
        self.scales = scales
        self.aggregator = aggregator
        self.policies = policies
        self.workflow = workflow
        self.renderers = renderers
        self.archive = archive
        self.office_name = office_name

    def list_for_user(self, user: User) -> list[Evaluation]:
        if user.role.value in ("hr", "admin"):
            return self.evaluations.list()
        return self.evaluations.list(lambda e: e.evaluator_id == user.id)

    def get(self, evaluation_id: str, user: User) -> Evaluation:
        ev = self.evaluations.get(evaluation_id)
        require_evaluation_access(user, ev)
        return ev

    def create(
        self,
        employee_id: str,
        evaluation_type: EvaluationType,
        user: User,
        form_override: FormType | None = None,
        period_anchor: date | None = None,
    ) -> Evaluation:
        employee = self.employees.get(employee_id)
        if user.role.value == "supervisor" and employee.supervisor_id != user.id:
            raise ValidationError("Możesz rozpocząć ocenę wyłącznie podległego pracownika")

        form = form_override or self.form_selector.select(evaluation_type, employee)
        form_def = self.criteria_policy.form(form)
        if form_def.evaluation_type is not evaluation_type:
            raise ValidationError(f"Arkusz {form.value} nie odpowiada ścieżce {evaluation_type.value}")

        anchors: dict[str, date] = {"employment_start": employee.employment_start}
        if employee.contract_end:
            anchors["contract_end"] = employee.contract_end
        if evaluation_type is EvaluationType.PERIODIC:
            anchors["period_anchor"] = (
                period_anchor
                or employee.last_evaluation_date
                or employee.indefinite_employment_date
                or employee.employment_start
            )

        path = self.workflow.path(evaluation_type)
        anchors = compute_anchors(path, anchors)
        deadlines = compute_deadlines(path, anchors)

        evaluation = Evaluation(
            id=f"eval-{uuid.uuid4().hex[:10]}",
            type=evaluation_type,
            form=form,
            employee_id=employee.id,
            evaluator_id=employee.supervisor_id,
            current_step=self.workflow.first_step(evaluation_type).id,
            anchors=anchors,
            deadlines=deadlines,
            mandatory_criteria=self.criteria_policy.mandatory(form),
            exam_status_recorded=not employee.preparatory_exam_required,
            exam_passed=None if not employee.preparatory_exam_required else False,
        )
        return self.evaluations.add(evaluation)

    def configure_criteria(
        self,
        evaluation_id: str,
        user: User,
        additional_criteria: list[str],
        goals: list[str] | None = None,
        confirm: bool = True,
    ) -> Evaluation:
        ev = self.get(evaluation_id, user)
        validated = self.criteria_policy.validate_additional(ev.form, additional_criteria)
        ev.additional_criteria = validated
        if goals is not None:
            ev.goals = [g.strip() for g in goals if g.strip()]
        ev.criteria_confirmed = confirm
        ev.touch()
        return self.evaluations.update(ev)

    def assess_criterion(
        self,
        evaluation_id: str,
        user: User,
        competency_id: str,
        indicators: list[IndicatorAssessment],
        final_points: int | None = None,
        justification: str | None = None,
    ) -> Evaluation:
        ev = self.get(evaluation_id, user)
        if competency_id not in ev.criteria:
            raise ValidationError(f"Kryterium '{competency_id}' nie należy do tego arkusza")

        comp = self.model.get(competency_id)
        known_ind_ids = {ind.id for ind in comp.indicators}
        by_id: dict[str, IndicatorAssessment] = {}
        for item in indicators:
            if item.indicator_id not in known_ind_ids:
                raise ValidationError(f"Nieznany wskaźnik '{item.indicator_id}' dla '{competency_id}'")
            if item.observed_points is not None:
                comp.indicator(item.indicator_id).describe(item.observed_points)
            by_id[item.indicator_id] = item

        ordered_observations = [
            by_id[ind.id].observed_points if ind.id in by_id else None for ind in comp.indicators
        ]
        form_def = self.criteria_policy.form(ev.form)
        scale = self.scales.scale(form_def.scale)
        suggestion = self.aggregator.suggest(ordered_observations, scale)

        if final_points is not None and final_points not in scale:
            raise ValidationError(f"Ocena cząstkowa {final_points} poza dopuszczalną skalą {scale}")

        ev.assessments[competency_id] = CriterionAssessment(
            competency_id=competency_id,
            indicators=list(by_id.values()),
            suggestion=suggestion,
            final_points=final_points,
            justification=justification,
            decided_at=utcnow() if final_points is not None else None,
        )
        ev.touch()
        return self.evaluations.update(ev)

    def record_first_eval_facts(
        self,
        evaluation_id: str,
        user: User,
        report_submitted_on_time: bool | None = None,
        exam_passed: bool | None = None,
        exam_applicable: bool = True,
        report_details: ReportDetails | None = None,
    ) -> Evaluation:
        ev = self.get(evaluation_id, user)
        if ev.type is not EvaluationType.FIRST:
            raise ValidationError("Egzamin i sprawozdanie dotyczą wyłącznie pierwszej oceny")
        if report_details is not None:
            if report_details.period_months is not None and report_details.period_months < 7:
                raise ValidationError(
                    "Sprawozdanie musi obejmować okres nie krótszy niż 7 miesięcy (§ 6 ust. 1)"
                )
            ev.report_details = report_details
        if report_submitted_on_time is not None:
            ev.report_submitted_on_time = report_submitted_on_time
        if not exam_applicable:
            ev.exam_passed = None
            ev.exam_status_recorded = True
        elif exam_passed is not None:
            ev.exam_passed = exam_passed
            ev.exam_status_recorded = True
        ev.touch()
        return self.evaluations.update(ev)

    def set_rank_promotion_motion(
        self,
        evaluation_id: str,
        user: User,
        requested_rank: str,
        rationale: str,
    ) -> Evaluation:
        """Część III arkusza B/C – wniosek o kolejny stopień służbowy (art. 89 ust. 1)."""
        ev = self.get(evaluation_id, user)
        if ev.type is not EvaluationType.PERIODIC:
            raise ValidationError("Wniosek o stopień służbowy dotyczy wyłącznie oceny okresowej")
        employee = self.employees.get(ev.employee_id)
        if not employee.is_civil_servant:
            raise ValidationError(
                "Wniosek o stopień służbowy przysługuje wyłącznie urzędnikowi służby cywilnej"
            )
        if ev.outcome is None or not ev.outcome.positive:
            raise ValidationError("Wniosek o stopień służbowy wymaga pozytywnej oceny okresowej")
        ev.rank_promotion_motion = RankPromotionMotion(
            requested_rank=requested_rank.strip(),
            rationale=rationale.strip(),
        )
        ev.touch()
        return self.evaluations.update(ev)

    def extend_deadline(
        self,
        evaluation_id: str,
        user: User,
        step_id: str,
        new_due_date: date,
        reason: str,
    ) -> Evaluation:
        """Extend a step deadline (§ 5 rozp. 2015 / art. 81 ust. 8 ustawy)."""
        ev = self.get(evaluation_id, user)
        for dl in ev.deadlines:
            if dl.step_id == step_id:
                prev = dl.due_date
                dl.due_date = new_due_date
                ev.deadline_extensions.append(
                    DeadlineExtension(
                        step_id=step_id,
                        previous_due_date=prev,
                        new_due_date=new_due_date,
                        reason=reason.strip(),
                    )
                )
                ev.touch()
                return self.evaluations.update(ev)
        raise ValidationError(f"Brak zdefiniowanego terminu dla etapu '{step_id}'")

    def compute_outcome(
        self,
        evaluation_id: str,
        user: User,
        justification: str | None = None,
        development_plan: str | None = None,
    ) -> tuple[Evaluation, EvaluationOutcome]:
        ev = self.get(evaluation_id, user)
        missing = [cid for cid in ev.criteria if cid not in ev.final_points()]
        if missing:
            raise ValidationError(
                "Przyznaj ostateczną ocenę cząstkową dla wszystkich kryteriów przed obliczeniem wyniku",
                details={"missing_criteria": missing},
            )
        policy = self.policies[ev.type]
        ctx = EvaluationContext(
            exam_passed=ev.exam_passed,
            report_submitted_on_time=ev.report_submitted_on_time,
        )
        outcome = policy.compute(ev.final_points(), ctx)
        ev.outcome = outcome
        if justification is not None:
            ev.justification = justification
        if development_plan is not None:
            ev.development_plan = development_plan
        ev.touch()
        return self.evaluations.update(ev), outcome

    def advance_step(
        self, evaluation_id: str, user: User, step_id: str, note: str | None = None
    ) -> Evaluation:
        ev = self.get(evaluation_id, user)
        self.workflow.complete_step(ev, step_id=step_id, user_id=user.id, note=note)
        return self.evaluations.update(ev)

    def export_document(
        self,
        evaluation_id: str,
        user: User,
        fmt: DocumentFormat = DocumentFormat.PDF,
        archive_copy: bool = False,
    ) -> tuple[bytes, str, str, str | None]:
        ev = self.get(evaluation_id, user)
        employee = self.employees.get(ev.employee_id)
        evaluator = self.users.find(ev.evaluator_id)
        form_def = self.criteria_policy.form(ev.form)
        data = build_document_data(
            ev, employee, evaluator, form_def, self.model, self.scales, self.office_name
        )
        renderer = self.renderers[fmt]
        content = renderer.render(data)
        filename = f"{ev.id}_{ev.form.value}.{renderer.extension}"
        archive_ref = self.archive.store(ev.id, filename, content) if archive_copy else None
        return content, renderer.media_type, filename, archive_ref
