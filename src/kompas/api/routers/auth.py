"""Authentication endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kompas.api.deps import get_container, get_current_user
from kompas.api.schemas import LoginRequest, TokenResponse
from kompas.container import AppContainer
from kompas.domain.people import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, container: AppContainer = Depends(get_container)) -> TokenResponse:
    user, token = container.auth.authenticate(body.username, body.password)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        full_name=user.full_name,
        role=user.role.value,
    )


@router.get("/me", response_model=User)
def me(user: User = Depends(get_current_user)) -> User:
    return user
