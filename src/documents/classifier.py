"""Document classifier using Claude Vision.

This module provides document classification for tax forms using Claude's vision
capabilities. It identifies the document type (W-2, 1099-INT, 1099-DIV, 1099-NEC)
from document images with confidence scoring.

Example:
    >>> from src.documents.classifier import classify_document
    >>> result = await classify_document(image_bytes, "image/jpeg")
    >>> print(f"Document type: {result.document_type}, confidence: {result.confidence}")
"""

from __future__ import annotations

import base64
from io import BytesIO
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from src.documents.models import DocumentType

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic


class ClassificationResult(BaseModel):
    """Document classification result.

    Attributes:
        document_type: The identified document type.
        confidence: Confidence score between 0.0 and 1.0.
        reasoning: Explanation for the classification decision.
    """

    document_type: DocumentType = Field(description="The identified tax document type")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score for classification")
    reasoning: str = Field(description="Explanation for the classification decision")


# Classification prompt describing distinguishing features of each document type
CLASSIFICATION_PROMPT = """You are a tax document classifier. Analyze the provided document image and identify its type.

Document Types and Distinguishing Features:

1. W-2 (Wage and Tax Statement):
   - Title: "Wage and Tax Statement" or "Form W-2"
   - Contains boxes labeled 1-20 for wages, taxes, and deductions
   - Has employee and employer sections with SSN and EIN
   - Common box labels: "Wages, tips, other compensation", "Federal income tax withheld"

2. 1099-INT (Interest Income):
   - Title: "Interest Income" or "Form 1099-INT"
   - Contains boxes for interest income amounts
   - Common fields: "Interest income" (Box 1), "Early withdrawal penalty" (Box 2)
   - Payer and recipient information sections

3. 1099-DIV (Dividends and Distributions):
   - Title: "Dividends and Distributions" or "Form 1099-DIV"
   - Contains boxes 1a, 1b, 2a, 2b, 2c, 2d for various dividend types
   - Common fields: "Total ordinary dividends", "Qualified dividends", "Capital gain distributions"
   - Payer and recipient information sections

4. 1099-NEC (Nonemployee Compensation):
   - Title: "Nonemployee Compensation" or "Form 1099-NEC"
   - Box 1 contains nonemployee compensation amount
   - Simpler layout compared to other 1099 forms
   - Used for independent contractor payments

If you cannot determine the document type with confidence, classify as UNKNOWN.

Analyze the document and provide:
1. document_type: One of W2, 1099-INT, 1099-DIV, 1099-NEC, or UNKNOWN
2. confidence: A score from 0.0 to 1.0 indicating classification confidence
3. reasoning: Brief explanation of why you classified it this way"""


SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


async def classify_document(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> ClassificationResult:
    """Classify tax document type from image using Claude Vision.

    Uses Claude's vision capabilities to identify the document type based on
    visual characteristics like form titles, box labels, and layout.

    Args:
        image_bytes: Document image as bytes.
        media_type: MIME type of the image. Supported types:
            - image/jpeg
            - image/png
            - image/gif
            - image/webp
        client: Optional Anthropic client for dependency injection in tests.

    Returns:
        ClassificationResult with document_type, confidence, and reasoning.

    Raises:
        ValueError: If media_type is not supported.
        anthropic.APIError: If the API request fails.

    Example:
        >>> with open("w2_form.jpg", "rb") as f:
        ...     result = await classify_document(f.read(), "image/jpeg")
        >>> print(result.document_type)  # DocumentType.W2
    """
    # Convert PDFs to images for classification
    if media_type == "application/pdf":
        image_bytes = _convert_pdf_to_image_bytes(image_bytes)
        media_type = "image/png"

    return await _classify_image(image_bytes, media_type, client)


async def _classify_image(
    image_bytes: bytes,
    media_type: str,
    client: "AsyncAnthropic | None" = None,
) -> ClassificationResult:
    """Classify an image using Claude Vision."""
    # Validate media type
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(
            f"Unsupported media type: {media_type}. Supported: {SUPPORTED_MEDIA_TYPES}"
        )

    # Import instructor and anthropic here to avoid circular imports
    import instructor
    from anthropic import AsyncAnthropic as AnthropicClient

    # Use provided client or create new one
    if client is None:
        from src.core.config import settings

        if settings.anthropic_api_key:
            client = AnthropicClient(api_key=settings.anthropic_api_key)
        else:
            client = AnthropicClient()

    # Wrap with instructor for structured output
    instructor_client = instructor.from_anthropic(client)

    # Encode image to base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Call Claude Vision API
    result = await instructor_client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": CLASSIFICATION_PROMPT,
                    },
                ],
            }
        ],
        response_model=ClassificationResult,
    )

    return result


def _convert_pdf_to_image_bytes(pdf_bytes: bytes) -> bytes:
    """Convert PDF bytes to PNG image bytes (first page only)."""
    try:
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise RuntimeError(
            "pdf2image is required for PDF classification. "
            "Install pdf2image and pillow, and ensure poppler is available."
        ) from exc

    images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, fmt="png")
    if not images:
        raise ValueError("No pages found in PDF for classification")

    buffer = BytesIO()
    images[0].save(buffer, format="PNG")
    return buffer.getvalue()


