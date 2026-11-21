"""Workflow engine – enforces step order and requirements, records audit trail."""

from __future__ import annotations

from kompas.core.exceptions import ConfigurationError, NotFoundError, WorkflowError
from kompas.domain.enums import EvaluationStatus, EvaluationType
from kompas.domain.evaluation import Evaluation, StepEvent
from kompas.workflow.definitions import PathDefinition, StepDefinition
from kompas.workflow.requirements import StepRequirement, requirement_registry


class WorkflowEngine:
    """Stateless service operating on :class:`Evaluation` aggregates."""

    def __init__(self, paths: dict[EvaluationType, PathDefinition]) -> None:
        self.paths = paths
        self._requirements: dict[str, StepRequirement] = {}
        for path in paths.values():
            for step in path.steps:
                for name in step.requires:
                    if name not in requirement_registry:
                        raise ConfigurationError(f"Step '{step.id}' requires unknown check '{name}'")
                    self._requirements.setdefault(name, requirement_registry.create(name))

    def path(self, evaluation_type: EvaluationType) -> PathDefinition:
        try:
            return self.paths[evaluation_type]
        except KeyError as exc:
            raise NotFoundError(f"No workflow configured for '{evaluation_type}'") from exc

    def first_step(self, evaluation_type: EvaluationType) -> StepDefinition:
        return self.path(evaluation_type).steps[0]

    def unmet_requirements(self, evaluation: Evaluation, step_id: str | None = None) -> list[str]:
        step = self.path(evaluation.type).step(step_id or evaluation.current_step)
        return [
            self._requirements[n].message
            for n in step.requires
            if not self._requirements[n].is_met(evaluation)
        ]

    def complete_step(
        self, evaluation: Evaluation, step_id: str, user_id: str, note: str | None = None
    ) -> Evaluation:
        """Complete the *current* step and advance; raises :class:`WorkflowError` otherwise."""
        if evaluation.status is not EvaluationStatus.IN_PROGRESS:
            raise WorkflowError(f"Evaluation is {evaluation.status.value}; no further steps allowed")
        path = self.path(evaluation.type)
        path.step(step_id)  # validates existence
        if step_id != evaluation.current_step:
            raise WorkflowError(
                f"Step '{step_id}' cannot be completed now; current step is '{evaluation.current_step}'",
                details={"current_step": evaluation.current_step},
            )
        unmet = self.unmet_requirements(evaluation, step_id)
        if unmet:
            raise WorkflowError("Step requirements not met", details={"unmet": unmet})

        evaluation.completed_steps.append(step_id)
        evaluation.history.append(StepEvent(step_id=step_id, completed_by=user_id, note=note))
        nxt = path.next_step(step_id)
        if nxt is None:
            evaluation.status = EvaluationStatus.COMPLETED
        else:
            evaluation.current_step = nxt.id
        evaluation.touch()
        return evaluation

    def progress(self, evaluation: Evaluation) -> list[dict[str, object]]:
        """Step list with state for UI stepper."""
        path = self.path(evaluation.type)
        result: list[dict[str, object]] = []
        for step in path.steps:
            if step.id in evaluation.completed_steps:
                state = "done"
            elif step.id == evaluation.current_step and evaluation.status is EvaluationStatus.IN_PROGRESS:
                state = "current"
            else:
                state = "pending"
            result.append(
                {"id": step.id, "title": step.title, "state": state, "legal_basis": step.legal_basis}
            )
        return result
