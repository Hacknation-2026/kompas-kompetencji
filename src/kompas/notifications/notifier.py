"""Pluggable notification channels."""

from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from email.message import EmailMessage

from pydantic import BaseModel, Field

from kompas.core.exceptions import ExternalServiceError
from kompas.core.logging import get_logger
from kompas.core.registry import Registry

log = get_logger(__name__)


class Notification(BaseModel):
    recipient_id: str
    recipient_email: str | None = None
    subject: str
    body: str
    evaluation_id: str | None = None
    sent_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Notifier(ABC):
    """Notification delivery contract."""

    @abstractmethod
    def send(self, notification: Notification) -> None: ...


notifier_registry: Registry[Notifier] = Registry("notifications")


@notifier_registry.register("memory")
class InMemoryNotifier(Notifier):
    """Collects sent notifications in memory (tests & offline demo)."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)


@notifier_registry.register("log")
class LogNotifier(Notifier):
    """Logs notifications via standard logger (dev environment)."""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def send(self, notification: Notification) -> None:
        self.sent.append(notification)
        log.info(
            "NOTIFICATION to=%s (%s) subject=%r eval=%s",
            notification.recipient_id,
            notification.recipient_email or "-",
            notification.subject,
            notification.evaluation_id or "-",
        )


@notifier_registry.register("smtp")
class SmtpNotifier(Notifier):
    """SMTP email sender for production environments."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 25,
        sender: str = "kompas@mc.gov.pl",
        use_tls: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.sender = sender
        self.use_tls = use_tls

    def send(self, notification: Notification) -> None:
        if not notification.recipient_email:
            log.warning("Skipping SMTP notification for %s: no email", notification.recipient_id)
            return
        msg = EmailMessage()
        msg["From"] = self.sender
        msg["To"] = notification.recipient_email
        msg["Subject"] = notification.subject
        msg.set_content(notification.body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=10) as client:
                if self.use_tls:
                    client.starttls()
                client.send_message(msg)
        except OSError as exc:
            raise ExternalServiceError(f"SMTP error: {exc}") from exc

