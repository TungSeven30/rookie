"""Document models for tax form extraction and scanning.

This module provides:
- Pydantic models for common tax documents with field validation
- Client folder scanner for document discovery
- Document classifier for identifying document types
- Confidence scoring for extraction reliability
"""

from src.documents.classifier import ClassificationResult, classify_document
from src.documents.confidence import (
    CRITICAL_FIELDS,
    ConfidenceResult,
    calculate_confidence,
    get_critical_fields,
)
from src.documents.models import (
    Box12Code,
    ConfidenceLevel,
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Data,
    validate_ein,
    validate_ssn,
)
from src.documents.scanner import ClientDocument, scan_client_folder

__all__ = [
    # Document models
    "Box12Code",
    "ConfidenceLevel",
    "DocumentType",
    "Form1099DIV",
    "Form1099INT",
    "Form1099NEC",
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
]
