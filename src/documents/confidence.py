"""Confidence scoring for document extraction reliability.

This module calculates confidence scores for extracted document data based on
multiple factors: LLM self-reported confidence, field validation pass rates,
and presence of critical fields.

The confidence score determines whether extractions need human review:
- HIGH: score >= 0.85 AND all critical fields present
- MEDIUM: score >= 0.60
- LOW: score < 0.60

Example:
    >>> from src.documents.confidence import calculate_confidence, ConfidenceLevel
    >>> result = calculate_confidence(
    ...     llm_reported_confidence="HIGH",
    ...     field_validations={"ssn": True, "ein": True},
    ...     critical_fields_present={"employee_ssn": True, "employer_ein": True},
    ... )
    >>> print(f"Level: {result.level}, Score: {result.score:.2f}")
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.documents.models import ConfidenceLevel, DocumentType


@dataclass
class ConfidenceResult:
    """Confidence scoring result for an extraction.

    Attributes:
        level: Overall confidence level (HIGH, MEDIUM, LOW).
        score: Numeric score between 0.0 and 1.0.
        factors: Individual factor scores contributing to overall score.
        notes: Explanation notes, especially for low confidence cases.
    """

    level: ConfidenceLevel
    score: float
    factors: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# Critical fields that must be present for HIGH confidence by document type
CRITICAL_FIELDS: dict[DocumentType, list[str]] = {
    DocumentType.W2: [
        "employee_ssn",
        "employer_ein",
        "wages_tips_compensation",
        "federal_tax_withheld",
    ],
    DocumentType.FORM_1099_INT: [
        "payer_tin",
        "recipient_tin",
        "interest_income",
    ],
    DocumentType.FORM_1099_DIV: [
        "payer_tin",
        "recipient_tin",
        "total_ordinary_dividends",
    ],
    DocumentType.FORM_1099_NEC: [
        "payer_tin",
        "recipient_tin",
        "nonemployee_compensation",
    ],
    DocumentType.UNKNOWN: [],
}

# Weights for each factor in confidence calculation
WEIGHT_LLM = 0.3  # LLM self-reported confidence
WEIGHT_VALIDATION = 0.4  # Field format validation pass rate
WEIGHT_CRITICAL = 0.3  # Critical field presence

# Confidence level mapping from string to numeric
LLM_CONFIDENCE_SCORES: dict[str, float] = {
    "HIGH": 1.0,
    "MEDIUM": 0.6,
    "LOW": 0.3,
}

# Thresholds for confidence levels
THRESHOLD_HIGH = 0.85
THRESHOLD_MEDIUM = 0.60


def get_critical_fields(document_type: DocumentType) -> list[str]:
    """Get critical field names for a document type.

    Critical fields are required for HIGH confidence. If any critical
    field is missing, the confidence level cannot be HIGH regardless
    of the numeric score.

    Args:
        document_type: The type of document.

    Returns:
        List of critical field names for the document type.

    Example:
        >>> fields = get_critical_fields(DocumentType.W2)
        >>> print(fields)
        ['employee_ssn', 'employer_ein', 'wages_tips_compensation', 'federal_tax_withheld']
    """
    return CRITICAL_FIELDS.get(document_type, [])


def calculate_confidence(
    llm_reported_confidence: str,
    field_validations: dict[str, bool],
    critical_fields_present: dict[str, bool],
    critical_field_names: list[str] | None = None,
) -> ConfidenceResult:
    """Calculate overall extraction confidence.

    Uses a weighted combination of three factors:
    - LLM self-reported confidence (30%): The confidence level reported by
      the extraction model itself.
    - Field validation pass rate (40%): What percentage of fields passed
      format validation (e.g., SSN format check).
    - Critical field presence (30%): What percentage of critical fields
      are present in the extraction.

    Args:
        llm_reported_confidence: "HIGH", "MEDIUM", or "LOW" from extraction.
        field_validations: Dict mapping field_name -> passed_validation.
        critical_fields_present: Dict mapping critical_field -> is_present.
        critical_field_names: Optional list of critical field names. If not
            provided, uses all keys from critical_fields_present.

    Returns:
        ConfidenceResult with level, score, factors breakdown, and notes.

    Example:
        >>> result = calculate_confidence(
        ...     llm_reported_confidence="HIGH",
        ...     field_validations={"ssn": True, "ein": True, "wages": True},
        ...     critical_fields_present={
        ...         "employee_ssn": True,
        ...         "employer_ein": True,
        ...         "wages_tips_compensation": True,
        ...         "federal_tax_withheld": True,
        ...     },
        ... )
        >>> result.level
        <ConfidenceLevel.HIGH: 'HIGH'>
    """
    notes: list[str] = []

    # Calculate LLM confidence factor
    llm_score = LLM_CONFIDENCE_SCORES.get(llm_reported_confidence.upper(), 0.3)
    if llm_reported_confidence.upper() not in LLM_CONFIDENCE_SCORES:
        notes.append(f"Unknown LLM confidence value: {llm_reported_confidence}")

    # Calculate validation pass rate factor
    if field_validations:
        passed_count = sum(1 for v in field_validations.values() if v)
        validation_score = passed_count / len(field_validations)
        failed_fields = [k for k, v in field_validations.items() if not v]
        if failed_fields:
            notes.append(f"Validation failed for: {', '.join(failed_fields)}")
    else:
        # No validations means we can't assess quality
        validation_score = 0.5
        notes.append("No field validations performed")

    # Calculate critical field presence factor
    if critical_fields_present:
        present_count = sum(1 for v in critical_fields_present.values() if v)
        critical_score = present_count / len(critical_fields_present)
        missing_fields = [k for k, v in critical_fields_present.items() if not v]
        if missing_fields:
            notes.append(f"Missing critical fields: {', '.join(missing_fields)}")
    else:
        # No critical fields to check
        critical_score = 1.0  # Don't penalize if no critical fields defined

    # Check if all critical fields are present
    all_critical_present = all(critical_fields_present.values()) if critical_fields_present else True

    # Calculate weighted score
    score = (
        (WEIGHT_LLM * llm_score)
        + (WEIGHT_VALIDATION * validation_score)
        + (WEIGHT_CRITICAL * critical_score)
    )

    # Determine confidence level
    # HIGH requires score >= 0.85 AND all critical fields present
    if score >= THRESHOLD_HIGH and all_critical_present:
        level = ConfidenceLevel.HIGH
    elif score >= THRESHOLD_MEDIUM:
        level = ConfidenceLevel.MEDIUM
        if not all_critical_present and score >= THRESHOLD_HIGH:
            notes.append("Score meets HIGH threshold but critical fields are missing")
    else:
        level = ConfidenceLevel.LOW

    # Build factors breakdown
    factors = {
        "llm_confidence": llm_score,
        "field_validation": validation_score,
        "critical_fields": critical_score,
    }

    return ConfidenceResult(
        level=level,
        score=score,
        factors=factors,
        notes=notes,
    )
