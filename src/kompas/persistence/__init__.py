"""Generic repositories. Swap implementation via ``repository.provider`` in config."""

from kompas.persistence.repository import (
    InMemoryRepository,
    JsonFileRepository,
    Repository,
    RepositoryFactory,
    repository_registry,
)

__all__ = [
    "InMemoryRepository",
    "JsonFileRepository",
    "Repository",
    "RepositoryFactory",
    "repository_registry",
]
