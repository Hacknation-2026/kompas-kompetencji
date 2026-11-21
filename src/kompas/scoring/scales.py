"""Rating levels and scales (config/scoring.yaml)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kompas.core.config import read_yaml
from kompas.core.exceptions import ConfigurationError, NotFoundError
from kompas.domain.competency import ScaleLevel


class RatingScales:
    """Level labels + named scales (``periodic`` = 1..9, ``first`` = 3/5/7)."""

    def __init__(self, levels: list[ScaleLevel], scales: dict[str, list[int]]) -> None:
        self.levels = {lvl.points: lvl for lvl in levels}
        self.scales = scales
        for name, points in scales.items():
            missing = [p for p in points if p not in self.levels]
            if missing:
                raise ConfigurationError(f"Scale '{name}' uses undefined levels {missing}")

    def scale(self, name: str) -> list[int]:
        try:
            return list(self.scales[name])
        except KeyError as exc:
            raise NotFoundError(f"Rating scale '{name}' is not configured") from exc

    def label(self, points: int) -> str:
        level = self.levels.get(points)
        return level.label if level else str(points)

    def describe(self, name: str) -> list[ScaleLevel]:
        return [self.levels[p] for p in self.scale(name)]


def load_scales(path: Path) -> tuple[RatingScales, dict[str, Any]]:
    """Return scales and the raw ``policies`` block from ``config/scoring.yaml``."""
    raw = read_yaml(path)
    levels = [ScaleLevel(**item) for item in raw.get("levels", [])]
    return RatingScales(levels, raw.get("scales", {})), raw.get("policies", {})
