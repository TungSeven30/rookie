"""Personal Tax Agent for orchestrating tax preparation workflow.

This module provides the main agent entry point that coordinates:
- Document scanning and discovery (PTAX-02)
- Document classification and extraction
- Missing document detection (PTAX-15)
- Conflict detection (PTAX-16)
- Tax calculation and credits evaluation
- Prior year comparison (PTAX-12)
- Output generation (PTAX-13, PTAX-14)

Example:
    >>> from src.agents.personal_tax.agent import PersonalTaxAgent
    >>> agent = PersonalTaxAgent(storage_url="s3://bucket", output_dir=Path("/output"))
    >>> result = await agent.process("client123", 2024, session)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from src.agents.personal_tax.calculator import (
    DeductionResult,
    IncomeSummary,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    calculate_deductions,
    calculate_tax,
    compare_years,
    evaluate_credits,
)
from src.agents.personal_tax.output import (
    generate_drake_worksheet,
    generate_preparer_notes,
)
from src.context.builder import AgentContext, build_agent_context
from src.core.logging import get_logger
from src.documents.classifier import ClassificationResult, classify_document
from src.documents.extractor import extract_document
from src.documents.models import (
    ConfidenceLevel,
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Data,
)
from src.documents.scanner import ClientDocument, scan_client_folder
from src.integrations.storage import read_file

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.models.task import Task

logger = get_logger(__name__)


class EscalationRequired(Exception):
    """Raised when agent needs human intervention.

    Attributes:
        reasons: List of reasons requiring escalation.
        result: Optional result payload for CPA review.
    """

    def __init__(
        self, reasons: list[str], result: "PersonalTaxResult | None" = None
    ) -> None:
        """Initialize with escalation reasons.

        Args:
            reasons: List of reasons requiring human attention.
            result: Optional result payload for CPA review.
        """
        self.reasons = reasons
        self.result = result
        super().__init__(f"Escalation required: {', '.join(reasons)}")


@dataclass
class PersonalTaxResult:
    """Result of personal tax agent execution.

    Attributes:
        drake_worksheet_path: Path to generated Drake worksheet Excel file.
        preparer_notes_path: Path to generated preparer notes Markdown file.
        income_summary: Aggregated income from all documents.
        tax_result: Tax calculation result with liability and credits.
        variances: List of significant variances from prior year.
        extractions: List of extraction metadata dicts.
        escalations: List of escalation reasons (if any).
        overall_confidence: Aggregate confidence level (HIGH/MEDIUM/LOW).
    """

    drake_worksheet_path: Path
    preparer_notes_path: Path
    income_summary: IncomeSummary
    tax_result: TaxResult
    variances: list[VarianceItem]
    extractions: list[dict[str, Any]]
    escalations: list[str]
    overall_confidence: str


class PersonalTaxAgent:
    """Personal Tax Agent for simple returns (W-2, 1099-INT/DIV/NEC).

    Orchestrates the complete tax preparation workflow:
    1. Load client context (profile, prior year)
    2. Scan client folder for documents
    3. Classify and extract each document
    4. Check for missing expected documents
    5. Check for conflicts across documents
    6. Aggregate income and calculate tax
    7. Compare with prior year
    8. Generate outputs (Drake worksheet, preparer notes)
    9. Handle escalations

    Attributes:
        storage_url: Base URL for document storage.
        output_dir: Directory for output files.
        escalations: List of accumulated escalation reasons.
    """

    def __init__(
        self,
        storage_url: str,
        output_dir: Path,
    ) -> None:
        """Initialize Personal Tax Agent.

        Args:
            storage_url: Base URL for document storage (s3://, gs://, /local/path).
            output_dir: Directory where output files will be written.
        """
        self.storage_url = storage_url
        self.output_dir = output_dir
        self.escalations: list[str] = []

    async def process(
        self,
        client_id: str,
        tax_year: int,
        session: "AsyncSession",
        filing_status: str = "single",
    ) -> PersonalTaxResult:
        """Process personal tax return.

        Executes the complete workflow for preparing a personal tax return:
        scanning documents, extracting data, calculating tax, and generating
        outputs for CPA review.

        Args:
            client_id: Client identifier.
            tax_year: Tax year to process.
            session: Database session for context loading.
            filing_status: Filing status for deductions/brackets.
                One of: single, mfj (married filing jointly),
                mfs (married filing separately), hoh (head of household).

        Returns:
            PersonalTaxResult with all outputs and metadata.

        Raises:
            EscalationRequired: If missing documents or conflicts require
                human attention.
        """
        logger.info(
            "personal_tax_agent_start",
            client_id=client_id,
            tax_year=tax_year,
            filing_status=filing_status,
        )

        # Reset escalations for this run
        self.escalations = []

        # 1. Load context (PTAX-01)
        context = await self._load_context(session, client_id, tax_year)

        # 2. Scan for documents (PTAX-02)
        documents = self._scan_documents(client_id, tax_year)

        # 3. Classify and extract each document
        extractions = await self._extract_documents(documents)

        # 4. Check for missing documents (PTAX-15)
        self._check_missing_documents(context, extractions)

        # 5. Check for conflicts (PTAX-16)
        self._check_conflicts(extractions)

        # 6. Aggregate income and calculate tax
        income_summary, deduction_result, tax_result = self._calculate_tax(
            extractions, filing_status, tax_year
        )

        # 7. Compare with prior year (PTAX-12)
        variances = self._compare_prior_year(context, income_summary, tax_result)

        # 8. Generate outputs (PTAX-13, PTAX-14)
        worksheet_path, notes_path = self._generate_outputs(
            context=context,
            extractions=extractions,
            income_summary=income_summary,
            deduction_result=deduction_result,
            tax_result=tax_result,
            variances=variances,
            filing_status=filing_status,
            tax_year=tax_year,
        )

        # 9. Determine overall confidence
        overall_confidence = self._determine_overall_confidence(extractions)

        result = PersonalTaxResult(
            drake_worksheet_path=worksheet_path,
            preparer_notes_path=notes_path,
            income_summary=income_summary,
            tax_result=tax_result,
            variances=variances,
            extractions=extractions,
            escalations=self.escalations,
            overall_confidence=overall_confidence,
        )

        # 10. Check for escalations
        if self.escalations:
            logger.warning(
                "personal_tax_agent_escalation",
                client_id=client_id,
                tax_year=tax_year,
                reasons=self.escalations,
            )
            raise EscalationRequired(self.escalations, result=result)

        logger.info(
            "personal_tax_agent_complete",
            client_id=client_id,
            tax_year=tax_year,
            documents_processed=len(extractions),
            overall_confidence=overall_confidence,
        )

        return result

    async def _load_context(
        self,
        session: "AsyncSession",
        client_id: str,
        tax_year: int,
    ) -> AgentContext:
        """Load client context for processing.

        Args:
            session: Database session.
            client_id: Client identifier.
            tax_year: Tax year.

        Returns:
            AgentContext with client profile and prior year data.
        """
        try:
            context = await build_agent_context(
                session=session,
                client_id=int(client_id),
                task_type="personal_tax",
                tax_year=tax_year,
            )
            return context
        except ValueError as e:
            # Client not found - create minimal context
            logger.warning(
                "client_not_found",
                client_id=client_id,
                error=str(e),
            )
            return AgentContext(
                client_id=0,
                client_name=f"Client {client_id}",
                tax_year=tax_year,
                task_type="personal_tax",
            )

    def _scan_documents(
        self,
        client_id: str,
        tax_year: int,
    ) -> list[ClientDocument]:
        """Scan client folder for documents.

        Args:
            client_id: Client identifier.
            tax_year: Tax year.

        Returns:
            List of discovered documents.

        Raises:
            EscalationRequired: If no documents found.
        """
        documents = scan_client_folder(
            self.storage_url,
            client_id,
            tax_year,
        )

        if not documents:
            self.escalations.append("No documents found in client folder")
            raise EscalationRequired(self.escalations)

        logger.info(
            "documents_scanned",
            client_id=client_id,
            tax_year=tax_year,
            count=len(documents),
        )

        return documents

    async def _extract_documents(
        self,
        documents: list[ClientDocument],
    ) -> list[dict[str, Any]]:
        """Classify and extract data from all documents.

        Args:
            documents: List of discovered documents.

        Returns:
            List of extraction result dicts with type, filename,
            confidence, and data. PDF files are processed per page.
        """
        extractions: list[dict[str, Any]] = []

        for doc in documents:
            try:
                # Read file bytes
                image_bytes = await read_file(self.storage_url, doc.path)

                # Determine media type from extension
                media_type = self._get_media_type(doc.extension)

                if media_type == "application/pdf":
                    pages = self._split_pdf_pages(image_bytes)
                    page_media_type = "image/png"
                else:
                    pages = [image_bytes]
                    page_media_type = media_type

                for page_number, page_bytes in enumerate(pages, start=1):
                    page_filename = (
                        doc.name
                        if len(pages) == 1
                        else f"{doc.name} (page {page_number})"
                    )

                    # Classify document
                    classification = await classify_document(page_bytes, page_media_type)
                    original_type = classification.document_type
                    original_confidence = classification.confidence
                    original_reasoning = classification.reasoning
                    classification_overridden = False

                    filename_hint = self._infer_document_type_from_filename(page_filename)
                    if (
                        filename_hint is not None
                        and filename_hint != classification.document_type
                    ):
                        logger.warning(
                            "classification_overridden_by_filename",
                            filename=page_filename,
                            classified=classification.document_type.value,
                            inferred=filename_hint.value,
                            confidence=classification.confidence,
                        )
                        classification = ClassificationResult(
                            document_type=filename_hint,
                            confidence=min(0.65, classification.confidence),
                            reasoning=f"Filename hint: {page_filename}",
                        )
                        classification_overridden = True

                    if classification.document_type == DocumentType.UNKNOWN:
                        logger.warning(
                            "unknown_document_type",
                            filename=page_filename,
                            confidence=classification.confidence,
                        )
                        continue

                    # Extract data
                    data = await extract_document(
                        page_bytes,
                        classification.document_type,
                        page_media_type,
                    )
                    multiple_forms_detected = (
                        isinstance(data, W2Data)
                        and "multiple_forms_detected" in data.uncertain_fields
                    )
                    if multiple_forms_detected:
                        reason = (
                            "Multiple W-2 forms detected on a single page. "
                            f"Split the file and re-upload: {page_filename}"
                        )
                        if reason not in self.escalations:
                            self.escalations.append(reason)
                            logger.warning(
                                "multiple_w2_forms_detected",
                                filename=page_filename,
                            )

                    extractions.append(
                        {
                            "type": classification.document_type,
                            "document_type": classification.document_type.value,
                            "filename": page_filename,
                            "confidence": data.confidence.value,
                            "data": data,
                            "classification": classification,
                            "classification_confidence": classification.confidence,
                            "classification_reasoning": classification.reasoning,
                            "classification_overridden": classification_overridden,
                            "multiple_forms_detected": multiple_forms_detected,
                            "classification_original_type": (
                                original_type.value if classification_overridden else None
                            ),
                            "classification_original_confidence": (
                                original_confidence if classification_overridden else None
                            ),
                            "classification_original_reasoning": (
                                original_reasoning if classification_overridden else None
                            ),
                        }
                    )

                    logger.info(
                        "document_extracted",
                        filename=page_filename,
                        document_type=classification.document_type.value,
                        confidence=data.confidence.value,
                    )

            except Exception as e:
                logger.error(
                    "extraction_failed",
                    filename=doc.name,
                    error=str(e),
                )
                self.escalations.append(f"Failed to extract {doc.name}: {str(e)}")

        return extractions

    def _get_media_type(self, extension: str) -> str:
        """Get MIME type from file extension.

        Args:
            extension: File extension without dot.

        Returns:
            MIME type string.
        """
        media_types = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
        }
        return media_types.get(extension.lower(), "image/jpeg")

    def _infer_document_type_from_filename(
        self, filename: str
    ) -> DocumentType | None:
        """Infer document type from filename hints.

        Args:
            filename: Original filename (may include page suffix).

        Returns:
            DocumentType inferred from filename or None if no match.
        """
        normalized = filename.lower()
        if "w-2" in normalized or "w2" in normalized:
            return DocumentType.W2
        return None

    def _split_pdf_pages(self, pdf_bytes: bytes) -> list[bytes]:
        """Convert PDF bytes into a list of PNG page bytes.

        Args:
            pdf_bytes: Raw PDF bytes.

        Returns:
            List of PNG-encoded page images.

        Raises:
            RuntimeError: If pdf2image is not installed.
            ValueError: If the PDF contains no pages.
        """
        try:
            from pdf2image import convert_from_bytes
        except ImportError as exc:
            raise RuntimeError(
                "pdf2image is required for PDF extraction. "
                "Install pdf2image and pillow, and ensure poppler is available."
            ) from exc

        images = convert_from_bytes(pdf_bytes, fmt="png")
        if not images:
            raise ValueError("No pages found in PDF for extraction")

        page_bytes: list[bytes] = []
        for image in images:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            page_bytes.append(buffer.getvalue())

        return page_bytes

    def _get_expected_document_types(
        self,
        prior_year_return: dict[str, Any] | None,
    ) -> set[DocumentType]:
        """Determine expected document types based on prior year.

        Args:
            prior_year_return: Prior year return data or None.

        Returns:
            Set of expected DocumentType values.
        """
        # Base expectation: at least one W-2 for most returns
        expected = {DocumentType.W2}

        if prior_year_return is None:
            return expected

        # Check prior year for other income types (nested or flat schema)
        prior_income = prior_year_return.get("income")
        income_data = prior_income if isinstance(prior_income, dict) else prior_year_return

        if income_data.get("interest", 0) > 0:
            expected.add(DocumentType.FORM_1099_INT)

        if income_data.get("dividends", 0) > 0:
            expected.add(DocumentType.FORM_1099_DIV)

        if income_data.get("self_employment", 0) > 0:
            expected.add(DocumentType.FORM_1099_NEC)

        return expected

    def _check_missing_documents(
        self,
        context: AgentContext,
        extractions: list[dict[str, Any]],
    ) -> None:
        """Check for missing expected documents (PTAX-15).

        Args:
            context: Agent context with prior year data.
            extractions: List of extraction results.
        """
        expected_types = self._get_expected_document_types(context.prior_year_return)
        found_types = {e["type"] for e in extractions}
        missing = expected_types - found_types

        if missing:
            for doc_type in missing:
                self.escalations.append(f"Missing expected document: {doc_type.value}")
                logger.warning(
                    "missing_expected_document",
                    document_type=doc_type.value,
                )

        if DocumentType.W2 in missing:
            for ext in extractions:
                filename = ext.get("filename", "")
                inferred = self._infer_document_type_from_filename(filename)
                if inferred == DocumentType.W2 and ext.get("type") != DocumentType.W2:
                    classified = ext.get("document_type", "unknown")
                    reason = (
                        "Filename suggests W-2 but classified as "
                        f"{classified}: {filename}"
                    )
                    if reason not in self.escalations:
                        self.escalations.append(reason)
                        logger.warning(
                            "missing_w2_filename_hint",
                            filename=filename,
                            classified=classified,
                        )

    def _check_conflicts(
        self,
        extractions: list[dict[str, Any]],
    ) -> list[str]:
        """Check for conflicting information across documents (PTAX-16).

        Looks for mismatches in SSN and name across documents.

        Args:
            extractions: List of extraction results.

        Returns:
            List of conflict descriptions.
        """
        conflicts: list[str] = []

        def _normalize_ssn(value: str | None) -> str | None:
            """Normalize SSN format and ignore EINs."""
            if not value:
                return None
            cleaned = value.strip()
            if re.fullmatch(r"\d{2}-\d{7}", cleaned):
                return None
            if re.fullmatch(r"\d{3}-\d{2}-\d{4}", cleaned):
                return cleaned
            digits = re.sub(r"\D", "", cleaned)
            if len(digits) == 9:
                return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
            return None

        # Collect SSNs from all documents
        ssns: dict[str, list[str]] = {}  # SSN -> list of filenames
        names: dict[str, list[str]] = {}  # name -> list of filenames

        for ext in extractions:
            data = ext.get("data")
            filename = ext.get("filename", "unknown")

            if data is None:
                continue

            # Get SSN/TIN based on document type
            if isinstance(data, W2Data):
                ssn = data.employee_ssn
                name = data.employee_name
            elif isinstance(data, (Form1099INT, Form1099DIV)):
                ssn = data.recipient_tin
                name = None  # No name field on these forms
            elif isinstance(data, Form1099NEC):
                ssn = data.recipient_tin
                name = data.recipient_name
            else:
                continue

            # Track SSNs
            normalized_ssn = _normalize_ssn(ssn)
            if normalized_ssn:
                if normalized_ssn not in ssns:
                    ssns[normalized_ssn] = []
                ssns[normalized_ssn].append(filename)

            # Track names
            if name:
                normalized_name = name.lower().strip()
                if normalized_name not in names:
                    names[normalized_name] = []
                names[normalized_name].append(filename)

        # Check for multiple different SSNs
        if len(ssns) > 1:
            conflict_msg = f"Multiple SSNs found: {list(ssns.keys())}"
            conflicts.append(conflict_msg)
            self.escalations.append(f"Conflicting information: {conflict_msg}")
            logger.warning("ssn_conflict", ssns=list(ssns.keys()))

        # Check for multiple different names (only if we have 2+ different names)
        if len(names) > 1:
            # This might be legitimate (e.g., maiden name), so log but don't escalate
            logger.info(
                "multiple_names_found",
                names=list(names.keys()),
            )

        return conflicts

    def _calculate_tax(
        self,
        extractions: list[dict[str, Any]],
        filing_status: str,
        tax_year: int,
    ) -> tuple[IncomeSummary, DeductionResult, TaxResult]:
        """Aggregate income and calculate tax.

        Args:
            extractions: List of extraction results.
            filing_status: Filing status for brackets.
            tax_year: Tax year.

        Returns:
            Tuple of (IncomeSummary, DeductionResult, TaxResult).
        """
        # Extract data objects
        documents = [ext["data"] for ext in extractions if ext.get("data")]

        # Aggregate income
        income_summary = aggregate_income(documents)

        # Calculate deductions (standard for now)
        deduction_result = calculate_deductions(
            income_summary,
            filing_status,
            tax_year,
        )

        # Calculate taxable income
        taxable_income = max(
            Decimal("0"),
            income_summary.total_income - deduction_result.amount,
        )

        # Calculate tax
        tax_result = calculate_tax(taxable_income, filing_status, tax_year)

        # Evaluate credits (requires pre-credit tax liability for ACTC)
        situation = TaxSituation(
            agi=income_summary.total_income,
            filing_status=filing_status,
            tax_year=tax_year,
            earned_income=income_summary.total_wages,
            tax_liability=tax_result.gross_tax,
        )
        credits_result = evaluate_credits(situation)

        # Apply credits
        tax_result.credits_applied = min(
            credits_result.total_nonrefundable,
            tax_result.gross_tax,
        )
        tax_result.final_liability = max(
            Decimal("0"),
            tax_result.gross_tax - tax_result.credits_applied,
        )
        tax_result.refundable_credits = credits_result.total_refundable

        return income_summary, deduction_result, tax_result

    def _compare_prior_year(
        self,
        context: AgentContext,
        income_summary: IncomeSummary,
        tax_result: TaxResult,
    ) -> list[VarianceItem]:
        """Compare with prior year and detect variances (PTAX-12).

        Args:
            context: Agent context with prior year data.
            income_summary: Current year income.
            tax_result: Current year tax result.

        Returns:
            List of significant variances.
        """
        if context.prior_year_return is None:
            return []

        prior = context.prior_year_return
        current = {
            "total_income": income_summary.total_income,
            "total_wages": income_summary.total_wages,
            "total_interest": income_summary.total_interest,
            "total_dividends": income_summary.total_dividends,
            "total_nec": income_summary.total_nec,
            "tax_liability": tax_result.final_liability,
        }

        # Build prior year dict with matching keys
        prior_values = {
            "total_income": Decimal(str(prior.get("total_income", 0))),
            "total_wages": Decimal(str(prior.get("wages", 0))),
            "total_interest": Decimal(str(prior.get("interest", 0))),
            "total_dividends": Decimal(str(prior.get("dividends", 0))),
            "total_nec": Decimal(str(prior.get("self_employment", 0))),
            "tax_liability": Decimal(str(prior.get("tax_liability", 0))),
        }

        variances = compare_years(current, prior_values)

        if variances:
            logger.info(
                "prior_year_variances",
                count=len(variances),
                fields=[v.field for v in variances],
            )

        return variances

    def _generate_outputs(
        self,
        context: AgentContext,
        extractions: list[dict[str, Any]],
        income_summary: IncomeSummary,
        deduction_result: DeductionResult,
        tax_result: TaxResult,
        variances: list[VarianceItem],
        filing_status: str,
        tax_year: int,
    ) -> tuple[Path, Path]:
        """Generate output files (PTAX-13, PTAX-14).

        Args:
            context: Agent context.
            extractions: List of extraction results.
            income_summary: Aggregated income.
            deduction_result: Deduction calculation.
            tax_result: Tax calculation.
            variances: Prior year variances.
            filing_status: Filing status.
            tax_year: Tax year.

        Returns:
            Tuple of (worksheet_path, notes_path).
        """
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Separate documents by type
        w2_data = [e["data"] for e in extractions if isinstance(e.get("data"), W2Data)]
        int_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099INT)
        ]
        div_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099DIV)
        ]
        nec_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099NEC)
        ]

        # Generate Drake worksheet
        worksheet_path = self.output_dir / f"drake_worksheet_{tax_year}.xlsx"
        generate_drake_worksheet(
            client_name=context.client_name,
            tax_year=tax_year,
            w2_data=w2_data,
            income_1099_int=int_data,
            income_1099_div=div_data,
            income_1099_nec=nec_data,
            income_summary=income_summary,
            deduction_result=deduction_result,
            tax_result=tax_result,
            output_path=worksheet_path,
        )

        # Generate preparer notes
        notes_path = self.output_dir / f"preparer_notes_{tax_year}.md"
        generate_preparer_notes(
            client_name=context.client_name,
            tax_year=tax_year,
            income_summary=income_summary,
            deduction_result=deduction_result,
            tax_result=tax_result,
            variances=variances,
            extractions=extractions,
            filing_status=filing_status,
            output_path=notes_path,
        )

        logger.info(
            "outputs_generated",
            worksheet_path=str(worksheet_path),
            notes_path=str(notes_path),
        )

        return worksheet_path, notes_path

    def _determine_overall_confidence(
        self,
        extractions: list[dict[str, Any]],
    ) -> str:
        """Determine overall confidence from extraction results.

        Returns HIGH if all HIGH, MEDIUM if any MEDIUM, LOW if any LOW.

        Args:
            extractions: List of extraction results with confidence.

        Returns:
            Overall confidence level string (HIGH, MEDIUM, or LOW).
        """
        if not extractions:
            return ConfidenceLevel.HIGH.value

        confidence_levels = [e.get("confidence", "HIGH") for e in extractions]

        if ConfidenceLevel.LOW.value in confidence_levels:
            return ConfidenceLevel.LOW.value
        if ConfidenceLevel.MEDIUM.value in confidence_levels:
            return ConfidenceLevel.MEDIUM.value
        return ConfidenceLevel.HIGH.value


async def personal_tax_handler(task: "Task", session: "AsyncSession") -> None:
    """Handle personal tax task from dispatcher.

    This function is registered with TaskDispatcher for task_type="personal_tax".
    Creates a PersonalTaxAgent and processes the task, updating status and
    creating artifacts as appropriate.

    Args:
        task: Task to process.
        session: Database session.

    Side effects:
        - Updates task status (completed/failed/escalated)
        - Creates TaskArtifact entries for outputs
        - Creates Escalation entries if needed
    """
    from src.core.config import settings
    from src.models.task import Escalation, TaskArtifact, TaskStatus

    # Get storage URL from task metadata or use default
    metadata = task.metadata if hasattr(task, "metadata") and task.metadata else {}
    storage_url = metadata.get(
        "storage_url", getattr(settings, "default_storage_url", "/tmp/storage")
    )

    # Build output directory path
    output_base = Path(getattr(settings, "output_dir", "/tmp/output"))
    tax_year = getattr(task, "tax_year", datetime.now().year)
    output_dir = output_base / str(task.client_id) / str(tax_year)
    output_dir.mkdir(parents=True, exist_ok=True)

    agent = PersonalTaxAgent(
        storage_url=storage_url,
        output_dir=output_dir,
    )

    try:
        result = await agent.process(
            client_id=str(task.client_id),
            tax_year=tax_year,
            session=session,
            filing_status=metadata.get("filing_status", "single"),
        )

        # Create artifacts
        artifact_worksheet = TaskArtifact(
            task_id=task.id,
            artifact_type="drake_worksheet",
            file_path=str(result.drake_worksheet_path),
        )
        session.add(artifact_worksheet)

        artifact_notes = TaskArtifact(
            task_id=task.id,
            artifact_type="preparer_notes",
            file_path=str(result.preparer_notes_path),
        )
        session.add(artifact_notes)

        # Task completed
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()

        logger.info(
            "personal_tax_task_completed",
            task_id=task.id,
            client_id=task.client_id,
        )

    except EscalationRequired as e:
        # Create escalation entry
        escalation = Escalation(
            task_id=task.id,
            reason="; ".join(e.reasons),
            escalated_at=datetime.utcnow(),
        )
        session.add(escalation)
        task.status = TaskStatus.ESCALATED

        logger.warning(
            "personal_tax_task_escalated",
            task_id=task.id,
            reasons=e.reasons,
        )

    except Exception as e:
        # Task failed
        task.status = TaskStatus.FAILED
        if hasattr(task, "error_message"):
            task.error_message = str(e)

        logger.error(
            "personal_tax_task_failed",
            task_id=task.id,
            error=str(e),
        )

    await session.commit()
