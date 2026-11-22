"""Safety & legal compliance guardrails for the AI assistant."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from kompas.core.registry import Registry


@dataclass
class GuardrailOutcome:
    """Result of running guardrails on a user query."""

    sanitized_query: str
    blocked: bool = False
    block_reason: str | None = None
    warnings: list[str] = field(default_factory=list)


class Guardrail(ABC):
    """Checks/sanitizes a query before retrieval or generation."""

    @abstractmethod
    def check(self, query: str, messages: dict[str, str]) -> GuardrailOutcome: ...


guardrail_registry: Registry[Guardrail] = Registry("guardrail")


@guardrail_registry.register("rating_decision")
class RatingDecisionGuardrail(Guardrail):
    """Prevents AI from deciding an employee's rating (challenge requirement)."""

    _PATTERNS = (
        re.compile(r"\b(wystaw|przyznaj|wybierz|zdecyduj|ustal)\b.{0,40}\b(ocen[eęą]|poziom|punkt)", re.I),
        re.compile(r"\b(jak[aą]\s+ocen[eę]\s+mam\s+wystawi[cć]|czy\s+da[cć]\s+ocen[eę]\s+negatywn)", re.I),
    )

    def check(self, query: str, messages: dict[str, str]) -> GuardrailOutcome:
        for pat in self._PATTERNS:
            if pat.search(query):
                return GuardrailOutcome(
                    sanitized_query=query,
                    blocked=True,
                    block_reason=messages.get(
                        "rating_decision",
                        "AI pełni wyłącznie funkcję doradczą. Ostateczna decyzja należy do przełożonego.",
                    ),
                )
        return GuardrailOutcome(sanitized_query=query)


@guardrail_registry.register("personal_data")
class PersonalDataGuardrail(Guardrail):
    """Redacts PESEL, email and phone numbers before sending text to an LLM."""

    _PESEL = re.compile(r"\b\d{11}\b")
    _EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    _PHONE = re.compile(r"(?<!\d)(?:\+48[\s-]?)?(?:\d[\s-]?){9}(?!\d)")

    def check(self, query: str, messages: dict[str, str]) -> GuardrailOutcome:
        redacted = query
        changed = False
        for pattern, token in (
            (self._PESEL, "[PESEL]"),
            (self._EMAIL, "[EMAIL]"),
            (self._PHONE, "[TELEFON]"),
        ):
            updated = pattern.sub(token, redacted)
            if updated != redacted:
                changed = True
                redacted = updated
        warnings = [messages.get("personal_data", "Usunięto dane osobowe z pytania.")] if changed else []
        return GuardrailOutcome(sanitized_query=redacted, warnings=warnings)
