"""Unit tests for RAG assistant, retrievers, guardrails and conversation prep."""

from __future__ import annotations

from pathlib import Path

import pytest

from kompas.assistant.embeddings import HashingEmbeddingModel, SentenceTransformerEmbeddingModel
from kompas.assistant.guardrails import PersonalDataGuardrail, RatingDecisionGuardrail
from kompas.assistant.knowledge import KnowledgeChunk, chunk_text
from kompas.assistant.llm import LLMClient
from kompas.assistant.retriever import BM25Retriever, EmbeddingRetriever, HybridRetriever
from kompas.container import AppContainer
from kompas.core.exceptions import ExternalServiceError
from kompas.domain.enums import AssistantMode, EvaluationType


def test_chunk_text_splits_with_overlap() -> None:
    text = " ".join(f"w{i}" for i in range(250))
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    assert len(chunks) == 3
    assert chunks[0].split()[-20:] == chunks[1].split()[:20]


def test_retrievers_rank_relevant_chunk_first() -> None:
    chunks = [
        KnowledgeChunk(id="1", source="s1", title="Sprzeciw", text="Sprzeciw wnosi się w terminie 7 dni."),
        KnowledgeChunk(
            id="2", source="s2", title="Urlopy", text="Pracownik ma prawo do urlopu wypoczynkowego."
        ),
    ]
    for ret in (
        BM25Retriever(),
        EmbeddingRetriever(HashingEmbeddingModel()),
        HybridRetriever(HashingEmbeddingModel()),
    ):
        ret.index(chunks)
        hits = ret.search("Ile dni na sprzeciw od oceny?", top_k=2)
        assert hits
        assert hits[0].chunk.id == "1"


def test_guardrails_block_rating_decision_and_redact_pii() -> None:
    msgs = {"rating_decision": "blocked", "personal_data": "redacted"}
    r_guard = RatingDecisionGuardrail()
    assert r_guard.check("Wystaw ocenę 7 punktów dla pracownika", msgs).blocked is True
    assert r_guard.check("Kiedy przeprowadzić rozmowę wstępną?", msgs).blocked is False

    p_guard = PersonalDataGuardrail()
    res = p_guard.check("PESEL 90010112345 email jan@example.pl tel +48 600 700 800", msgs)
    assert "[PESEL]" in res.sanitized_query
    assert "[EMAIL]" in res.sanitized_query
    assert "[TELEFON]" in res.sanitized_query
    assert res.warnings == ["redacted"]


def test_assistant_returns_no_answer_for_unrelated_question(container: AppContainer) -> None:
    resp = container.assistant.ask("Jaki jest przepis na szarlotkę z cynamonem?", mode=AssistantMode.FORMAL)
    assert resp.grounded is False
    assert "Nie znalazłem" in resp.answer


def test_assistant_answers_with_citations_and_prepares_conversation(container: AppContainer) -> None:
    resp = container.assistant.ask(
        "W jakim terminie wnosi się sprzeciw od oceny okresowej?", mode=AssistantMode.FORMAL
    )
    assert resp.grounded is True
    assert resp.citations
    assert "7 dni" in resp.answer

    supervisor, _ = container.auth.authenticate("przelozony", "demo-password-1")
    ev = container.evaluation_service.create("emp-2", EvaluationType.PERIODIC, supervisor)
    prep = container.assistant.prepare_conversation(ev, container.competency_model, container.scales)
    assert len(prep.opening_questions) >= 3
    assert len(prep.criterion_prompts) == len(ev.criteria)


@pytest.mark.slow
def test_live_hybrid_retriever_with_sentence_transformers() -> None:
    pytest.importorskip("sentence_transformers")
    chunks = [
        KnowledgeChunk(
            id="1",
            source="ustawa.pdf",
            title="Sprzeciw",
            text="Od oceny okresowej przysługuje sprzeciw do dyrektora generalnego w terminie 7 dni.",
        ),
        KnowledgeChunk(
            id="2",
            source="poradnik.pdf",
            title="Rozmowa wstępna",
            text="Rozmowę wstępną przeprowadza się w ciągu 21 dni od nawiązania stosunku pracy.",
        ),
    ]
    retriever = HybridRetriever(SentenceTransformerEmbeddingModel())
    retriever.index(chunks)
    hits = retriever.search("Ile czasu ma pracownik na odwołanie od oceny?", top_k=2)
    assert hits
    assert hits[0].chunk.id == "1"


def test_embedding_retriever_caches_vectors_to_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chunks = [
        KnowledgeChunk(id="1", source="s1", title="Sprzeciw", text="Sprzeciw wnosi się w terminie 7 dni."),
    ]
    cache_file = tmp_path / "emb_cache.json"
    r1 = EmbeddingRetriever(HashingEmbeddingModel(), cache_file=cache_file)
    r1.index(chunks)
    assert cache_file.is_file()

    cached_embedder = HashingEmbeddingModel()
    monkeypatch.setattr(
        cached_embedder,
        "embed",
        lambda _texts: (_ for _ in ()).throw(AssertionError("Should load vectors from disk cache")),
    )
    r2 = EmbeddingRetriever(cached_embedder, cache_file=cache_file)
    r2.index(chunks)
    assert r2._vectors == r1._vectors
    monkeypatch.undo()
    assert r2.search("sprzeciw", top_k=1)[0].chunk.id == "1"


def test_assistant_falls_back_to_extractive_on_llm_timeout(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    class TimeoutLLM(LLMClient):
        def generate(self, system_prompt: str, user_prompt: str) -> str:
            raise ExternalServiceError("Ollama error: timed out")

    monkeypatch.setattr(container.assistant, "llm", TimeoutLLM())
    resp = container.assistant.ask("W jakim terminie wnosi się sprzeciw od oceny okresowej?")
    assert resp.grounded is True
    assert "7 dni" in resp.answer
    assert any("nie odpowiedział na czas" in w for w in resp.warnings)
