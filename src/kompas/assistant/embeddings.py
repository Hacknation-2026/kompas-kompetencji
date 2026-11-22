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
    """Local neural embeddings via ``sentence-transformers`` (lazy-loaded on first ``embed()``)."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        cache_dir: str = "models/embeddings",
        device: str = "cpu",
        normalize: bool = True,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.device = device
        self.normalize = normalize
        self._model: object | None = None

    def _get_model(self) -> object:
        if self._model is not None:
            return self._model
        import os

        cache_path = resolve_path(self.cache_dir)
        model_slug = f"models--{self.model_name.replace('/', '--')}"
        has_local_cache = (cache_path / model_slug).is_dir()
        if has_local_cache:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional heavy extra
            raise ConfigurationError(
                "sentence-transformers is not installed. Run `make install-ml`."
            ) from exc
        try:
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=str(cache_path),
                device=self.device,
                local_files_only=has_local_cache,
            )
        except Exception:
            self._model = SentenceTransformer(
                self.model_name,
                cache_folder=str(cache_path),
                device=self.device,
            )
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - optional heavy extra
        model = self._get_model()
        arr = model.encode(list(texts), normalize_embeddings=self.normalize)  # type: ignore[attr-defined]
        return [list(map(float, row)) for row in arr]
