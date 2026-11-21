"""Pluggable knowledge-base retrievers (BM25, dense embeddings, hybrid)."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import Counter
from dataclasses import dataclass

from kompas.assistant.embeddings import EmbeddingModel, cosine_similarity, tokenize
from kompas.assistant.knowledge import KnowledgeChunk
from kompas.core.registry import Registry


@dataclass(frozen=True)
class RetrievedChunk:
    chunk: KnowledgeChunk
    score: float  # normalised 0..1


class Retriever(ABC):
    """Indexes knowledge chunks and returns the most relevant ones for a query."""

    @abstractmethod
    def index(self, chunks: list[KnowledgeChunk]) -> None: ...

    @abstractmethod
    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]: ...


retriever_registry: Registry[Retriever] = Registry("retriever")


@retriever_registry.register("bm25")
class BM25Retriever(Retriever):
    """Okapi BM25 lexical retriever with Polish prefix stemming."""

    def __init__(self, stem_length: int = 6, k1: float = 1.5, b: float = 0.75) -> None:
        self.stem_length = stem_length
        self.k1 = k1
        self.b = b
        self._chunks: list[KnowledgeChunk] = []
        self._tfs: list[Counter[str]] = []
        self._idf: dict[str, float] = {}
        self._avg_len: float = 1.0

    def index(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)
        self._tfs = []
        df: Counter[str] = Counter()
        total_len = 0
        for chunk in self._chunks:
            tokens = tokenize(f"{chunk.title} {chunk.text}", self.stem_length)
            tf = Counter(tokens)
            self._tfs.append(tf)
            total_len += len(tokens)
            for term in tf:
                df[term] += 1
        n = len(self._chunks) or 1
        self._avg_len = (total_len / n) or 1.0
        self._idf = {term: math.log(1.0 + (n - freq + 0.5) / (freq + 0.5)) for term, freq in df.items()}

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        if not self._chunks:
            return []
        q_tokens = tokenize(query, self.stem_length)
        if not q_tokens:
            return []
        max_possible = sum(self._idf.get(t, 0.0) * (self.k1 + 1.0) for t in set(q_tokens)) or 1.0
        scored: list[RetrievedChunk] = []
        for chunk, tf in zip(self._chunks, self._tfs, strict=True):
            doc_len = sum(tf.values()) or 1
            raw = 0.0
            for term in set(q_tokens):
                freq = tf.get(term, 0)
                if freq == 0:
                    continue
                idf = self._idf.get(term, 0.0)
                denom = freq + self.k1 * (1.0 - self.b + self.b * doc_len / self._avg_len)
                raw += idf * (freq * (self.k1 + 1.0)) / denom
            if raw > 0.0:
                scored.append(RetrievedChunk(chunk=chunk, score=min(1.0, raw / max_possible)))
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


@retriever_registry.register("embedding")
class EmbeddingRetriever(Retriever):
    """Vector similarity retriever using any :class:`EmbeddingModel`."""

    def __init__(self, embeddings: EmbeddingModel) -> None:
        self.embeddings = embeddings
        self._chunks: list[KnowledgeChunk] = []
        self._vectors: list[list[float]] = []

    def index(self, chunks: list[KnowledgeChunk]) -> None:
        self._chunks = list(chunks)
        self._vectors = self.embeddings.embed([f"{c.title} {c.text}" for c in self._chunks]) if chunks else []

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        if not self._chunks:
            return []
        q_vec = self.embeddings.embed_one(query)
        scored = [
            RetrievedChunk(chunk=chunk, score=max(0.0, min(1.0, cosine_similarity(q_vec, vec))))
            for chunk, vec in zip(self._chunks, self._vectors, strict=True)
        ]
        scored = [s for s in scored if s.score > 0.0]
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]


@retriever_registry.register("hybrid")
class HybridRetriever(Retriever):
    """Weighted combination of BM25 and dense embedding similarity."""

    def __init__(self, embeddings: EmbeddingModel, bm25_weight: float = 0.65, stem_length: int = 6) -> None:
        self.bm25 = BM25Retriever(stem_length=stem_length)
        self.dense = EmbeddingRetriever(embeddings=embeddings)
        self.bm25_weight = bm25_weight

    def index(self, chunks: list[KnowledgeChunk]) -> None:
        self.bm25.index(chunks)
        self.dense.index(chunks)

    def search(self, query: str, top_k: int = 4) -> list[RetrievedChunk]:
        n = max(top_k * 3, 10)
        bm25_hits = {h.chunk.id: h for h in self.bm25.search(query, top_k=n)}
        dense_hits = {h.chunk.id: h for h in self.dense.search(query, top_k=n)}
        all_ids = set(bm25_hits) | set(dense_hits)
        combined: list[RetrievedChunk] = []
        for cid in all_ids:
            b = bm25_hits.get(cid)
            d = dense_hits.get(cid)
            chunk = (b or d).chunk  # type: ignore[union-attr]
            score = self.bm25_weight * (b.score if b else 0.0) + (1.0 - self.bm25_weight) * (
                d.score if d else 0.0
            )
            combined.append(RetrievedChunk(chunk=chunk, score=score))
        combined.sort(key=lambda item: item.score, reverse=True)
        return combined[:top_k]
