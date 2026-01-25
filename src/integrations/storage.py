"""Storage integration using fsspec for filesystem abstraction.

Provides unified access to local filesystem and cloud storage (S3, GCS)
through fsspec's protocol detection.
"""

import asyncio
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

import fsspec


def get_filesystem(url: str) -> fsspec.AbstractFileSystem:
    """Get filesystem for URL, auto-detecting protocol.

    Args:
        url: Storage URL (file://, s3://, gs://, or local path)

    Returns:
        Filesystem instance for the protocol

    Examples:
        get_filesystem("s3://bucket/path") -> S3FileSystem
        get_filesystem("/local/path") -> LocalFileSystem
        get_filesystem("file:///local/path") -> LocalFileSystem
    """
    parsed = urlparse(url)

    # For local paths without scheme or with file:// scheme
    if not parsed.scheme or parsed.scheme == "file":
        return fsspec.filesystem("file")

    # For cloud protocols (s3://, gs://, etc.)
    return fsspec.filesystem(parsed.scheme)


async def read_file(url: str, path: str = "") -> bytes:
    """Read file bytes from storage.

    Args:
        url: Base storage URL
        path: File path within storage (optional if url is full path)

    Returns:
        File contents as bytes
    """
    fs = get_filesystem(url)
    full_path = build_full_path(url, path)

    return await asyncio.to_thread(_read_file_sync, fs, full_path)


def list_files(url: str, path: str = "") -> list[dict]:
    """List files in storage path.

    Args:
        url: Base storage URL
        path: Subdirectory path (optional)

    Returns:
        List of file info dicts with name, size, type, mtime
    """
    fs = get_filesystem(url)
    full_path = build_full_path(url, path)

    # Check if path exists
    if not fs.exists(full_path):
        return []

    # Get file details
    try:
        items = fs.ls(full_path, detail=True)
    except FileNotFoundError:
        return []

    result = []
    for item in items:
        # Skip directories
        if item.get("type") == "directory":
            continue

        # Extract filename from path
        item_path = item.get("name", "")
        name = os.path.basename(item_path)

        # Get modification time
        mtime = item.get("mtime")
        if mtime is not None:
            if isinstance(mtime, (int, float)):
                mtime = datetime.fromtimestamp(mtime, tz=timezone.utc)
        else:
            mtime = datetime.now(timezone.utc)

        result.append(
            {
                "name": name,
                "path": item_path,
                "size": item.get("size", 0),
                "type": "file",
                "mtime": mtime,
            }
        )

    return result


def build_full_path(url: str, path: str) -> str:
    """Build full path from base URL and relative path.

    Args:
        url: Base storage URL
        path: Relative path within storage

    Returns:
        Full path for filesystem operations
    """
    parsed = urlparse(url)

    if not parsed.scheme or parsed.scheme == "file":
        # Local filesystem
        base = parsed.path if parsed.path else url
        if path:
            return os.path.join(base, path)
        return base

    # Cloud storage - combine netloc and path
    base = f"{parsed.netloc}{parsed.path}" if parsed.netloc else parsed.path
    if path:
        return f"{base.rstrip('/')}/{path.lstrip('/')}"
    return base


def _read_file_sync(fs: fsspec.AbstractFileSystem, path: str) -> bytes:
    """Read file contents synchronously."""
    with fs.open(path, "rb") as f:
        return f.read()


async def write_file(url: str, path: str, content: bytes) -> str:
    """Write file bytes to storage.

    Args:
        url: Base storage URL
        path: File path within storage
        content: File contents as bytes

    Returns:
        Full storage path written to.
    """
    fs = get_filesystem(url)
    full_path = build_full_path(url, path)
    parsed = urlparse(url)
    if not parsed.scheme or parsed.scheme == "file":
        directory = os.path.dirname(full_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
    await asyncio.to_thread(_write_file_sync, fs, full_path, content)
    return full_path


def _write_file_sync(
    fs: fsspec.AbstractFileSystem, path: str, content: bytes
) -> None:
    """Write file contents synchronously."""
    with fs.open(path, "wb") as f:
        f.write(content)
