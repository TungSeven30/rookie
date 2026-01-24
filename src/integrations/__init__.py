"""Integrations module for external services and storage.

Provides unified access to storage systems through fsspec abstraction.
"""

from src.integrations.storage import get_filesystem, list_files, read_file

__all__ = [
    "get_filesystem",
    "list_files",
    "read_file",
]
