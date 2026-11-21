"""AI Assistant endpoints (formal guidance + interview preparation)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kompas.api.deps import get_container, get_current_user
from kompas.api.schemas import AssistantAskRequest
from kompas.assistant.service import AssistantResponse, ConversationPrep
from kompas.container import AppContainer
from kompas.domain.people import User

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=AssistantResponse)
def ask(
    body: AssistantAskRequest,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> AssistantResponse:
    extra: str | None = None
    if body.evaluation_id:
        ev = container.evaluation_service.get(body.evaluation_id, user)
        extra = (
            f"Ścieżka: {ev.type.value}, formularz: {ev.form.value}, etap: {ev.current_step}, "
            f"kryteria: {', '.join(ev.criteria)}"
        )
    return container.assistant.ask(question=body.question, mode=body.mode, extra_context=extra)


@router.get("/conversation-prep/{evaluation_id}", response_model=ConversationPrep)
def conversation_prep(
    evaluation_id: str,
    include_ai_tips: bool = True,
    user: User = Depends(get_current_user),
    container: AppContainer = Depends(get_container),
) -> ConversationPrep:
    ev = container.evaluation_service.get(evaluation_id, user)
    return container.assistant.prepare_conversation(
        evaluation=ev,
        model=container.competency_model,
        scales=container.scales,
        include_ai_tips=include_ai_tips,
    )
