"""Health & readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from kompas.api.deps import get_container
from kompas.container import AppContainer

router = APIRouter(tags=["health"])


@router.get("/health")
def health(container: AppContainer = Depends(get_container)) -> dict[str, object]:
    return {
        "status": "ok",
        "app": container.settings.app.name,
        "version": container.settings.app.version,
        "environment": container.settings.app.environment,
        "llm_provider": container.settings.llm.provider,
        "retriever_provider": container.settings.retriever.provider,
        "competencies_loaded": len(container.competency_model.competencies),
    }
