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
from typing import Any, TYPE_CHECKING

from src.documents.model_resolver import resolve_vision_model
from pydantic import BaseModel, Field

from src.documents.models import DocumentType

if TYPE_CHECKING:
    from anthropic import AsyncAnthropic
    from openai import AsyncOpenAI


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

5. 1098 (Mortgage Interest Statement):
   - Title: "Mortgage Interest Statement" or "Form 1098"
   - Contains mortgage interest (Box 1), outstanding principal (Box 2)
   - Has lender/recipient and borrower/payer sections
   - Common fields: "Mortgage interest received", "Points paid", "Property taxes"

6. 1099-R (Distributions From Pensions, Annuities, Retirement):
   - Title: "Distributions From Pensions, Annuities, Retirement or Profit-Sharing Plans" or "Form 1099-R"
   - Contains gross distribution (Box 1), taxable amount (Box 2a)
   - Has distribution code (Box 7) and IRA/SEP/SIMPLE checkbox
   - Common fields: "Gross distribution", "Taxable amount", "Federal income tax withheld"

7. 1099-G (Government Payments):
   - Title: "Certain Government Payments" or "Form 1099-G"
   - Contains unemployment compensation (Box 1), state tax refund (Box 2)
   - Issued by government agencies
   - Common fields: "Unemployment compensation", "State or local income tax refunds"

8. 1098-T (Tuition Statement):
   - Title: "Tuition Statement" or "Form 1098-T"
   - Contains payments received (Box 1), scholarships (Box 5)
   - Issued by educational institutions
   - Common fields: "Payments received for qualified tuition", "Scholarships or grants"

9. 5498 (IRA Contribution Information):
   - Title: "IRA Contribution Information" or "Form 5498"
   - Contains IRA contributions (Box 1), Roth IRA contributions (Box 10)
   - Has trustee/issuer and participant sections
   - Common fields: "IRA contributions", "Rollover contributions", "Fair market value"

10. 1099-S (Proceeds from Real Estate Transactions):
    - Title: "Proceeds From Real Estate Transactions" or "Form 1099-S"
    - Contains gross proceeds (Box 2), date of closing (Box 1)
    - Has property address/description (Box 3)
    - Common fields: "Gross proceeds", "Address or legal description"

11. K-1 (Schedule K-1):
    - Title: "Schedule K-1" from Partnership (Form 1065) or S-Corporation (Form 1120-S)
    - Contains entity information (Part I), partner/shareholder information (Part II)
    - Contains boxes for various income, deductions, credits (Part III)
    - Common fields: "Ordinary business income", "Net rental real estate income",
      "Guaranteed payments", "Interest income", "Distributions"
    - Look for "Schedule K-1" header and "Partner's Share" or "Shareholder's Share"

12. 1099-B (Proceeds from Broker and Barter Exchange Transactions):
    - Title: "Proceeds From Broker and Barter Exchange Transactions" or "Form 1099-B"
    - Contains stock/security sales with dates acquired/sold, proceeds, cost basis
    - Shows gain/loss calculations and wash sale adjustments
    - Common fields: "Proceeds", "Cost or other basis", "Date sold", "Description"
    - Look for broker name and multiple transaction listings

13. 1095-A (Health Insurance Marketplace Statement):
    - Title: "Health Insurance Marketplace Statement" or "Form 1095-A"
    - Shows monthly premiums, SLCSP amounts, and advance payments of premium tax credit
    - Contains coverage dates and marketplace policy information
    - Common fields: "Monthly enrollment premiums", "Monthly SLCSP premiums",
      "Monthly advance payment of PTC"
    - Look for "1095-A" and Marketplace coverage information

If you cannot determine the document type with confidence, classify as UNKNOWN.

Analyze the document and provide:
1. document_type: One of W2, 1099-INT, 1099-DIV, 1099-NEC, 1098, 1099-R, 1099-G, 1098-T, 5498, 1099-S, K-1, 1099-B, 1095-A, or UNKNOWN
2. confidence: A score from 0.0 to 1.0 indicating classification confidence
3. reasoning: Brief explanation of why you classified it this way"""


SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


async def classify_document(
    image_bytes: bytes,
    media_type: str = "image/jpeg",
    client: "AsyncAnthropic | AsyncOpenAI | Any | None" = None,
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
    client: "AsyncAnthropic | AsyncOpenAI | Any | None" = None,
) -> ClassificationResult:
    """Classify an image using Claude Vision."""
    # Validate media type
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ValueError(
            f"Unsupported media type: {media_type}. Supported: {SUPPORTED_MEDIA_TYPES}"
        )

    # Import instructors and providers here to avoid circular imports.
    import instructor
    from anthropic import AsyncAnthropic as AnthropicClient
    try:
        from openai import AsyncOpenAI as OpenAIClient
    except ModuleNotFoundError as exc:
        OpenAIClient = None
        openai_import_error = exc
    else:
        openai_import_error = None

    from src.core.config import settings

    resolved_model = resolve_vision_model(settings.anthropic_model)

    # Use provided client or create new one
    if client is None:
        if resolved_model.provider == "openai":
            if OpenAIClient is None:
                raise ModuleNotFoundError(
                    "openai package is required for gpt-5.3/OpenAI vision flow"
                ) from openai_import_error
            if settings.openai_api_key is None:
                raise ValueError("OPENAI_API_KEY is required for gpt-5.3 model usage")
            client = OpenAIClient(api_key=settings.openai_api_key)
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

    # Call vision API
    if resolved_model.provider == "openai":
        message_content = [
            {"type": "text", "text": CLASSIFICATION_PROMPT},
            {"type": "image_url", "image_url": {"url": _build_openai_image_url(media_type, image_base64)}},
        ]
        result = await instructor_client.chat.completions.create(
            model=resolved_model.model,
            messages=[{"role": "user", "content": message_content}],
            max_tokens=512,
            response_model=ClassificationResult,
        )
    else:
        result = await instructor_client.messages.create(
            model=resolved_model.model,
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


def _build_openai_image_url(media_type: str, image_base64: str) -> str:
    """Build an OpenAI-compatible inline image URL."""
    return f"data:{media_type};base64,{image_base64}"


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
