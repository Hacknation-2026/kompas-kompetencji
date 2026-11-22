"""Generic plugin registry – the backbone of configuration-driven composition.

Each pluggable abstraction (LLM client, retriever, renderer, notifier, ...) owns a
:class:`Registry`. Concrete implementations register themselves with a decorator::

    llm_registry = Registry[LLMClient]("llm")

    @llm_registry.register("ollama")
    class OllamaClient(LLMClient): ...

and are instantiated from YAML (``provider`` + ``params``)::

    client = llm_registry.create(settings.llm)

Adding a new provider never requires modifying existing code (Open/Closed principle),
and consumers depend only on the abstract base class (Dependency Inversion).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from kompas.core.exceptions import ConfigurationError

T = TypeVar("T")


class Registry(Generic[T]):
    """Name -> factory mapping for one family of components."""

    def __init__(self, kind: str) -> None:
        self.kind = kind
        self._factories: dict[str, Callable[..., T]] = {}

    def register(self, name: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Class/function decorator registering a factory under ``name``."""

        def decorator(factory: Callable[..., T]) -> Callable[..., T]:
            if name in self._factories:
                raise ConfigurationError(f"{self.kind} provider '{name}' already registered")
            self._factories[name] = factory
            return factory

        return decorator

    def available(self) -> list[str]:
        """Sorted provider names."""
        return sorted(self._factories)

    def __contains__(self, name: object) -> bool:
        return name in self._factories

    def get(self, name: str) -> Callable[..., T]:
        """Return the factory registered under ``name``."""
        try:
            return self._factories[name]
        except KeyError as exc:
            raise ConfigurationError(
                f"Unknown {self.kind} provider '{name}'. Available: {', '.join(self.available()) or '-'}"
            ) from exc

    def create(self, provider: str, params: dict[str, Any] | None = None, **dependencies: Any) -> T:
        """Instantiate ``provider`` with YAML ``params`` plus injected ``dependencies``.

        Dependencies not accepted by the factory signature are silently dropped so that the
        container can offer a common set of collaborators to all providers.
        """
        factory = self.get(provider)
        kwargs: dict[str, Any] = dict(params or {})
        kwargs.update(self._accepted(factory, dependencies))
        try:
            return factory(**kwargs)
        except TypeError as exc:
            raise ConfigurationError(f"Invalid params for {self.kind} provider '{provider}': {exc}") from exc

    @staticmethod
    def _accepted(factory: Callable[..., Any], dependencies: dict[str, Any]) -> dict[str, Any]:
        try:
            signature = inspect.signature(factory)
        except (TypeError, ValueError):  # pragma: no cover - builtins without signature
            return dependencies
        params = signature.parameters.values()
        if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params):
            return dependencies
        names = {p.name for p in params}
        return {k: v for k, v in dependencies.items() if k in names}
