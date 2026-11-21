"""Electronic document management gateway (EZD RP / EZD PUW adapter contract)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from kompas.core.config import resolve_path
from kompas.core.registry import Registry


class ArchiveGateway(ABC):
    """Stores finalised evaluation sheets in an external EZD repository."""

    @abstractmethod
    def store(self, evaluation_id: str, filename: str, content: bytes) -> str:
        """Persist document and return an external archive reference/URI."""


archive_registry: Registry[ArchiveGateway] = Registry("archive")


@archive_registry.register("local_folder")
class LocalFolderArchive(ArchiveGateway):
    """Stores exported documents in a local folder (prototype stub for EZD)."""

    def __init__(self, directory: str = "data/output/archive") -> None:
        self.directory = resolve_path(directory)

    def store(self, evaluation_id: str, filename: str, content: bytes) -> str:
        target_dir = Path(self.directory) / evaluation_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(content)
        return str(target)

