"""CLI / ``python -m kompas`` entrypoint (server or scheduled reminder worker)."""

from __future__ import annotations

import argparse

import uvicorn

from kompas.core.config import get_settings
from kompas.notifications.worker import run_reminder_job


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kompas", description="Kompas Kompetencji CLI")
    parser.add_argument(
        "command",
        nargs="?",
        default="serve",
        choices=["serve", "reminders"],
        help="Uruchom serwer HTTP (serve) lub jednorazową wysyłkę przypomnień (reminders).",
    )
    args = parser.parse_args(argv)

    if args.command == "reminders":
        run_reminder_job()
        return

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
