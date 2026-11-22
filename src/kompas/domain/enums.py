"""Enumerations shared across the domain."""

from __future__ import annotations

from enum import StrEnum


class EvaluationType(StrEnum):
    """Two legally distinct evaluation paths."""

    FIRST = "first"  # pierwsza ocena w służbie cywilnej (art. 37–38 ustawy)
    PERIODIC = "periodic"  # ocena okresowa (art. 81 ustawy)


class FormType(StrEnum):
    """Evaluation sheets (arkusze)."""

    FIRST = "first"  # arkusz pierwszej oceny
    A = "A"  # kierownik urzędu
    B = "B"  # stanowisko kierownicze
    C = "C"  # pozostałe stanowiska


class EvaluationStatus(StrEnum):
    """Coarse lifecycle status used by HR monitoring."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Role(StrEnum):
    """User roles (RBAC)."""

    SUPERVISOR = "supervisor"  # przełożony – oceniający
    HR = "hr"  # pracownik kadr – monitoring procesu
    ADMIN = "admin"  # administrator systemu


class DeadlineKind(StrEnum):
    """Whether a deadline is the latest or the earliest permitted date."""

    DUE = "due"
    NOT_BEFORE = "not_before"


class AssistantMode(StrEnum):
    """Two assistant personas from the challenge brief."""

    FORMAL = "formal"  # Asystent formalny oceny
    CONVERSATION = "conversation"  # Asystent rozmowy


class DocumentFormat(StrEnum):
    PDF = "pdf"
    HTML = "html"
