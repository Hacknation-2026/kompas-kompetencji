"""CLI / ``python -m kompas`` entrypoint running uvicorn from YAML server config."""

from __future__ import annotations

import uvicorn

from kompas.core.config import get_settings


def main() -> None:
    cfg = get_settings()
    uvicorn.run(
        "kompas.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=cfg.server.reload,
        workers=cfg.server.workers if not cfg.server.reload else 1,
    )


if __name__ == "__main__":
    main()

