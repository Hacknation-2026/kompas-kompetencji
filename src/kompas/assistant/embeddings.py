"""Pluggable text embedding models (offline hashing baseline + optional sentence-transformers)."""

from __future__ import annotations

import hashlib
import math
import re
from abc import ABC, abstractmethod
from collections.abc import Sequence

from kompas.core.config import resolve_path
from kompas.core.exceptions import ConfigurationError
from kompas.core.registry import Registry

_TOKEN_RE = re.compile(r"[^\W_]{2,}", re.UNICODE)


def tokenize(text: str, stem_length: int = 6) -> list[str]:
    """Simple Unicode word tokenizer with prefix stemming suited for Polish inflection."""
    tokens = _TOKEN_RE.findall(text.lower())
    return [t[:stem_length] if len(t) > stem_length else t for t in tokens]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingModel(ABC):
    """Maps text to a dense vector."""

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


embedding_registry: Registry[EmbeddingModel] = Registry("embeddings")


@embedding_registry.register("hashing")
class HashingEmbeddingModel(EmbeddingModel):
    """Dependency-free feature-hashing embedder (deterministic, fast)."""

    def __init__(self, dimensions: int = 1024, stem_length: int = 6) -> None:
        if dimensions <= 0:
            raise ConfigurationError("dimensions must be positive")
        self.dimensions = dimensions
        self.stem_length = stem_length

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dimensions
            for token in tokenize(text, self.stem_length):
                digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
                idx = int.from_bytes(digest, "little") % self.dimensions
                vec[idx] += 1.0
            norm = math.sqrt(sum(v * v for v in vec))
            if norm > 0.0:
                vec = [v / norm for v in vec]
            vectors.append(vec)
        return vectors


@embedding_registry.register("sentence_transformers")
class SentenceTransformerEmbeddingModel(EmbeddingModel):
    """Local neural embeddings via ``sentence-transformers`` (requires ``ml`` extra)."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: str = "models/embeddings",
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional heavy extra
            raise ConfigurationError(
                "sentence-transformers is not installed. Run `make install-ml`."
            ) from exc
        self._model = SentenceTransformer(
            model_name, cache_folder=str(resolve_path(cache_dir)), device=device
        )
        self.normalize = normalize

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - optional heavy extra
        arr = self._model.encode(list(texts), normalize_embeddings=self.normalize)
        return [list(map(float, row)) for row in arr]
