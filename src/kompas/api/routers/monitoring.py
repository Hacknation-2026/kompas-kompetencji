"""HR & Administrator monitoring endpoints."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from kompas.api.deps import get_container, require_hr_or_admin
from kompas.container import AppContainer
from kompas.domain.people import User
from kompas.notifications.notifier import Notification
from kompas.services.monitoring import MonitoringDashboard

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
