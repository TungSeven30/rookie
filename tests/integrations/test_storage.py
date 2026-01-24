"""Tests for storage integration module.

Tests cover:
- Filesystem detection for local paths and URLs
- File listing with detailed info
- File reading
- Edge cases and error handling
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest

from src.integrations.storage import get_filesystem, list_files, read_file


def _has_s3fs() -> bool:
    """Check if s3fs package is available."""
    try:
        import s3fs  # noqa: F401

        return True
    except ImportError:
        return False


def _has_gcsfs() -> bool:
    """Check if gcsfs package is available."""
    try:
        import gcsfs  # noqa: F401

        return True
    except ImportError:
        return False


class TestGetFilesystem:
    """Tests for get_filesystem function."""

    def test_local_path_returns_local_filesystem(self) -> None:
        """Local path returns LocalFileSystem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = get_filesystem(tmpdir)
            assert "LocalFileSystem" in type(fs).__name__

    def test_file_url_returns_local_filesystem(self) -> None:
        """file:// URL returns LocalFileSystem."""
        with tempfile.TemporaryDirectory() as tmpdir:
            url = f"file://{tmpdir}"
            fs = get_filesystem(url)
            assert "LocalFileSystem" in type(fs).__name__

    def test_relative_path_returns_local_filesystem(self) -> None:
        """Relative path returns LocalFileSystem."""
        fs = get_filesystem("./some/path")
        assert "LocalFileSystem" in type(fs).__name__

    @pytest.mark.skipif(
        not _has_s3fs(),
        reason="s3fs not installed",
    )
    def test_s3_url_returns_s3_filesystem(self) -> None:
        """s3:// URL returns S3FileSystem (lazy initialization)."""
        fs = get_filesystem("s3://bucket/path")
        assert "S3FileSystem" in type(fs).__name__

    @pytest.mark.skipif(
        not _has_gcsfs(),
        reason="gcsfs not installed",
    )
    def test_gs_url_returns_gcs_filesystem(self) -> None:
        """gs:// URL returns GCSFileSystem (lazy initialization)."""
        fs = get_filesystem("gs://bucket/path")
        assert "GCSFileSystem" in type(fs).__name__


class TestListFiles:
    """Tests for list_files function."""

    def test_list_files_returns_file_info(self) -> None:
        """list_files returns list of file info dicts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test content")

            files = list_files(tmpdir)
            assert len(files) == 1
            assert files[0]["name"] == "test.txt"
            assert files[0]["size"] > 0
            assert files[0]["type"] == "file"
            assert "mtime" in files[0]

    def test_list_files_returns_multiple_files(self) -> None:
        """list_files returns all files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple test files
            for name in ["a.pdf", "b.jpg", "c.png"]:
                open(os.path.join(tmpdir, name), "w").close()

            files = list_files(tmpdir)
            assert len(files) == 3
            names = {f["name"] for f in files}
            assert names == {"a.pdf", "b.jpg", "c.png"}

    def test_list_files_empty_directory_returns_empty_list(self) -> None:
        """list_files on empty directory returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            files = list_files(tmpdir)
            assert files == []

    def test_list_files_nonexistent_returns_empty_list(self) -> None:
        """list_files on nonexistent directory returns empty list."""
        files = list_files("/nonexistent/path/12345")
        assert files == []

    def test_list_files_excludes_directories(self) -> None:
        """list_files excludes subdirectories from results."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a file and a subdirectory
            open(os.path.join(tmpdir, "file.txt"), "w").close()
            os.makedirs(os.path.join(tmpdir, "subdir"))

            files = list_files(tmpdir)
            assert len(files) == 1
            assert files[0]["name"] == "file.txt"

    def test_list_files_with_subpath(self) -> None:
        """list_files with subpath lists files in subdirectory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subdirectory with file
            subdir = os.path.join(tmpdir, "subdir")
            os.makedirs(subdir)
            open(os.path.join(subdir, "nested.txt"), "w").close()

            files = list_files(tmpdir, "subdir")
            assert len(files) == 1
            assert files[0]["name"] == "nested.txt"

    def test_list_files_mtime_is_datetime(self) -> None:
        """list_files returns mtime as datetime object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test.txt"), "w").close()

            files = list_files(tmpdir)
            assert len(files) == 1
            assert isinstance(files[0]["mtime"], datetime)

    def test_list_files_with_file_url(self) -> None:
        """list_files works with file:// URL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            open(os.path.join(tmpdir, "test.txt"), "w").close()
            url = f"file://{tmpdir}"

            files = list_files(url)
            assert len(files) == 1
            assert files[0]["name"] == "test.txt"


class TestReadFile:
    """Tests for read_file function."""

    @pytest.mark.asyncio
    async def test_read_file_returns_bytes(self) -> None:
        """read_file returns file contents as bytes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("hello world")

            content = await read_file(tmpdir, "test.txt")
            assert content == b"hello world"

    @pytest.mark.asyncio
    async def test_read_file_binary_content(self) -> None:
        """read_file correctly reads binary content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "binary.bin")
            binary_data = bytes([0x00, 0xFF, 0x42, 0x89])
            with open(test_file, "wb") as f:
                f.write(binary_data)

            content = await read_file(tmpdir, "binary.bin")
            assert content == binary_data

    @pytest.mark.asyncio
    async def test_read_file_with_full_path(self) -> None:
        """read_file works with full path in url parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("content")

            # Pass full path as url, empty path
            content = await read_file(test_file, "")
            assert content == b"content"

    @pytest.mark.asyncio
    async def test_read_file_nonexistent_raises(self) -> None:
        """read_file raises FileNotFoundError for nonexistent file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(FileNotFoundError):
                await read_file(tmpdir, "nonexistent.txt")

    @pytest.mark.asyncio
    async def test_read_file_in_subdirectory(self) -> None:
        """read_file reads files in subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "sub", "dir")
            os.makedirs(subdir)
            test_file = os.path.join(subdir, "nested.txt")
            with open(test_file, "w") as f:
                f.write("nested content")

            content = await read_file(tmpdir, "sub/dir/nested.txt")
            assert content == b"nested content"
