"""Repository abstraction (Liskov-substitutable implementations).

A future SQL/ORM implementation only needs to subclass :class:`Repository` and register a
:class:`RepositoryFactory` under a new provider name.
"""

from __future__ import annotations

import json
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from kompas.core.config import resolve_path
from kompas.core.exceptions import NotFoundError, ValidationError
from kompas.core.registry import Registry

M = TypeVar("M", bound=BaseModel)


class Repository(ABC, Generic[M]):
    """CRUD contract for aggregates identified by ``id``."""

    @abstractmethod
    def get(self, entity_id: str) -> M: ...

    @abstractmethod
    def find(self, entity_id: str) -> M | None: ...

    @abstractmethod
    def list(self, predicate: Callable[[M], bool] | None = None) -> list[M]: ...

    @abstractmethod
    def add(self, entity: M) -> M: ...

    @abstractmethod
    def update(self, entity: M) -> M: ...

    @abstractmethod
    def delete(self, entity_id: str) -> None: ...

    def add_many(self, entities: Iterable[M]) -> None:
        for entity in entities:
            self.add(entity)

    def upsert(self, entity: M) -> M:
        return self.update(entity) if self.find(self._id(entity)) else self.add(entity)

    @staticmethod
    def _id(entity: BaseModel) -> str:
        return str(entity.id)  # type: ignore[attr-defined]


class InMemoryRepository(Repository[M]):
    """Thread-safe dict-backed repository (prototype / tests)."""

    def __init__(self, model: type[M], name: str) -> None:
        self.model = model
        self.name = name
        self._items: dict[str, M] = {}
        self._lock = threading.RLock()

    def get(self, entity_id: str) -> M:
        item = self.find(entity_id)
        if item is None:
            raise NotFoundError(f"{self.name}: '{entity_id}' not found")
        return item

    def find(self, entity_id: str) -> M | None:
        with self._lock:
            item = self._items.get(entity_id)
            return item.model_copy(deep=True) if item else None

    def list(self, predicate: Callable[[M], bool] | None = None) -> list[M]:
        with self._lock:
            items = [i.model_copy(deep=True) for i in self._items.values()]
        return [i for i in items if predicate is None or predicate(i)]

    def add(self, entity: M) -> M:
        with self._lock:
            key = self._id(entity)
            if key in self._items:
                raise ValidationError(f"{self.name}: '{key}' already exists")
            self._items[key] = entity.model_copy(deep=True)
            self._persist()
        return entity

    def update(self, entity: M) -> M:
        with self._lock:
            key = self._id(entity)
            if key not in self._items:
                raise NotFoundError(f"{self.name}: '{key}' not found")
            self._items[key] = entity.model_copy(deep=True)
            self._persist()
        return entity

    def delete(self, entity_id: str) -> None:
        with self._lock:
            if self._items.pop(entity_id, None) is None:
                raise NotFoundError(f"{self.name}: '{entity_id}' not found")
            self._persist()

    def _persist(self) -> None:
        """Hook for durable subclasses."""


class JsonFileRepository(InMemoryRepository[M]):
    """Simple durable repository: one JSON file per collection (single-instance deployments)."""

    def __init__(self, model: type[M], name: str, directory: Path) -> None:
        super().__init__(model, name)
        self.path = Path(directory) / f"{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_file():
            raw = json.loads(self.path.read_text(encoding="utf-8") or "[]")
            self._items = {str(r["id"]): model.model_validate(r) for r in raw}

    def _persist(self) -> None:
        payload = [item.model_dump(mode="json") for item in self._items.values()]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)


class RepositoryFactory(ABC):
    """Creates repositories for different aggregate types."""

    @abstractmethod
    def create(self, model: type[M], name: str) -> Repository[M]: ...


repository_registry: Registry[RepositoryFactory] = Registry("repository")


@repository_registry.register("memory")
class InMemoryRepositoryFactory(RepositoryFactory):
    def create(self, model: type[M], name: str) -> Repository[M]:
        return InMemoryRepository(model, name)


@repository_registry.register("json_file")
class JsonFileRepositoryFactory(RepositoryFactory):
    def __init__(self, directory: str = "data/runtime/store") -> None:
        self.directory = resolve_path(directory)

    def create(self, model: type[M], name: str) -> Repository[M]:
        return JsonFileRepository(model, name, self.directory)
