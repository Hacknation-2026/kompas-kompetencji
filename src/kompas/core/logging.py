"""Logging setup with GDPR PII scrubbing filter (stdlib only)."""

from __future__ import annotations

import logging
import re

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

_PESEL_RE = re.compile(r"\b\d{11}\b")
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+48[\s-]?)?(?:\d[\s-]?){9}(?!\d)")


def scrub_pii(text: str) -> str:
    """Mask PESEL, email addresses and phone numbers in log messages."""
    text = _PESEL_RE.sub("[PESEL]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    return _PHONE_RE.sub("[TELEFON]", text)


class PIIScrubbingFilter(logging.Filter):
    """Logging filter redacting personal data from rendered log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        rendered = record.getMessage()
        scrubbed = scrub_pii(rendered)
        if scrubbed != rendered:
            record.msg = scrubbed
            record.args = ()
        return True


def configure_logging(debug: bool = False) -> None:
    """Configure root logging once with PII scrubbing; idempotent."""
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_FORMAT)
    for handler in root.handlers:
        if not any(isinstance(f, PIIScrubbingFilter) for f in handler.filters):
            handler.addFilter(PIIScrubbingFilter())
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Namespaced logger under ``kompas``."""
    return logging.getLogger(name if name.startswith("kompas") else f"kompas.{name}")
