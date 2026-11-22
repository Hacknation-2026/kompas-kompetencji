"""SQL-backed repositories (stdlib SQLite + PostgreSQL via SQLAlchemy 2.0)."""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from kompas.core.config import resolve_path
from kompas.core.exceptions import ConfigurationError, NotFoundError, ValidationError
from kompas.core.registry import Registry
from kompas.persistence.repository import Repository, RepositoryFactory, repository_registry

M = TypeVar("M", bound=BaseModel)


class SqliteRepository(Repository[M], Generic[M]):
    """Thread-safe SQLite repository storing JSON-serialized aggregates per collection."""

    def __init__(self, model: type[M], name: str, db_path: str | Path) -> None:
        self.model = model
        self.name = name
        self._lock = threading.RLock()
        target = str(db_path)
        if target != ":memory:":
            Path(target).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(target, check_same_thread=False)
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS {self._table()} ("
            "id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        self._conn.commit()

    def _table(self) -> str:
        safe = "".join(ch for ch in self.name if ch.isalnum() or ch == "_")
        if not safe:
            raise ConfigurationError(f"Invalid collection name: {self.name!r}")
        return f"kompas_{safe}"

    def get(self, entity_id: str) -> M:
        item = self.find(entity_id)
        if item is None:
            raise NotFoundError(f"{self.name}: '{entity_id}' not found")
        return item

    def find(self, entity_id: str) -> M | None:
        with self._lock:
            row = self._conn.execute(
                f"SELECT payload FROM {self._table()} WHERE id = ?",
                (entity_id,),
            ).fetchone()
        return self.model.model_validate_json(row[0]) if row else None

    def list(self, predicate: Callable[[M], bool] | None = None) -> list[M]:
        with self._lock:
            rows = self._conn.execute(f"SELECT payload FROM {self._table()} ORDER BY id").fetchall()
        items = [self.model.model_validate_json(r[0]) for r in rows]
        return [i for i in items if predicate is None or predicate(i)]

    def add(self, entity: M) -> M:
        key = self._id(entity)
        payload = entity.model_dump_json()
        now = datetime.now(UTC).isoformat()
        with self._lock:
            try:
                self._conn.execute(
                    f"INSERT INTO {self._table()} (id, payload, updated_at) VALUES (?, ?, ?)",
                    (key, payload, now),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValidationError(f"{self.name}: '{key}' already exists") from exc
        return entity

    def update(self, entity: M) -> M:
        key = self._id(entity)
        payload = entity.model_dump_json()
        now = datetime.now(UTC).isoformat()
        with self._lock:
            cur = self._conn.execute(
                f"UPDATE {self._table()} SET payload = ?, updated_at = ? WHERE id = ?",
                (payload, now, key),
            )
            self._conn.commit()
            if cur.rowcount == 0:
                raise NotFoundError(f"{self.name}: '{key}' not found")
        return entity

    def delete(self, entity_id: str) -> None:
        with self._lock:
            cur = self._conn.execute(f"DELETE FROM {self._table()} WHERE id = ?", (entity_id,))
            self._conn.commit()
            if cur.rowcount == 0:
                raise NotFoundError(f"{self.name}: '{entity_id}' not found")


class SqlAlchemyRepository(Repository[M], Generic[M]):
    """PostgreSQL / SQLAlchemy 2.0 repository for production deployments."""

    def __init__(self, model: type[M], name: str, engine: Any) -> None:
        try:
            from sqlalchemy import Column, DateTime, MetaData, String, Table, Text
        except ImportError as exc:  # pragma: no cover - optional prod extra
            raise ConfigurationError(
                "sqlalchemy is not installed. Install production extras: pip install -e '.[prod]'."
            ) from exc

        self.model = model
        self.name = name
        self.engine = engine
        safe = "".join(ch for ch in name if ch.isalnum() or ch == "_")
        if not safe:
            raise ConfigurationError(f"Invalid collection name: {name!r}")
        metadata = MetaData()
        self.table = Table(
            f"kompas_{safe}",
            metadata,
            Column("id", String(128), primary_key=True),
            Column("payload", Text, nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(self.engine, checkfirst=True)

    def get(self, entity_id: str) -> M:
        item = self.find(entity_id)
        if item is None:
            raise NotFoundError(f"{self.name}: '{entity_id}' not found")
        return item

    def find(self, entity_id: str) -> M | None:
        from sqlalchemy import select

        stmt = select(self.table.c.payload).where(self.table.c.id == entity_id)
        with self.engine.connect() as conn:
            row = conn.execute(stmt).fetchone()
        return self.model.model_validate_json(row[0]) if row else None

    def list(self, predicate: Callable[[M], bool] | None = None) -> list[M]:
        from sqlalchemy import select

        stmt = select(self.table.c.payload).order_by(self.table.c.id)
        with self.engine.connect() as conn:
            rows = conn.execute(stmt).fetchall()
        items = [self.model.model_validate_json(r[0]) for r in rows]
        return [i for i in items if predicate is None or predicate(i)]

    def add(self, entity: M) -> M:
        from sqlalchemy import insert
        from sqlalchemy.exc import IntegrityError

        key = self._id(entity)
        stmt = insert(self.table).values(
            id=key,
            payload=entity.model_dump_json(),
            updated_at=datetime.now(UTC),
        )
        try:
            with self.engine.begin() as conn:
                conn.execute(stmt)
        except IntegrityError as exc:
            raise ValidationError(f"{self.name}: '{key}' already exists") from exc
        return entity

    def update(self, entity: M) -> M:
        from sqlalchemy import update

        key = self._id(entity)
        stmt = (
            update(self.table)
            .where(self.table.c.id == key)
            .values(payload=entity.model_dump_json(), updated_at=datetime.now(UTC))
        )
        with self.engine.begin() as conn:
            res = conn.execute(stmt)
            if res.rowcount == 0:
                raise NotFoundError(f"{self.name}: '{key}' not found")
        return entity

    def delete(self, entity_id: str) -> None:
        from sqlalchemy import delete

        stmt = delete(self.table).where(self.table.c.id == entity_id)
        with self.engine.begin() as conn:
            res = conn.execute(stmt)
            if res.rowcount == 0:
                raise NotFoundError(f"{self.name}: '{entity_id}' not found")


@repository_registry.register("sqlite")
class SqliteRepositoryFactory(RepositoryFactory):
    """Creates SQLite-backed repositories (zero-dependency durable SQL)."""

    def __init__(self, path: str = "data/runtime/kompas.db") -> None:
        self.db_path = ":memory:" if path == ":memory:" else resolve_path(path)

    def create(self, model: type[M], name: str) -> Repository[M]:
        return SqliteRepository(model, name, self.db_path)


@repository_registry.register("postgres")
class SqlAlchemyRepositoryFactory(RepositoryFactory):
    """Creates PostgreSQL repositories via SQLAlchemy 2.0."""

    def __init__(
        self,
        dsn: str | None = None,
        dsn_env: str = "KOMPAS_DATABASE_URL",
        pool_pre_ping: bool = True,
    ) -> None:
        resolved_dsn = os.environ.get(dsn_env) or dsn
        if not resolved_dsn:
            raise ConfigurationError(
                f"PostgreSQL DSN not configured. Set {dsn_env} or repository.params.dsn."
            )
        try:
            from sqlalchemy import create_engine
        except ImportError as exc:  # pragma: no cover - optional prod extra
            raise ConfigurationError(
                "sqlalchemy is not installed. Install production extras: pip install -e '.[prod]'."
            ) from exc
        self.engine = create_engine(resolved_dsn, pool_pre_ping=pool_pre_ping)

    def create(self, model: type[M], name: str) -> Repository[M]:
        return SqlAlchemyRepository(model, name, self.engine)


def ensure_registered() -> Registry[RepositoryFactory]:
    return repository_registry
