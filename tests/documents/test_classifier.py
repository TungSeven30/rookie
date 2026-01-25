"""Tests for document classifier module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.documents.classifier import (
    CLASSIFICATION_PROMPT,
    ClassificationResult,
    classify_document,
    _classify_image,
)
from src.documents.models import DocumentType


class TestClassificationResult:
    """Tests for ClassificationResult model."""

    def test_valid_classification_result(self) -> None:
        """Test valid ClassificationResult creation."""
        result = ClassificationResult(
            document_type=DocumentType.W2,
            confidence=0.95,
            reasoning="Identified W-2 form by wage and tax statement header.",
        )
        assert result.document_type == DocumentType.W2
        assert result.confidence == 0.95
        assert "W-2" in result.reasoning

    def test_confidence_minimum_bound(self) -> None:
        """Test confidence must be at least 0.0."""
        with pytest.raises(ValueError, match="Input should be greater than or equal to 0"):
            ClassificationResult(
                document_type=DocumentType.W2,
                confidence=-0.1,
                reasoning="Invalid confidence",
            )

    def test_confidence_maximum_bound(self) -> None:
        """Test confidence must be at most 1.0."""
        with pytest.raises(ValueError, match="Input should be less than or equal to 1"):
            ClassificationResult(
                document_type=DocumentType.W2,
                confidence=1.1,
                reasoning="Invalid confidence",
            )

    def test_confidence_exactly_zero(self) -> None:
        """Test confidence of exactly 0.0 is valid."""
        result = ClassificationResult(
            document_type=DocumentType.UNKNOWN,
            confidence=0.0,
            reasoning="No confidence in classification.",
        )
        assert result.confidence == 0.0

    def test_confidence_exactly_one(self) -> None:
        """Test confidence of exactly 1.0 is valid."""
        result = ClassificationResult(
            document_type=DocumentType.W2,
            confidence=1.0,
            reasoning="Perfect confidence.",
        )
        assert result.confidence == 1.0

    @pytest.mark.parametrize(
        "doc_type",
        [
            DocumentType.W2,
            DocumentType.FORM_1099_INT,
            DocumentType.FORM_1099_DIV,
            DocumentType.FORM_1099_NEC,
            DocumentType.UNKNOWN,
        ],
    )
    def test_all_document_types_accessible(self, doc_type: DocumentType) -> None:
        """Test all document types can be used in ClassificationResult."""
        result = ClassificationResult(
            document_type=doc_type,
            confidence=0.8,
            reasoning=f"Classified as {doc_type.value}",
        )
        assert result.document_type == doc_type


class TestClassifyDocument:
    """Tests for classify_document async function."""

    @pytest.mark.asyncio
    async def test_classify_document_invalid_media_type(self) -> None:
        """Test classify_document raises for unsupported media type."""
        with pytest.raises(ValueError, match="Unsupported media type"):
            await _classify_image(b"test", "application/octet-stream")

    @pytest.mark.asyncio
    async def test_classify_document_valid_media_types(self) -> None:
        """Test all supported media types route to _classify_image."""
        fake_result = ClassificationResult(
            document_type=DocumentType.W2,
            confidence=0.9,
            reasoning="Test result",
        )
        with patch(
            "src.documents.classifier._classify_image",
            new=AsyncMock(return_value=fake_result),
        ):
            for media_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
                result = await classify_document(b"test", media_type)
                assert result == fake_result

    @pytest.mark.asyncio
    async def test_classify_document_accepts_client_parameter(self) -> None:
        """Test classify_document accepts a client parameter for DI."""
        fake_client = object()
        fake_result = ClassificationResult(
            document_type=DocumentType.FORM_1099_INT,
            confidence=0.88,
            reasoning="Test result",
        )
        with patch(
            "src.documents.classifier._classify_image",
            new=AsyncMock(return_value=fake_result),
        ) as mock_classify:
            result = await classify_document(
                b"test image",
                "image/jpeg",
                client=fake_client,
            )
        assert result == fake_result
        mock_classify.assert_called_once_with(b"test image", "image/jpeg", fake_client)

    @pytest.mark.asyncio
    async def test_classify_document_pdf_converts_to_image(self) -> None:
        """PDF inputs are converted to images before classification."""
        converted_bytes = b"fake png bytes"

        def fake_convert(pdf_bytes: bytes) -> bytes:
            assert pdf_bytes == b"%PDF-1.4"
            return converted_bytes

        async def fake_classify_image(
            image_bytes: bytes, media_type: str, client=None
        ) -> ClassificationResult:
            assert image_bytes == converted_bytes
            assert media_type == "image/png"
            return ClassificationResult(
                document_type=DocumentType.W2,
                confidence=0.9,
                reasoning="Converted PDF to image for classification.",
            )

        with patch(
            "src.documents.classifier._convert_pdf_to_image_bytes",
            side_effect=fake_convert,
        ):
            with patch(
                "src.documents.classifier._classify_image",
                side_effect=fake_classify_image,
            ):
                result = await classify_document(b"%PDF-1.4", "application/pdf")

        assert result.document_type == DocumentType.W2


class TestClassificationPrompt:
    """Tests for classification prompt content."""

    def test_prompt_describes_w2(self) -> None:
        """Test prompt contains W-2 distinguishing features."""
        assert "W-2" in CLASSIFICATION_PROMPT
        assert "Wage and Tax Statement" in CLASSIFICATION_PROMPT
        assert "boxes labeled 1-20" in CLASSIFICATION_PROMPT

    def test_prompt_describes_1099_int(self) -> None:
        """Test prompt contains 1099-INT distinguishing features."""
        assert "1099-INT" in CLASSIFICATION_PROMPT
        assert "Interest Income" in CLASSIFICATION_PROMPT

    def test_prompt_describes_1099_div(self) -> None:
        """Test prompt contains 1099-DIV distinguishing features."""
        assert "1099-DIV" in CLASSIFICATION_PROMPT
        assert "Dividends and Distributions" in CLASSIFICATION_PROMPT
        assert "boxes 1a, 1b, 2a" in CLASSIFICATION_PROMPT

    def test_prompt_describes_1099_nec(self) -> None:
        """Test prompt contains 1099-NEC distinguishing features."""
        assert "1099-NEC" in CLASSIFICATION_PROMPT
        assert "Nonemployee Compensation" in CLASSIFICATION_PROMPT

    def test_prompt_mentions_unknown_fallback(self) -> None:
        """Test prompt mentions UNKNOWN as fallback."""
        assert "UNKNOWN" in CLASSIFICATION_PROMPT
