"""HR / Kadry system gateway (e.g. QNT adapter contract)."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path

from kompas.core.config import resolve_path
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
