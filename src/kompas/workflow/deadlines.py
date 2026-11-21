"""Deadline calculation following Polish civil-law rules for time limits.

* Days (art. 111 KC): counted from the day after the event – ``anchor + N days``.
* Months (art. 112 KC): ends on the day with the same number; if absent, last day of month.
* If the deadline falls on Sunday/public holiday it moves to the next working day
  (art. 115 KC) – optional via ``shift_non_working``; Saturdays are handled the same way
  since the 2024 interpretation (see Poradnik KPRM) only where configured.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from kompas.domain.evaluation import Deadline
from kompas.workflow.definitions import DeadlineSpec, PathDefinition


def add_months(start: date, months: int) -> date:
    """Calendar month arithmetic (art. 112 KC)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 22 * m) // 451
    month, day = divmod(h + m - 7 * n + 114, 31)
    return date(year, month, day + 1)


def polish_public_holidays(year: int) -> set[date]:
    """Statutory non-working days in Poland."""
    easter = _easter(year)
    fixed = [(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 25), (12, 26)]
    if year >= 2025:
        fixed.append((12, 24))  # Wigilia – dzień wolny od 2025 r.
    days = {date(year, m, d) for m, d in fixed}
    days |= {easter, easter + timedelta(days=1), easter + timedelta(days=49), easter + timedelta(days=60)}
    return days


def next_working_day(day: date) -> date:
    """Move Sundays and public holidays to the following working day (art. 115 KC)."""
    while day.weekday() == 6 or day in polish_public_holidays(day.year):
        day += timedelta(days=1)
    return day


def apply_offset(anchor: date, spec: DeadlineSpec) -> date:
    result = add_months(anchor, spec.offset.months) if spec.offset.months else anchor
    return result + timedelta(days=spec.offset.days)


def compute_anchors(path: PathDefinition, anchors: dict[str, date]) -> dict[str, date]:
    """Add derived anchors (e.g. ``contract_end`` = employment_start + 12 months) when missing."""
    result = dict(anchors)
    for name, spec in path.derived_anchors.items():
        if name not in result and spec.anchor in result:
            result[name] = apply_offset(result[spec.anchor], spec)
    return result


def compute_deadlines(
    path: PathDefinition, anchors: dict[str, date], shift_non_working: bool = True
) -> list[Deadline]:
    """Deadlines for each step whose anchor is known."""
    deadlines: list[Deadline] = []
    for step in path.steps:
        spec = step.deadline
        if spec is None or spec.anchor not in anchors:
            continue
        due = apply_offset(anchors[spec.anchor], spec)
        if shift_non_working and spec.kind.value == "due":
            due = next_working_day(due)
        deadlines.append(
            Deadline(
                step_id=step.id, label=step.title, due_date=due, kind=spec.kind, legal_basis=step.legal_basis
            )
        )
    return deadlines
