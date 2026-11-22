"""Form (arkusz) definitions, form selection and criteria validation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from kompas.core.config import read_yaml
from kompas.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import EvaluationType, FormType
from kompas.domain.people import Employee


class FormDefinition(BaseModel):
    """Configuration of one evaluation sheet (config/forms.yaml)."""

    form: FormType
    evaluation_type: EvaluationType
    title: str
    legal_basis: str
    scale: str
    mandatory_criteria: list[str]
    max_additional_criteria: int = Field(ge=0)


def load_forms(path: Path) -> dict[FormType, FormDefinition]:
    """Parse ``config/forms.yaml``."""
    raw = read_yaml(path).get("forms", {})
    return {FormType(key): FormDefinition(form=FormType(key), **value) for key, value in raw.items()}


class FormSelector:
    """Chooses the sheet for an employee – § 3 rozporządzenia z 2016 r."""

    def select(self, evaluation_type: EvaluationType, employee: Employee) -> FormType:
        if evaluation_type is EvaluationType.FIRST:
            return FormType.FIRST
        if employee.is_head_of_office:
            return FormType.A
        if employee.manages_people:
            return FormType.B
        return FormType.C


class CriteriaPolicy:
    """Validates criteria choices against forms and the competency model."""

    def __init__(self, forms: dict[FormType, FormDefinition], model: CompetencyModel) -> None:
        self.forms = forms
        self.model = model
        self._validate_configuration()

    def _validate_configuration(self) -> None:
        known = set(self.model.ids())
        for definition in self.forms.values():
            unknown = set(definition.mandatory_criteria) - known
            if unknown:
                raise ConfigurationError(
                    f"Form {definition.form} references unknown competencies: {sorted(unknown)}"
                )

    def form(self, form: FormType) -> FormDefinition:
        try:
            return self.forms[form]
        except KeyError as exc:
            raise NotFoundError(f"Form '{form}' is not configured") from exc

    def mandatory(self, form: FormType) -> list[str]:
        return list(self.form(form).mandatory_criteria)

    def allowed_additional(self, form: FormType) -> list[str]:
        """Competencies that may be selected as additional criteria."""
        definition = self.form(form)
        if definition.max_additional_criteria == 0:
            return []
        mandatory = set(definition.mandatory_criteria)
        return [cid for cid in self.model.ids() if cid not in mandatory]

    def validate_additional(self, form: FormType, additional: list[str]) -> list[str]:
        """Return normalised additional criteria or raise :class:`ValidationError` (§ 5 ust. 2)."""
        definition = self.form(form)
        if len(additional) != len(set(additional)):
            raise ValidationError("Additional criteria must not repeat")
        if len(additional) > definition.max_additional_criteria:
            raise ValidationError(
                f"Form {form} allows at most {definition.max_additional_criteria} additional criteria",
                details={"max": definition.max_additional_criteria},
            )
        allowed = set(self.allowed_additional(form))
        invalid = [cid for cid in additional if cid not in allowed]
        if invalid:
            raise ValidationError(
                "Invalid additional criteria (unknown or already mandatory)", details={"invalid": invalid}
            )
        return list(additional)
