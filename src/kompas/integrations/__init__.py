"""Integration abstractions for HR systems (e.g. QNT) and document management (EZD)."""

from kompas.integrations.ezd import ArchiveGateway, LocalFolderArchive, archive_registry
from kompas.integrations.hr import HRGateway, StaticFileHRGateway, hr_registry

__all__ = [
    "ArchiveGateway",
    "HRGateway",
    "LocalFolderArchive",
    "StaticFileHRGateway",
    "archive_registry",
    "hr_registry",
]
