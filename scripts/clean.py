"""Remove local caches and test/runtime artefacts."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "docs/coverage",
    "data/runtime",
    "data/output",
)


def main() -> None:
    for rel in TARGETS:
        path = ROOT / rel
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.is_file():
            path.unlink(missing_ok=True)
    for cache in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    print("Cleaned caches and runtime directories.")


if __name__ == "__main__":
    main()

