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


from src.documents.model_resolver import resolve_vision_model
from pydantic import BaseModel, Field

from src.documents.models import (
    DocumentType,
    Form1095A,
    Form1098,
    Form1098T,
    Form1099B,
    Form1099BSummary,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Form1099S,
    Form5498,
    FormK1,
    W2Batch,
    W2Data,
)
from src.documents.prompts import (
    FORM_1095_A_PROMPT,
    FORM_1098_PROMPT,
    FORM_1098_T_PROMPT,
    FORM_1099_B_PROMPT,
    FORM_1099_B_SUMMARY_PROMPT,
    FORM_1099_DIV_PROMPT,
    FORM_1099_G_PROMPT,
    FORM_1099_INT_PROMPT,
    FORM_1099_NEC_PROMPT,
    FORM_1099_R_PROMPT,
    FORM_1099_S_PROMPT,
    FORM_5498_PROMPT,
    FORM_K1_PROMPT,
    W2_MULTI_EXTRACTION_PROMPT,
)

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic


# Wrapper model for 1099-B multi-transaction extraction
class Form1099BExtraction(BaseModel):
    """Wrapper for 1099-B multi-transaction extraction."""

    transactions: list[Form1099B] = Field(
        default_factory=list, description="List of extracted transactions"
    )
    form_level_uncertain_fields: list[str] = Field(
        default_factory=list, description="Fields uncertain at the form level"
    )


# Type alias for extraction results
ExtractionResult = Union[
    W2Batch,
    W2Data,
    Form1099INT,
    Form1099DIV,
    Form1099NEC,
    Form1098,
    Form1099R,
    Form1099G,
    Form1098T,
    Form5498,
    Form1099S,
    FormK1,
    list[Form1099B],
    Form1099BSummary,
    Form1095A,
]

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
        DocumentType.FORM_1098: extract_1098,
        DocumentType.FORM_1099_R: extract_1099_r,
        DocumentType.FORM_1099_G: extract_1099_g,
        DocumentType.FORM_1098_T: extract_1098_t,
        DocumentType.FORM_5498: extract_5498,
        DocumentType.FORM_1099_S: extract_1099_s,
        DocumentType.FORM_K1: extract_k1,
        DocumentType.FORM_1099_B: extract_1099_b,
        DocumentType.FORM_1095_A: extract_1095_a,
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


async def extract_1098(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1098:
    """Extract 1098 Mortgage Interest Statement data using Claude Vision.

    Args:
        image_bytes: 1098 document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1098 with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1098_PROMPT,
        response_model=Form1098,
        client=client,
    )


async def extract_1099_r(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099R:
    """Extract 1099-R Retirement Distributions data using Claude Vision.

    Args:
        image_bytes: 1099-R document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099R with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_R_PROMPT,
        response_model=Form1099R,
        client=client,
    )


async def extract_1099_g(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099G:
    """Extract 1099-G Government Payments data using Claude Vision.

    Args:
        image_bytes: 1099-G document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099G with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_G_PROMPT,
        response_model=Form1099G,
        client=client,
    )


async def extract_1098_t(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1098T:
    """Extract 1098-T Tuition Statement data using Claude Vision.

    Args:
        image_bytes: 1098-T document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1098T with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1098_T_PROMPT,
        response_model=Form1098T,
        client=client,
    )


async def extract_5498(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form5498:
    """Extract 5498 IRA Contribution Information data using Claude Vision.

    Args:
        image_bytes: 5498 document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form5498 with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_5498_PROMPT,
        response_model=Form5498,
        client=client,
    )


async def extract_1099_s(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099S:
    """Extract 1099-S Real Estate Proceeds data using Claude Vision.

    Args:
        image_bytes: 1099-S document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099S with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_S_PROMPT,
        response_model=Form1099S,
        client=client,
    )


