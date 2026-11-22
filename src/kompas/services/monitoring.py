"""HR / Administrator monitoring dashboard and reminder trigger."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from pydantic import BaseModel, Field

from kompas.domain.enums import EvaluationStatus
from kompas.domain.evaluation import Evaluation
from kompas.notifications.notifier import Notification
from kompas.notifications.reminders import ReminderItem, ReminderService
from kompas.persistence.repository import Repository


class AuditEvent(BaseModel):
    """Immutable audit-trail entry exported for HR / Admin compliance."""

    evaluation_id: str
    employee_id: str
    evaluator_id: str
    event_type: str
    timestamp: datetime
    actor: str
    details: str


class AnonymizationReport(BaseModel):
    """Result of GDPR retention / anonymization run."""

    anonymized_count: int
    evaluation_ids: list[str] = Field(default_factory=list)


class MonitoringDashboard(BaseModel):
    total_evaluations: int
    in_progress: int
    completed: int
    overdue_count: int
    upcoming_deadlines: list[ReminderItem]


class MonitoringService:
    """Provides HR/Admin visibility over evaluation progress and deadlines."""

    def __init__(self, evaluations: Repository[Evaluation], reminders: ReminderService) -> None:
        self.evaluations = evaluations
        self.reminders = reminders

    def dashboard(self, as_of: date | None = None, lead_days: int | None = None) -> MonitoringDashboard:
        all_evals = self.evaluations.list()
        upcoming = self.reminders.upcoming(as_of=as_of, lead_days=lead_days)
        return MonitoringDashboard(
            total_evaluations=len(all_evals),
            in_progress=sum(1 for e in all_evals if e.status is EvaluationStatus.IN_PROGRESS),
            completed=sum(1 for e in all_evals if e.status is EvaluationStatus.COMPLETED),
            overdue_count=sum(1 for item in upcoming if item.overdue),
            upcoming_deadlines=upcoming,
        )

    def send_reminders(self, as_of: date | None = None, lead_days: int | None = None) -> list[Notification]:
        return self.reminders.dispatch(as_of=as_of, lead_days=lead_days)

    def export_audit_log(self) -> list[AuditEvent]:
        """Export chronological audit trail across all evaluations."""
        events: list[AuditEvent] = []
        for ev in self.evaluations.list():
            events.append(
                AuditEvent(
                    evaluation_id=ev.id,
                    employee_id=ev.employee_id,
                    evaluator_id=ev.evaluator_id,
                    event_type="evaluation_created",
                    timestamp=ev.created_at,
                    actor=ev.evaluator_id,
                    details=f"type={ev.type.value}, form={ev.form.value}",
                )
            )
            for step in ev.history:
                events.append(
                    AuditEvent(
                        evaluation_id=ev.id,
                        employee_id=ev.employee_id,
                        evaluator_id=ev.evaluator_id,
                        event_type="step_completed",
                        timestamp=step.completed_at,
                        actor=step.completed_by,
                        details=f"step={step.step_id}" + (f", note={step.note}" if step.note else ""),
                    )
                )
            for ext in ev.deadline_extensions:
                events.append(
                    AuditEvent(
                        evaluation_id=ev.id,
                        employee_id=ev.employee_id,
                        evaluator_id=ev.evaluator_id,
                        event_type="deadline_extended",
                        timestamp=ext.notified_at,
                        actor=ev.evaluator_id,
                        details=(
                            f"step={ext.step_id}, "
                            f"{ext.previous_due_date}->{ext.new_due_date}: {ext.reason}"
                        ),
                    )
                )
            if ev.outcome is not None:
                events.append(
                    AuditEvent(
                        evaluation_id=ev.id,
                        employee_id=ev.employee_id,
                        evaluator_id=ev.evaluator_id,
                        event_type="outcome_computed",
                        timestamp=ev.outcome.computed_at,
                        actor=ev.evaluator_id,
                        details=f"positive={ev.outcome.positive}, average={ev.outcome.average}",
                    )
                )
        return sorted(events, key=lambda item: item.timestamp)

    def anonymize_completed(
        self, older_than_days: int = 365, as_of: date | None = None
    ) -> AnonymizationReport:
        """Scrub narrative free-text fields on completed evaluations past the retention window."""
        ref = as_of or datetime.now(UTC).date()
        cutoff = datetime(ref.year, ref.month, ref.day, tzinfo=UTC) - timedelta(days=older_than_days)
        anonymized_ids: list[str] = []
        for ev in self.evaluations.list():
            if ev.status is not EvaluationStatus.COMPLETED:
                continue
            updated = ev.updated_at if ev.updated_at.tzinfo else ev.updated_at.replace(tzinfo=UTC)
            if updated > cutoff:
                continue
            ev.justification = "[ZANONIMIZOWANO]" if ev.justification else None
            ev.development_plan = "[ZANONIMIZOWANO]" if ev.development_plan else None
            ev.report_details = None
            ev.rank_promotion_motion = None
            for assess in ev.assessments.values():
                assess.justification = None
                for ind in assess.indicators:
                    ind.evidence = None
            ev.touch()
            self.evaluations.update(ev)
            anonymized_ids.append(ev.id)
        return AnonymizationReport(anonymized_count=len(anonymized_ids), evaluation_ids=anonymized_ids)
