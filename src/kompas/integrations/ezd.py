"""Electronic document management gateway (EZD RP / EZD PUW adapter contract)."""

from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from pathlib import Path

import httpx

from kompas.core.config import resolve_path
from kompas.core.exceptions import ConfigurationError, ExternalServiceError
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


@archive_registry.register("ezd_rp")
class EzdRpArchiveGateway(ArchiveGateway):
    """REST adapter pushing finalized evaluation sheets into EZD RP / EZD PUW personal files."""

    def __init__(
        self,
        base_url: str,
        api_key_env: str = "EZD_RP_API_KEY",
        category: str = "akta_osobowe",
        timeout_seconds: float = 20.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key_env = api_key_env
        self.category = category
        self.timeout_seconds = timeout_seconds

    def store(self, evaluation_id: str, filename: str, content: bytes) -> str:
        token = os.environ.get(self.api_key_env, "").strip()
        if not token:
            raise ConfigurationError(f"Brak klucza API EZD RP w zmiennej środowiskowej {self.api_key_env}")
        payload = {
            "evaluation_id": evaluation_id,
            "filename": filename,
            "category": self.category,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/documents/archive",
                json=payload,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=self.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Błąd komunikacji z EZD RP: {exc}") from exc

        return str(data.get("archive_ref") or data.get("uri") or f"ezd-rp://{evaluation_id}/{filename}")
