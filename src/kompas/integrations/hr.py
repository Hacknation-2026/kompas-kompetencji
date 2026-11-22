"""HR / Kadry system gateway (e.g. QNT adapter contract)."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from kompas.core.config import resolve_path
from kompas.core.exceptions import ConfigurationError, ExternalServiceError
from kompas.core.registry import Registry
from kompas.domain.people import Employee


class HRGateway(ABC):
    """Read-only contract for synchronizing employee master data."""

    @abstractmethod
    def fetch_employees(self) -> list[Employee]: ...


hr_registry: Registry[HRGateway] = Registry("hr_system")


@hr_registry.register("static_file")
class StaticFileHRGateway(HRGateway):
    """Reads fictional/sample employees from a JSON file (prototype stub for QNT)."""

    def __init__(self, path: str = "data/samples/employees.json") -> None:
        self.path = resolve_path(path)

    def fetch_employees(self) -> list[Employee]:
        if not Path(self.path).is_file():
            return []
        raw = json.loads(Path(self.path).read_text(encoding="utf-8"))
        return [Employee.model_validate(item) for item in raw]


@hr_registry.register("qnt")
class QntHrGateway(HRGateway):
    """REST adapter for QNT HR system (organizational structure, dates, civil-servant status)."""

    def __init__(
        self,
        base_url: str,
        api_key_env: str = "QNT_API_KEY",
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.timeout_seconds = timeout_seconds

    def fetch_employees(self) -> list[Employee]:
        token = os.environ.get(self.api_key_env, "").strip()
        if not token:
            raise ConfigurationError(f"Brak klucza API QNT w zmiennej środowiskowej {self.api_key_env}")
        try:
            resp = httpx.get(
                f"{self.base_url}/employees",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            payload = resp.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Błąd komunikacji z systemem QNT: {exc}") from exc

        rows = payload.get("items", payload) if isinstance(payload, dict) else payload
        return [Employee.model_validate(item) for item in rows]
