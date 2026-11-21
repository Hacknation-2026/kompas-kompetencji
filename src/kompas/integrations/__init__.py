"""Integration abstractions for HR systems (e.g. QNT) and document management (EZD)."""

from kompas.integrations.ezd import (
    ArchiveGateway,
    EzdRpArchiveGateway,
    LocalFolderArchive,
    archive_registry,
)
from kompas.integrations.hr import HRGateway, QntHrGateway, StaticFileHRGateway, hr_registry

__all__ = [
    "ArchiveGateway",
    "EzdRpArchiveGateway",
    "HRGateway",
    "LocalFolderArchive",
    "QntHrGateway",
    "StaticFileHRGateway",
    "archive_registry",
    "hr_registry",
]
