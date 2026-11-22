"""Assistant service – orchestrates guardrails, retrieval, citation & LLM generation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from kompas.assistant.guardrails import Guardrail
from kompas.assistant.knowledge import KnowledgeChunk
from kompas.assistant.llm import ExtractiveLLMClient, LLMClient
from kompas.assistant.retriever import Retriever
from kompas.core.config import read_yaml
from kompas.core.exceptions import ExternalServiceError
from kompas.core.logging import get_logger
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import AssistantMode
from kompas.domain.evaluation import Evaluation
from kompas.scoring.scales import RatingScales


class ConversationPromptsConfig(BaseModel):
    opening_questions: list[str] = Field(default_factory=list)
    by_level: dict[str, str] = Field(default_factory=dict)
    closing_points: list[str] = Field(default_factory=list)


class PromptsConfig(BaseModel):
    system: dict[str, str]
    user_template: str
    messages: dict[str, str]
    conversation: ConversationPromptsConfig = Field(default_factory=ConversationPromptsConfig)


def load_prompts(path: Path) -> PromptsConfig:
    return PromptsConfig.model_validate(read_yaml(path))


class Citation(BaseModel):
    index: int
    source: str
    title: str
    excerpt: str
    relevance: float


class AssistantResponse(BaseModel):
    mode: AssistantMode
    answer: str
    grounded: bool
    citations: list[Citation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = ""


class ConversationPrep(BaseModel):
    evaluation_id: str
    opening_questions: list[str]
    criterion_prompts: list[dict[str, object]]
    closing_points: list[str]
    ai_tips: str | None = None


class AssistantService:
    """Grounded RAG assistant for formal rules and interview preparation."""

    def __init__(
        self,
        retriever: Retriever,
        llm: LLMClient,
        prompts: PromptsConfig,
        guardrails: list[Guardrail],
        chunks: list[KnowledgeChunk],
        top_k: int = 4,
        min_relevance: float = 0.35,
        max_context_chars: int = 6000,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.prompts = prompts
        self.guardrails = guardrails
        self.top_k = top_k
        self.min_relevance = min_relevance
        self.max_context_chars = max_context_chars
        self.retriever.index(chunks)

    def ask(
        self,
        question: str,
        mode: AssistantMode = AssistantMode.FORMAL,
        extra_context: str | None = None,
    ) -> AssistantResponse:
        query = question.strip()
        warnings: list[str] = []
        for guard in self.guardrails:
            outcome = guard.check(query, self.prompts.messages)
            query = outcome.sanitized_query
            warnings.extend(outcome.warnings)
            if outcome.blocked:
                return AssistantResponse(
                    mode=mode,
                    answer=outcome.block_reason or self.prompts.messages["rating_decision"],
                    grounded=True,
                    warnings=warnings,
                    disclaimer=self.prompts.messages.get("disclaimer", ""),
                )

        hits = self.retriever.search(query, top_k=self.top_k)
        relevant = [h for h in hits if h.score >= self.min_relevance]
        if not relevant and not extra_context:
            return AssistantResponse(
                mode=mode,
                answer=self.prompts.messages["no_answer"],
                grounded=False,
                warnings=warnings,
                disclaimer=self.prompts.messages.get("disclaimer", ""),
            )

        citations: list[Citation] = []
        blocks: list[str] = []
        if extra_context:
            blocks.append(f"[Dane bieżącej oceny]\n{extra_context}")
        for idx, hit in enumerate(relevant, start=1):
            citations.append(
                Citation(
                    index=idx,
                    source=hit.chunk.source,
                    title=hit.chunk.title,
                    excerpt=hit.chunk.text[:240],
                    relevance=round(hit.score, 3),
                )
            )
            blocks.append(f"[{idx}] ({hit.chunk.source} – {hit.chunk.title})\n{hit.chunk.text}")

        context = "\n\n".join(blocks)[: self.max_context_chars]
        no_answer = self.prompts.messages["no_answer"]
        system_prompt = self.prompts.system[mode.value].format(no_answer=no_answer)
        user_prompt = self.prompts.user_template.format(context=context, question=query)
        try:
            answer = self.llm.generate(system_prompt, user_prompt)
        except ExternalServiceError as exc:
            get_logger("assistant").warning("Primary LLM failed (%s); falling back to extractive", exc)
            answer = ExtractiveLLMClient().generate(system_prompt, user_prompt)
            warnings.append(
                "Lokalny model LLM nie odpowiedział na czas — "
                "wyświetlono odpowiedź bezpośrednio z bazy wiedzy."
            )
        return AssistantResponse(
            mode=mode,
            answer=answer,
            grounded=bool(relevant),
            citations=citations,
            warnings=warnings,
            disclaimer=self.prompts.messages.get("disclaimer", ""),
        )

    def prepare_conversation(
        self,
        evaluation: Evaluation,
        model: CompetencyModel,
        scales: RatingScales,
        include_ai_tips: bool = True,
    ) -> ConversationPrep:
        conv_cfg = self.prompts.conversation
        by_level = conv_cfg.by_level
        criterion_prompts: list[dict[str, object]] = []
        summary_lines: list[str] = []

        for cid in evaluation.criteria:
            comp = model.get(cid)
            assess = evaluation.assessments.get(cid)
            pts = assess.final_points if assess else None
            if pts is None:
                pts = assess.suggestion.points if assess and assess.suggestion else None
            if pts is None:
                bucket = "missing"
            elif pts <= 3:
                bucket = "low"
            elif pts == 5:
                bucket = "meets"
            else:
                bucket = "high"

            template = by_level.get(bucket, "{competency}")
            guidance = template.format(competency=comp.name)
            label = scales.label(pts) if pts is not None else "brak oceny"
            criterion_prompts.append(
                {
                    "competency_id": cid,
                    "competency": comp.name,
                    "points": pts,
                    "label": label,
                    "guidance": guidance,
                }
            )
            summary_lines.append(f"- {comp.name}: {pts or '-'} ({label})")

        ai_tips: str | None = None
        if include_ai_tips:
            extra = "Oceny cząstkowe / sugestie:\n" + "\n".join(summary_lines)
            resp = self.ask(
                "Zaproponuj 3 konkretne pytania i główne wątki do rozmowy oceniającej.",
                mode=AssistantMode.CONVERSATION,
                extra_context=extra,
            )
            ai_tips = resp.answer

        return ConversationPrep(
            evaluation_id=evaluation.id,
            opening_questions=list(conv_cfg.opening_questions),
            criterion_prompts=criterion_prompts,
            closing_points=list(conv_cfg.closing_points),
            ai_tips=ai_tips,
        )
