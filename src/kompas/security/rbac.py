"""Role-based and object-level access checks."""

from __future__ import annotations

from kompas.core.exceptions import AuthorizationError
from kompas.domain.enums import Role
from kompas.domain.evaluation import Evaluation
from kompas.domain.people import User


def require_role(user: User, *allowed: Role) -> None:
    if user.role not in allowed:
        raise AuthorizationError(
            "Brak uprawnień do wykonania tej operacji",
            details={"required_roles": [r.value for r in allowed], "actual_role": user.role.value},
        )


def require_evaluation_access(user: User, evaluation: Evaluation) -> None:
    """Supervisors access their own evaluations; HR and Admin access all."""
    if user.role in (Role.HR, Role.ADMIN):
        return
    if evaluation.evaluator_id != user.id:
        raise AuthorizationError("Brak dostępu do oceny innego przełożonego")
