"""Tests for client folder scanner module.

Tests cover:
- Document discovery with filtering by extension
- ClientDocument dataclass attributes
- Folder path construction
- Edge cases (empty folders, nonexistent folders)
- Deterministic ordering
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest

from src.documents.scanner import (
    SUPPORTED_EXTENSIONS,
    ClientDocument,
    scan_client_folder,
)


class TestClientDocument:
    """Tests for ClientDocument dataclass."""

    def test_client_document_has_correct_attributes(self) -> None:
        """ClientDocument has all expected attributes."""
        doc = ClientDocument(
            path="/storage/client/2024/w2.pdf",
            name="w2.pdf",
            size=1024,
            modified=datetime.now(timezone.utc),
            extension="pdf",
        )
        assert doc.path == "/storage/client/2024/w2.pdf"
        assert doc.name == "w2.pdf"
        assert doc.size == 1024
        assert isinstance(doc.modified, datetime)
        assert doc.extension == "pdf"

    def test_client_document_extension_without_dot(self) -> None:
        """ClientDocument stores extension without leading dot."""
        doc = ClientDocument(
            path="/test.jpg",
            name="test.jpg",
            size=0,
            modified=datetime.now(timezone.utc),
            extension="jpg",
        )
        assert doc.extension == "jpg"
        assert not doc.extension.startswith(".")


class TestSupportedExtensions:
    """Tests for supported file extensions."""

    def test_pdf_is_supported(self) -> None:
        """PDF extension is supported."""
        assert ".pdf" in SUPPORTED_EXTENSIONS

    def test_jpg_is_supported(self) -> None:
        """JPG extension is supported."""
        assert ".jpg" in SUPPORTED_EXTENSIONS

    def test_jpeg_is_supported(self) -> None:
        """JPEG extension is supported."""
        assert ".jpeg" in SUPPORTED_EXTENSIONS

    def test_png_is_supported(self) -> None:
        """PNG extension is supported."""
        assert ".png" in SUPPORTED_EXTENSIONS

    def test_txt_is_not_supported(self) -> None:
        """TXT extension is not supported."""
        assert ".txt" not in SUPPORTED_EXTENSIONS

    def test_docx_is_not_supported(self) -> None:
        """DOCX extension is not supported."""
        assert ".docx" not in SUPPORTED_EXTENSIONS


class TestScanClientFolder:
    """Tests for scan_client_folder function."""

    def test_scan_finds_pdf_files(self) -> None:
        """scan_client_folder finds PDF files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "w2.pdf"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "w2.pdf"
            assert docs[0].extension == "pdf"

    def test_scan_finds_jpg_files(self) -> None:
        """scan_client_folder finds JPG files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "receipt.jpg"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "receipt.jpg"
            assert docs[0].extension == "jpg"

    def test_scan_finds_jpeg_files(self) -> None:
        """scan_client_folder finds JPEG files (alternate extension)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "photo.jpeg"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "photo.jpeg"
            assert docs[0].extension == "jpeg"

    def test_scan_finds_png_files(self) -> None:
        """scan_client_folder finds PNG files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "scan.png"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "scan.png"
            assert docs[0].extension == "png"

    def test_scan_filters_unsupported_extensions(self) -> None:
        """scan_client_folder filters out unsupported file types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            # Create supported and unsupported files
            open(os.path.join(client_dir, "w2.pdf"), "w").close()
            open(os.path.join(client_dir, "notes.txt"), "w").close()
            open(os.path.join(client_dir, "spreadsheet.xlsx"), "w").close()
            open(os.path.join(client_dir, "document.docx"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "w2.pdf"

    def test_scan_case_insensitive_extension(self) -> None:
        """scan_client_folder matches extensions case-insensitively."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            # Mixed case extensions
            open(os.path.join(client_dir, "w2.PDF"), "w").close()
            open(os.path.join(client_dir, "receipt.Jpg"), "w").close()
            open(os.path.join(client_dir, "scan.PNG"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 3

    def test_scan_returns_empty_for_nonexistent_folder(self) -> None:
        """scan_client_folder returns empty list for nonexistent folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Don't create the client folder
            docs = scan_client_folder(tmpdir, "nonexistent", 2024)
            assert docs == []

    def test_scan_returns_empty_for_empty_folder(self) -> None:
        """scan_client_folder returns empty list for empty folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert docs == []

    def test_scan_builds_correct_path(self) -> None:
        """scan_client_folder builds path as {storage_url}/{client_id}/{tax_year}."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the expected path structure
            client_dir = os.path.join(tmpdir, "client-abc-123", "2025")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "test.pdf"), "w").close()

            docs = scan_client_folder(tmpdir, "client-abc-123", 2025)
            assert len(docs) == 1
            assert "client-abc-123" in docs[0].path
            assert "2025" in docs[0].path

    def test_scan_results_sorted_by_filename(self) -> None:
        """scan_client_folder returns results sorted by filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            # Create files in non-alphabetical order
            open(os.path.join(client_dir, "z_last.pdf"), "w").close()
            open(os.path.join(client_dir, "a_first.pdf"), "w").close()
            open(os.path.join(client_dir, "m_middle.jpg"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            names = [d.name for d in docs]
            assert names == ["a_first.pdf", "m_middle.jpg", "z_last.pdf"]

    def test_scan_finds_multiple_document_types(self) -> None:
        """scan_client_folder finds all supported document types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            open(os.path.join(client_dir, "w2.pdf"), "w").close()
            open(os.path.join(client_dir, "1099.jpg"), "w").close()
            open(os.path.join(client_dir, "receipt.jpeg"), "w").close()
            open(os.path.join(client_dir, "bank_stmt.png"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 4
            extensions = {d.extension for d in docs}
            assert extensions == {"pdf", "jpg", "jpeg", "png"}

    def test_scan_document_has_size(self) -> None:
        """scan_client_folder returns documents with file size."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            test_file = os.path.join(client_dir, "test.pdf")
            with open(test_file, "w") as f:
                f.write("some content here")

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].size > 0

    def test_scan_document_has_modified_datetime(self) -> None:
        """scan_client_folder returns documents with modification time."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)
            open(os.path.join(client_dir, "test.pdf"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert isinstance(docs[0].modified, datetime)

    def test_scan_with_different_tax_years(self) -> None:
        """scan_client_folder scans correct year folder."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create folders for multiple years
            for year in [2023, 2024, 2025]:
                year_dir = os.path.join(tmpdir, "client1", str(year))
                os.makedirs(year_dir)
                open(os.path.join(year_dir, f"w2_{year}.pdf"), "w").close()

            # Scan only 2024
            docs = scan_client_folder(tmpdir, "client1", 2024)
            assert len(docs) == 1
            assert docs[0].name == "w2_2024.pdf"

    def test_scan_ignores_subdirectories(self) -> None:
        """scan_client_folder only scans top-level files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client_dir = os.path.join(tmpdir, "client1", "2024")
            os.makedirs(client_dir)

            # Create file at top level
            open(os.path.join(client_dir, "top_level.pdf"), "w").close()

            # Create subdirectory with file (should be ignored)
            subdir = os.path.join(client_dir, "subfolder")
            os.makedirs(subdir)
            open(os.path.join(subdir, "nested.pdf"), "w").close()

            docs = scan_client_folder(tmpdir, "client1", 2024)
            # Only top-level file should be found
            assert len(docs) == 1
            assert docs[0].name == "top_level.pdf"
