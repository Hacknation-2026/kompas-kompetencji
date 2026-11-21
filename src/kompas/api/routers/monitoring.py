"""HR & Administrator monitoring endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from kompas.api.deps import get_container, require_hr_or_admin
from kompas.container import AppContainer
from kompas.domain.people import User
from kompas.notifications.notifier import Notification
from kompas.services.monitoring import (
    AnonymizationReport,
    AuditEvent,
    MonitoringDashboard,
)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/dashboard", response_model=MonitoringDashboard)
def dashboard(
    as_of: date | None = Query(default=None),
    lead_days: int | None = Query(default=None, ge=0, le=365),
    _user: User = Depends(require_hr_or_admin),
    container: AppContainer = Depends(get_container),
) -> MonitoringDashboard:
    return container.monitoring.dashboard(as_of=as_of, lead_days=lead_days)


@router.post("/reminders/send", response_model=list[Notification])
def send_reminders(
    as_of: date | None = Query(default=None),
    lead_days: int | None = Query(default=None, ge=0, le=365),
    _user: User = Depends(require_hr_or_admin),
    container: AppContainer = Depends(get_container),
) -> list[Notification]:
    return container.monitoring.send_reminders(as_of=as_of, lead_days=lead_days)


@router.get("/audit-log", response_model=list[AuditEvent])
def audit_log(
    _user: User = Depends(require_hr_or_admin),
    container: AppContainer = Depends(get_container),
) -> list[AuditEvent]:
    return container.monitoring.export_audit_log()


@router.post("/retention/anonymize", response_model=AnonymizationReport)
def anonymize_completed(
    older_than_days: int = Query(default=365, ge=0, le=3650),
    as_of: date | None = Query(default=None),
    _user: User = Depends(require_hr_or_admin),
    container: AppContainer = Depends(get_container),
) -> AnonymizationReport:
    return container.monitoring.anonymize_completed(older_than_days=older_than_days, as_of=as_of)
