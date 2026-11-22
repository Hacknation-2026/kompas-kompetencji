"""Typed workflow definitions."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from kompas.core.config import read_yaml
from kompas.core.exceptions import ConfigurationError, NotFoundError
from kompas.domain.enums import DeadlineKind, EvaluationType


class Offset(BaseModel):
    days: int = 0
    months: int = 0


class DeadlineSpec(BaseModel):
    anchor: str
    offset: Offset = Field(default_factory=Offset)
    kind: DeadlineKind = DeadlineKind.DUE


class StepDefinition(BaseModel):
    id: str
    title: str
    description: str = ""
    legal_basis: str | None = None
    deadline: DeadlineSpec | None = None
    requires: list[str] = Field(default_factory=list)


class PathDefinition(BaseModel):
    type: EvaluationType
    title: str
    derived_anchors: dict[str, DeadlineSpec] = Field(default_factory=dict)
    steps: list[StepDefinition]

    @model_validator(mode="after")
    def _unique_steps(self) -> PathDefinition:
        ids = [s.id for s in self.steps]
        if not ids:
            raise ValueError("A path needs at least one step")
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate step ids in path {self.type}")
        return self

    def step(self, step_id: str) -> StepDefinition:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise NotFoundError(f"Step '{step_id}' not found in path '{self.type}'")

    def index(self, step_id: str) -> int:
        return [s.id for s in self.steps].index(self.step(step_id).id)

    def next_step(self, step_id: str) -> StepDefinition | None:
        idx = self.index(step_id)
        return self.steps[idx + 1] if idx + 1 < len(self.steps) else None


def load_paths(path: Path) -> dict[EvaluationType, PathDefinition]:
    raw = read_yaml(path).get("paths", {})
    try:
        return {EvaluationType(k): PathDefinition(type=EvaluationType(k), **v) for k, v in raw.items()}
    except ValueError as exc:
        raise ConfigurationError(f"Invalid workflow definition: {exc}") from exc
