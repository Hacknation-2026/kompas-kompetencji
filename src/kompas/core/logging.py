"""Logging setup (structured-ish, stdlib only)."""

from __future__ import annotations

import logging

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def configure_logging(debug: bool = False) -> None:
    """Configure root logging once; idempotent."""
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_FORMAT)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Namespaced logger under ``kompas``."""
    return logging.getLogger(name if name.startswith("kompas") else f"kompas.{name}")
