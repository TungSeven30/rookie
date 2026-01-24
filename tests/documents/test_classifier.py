"""Tests for document classifier module."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

from src.documents.classifier import (
    CLASSIFICATION_PROMPT,
    ClassificationResult,
    _mock_classify,
    classify_document,
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


class TestMockClassify:
    """Tests for mock classification function."""

    def test_mock_classify_returns_result(self) -> None:
        """Test mock classify returns valid ClassificationResult."""
        result = _mock_classify(b"test image bytes")
        assert isinstance(result, ClassificationResult)
        assert isinstance(result.document_type, DocumentType)
        assert 0.0 <= result.confidence <= 1.0
        assert len(result.reasoning) > 0

    def test_mock_classify_deterministic(self) -> None:
        """Test mock classify is deterministic for same input."""
        input_bytes = b"consistent test data"
        result1 = _mock_classify(input_bytes)
        result2 = _mock_classify(input_bytes)
        assert result1.document_type == result2.document_type
        assert result1.confidence == result2.confidence
        assert result1.reasoning == result2.reasoning

    def test_mock_classify_different_inputs(self) -> None:
        """Test mock classify varies by input."""
        # Different lengths should give different results (based on modulo)
        results = []
        for i in range(5):
            # Create inputs with lengths 0, 1, 2, 3, 4 (mod 5 gives 0-4)
            result = _mock_classify(b"x" * i)
            results.append(result.document_type)
        # Should have variety in document types
        assert len(set(results)) > 1

    def test_mock_classify_unknown_has_lower_confidence(self) -> None:
        """Test UNKNOWN document type gets lower confidence."""
        # Input with length mod 5 == 4 gives UNKNOWN
        result = _mock_classify(b"xxxx")  # length 4
        assert result.document_type == DocumentType.UNKNOWN
        assert result.confidence <= 0.60

    def test_mock_classify_known_types_higher_confidence(self) -> None:
        """Test known document types get higher confidence."""
        # Input with length mod 5 == 0 gives W2
        result = _mock_classify(b"")  # length 0
        assert result.document_type == DocumentType.W2
        assert result.confidence >= 0.85

    def test_mock_classify_reasoning_matches_type(self) -> None:
        """Test mock reasoning message matches document type."""
        result = _mock_classify(b"")  # W2
        assert "W-2" in result.reasoning

        result = _mock_classify(b"x")  # 1099-INT
        assert "1099-INT" in result.reasoning


class TestClassifyDocument:
    """Tests for classify_document async function."""

    @pytest.mark.asyncio
    async def test_classify_document_mock_mode(self) -> None:
        """Test classify_document returns result in mock mode."""
        with patch.dict(os.environ, {"MOCK_LLM": "true"}):
            result = await classify_document(b"fake image bytes", "image/jpeg")
            assert isinstance(result, ClassificationResult)
            assert isinstance(result.document_type, DocumentType)

    @pytest.mark.asyncio
    async def test_classify_document_mock_mode_case_insensitive(self) -> None:
        """Test MOCK_LLM environment variable is case insensitive."""
        with patch.dict(os.environ, {"MOCK_LLM": "TRUE"}):
            result = await classify_document(b"test", "image/jpeg")
            assert isinstance(result, ClassificationResult)

    @pytest.mark.asyncio
    async def test_classify_document_invalid_media_type(self) -> None:
        """Test classify_document raises for unsupported media type."""
        with patch.dict(os.environ, {"MOCK_LLM": "false"}):
            with pytest.raises(ValueError, match="Unsupported media type"):
                await classify_document(b"test", "application/pdf")

    @pytest.mark.asyncio
    async def test_classify_document_valid_media_types(self) -> None:
        """Test all supported media types work in mock mode."""
        with patch.dict(os.environ, {"MOCK_LLM": "true"}):
            for media_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
                result = await classify_document(b"test", media_type)
                assert isinstance(result, ClassificationResult)

    @pytest.mark.asyncio
    async def test_classify_document_accepts_client_parameter(self) -> None:
        """Test classify_document accepts a client parameter for DI."""
        # This test verifies the function signature accepts a client parameter
        # for dependency injection. The actual API call is tested via mock mode.
        # Testing with a real client would require API credentials.

        # Verify the function can be called with mock mode using default client
        with patch.dict(os.environ, {"MOCK_LLM": "true"}):
            result = await classify_document(
                b"test image",
                "image/jpeg",
                client=None,  # Uses default
            )
            assert isinstance(result, ClassificationResult)


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
