"""Document extraction using Claude Vision API.

This module provides document extraction for tax forms using Claude's vision
capabilities with Instructor for validated Pydantic output. Each document type
has its own extraction function that returns the appropriate data model.

Example:
    >>> from src.documents.extractor import extract_document, extract_w2
    >>> from src.documents.models import DocumentType
    >>> 
    >>> # Extract using router function
    >>> result = await extract_document(image_bytes, DocumentType.W2, "image/jpeg")
    >>> print(f"Wages: {result.wages_tips_compensation}")
    >>>
    >>> # Or use type-specific function directly
    >>> w2 = await extract_w2(image_bytes, "image/jpeg")
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Union

from src.documents.models import (
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Batch,
    W2Data,
)
from src.documents.prompts import (
    FORM_1099_DIV_PROMPT,
    FORM_1099_INT_PROMPT,
    FORM_1099_NEC_PROMPT,
    W2_MULTI_EXTRACTION_PROMPT,
    W2_EXTRACTION_PROMPT,
)

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic


# Type alias for extraction results
ExtractionResult = Union[W2Batch, W2Data, Form1099INT, Form1099DIV, Form1099NEC]

# Supported media types for document images
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf"}


async def extract_document(
    image_bytes: bytes,
    document_type: DocumentType,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> ExtractionResult:
    """Extract document data based on type.

    Routes to the appropriate type-specific extractor based on document_type.
    This is the primary entry point for document extraction.

    Args:
        image_bytes: Document image as bytes.
        document_type: Type of document to extract (W2, 1099-INT, etc.).
        media_type: MIME type of the image (image/jpeg, image/png, etc.).
        client: Optional Anthropic client for dependency injection in tests.

    Returns:
        Extracted data model based on document_type:
        - W2Batch for DocumentType.W2
        - Form1099INT for DocumentType.FORM_1099_INT
        - Form1099DIV for DocumentType.FORM_1099_DIV
        - Form1099NEC for DocumentType.FORM_1099_NEC

    Raises:
        ValueError: If document_type is UNKNOWN or unsupported.

    Example:
        >>> result = await extract_document(image_bytes, DocumentType.W2)
        >>> print(f"Wages: {result.wages_tips_compensation}")
    """
    if document_type == DocumentType.UNKNOWN:
        raise ValueError("Cannot extract data from UNKNOWN document type. Classify first.")

    extractors = {
        DocumentType.W2: extract_w2,
        DocumentType.FORM_1099_INT: extract_1099_int,
        DocumentType.FORM_1099_DIV: extract_1099_div,
        DocumentType.FORM_1099_NEC: extract_1099_nec,
    }

    extractor = extractors.get(document_type)
    if extractor is None:
        raise ValueError(f"No extractor available for document type: {document_type}")

    return await extractor(image_bytes, media_type, client)


async def extract_w2(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> W2Batch:
    """Extract one or more W-2 forms using Claude Vision.

    Extracts all data fields from a W-2 Wage and Tax Statement image.
    The prompt instructs Claude to:
    - Extract all numbered boxes (1-20)
    - Format SSN as XXX-XX-XXXX
    - Format EIN as XX-XXXXXXX
    - Report confidence level (HIGH/MEDIUM/LOW)
    - Note any uncertain fields in uncertain_fields list

    Args:
        image_bytes: W-2 document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        W2Batch with one or more extracted W-2 forms.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=W2_MULTI_EXTRACTION_PROMPT,
        response_model=W2Batch,
        client=client,
    )


async def extract_1099_int(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099INT:
    """Extract 1099-INT form data using Claude Vision.

    Extracts all data fields from a 1099-INT Interest Income form image.

    Args:
        image_bytes: 1099-INT document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099INT with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_INT_PROMPT,
        response_model=Form1099INT,
        client=client,
    )


async def extract_1099_div(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099DIV:
    """Extract 1099-DIV form data using Claude Vision.

    Extracts all data fields from a 1099-DIV Dividends and Distributions form image.

    Args:
        image_bytes: 1099-DIV document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099DIV with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_DIV_PROMPT,
        response_model=Form1099DIV,
        client=client,
    )


async def extract_1099_nec(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099NEC:
    """Extract 1099-NEC form data using Claude Vision.

    Extracts all data fields from a 1099-NEC Nonemployee Compensation form image.

    Args:
        image_bytes: 1099-NEC document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099NEC with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_NEC_PROMPT,
        response_model=Form1099NEC,
        client=client,
    )


async def _extract_with_vision(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    response_model: type,
    client: "AsyncAnthropic | None" = None,
) -> ExtractionResult:
    """Internal function to extract document data using Claude Vision API.

    Args:
        image_bytes: Document image as bytes.
        media_type: MIME type of the image.
        prompt: Extraction prompt for the specific document type.
        response_model: Pydantic model class for the response.
        client: Optional Anthropic client.

    Returns:
        Extracted data as the specified response_model type.

    Raises:
        ValueError: If media_type is not supported.
    """
    # Validate media type
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(f"Unsupported media type: {media_type}. Supported: {SUPPORTED_MEDIA_TYPES}")

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
        max_tokens=2048,
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
                        "text": prompt,
                    },
                ],
            }
        ],
        response_model=response_model,
    )

    return result


