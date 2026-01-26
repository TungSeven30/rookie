"""Document models for tax form extraction and scanning.

This module provides:
- Pydantic models for common tax documents with field validation
- Client folder scanner for document discovery
- Document classifier for identifying document types
- Confidence scoring for extraction reliability
- Document extraction using Claude Vision API
"""

from src.documents.classifier import ClassificationResult, classify_document
from src.documents.confidence import (
    CRITICAL_FIELDS,
    ConfidenceResult,
    calculate_confidence,
    get_critical_fields,
    get_critical_fields_for_1099b,
)
from src.documents.extractor import (
    extract_1095_a,
    extract_1098,
    extract_1098_t,
    extract_1099_b,
    extract_1099_b_summary,
    extract_1099_div,
    extract_1099_g,
    extract_1099_int,
    extract_1099_nec,
    extract_1099_r,
    extract_1099_s,
    extract_5498,
    extract_document,
    extract_k1,
    extract_w2,
)
from src.documents.models import (
    Box12Code,
    ConfidenceLevel,
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
    validate_ein,
    validate_ssn,
)
from src.documents.scanner import ClientDocument, scan_client_folder
from src.documents.validation import DocumentValidator, ValidationResult

__all__ = [
    # Document models
    "Box12Code",
    "ConfidenceLevel",
    "DocumentType",
    "Form1095A",
    "Form1098",
    "Form1098T",
    "Form1099B",
    "Form1099BSummary",
    "Form1099DIV",
    "Form1099G",
    "Form1099INT",
    "Form1099NEC",
    "Form1099R",
    "Form1099S",
    "Form5498",
    "FormK1",
    "W2Batch",
    "W2Data",
    "validate_ein",
    "validate_ssn",
    # Scanner
    "ClientDocument",
    "scan_client_folder",
    # Classifier
    "ClassificationResult",
    "classify_document",
    # Confidence
    "CRITICAL_FIELDS",
    "ConfidenceResult",
    "calculate_confidence",
    "get_critical_fields",
    "get_critical_fields_for_1099b",
    # Extractor
    "extract_document",
    "extract_w2",
    "extract_1099_int",
    "extract_1099_div",
    "extract_1099_nec",
    "extract_1098",
    "extract_1099_r",
    "extract_1099_g",
    "extract_1098_t",
    "extract_5498",
    "extract_1099_s",
    "extract_k1",
    "extract_1099_b",
    "extract_1099_b_summary",
    "extract_1095_a",
    # Validation
    "DocumentValidator",
    "ValidationResult",
]