async def extract_k1(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> FormK1:
    """Extract Schedule K-1 data using Claude Vision.

    Extracts all data fields from a Schedule K-1 (Form 1065 Partnership or
    Form 1120-S S-Corporation) including Part I entity info, Part II partner/
    shareholder info, and Part III share of income/deductions/credits.

    Args:
        image_bytes: K-1 document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        FormK1 with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_K1_PROMPT,
        response_model=FormK1,
        client=client,
    )


async def extract_1099_b(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> list[Form1099B]:
    """Extract Form 1099-B transactions using Claude Vision.

    A single 1099-B form may contain multiple stock/security transactions.
    This function extracts each transaction separately with its own details.

    Args:
        image_bytes: 1099-B document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        List of Form1099B models, one per transaction on the form.

    Raises:
        ValueError: If media_type is not supported.
    """
    result = await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_B_PROMPT,
        response_model=Form1099BExtraction,
        client=client,
    )
    return result.transactions


async def extract_1099_b_summary(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1099BSummary:
    """Extract Form 1099-B summary totals using Claude Vision.

    For high-volume broker statements with many transactions, extracts
    category totals instead of individual transactions. Categories match
    IRS Form 8949 (A/B/D/E).

    Args:
        image_bytes: 1099-B document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1099BSummary with category totals.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1099_B_SUMMARY_PROMPT,
        response_model=Form1099BSummary,
        client=client,
    )


async def extract_1095_a(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | None" = None,
) -> Form1095A:
    """Extract Form 1095-A Health Insurance Marketplace Statement using Claude Vision.

    Extracts coverage information, monthly premiums, SLCSP premiums, and
    advance premium tax credit data needed for Form 8962 reconciliation.

    Args:
        image_bytes: 1095-A document image as bytes.
        media_type: MIME type of the image.
        client: Optional Anthropic client for dependency injection.

    Returns:
        Form1095A with all extracted fields and confidence metadata.

    Raises:
        ValueError: If media_type is not supported.
    """
    return await _extract_with_vision(
        image_bytes=image_bytes,
        media_type=media_type,
        prompt=FORM_1095_A_PROMPT,
        response_model=Form1095A,
        client=client,
    )


async def _extract_with_vision(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    response_model: type,
    client: "object | None" = None,
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

    # Import instructors and providers here to avoid circular imports.
    import instructor
    from anthropic import AsyncAnthropic as AnthropicClient
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as exc:
        AsyncOpenAI = None
        openai_import_error = exc
    else:
        openai_import_error = None

    from src.core.config import settings

    # Use provided client or create new one
    resolved_model = resolve_vision_model(settings.anthropic_model)
    if client is None:
        if resolved_model.provider == "openai":
            if AsyncOpenAI is None:
                raise ModuleNotFoundError(
                    "openai package is required for gpt-5.3/OpenAI vision flow"
                ) from openai_import_error
            if settings.openai_api_key is None:
                raise ValueError("OPENAI_API_KEY is required for gpt-5.3 model usage")
            client = AsyncOpenAI(api_key=settings.openai_api_key)
            # Type checkers can't infer union with `Any` here.
        elif settings.anthropic_api_key:
            client = AnthropicClient(api_key=settings.anthropic_api_key)
        else:
            client = AnthropicClient()

    # Wrap with instructor for structured output
    if resolved_model.provider == "openai":
        instructor_client = instructor.from_openai(client)
    else:
        instructor_client = instructor.from_anthropic(client)

    # Encode image to base64
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    # Call Claude Vision API
    if resolved_model.provider == "openai":
        message_content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": _build_openai_image_url(media_type, image_base64)},
            },
        ]
        result = await instructor_client.chat.completions.create(
            model=resolved_model.model,
            messages=[{"role": "user", "content": message_content}],
            max_tokens=2048,
            response_model=response_model,
        )
    else:
        result = await instructor_client.messages.create(
            model=resolved_model.model,
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


def _build_openai_image_url(media_type: str, image_base64: str) -> str:
    """Build an OpenAI-compatible inline image URL."""
    return f"data:{media_type};base64,{image_base64}"
