"""Step completion requirements (pluggable checks referenced by name in workflows.yaml)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from kompas.core.registry import Registry
from kompas.domain.evaluation import Evaluation


class StepRequirement(ABC):
    """A single pre-condition for completing a workflow step."""

    message: str = "Requirement not met"

    @abstractmethod
    def is_met(self, evaluation: Evaluation) -> bool: ...


requirement_registry: Registry[StepRequirement] = Registry("step_requirement")


@requirement_registry.register("form_selected")
class FormSelected(StepRequirement):
    message = "Wybierz właściwy arkusz oceny."

    def is_met(self, evaluation: Evaluation) -> bool:
        return bool(evaluation.form) and bool(evaluation.mandatory_criteria)


@requirement_registry.register("criteria_confirmed")
class CriteriaConfirmed(StepRequirement):
    message = "Zatwierdź kryteria oceny (obowiązkowe i ewentualne dodatkowe)."

    def is_met(self, evaluation: Evaluation) -> bool:
        return evaluation.criteria_confirmed


@requirement_registry.register("all_criteria_decided")
class AllCriteriaDecided(StepRequirement):
    message = "Przyznaj ocenę cząstkową dla każdego kryterium."

    def is_met(self, evaluation: Evaluation) -> bool:
        return set(evaluation.criteria) <= set(evaluation.final_points())


@requirement_registry.register("outcome_computed")
class OutcomeComputed(StepRequirement):
    message = "Oblicz wynik oceny."

    def is_met(self, evaluation: Evaluation) -> bool:
        return evaluation.outcome is not None


@requirement_registry.register("justification_if_negative")
class JustificationIfNegative(StepRequirement):
    message = "Ocena negatywna wymaga uzasadnienia."

    def is_met(self, evaluation: Evaluation) -> bool:
        if evaluation.outcome is None or evaluation.outcome.positive:
            return True
        return bool((evaluation.justification or "").strip())


@requirement_registry.register("development_plan_present")
class DevelopmentPlanPresent(StepRequirement):
    message = "Wpisz wnioski dotyczące indywidualnego programu rozwoju zawodowego (IPRZ)."

    def is_met(self, evaluation: Evaluation) -> bool:
        return bool((evaluation.development_plan or "").strip())


@requirement_registry.register("report_status_recorded")
class ReportStatusRecorded(StepRequirement):
    message = "Odnotuj, czy sprawozdanie zostało złożone w wyznaczonym terminie."

    def is_met(self, evaluation: Evaluation) -> bool:
        return evaluation.report_submitted_on_time is not None


@requirement_registry.register("exam_status_recorded")
class ExamStatusRecorded(StepRequirement):
    message = "Odnotuj wynik egzaminu ze służby przygotowawczej (lub „nie dotyczy”)."

    def is_met(self, evaluation: Evaluation) -> bool:
        return evaluation.exam_status_recorded
