"""Generic repositories. Swap implementation via ``repository.provider`` in config."""

from kompas.persistence.repository import (
    InMemoryRepository,
    JsonFileRepository,
    Repository,
    RepositoryFactory,
    repository_registry,
)
from kompas.persistence.sql import (
    SqlAlchemyRepository,
    SqlAlchemyRepositoryFactory,
    SqliteRepository,
    SqliteRepositoryFactory,
)

__all__ = [
    "InMemoryRepository",
    "JsonFileRepository",
    "Repository",
    "RepositoryFactory",
    "SqlAlchemyRepository",
    "SqlAlchemyRepositoryFactory",
    "SqliteRepository",
    "SqliteRepositoryFactory",
    "repository_registry",
]
