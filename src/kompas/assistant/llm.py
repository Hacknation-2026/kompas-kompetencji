"""Pluggable LLM clients (offline extractive baseline, Ollama, OpenAI-compatible)."""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

import httpx

from kompas.core.exceptions import ConfigurationError, ExternalServiceError
from kompas.core.registry import Registry


class LLMClient(ABC):
    """Text generation contract."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str: ...


llm_registry: Registry[LLMClient] = Registry("llm")


@llm_registry.register("extractive")
class ExtractiveLLMClient(LLMClient):
    """Offline, deterministic answer composer extracting relevant sentences from KONTEKST."""

    def __init__(self, max_sentences: int = 4, min_sentence_chars: int = 25) -> None:
        self.max_sentences = max_sentences
        self.min_sentence_chars = min_sentence_chars

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        context, _, question = user_prompt.partition("\nPYTANIE:")
        q_words = {w.lower()[:5] for w in re.findall(r"[^\W_]{3,}", question)}
        lines: list[tuple[int, str]] = []
        for raw_line in context.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("KONTEKST"):
                continue
            for sent in re.split(r"(?<=[.!?])\s+", line):
                if len(sent) < self.min_sentence_chars:
                    continue
                overlap = sum(1 for w in re.findall(r"[^\W_]{3,}", sent.lower()) if w[:5] in q_words)
                lines.append((overlap, sent))
        lines.sort(key=lambda pair: pair[0], reverse=True)
        chosen: list[str] = []
        seen: set[str] = set()
        for _, sent in lines:
            if sent not in seen:
                seen.add(sent)
                chosen.append(sent)
            if len(chosen) >= self.max_sentences:
                break
        if not chosen:
            return context.strip()
        return " ".join(chosen)


@llm_registry.register("ollama")
class OllamaLLMClient(LLMClient):
    """Local Ollama chat endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b-instruct",
        temperature: float = 0.1,
        timeout_seconds: float = 120.0,
        num_ctx: int = 8192,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.num_ctx = num_ctx

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout_seconds)
            resp.raise_for_status()
            return str(resp.json()["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError) as exc:
            raise ExternalServiceError(f"Ollama error: {exc}") from exc


@llm_registry.register("openai_compatible")
class OpenAICompatibleLLMClient(LLMClient):
    """OpenAI-compatible ``/chat/completions`` client (Groq, Gemini, vLLM, LM Studio...)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key_env: str = "LLM_API_KEY",
        temperature: float = 0.1,
        max_tokens: int = 900,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key_env = api_key_env
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        api_key = os.getenv(self.api_key_env, "")
        if not api_key:
            raise ConfigurationError(f"Missing API key in environment variable '{self.api_key_env}'")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"]).strip()
        except (httpx.HTTPError, KeyError, IndexError) as exc:
            raise ExternalServiceError(f"LLM API error: {exc}") from exc

