"""People: evaluated employees and system users (data minimisation by design)."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from kompas.domain.enums import Role


class Employee(BaseModel):
    """Evaluated employee – only fields needed for the evaluation process are stored."""

    id: str
    first_name: str
    last_name: str
    org_unit: str
    position: str
    position_symbol: str | None = None
    supervisor_id: str = Field(description="User id of the direct supervisor (oceniający)")
    employment_start: date
    contract_end: date | None = None
    indefinite_employment_date: date | None = None
    last_evaluation_date: date | None = None
    is_civil_servant: bool = False  # urzędnik służby cywilnej (mianowany)
    manages_people: bool = False  # bezpośrednie kierowanie pracownikami -> arkusz B
    is_head_of_office: bool = False  # kierownik urzędu -> arkusz A
    preparatory_exam_required: bool = True
    job_description_summary: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class User(BaseModel):
    """Application user (supervisor, HR, admin)."""

    id: str
    username: str
    full_name: str
    role: Role
    email: str | None = None
    org_unit: str | None = None
    position: str | None = None
    password_hash: str = Field(default="", repr=False, exclude=True)
    active: bool = True
