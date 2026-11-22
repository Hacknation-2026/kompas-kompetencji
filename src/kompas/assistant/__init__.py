"""RAG-based AI assistant (formal rules + interview preparation) with guardrails."""

from kompas.assistant.embeddings import EmbeddingModel, HashingEmbeddingModel, embedding_registry
from kompas.assistant.guardrails import Guardrail, guardrail_registry
from kompas.assistant.knowledge import KnowledgeBaseBuilder, KnowledgeChunk
from kompas.assistant.llm import ExtractiveLLMClient, LLMClient, llm_registry
from kompas.assistant.retriever import (
    BM25Retriever,
    EmbeddingRetriever,
    HybridRetriever,
    Retriever,
    retriever_registry,
)
from kompas.assistant.service import (
    AssistantResponse,
    AssistantService,
    Citation,
    ConversationPrep,
    load_prompts,
)

__all__ = [
    "AssistantResponse",
    "AssistantService",
    "BM25Retriever",
    "Citation",
    "ConversationPrep",
    "EmbeddingModel",
    "EmbeddingRetriever",
    "ExtractiveLLMClient",
    "Guardrail",
    "HashingEmbeddingModel",
    "HybridRetriever",
    "KnowledgeBaseBuilder",
    "KnowledgeChunk",
    "LLMClient",
    "Retriever",
    "embedding_registry",
    "guardrail_registry",
    "llm_registry",
    "load_prompts",
    "retriever_registry",
]
