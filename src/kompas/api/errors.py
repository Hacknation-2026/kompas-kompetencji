"""Maps :class:`KompasError` exceptions to consistent JSON error responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from kompas.core.exceptions import KompasError


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(KompasError)
    async def _handle_kompas_error(_request: Request, exc: KompasError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )
