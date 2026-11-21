"""HR / Administrator monitoring dashboard and reminder trigger."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from kompas.domain.enums import EvaluationStatus
from kompas.domain.evaluation import Evaluation
from kompas.notifications.notifier import Notification
from kompas.notifications.reminders import ReminderItem, ReminderService
from kompas.persistence.repository import Repository


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
