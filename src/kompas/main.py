"""FastAPI application factory & ASGI entrypoint (``uvicorn kompas.main:app``)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kompas.api.errors import register_exception_handlers
from kompas.api.routers import assistant, auth, competencies, evaluations, health, monitoring
from kompas.container import AppContainer, build_container
from kompas.core.config import Settings

_STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


def create_app(settings: Settings | None = None, container: AppContainer | None = None) -> FastAPI:
    """Create a configured FastAPI instance."""
    resolved = container or build_container(settings)
    cfg = resolved.settings

    application = FastAPI(
        title=cfg.app.name,
        version=cfg.app.version,
        debug=cfg.app.debug,
        openapi_url=f"{cfg.server.api_prefix}/openapi.json",
        docs_url=f"{cfg.server.api_prefix}/docs",
    )
    application.state.container = resolved

    if cfg.server.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=cfg.server.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    register_exception_handlers(application)

    prefix = cfg.server.api_prefix
    for router in (
        health.router,
        auth.router,
        competencies.router,
        evaluations.router,
        assistant.router,
        monitoring.router,
    ):
        application.include_router(router, prefix=prefix)

    if _STATIC_DIR.is_dir():
        application.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

        @application.get("/", include_in_schema=False)
        def index() -> FileResponse:
            return FileResponse(_STATIC_DIR / "index.html")

    return application


app = create_app()
