"""FastAPI dependencies (container lookup + authenticated user)."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kompas.container import AppContainer
from kompas.core.exceptions import AuthenticationError
from kompas.domain.enums import Role
from kompas.domain.people import User
from kompas.security.rbac import require_role

_bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> AppContainer:
    container: AppContainer = request.app.state.container
    return container


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    container: AppContainer = Depends(get_container),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Wymagane uwierzytelnienie (Bearer token)")
    return container.auth.current_user(credentials.credentials)


def require_hr_or_admin(user: User = Depends(get_current_user)) -> User:
    require_role(user, Role.HR, Role.ADMIN)
    return user
