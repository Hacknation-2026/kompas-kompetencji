"""Competency model entities (14 competencies, behavioural indicators, 5 levels)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kompas.core.exceptions import NotFoundError


class ScaleLevel(BaseModel):
    """One level of the rating scale (points + Polish label)."""

    model_config = ConfigDict(frozen=True)

    points: int
    key: str
    label: str


class BehavioralIndicator(BaseModel):
    """Observable behaviour described on each level of the scale."""

    id: str
    name: str
    levels: dict[int, str] = Field(description="points -> behaviour description")

    def describe(self, points: int) -> str:
        """Behaviour text for the given level."""
        try:
            return self.levels[points]
        except KeyError as exc:
            raise NotFoundError(f"Indicator {self.id} has no level {points}") from exc


class Competency(BaseModel):
    """Competency (kryterium oceny / element oceny) with its indicators."""

    id: str
    name: str
    indicators: list[BehavioralIndicator]

    def indicator(self, indicator_id: str) -> BehavioralIndicator:
        for item in self.indicators:
            if item.id == indicator_id:
                return item
        raise NotFoundError(f"Indicator '{indicator_id}' not found in competency '{self.id}'")


class CompetencyModel(BaseModel):
    """Complete competency model."""

    name: str
    version: str
    source: str | None = None
    guidance: list[str] = Field(default_factory=list)
    competencies: list[Competency]

    @model_validator(mode="after")
    def _unique_ids(self) -> CompetencyModel:
        ids = [c.id for c in self.competencies]
        if len(ids) != len(set(ids)):
            raise ValueError("Competency ids must be unique")
        return self

    @property
    def indicator_count(self) -> int:
        return sum(len(c.indicators) for c in self.competencies)

    def ids(self) -> list[str]:
        return [c.id for c in self.competencies]

    def get(self, competency_id: str) -> Competency:
        for competency in self.competencies:
            if competency.id == competency_id:
                return competency
        raise NotFoundError(f"Competency '{competency_id}' not found")
