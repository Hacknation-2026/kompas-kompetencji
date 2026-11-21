"""Deadline scanning and reminder dispatch for HR monitoring."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from kompas.domain.enums import DeadlineKind, EvaluationStatus
from kompas.domain.evaluation import Evaluation
from kompas.domain.people import User
from kompas.notifications.notifier import Notification, Notifier
from kompas.persistence.repository import Repository


class ReminderItem(BaseModel):
    evaluation_id: str
    employee_id: str
    evaluator_id: str
    step_id: str
    label: str
    due_date: date
    days_remaining: int
    overdue: bool


class ReminderService:
    """Finds upcoming/overdue deadlines and notifies supervisors."""

    def __init__(
        self,
        evaluations: Repository[Evaluation],
        users: Repository[User],
        notifier: Notifier,
        lead_days: int = 7,
    ) -> None:
        self.evaluations = evaluations
        self.users = users
        self.notifier = notifier
        self.lead_days = lead_days

    def upcoming(self, as_of: date | None = None, lead_days: int | None = None) -> list[ReminderItem]:
        today = as_of or date.today()
        window = self.lead_days if lead_days is None else lead_days
        items: list[ReminderItem] = []
        for ev in self.evaluations.list(lambda e: e.status is EvaluationStatus.IN_PROGRESS):
            for dl in ev.deadlines:
                if dl.kind is not DeadlineKind.DUE or dl.step_id in ev.completed_steps:
                    continue
                delta = (dl.due_date - today).days
                if delta <= window:
                    items.append(
                        ReminderItem(
                            evaluation_id=ev.id,
                            employee_id=ev.employee_id,
                            evaluator_id=ev.evaluator_id,
                            step_id=dl.step_id,
                            label=dl.label,
                            due_date=dl.due_date,
                            days_remaining=delta,
                            overdue=delta < 0,
                        )
                    )
        return sorted(items, key=lambda i: i.due_date)

    def dispatch(self, as_of: date | None = None, lead_days: int | None = None) -> list[Notification]:
        items = self.upcoming(as_of=as_of, lead_days=lead_days)
        dispatched: list[Notification] = []
        for item in items:
            user = self.users.find(item.evaluator_id)
            prefix = "ZALEGŁY TERMIN" if item.overdue else "Nadchodzący termin"
            note = Notification(
                recipient_id=item.evaluator_id,
                recipient_email=user.email if user else None,
                subject=f"[{prefix}] {item.label} (do {item.due_date.isoformat()})",
                body=(
                    f"Dotyczy oceny {item.evaluation_id} (pracownik {item.employee_id}).\n"
                    f"Etap: {item.label}\nTermin: {item.due_date.isoformat()} "
                    f"(pozostało dni: {item.days_remaining})."
                ),
                evaluation_id=item.evaluation_id,
            )
            self.notifier.send(note)
            dispatched.append(note)
        return dispatched

