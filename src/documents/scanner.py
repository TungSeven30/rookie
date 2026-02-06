"""Client folder scanner for document discovery.

Scans client folders in storage systems to discover tax documents
for processing. Supports local filesystem and cloud storage.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from src.integrations.storage import get_filesystem, list_files

logger = logging.getLogger(__name__)

# Supported file extensions for tax documents (case-insensitive)
SUPPORTED_EXTENSIONS = frozenset({".pdf", ".jpg", ".jpeg", ".png"})


@dataclass
class ClientDocument:
    """Represents a discovered document in a client folder.

    Attributes:
        path: Full path to document in storage
        name: Filename only (without path)
        size: File size in bytes
        modified: Last modified timestamp
        extension: File extension (lowercase, without dot)
    """

    path: str
    name: str
    size: int
    modified: datetime
    extension: str


def scan_client_folder(
    storage_url: str,
    client_id: str,
    tax_year: int,
) -> list[ClientDocument]:
    """Scan client folder for tax documents.

    Folder convention: {storage_url}/{client_id}/{tax_year}/

    Args:
        storage_url: Base storage URL (s3://bucket, gs://bucket, /local/path)
        client_id: Client identifier
        tax_year: Tax year to scan

    Returns:
        List of discovered documents (pdf, jpg, jpeg, png only).
        Empty list if folder doesn't exist.

    Examples:
        >>> docs = scan_client_folder("/data", "client123", 2024)
        >>> # Scans /data/client123/2024/ for supported documents
    """
    # Build folder path using convention
    folder_path = f"{client_id}/{tax_year}"

    try:
        # Validate storage URL by attempting to get filesystem
        get_filesystem(storage_url)
    except Exception as e:
        logger.warning("Failed to get filesystem for %s: %s", storage_url, e)
        return []

    # Get file listing
    files = list_files(storage_url, folder_path)

    if not files:
        logger.debug(
            "No files found in client folder: %s/%s/%s",
            storage_url,
            client_id,
            tax_year,
        )
        return []

    documents: list[ClientDocument] = []

    for file_info in files:
        name = file_info.get("name", "")
        if not name:
            continue

        # Get extension (case-insensitive check)
        _, ext = os.path.splitext(name)
        ext_lower = ext.lower()

        # Filter for supported extensions only
        if ext_lower not in SUPPORTED_EXTENSIONS:
            continue

        # Extract modification time
        mtime = file_info.get("mtime")
        if mtime is None:
            mtime = datetime.now(timezone.utc)
        elif not isinstance(mtime, datetime):
            # Handle timestamp as float/int
            mtime = datetime.fromtimestamp(float(mtime), tz=timezone.utc)

        doc = ClientDocument(
            path=file_info.get("path", ""),
            name=name,
            size=file_info.get("size", 0),
            modified=mtime,
            extension=ext_lower.lstrip("."),  # Remove leading dot
        )
        documents.append(doc)

    # Sort by filename for deterministic ordering
    documents.sort(key=lambda d: d.name)

    logger.info(
        "Scanned client folder %s/%s/%s: found %d documents",
        storage_url,
        client_id,
        tax_year,
        len(documents),
    )

    return documents
