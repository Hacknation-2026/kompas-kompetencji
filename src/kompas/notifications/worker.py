"""Scheduled background job for dispatching evaluation deadline reminders."""

from __future__ import annotations

from datetime import date

from kompas.container import AppContainer, build_container
from kompas.core.logging import get_logger
from kompas.notifications.notifier import Notification

logger = get_logger("notifications.worker")


def run_reminder_job(
    container: AppContainer | None = None,
    as_of: date | None = None,
    lead_days: int | None = None,
) -> list[Notification]:
    """Execute one reminder dispatch cycle (intended for cron / k8s CronJob)."""
    resolved = container or build_container()
    sent = resolved.monitoring.send_reminders(as_of=as_of, lead_days=lead_days)
    logger.info("Reminder job finished: dispatched %d notification(s)", len(sent))
    return sent
