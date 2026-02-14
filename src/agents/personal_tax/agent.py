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

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
from typing import TYPE_CHECKING, Any

from src.agents.personal_tax.calculator import (
    CapitalTransaction,
    DeductionResult,
    FilingStatus,
    IncomeSummary,
    RentalExpenses,
    RentalProperty,
    ScheduleCData,
    ScheduleCExpenses,
    ScheduleDData,
    ScheduleEData,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    build_credit_inputs,
    build_qbi_from_k1,
    build_qbi_from_rental,
    build_qbi_from_schedule_c,
    calculate_deductions,
    calculate_premium_tax_credit,
    calculate_qbi_deduction,
    calculate_schedule_d,
    calculate_tax,
    compare_years,
    compute_itemized_deductions,
    convert_1099b_to_transactions,
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
    Form1095A,
    Form1098,
    Form1098T,
    Form1099B,
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
        document_model: str | None = None,
    ) -> None:
        """Initialize Personal Tax Agent.

        Args:
            storage_url: Base URL for document storage (s3://, gs://, /local/path).
            output_dir: Directory where output files will be written.
            document_model: Optional model override for document processing.
        """
        self.storage_url = storage_url
        self.output_dir = output_dir
        self.document_model = document_model
        self.escalations: list[str] = []
        self._user_form_type_overrides: dict[str, str] = {}

    async def process(
        self,
        client_id: str,
        tax_year: int,
        session: "AsyncSession",
        filing_status: str = "single",
        user_form_type_overrides: dict[str, str] | None = None,
        document_model: str | None = None,
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
            user_form_type_overrides: Optional mapping of filename to user-selected
                form type. When provided, the agent will use this instead of
                automatic classification.
            document_model: Optional model name override for document processing.

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
        
        # Store form type overrides for use during extraction
        self._user_form_type_overrides = user_form_type_overrides or {}
        self.document_model = document_model

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

        # 5.5 Check for new form-specific escalations
        self._check_new_form_escalations(extractions)

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
        from src.core.config import settings

        extractions: list[dict[str, Any]] = []
        concurrency = max(1, settings.document_processing_concurrency)
        semaphore = asyncio.Semaphore(concurrency)
        tasks: list[asyncio.Task[list[dict[str, Any]]]] = []
        task_filenames: list[str] = []

        async def _run_page(
            page_bytes: bytes,
            page_media_type: str,
            page_filename: str,
            original_filename: str,
        ) -> list[dict[str, Any]]:
            async with semaphore:
                # Check for user-selected form type override
                user_form_type = self._user_form_type_overrides.get(original_filename)
                return await self._process_page(
                    page_bytes=page_bytes,
                    page_media_type=page_media_type,
                    page_filename=page_filename,
                    user_form_type=user_form_type,
                )

        for doc in documents:
            try:
                # Read file bytes
                image_bytes = await read_file(self.storage_url, doc.path)

                # Determine media type from extension
                media_type = self._get_media_type(doc.extension)

                if media_type == "application/pdf":
                    pages = await asyncio.to_thread(self._split_pdf_pages, image_bytes)
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
                    tasks.append(
                        asyncio.create_task(
                            _run_page(
                                page_bytes=page_bytes,
                                page_media_type=page_media_type,
                                page_filename=page_filename,
                                original_filename=doc.name,
                            )
                        )
                    )
                    task_filenames.append(page_filename)

            except Exception as e:
                logger.error(
                    "extraction_failed",
                    filename=doc.name,
                    error=str(e),
                )
                self.escalations.append(f"Failed to extract {doc.name}: {str(e)}")

        if not tasks:
            return extractions

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result, page_filename in zip(results, task_filenames, strict=True):
            if isinstance(result, Exception):
                logger.error(
                    "extraction_failed",
                    filename=page_filename,
                    error=str(result),
                )
                self.escalations.append(
                    f"Failed to extract {page_filename}: {str(result)}"
                )
                continue

            extractions.extend(result)

        return extractions

    async def _process_page(
        self,
        page_bytes: bytes,
        page_media_type: str,
        page_filename: str,
        user_form_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Classify and extract data for a single page.
        
        Args:
            page_bytes: Image bytes for the page.
            page_media_type: MIME type of the image.
            page_filename: Display name for the page (may include page number).
            user_form_type: User-selected form type override. If provided,
                classification is still run for mismatch detection, but
                extraction uses the user-selected type.
        """
        # Always run classification (needed for mismatch detection)
        classification = await classify_document(
            page_bytes,
            page_media_type,
            model_name=self.document_model,
        )
        original_type = classification.document_type
        original_confidence = classification.confidence
        original_reasoning = classification.reasoning
        classification_overridden = False
        classification_override_source: str | None = None
        user_selection_used = False

        # Check for user-selected form type override
        if user_form_type is not None:
            try:
                user_doc_type = DocumentType(user_form_type)
                
                # Check for mismatch between user selection and classifier
                if classification.document_type != user_doc_type:
                    if classification.confidence >= 0.8:
                        # High-confidence mismatch - warn but use user selection
                        logger.warning(
                            "user_selection_mismatch",
                            filename=page_filename,
                            user_selected=user_form_type,
                            classified=classification.document_type.value,
                            classifier_confidence=classification.confidence,
                        )
                        self.escalations.append(
                            f"User selected {user_form_type} for {page_filename}, "
                            f"but classifier detected {classification.document_type.value} "
                            f"with {classification.confidence:.0%} confidence. Please verify."
                        )
                
                # Use user-selected type
                classification = ClassificationResult(
                    document_type=user_doc_type,
                    confidence=1.0,  # User selection has highest confidence
                    reasoning=f"User selected form type: {user_form_type}",
                )
                classification_overridden = True
                classification_override_source = "user"
                user_selection_used = True
            except ValueError:
                # Invalid document type - fall back to classifier
                logger.warning(
                    "invalid_user_form_type",
                    filename=page_filename,
                    user_form_type=user_form_type,
                )

        # Filename hint override (only if user didn't select a type)
        if not user_selection_used:
            filename_hint = self._infer_document_type_from_filename(page_filename)
            if filename_hint is not None and filename_hint != classification.document_type:
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
                classification_override_source = "filename"

        if classification.document_type == DocumentType.UNKNOWN:
            logger.warning(
                "unknown_document_type",
                filename=page_filename,
                confidence=classification.confidence,
            )
            return []

        # Extract data
        data = await extract_document(
            page_bytes,
            classification.document_type,
            page_media_type,
            model_name=self.document_model,
        )

        w2_forms: list[W2Data] | None = None
        if isinstance(data, W2Batch):
            w2_forms = data.forms
        elif isinstance(data, W2Data):
            w2_forms = [data]

        if w2_forms is not None:
            # Multiple forms flag is informational only - extraction succeeded
            # The flag will still be included in the extraction metadata for review
            extractions: list[dict[str, Any]] = []
            for form_index, form in enumerate(w2_forms, start=1):
                form_filename = (
                    page_filename
                    if len(w2_forms) == 1
                    else f"{page_filename} (form {form_index})"
                )
                multiple_forms_detected = (
                    "multiple_forms_detected" in form.uncertain_fields
                )
                extractions.append(
                    {
                        "type": classification.document_type,
                        "document_type": classification.document_type.value,
                        "filename": form_filename,
                        "confidence": form.confidence.value,
                        "data": form,
                        "classification": classification,
                        "classification_confidence": classification.confidence,
                        "classification_reasoning": classification.reasoning,
                        "classification_overridden": classification_overridden,
                        "classification_override_source": classification_override_source,
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
                    filename=form_filename,
                    document_type=classification.document_type.value,
                    confidence=form.confidence.value,
                )
            return extractions

        extraction = {
            "type": classification.document_type,
            "document_type": classification.document_type.value,
            "filename": page_filename,
            "confidence": data.confidence.value,
            "data": data,
            "classification": classification,
            "classification_confidence": classification.confidence,
            "classification_reasoning": classification.reasoning,
            "classification_overridden": classification_overridden,
            "classification_override_source": classification_override_source,
            "multiple_forms_detected": False,
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

        logger.info(
            "document_extracted",
            filename=page_filename,
            document_type=classification.document_type.value,
            confidence=data.confidence.value,
        )

        return [extraction]

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
            ssn = None
            name = None
            if isinstance(data, W2Data):
                ssn = data.employee_ssn
                name = data.employee_name
            elif isinstance(data, (Form1099INT, Form1099DIV)):
                ssn = data.recipient_tin
                name = None  # No name field on these forms
            elif isinstance(data, Form1099NEC):
                ssn = data.recipient_tin
                name = data.recipient_name
            elif isinstance(data, Form1098):
                ssn = data.borrower_tin
                name = data.borrower_name
            elif isinstance(data, Form1099R):
                ssn = data.recipient_tin
                name = data.recipient_name
            elif isinstance(data, Form1099G):
                ssn = data.recipient_tin
                name = data.recipient_name
            elif isinstance(data, Form1098T):
                ssn = data.student_tin
                name = data.student_name
            elif isinstance(data, Form5498):
                ssn = data.participant_tin
                name = data.participant_name
            elif isinstance(data, Form1099S):
                ssn = data.transferor_tin
                name = data.transferor_name
            
            if ssn is None:
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
            ssn_list = list(ssns.keys())
            files_with_ssns = {ssn: filenames for ssn, filenames in ssns.items()}
            conflict_msg = (
                f"Multiple different SSNs found across documents: {ssn_list}. "
                f"This may indicate documents for different taxpayers were uploaded together, "
                f"or there is an error in the documents. Please verify all documents belong to the same taxpayer."
            )
            conflicts.append(conflict_msg)
            self.escalations.append(f"Conflicting information: {conflict_msg}")
            logger.warning(
                "ssn_conflict",
                ssns=ssn_list,
                files_with_ssns=files_with_ssns,
            )

        # Check for multiple different names (only if we have 2+ different names)
        if len(names) > 1:
            # This might be legitimate (e.g., maiden name), so log but don't escalate
            logger.info(
                "multiple_names_found",
                names=list(names.keys()),
            )

        return conflicts

    def _check_new_form_escalations(
        self,
        extractions: list[dict[str, Any]],
    ) -> None:
        """Check for escalations specific to new form types.

        Adds escalations for forms that require additional information or
        professional review before tax calculations can be accurate.

        Args:
            extractions: List of extraction results.
        """
        for ext in extractions:
            data = ext.get("data")
            filename = ext.get("filename", "unknown")

            if data is None:
                continue

            # 1099-R: Check for taxable amount not determined
            if isinstance(data, Form1099R):
                if data.taxable_amount_not_determined:
                    self.escalations.append(
                        f"1099-R taxable amount not determined for {filename}. "
                        "Review distribution details to calculate taxable portion."
                    )
                # Check for early distribution penalty codes
                code = data.distribution_code.upper().strip() if data.distribution_code else ""
                early_distribution_codes = {"1", "J", "S"}
                if any(c in code for c in early_distribution_codes):
                    self.escalations.append(
                        f"1099-R distribution code '{code}' in {filename} may indicate "
                        "early distribution penalty. Verify if exception applies."
                    )

            # 1099-G: Check for state tax refund (may be taxable)
            elif isinstance(data, Form1099G):
                if data.state_local_tax_refund > 0:
                    self.escalations.append(
                        f"State tax refund of ${data.state_local_tax_refund:.2f} in {filename}. "
                        "Taxability depends on whether itemized deductions were claimed in the prior year."
                    )

            # 1098: Mortgage interest deduction info
            elif isinstance(data, Form1098):
                # Note: This is informational, not an escalation
                # Itemized deduction calculation would use this
                pass

            # 1098-T: Education credit eligibility
            elif isinstance(data, Form1098T):
                # Check if we have enough info for education credits
                if not data.at_least_half_time:
                    self.escalations.append(
                        f"1098-T for {filename}: Student not marked as at least half-time. "
                        "American Opportunity Credit requires half-time enrollment. "
                        "Verify student status for credit eligibility."
                    )

            # 5498: IRA contribution deduction eligibility
            elif isinstance(data, Form5498):
                total_ira = (
                    data.ira_contributions
                    + data.sep_contributions
                    + data.simple_contributions
                )
                if total_ira > 0:
                    self.escalations.append(
                        f"IRA contributions of ${total_ira:.2f} in {filename}. "
                        "Deductibility depends on retirement plan coverage and MAGI limits. "
                        "Please verify deduction eligibility."
                    )

            # 1099-S: Real estate sale
            elif isinstance(data, Form1099S):
                self.escalations.append(
                    f"Real estate sale of ${data.gross_proceeds:.2f} in {filename}. "
                    f"Property: {data.property_address}. "
                    "Capital gains calculation requires cost basis and primary residence information."
                )

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
        # Extract data objects and normalize 1099-B transaction lists
        documents: list[Any] = []
        forms_1099b: list[Form1099B] = []
        for extraction in extractions:
            data = extraction.get("data")
            if data is None:
                continue
            if isinstance(data, list) and data and all(
                isinstance(item, Form1099B) for item in data
            ):
                forms_1099b.extend(data)
                continue
            if isinstance(data, Form1099B):
                forms_1099b.append(data)
                continue
            documents.append(data)

        try:
            filing_status_enum = FilingStatus(filing_status)
        except ValueError:
            logger.warning("unknown_filing_status", filing_status=filing_status)
            filing_status_enum = FilingStatus.SINGLE

        schedule_c_data: list[ScheduleCData] = []
        for doc in documents:
            if (
                isinstance(doc, Form1099NEC)
                and doc.nonemployee_compensation > 0
            ):
                schedule_c_data.append(
                    ScheduleCData(
                        business_name=doc.payer_name,
                        business_activity="Independent contractor",
                        principal_business_code="999999",
                        gross_receipts=doc.nonemployee_compensation,
                        expenses=ScheduleCExpenses(),
                    )
                )

        rental_properties: list[RentalProperty] = []
        for doc in documents:
            if isinstance(doc, FormK1):
                rental_income = (
                    (doc.net_rental_real_estate or Decimal("0"))
                    + (doc.other_rental_income or Decimal("0"))
                )
                if rental_income != Decimal("0"):
                    rental_properties.append(
                        RentalProperty(
                            property_address=f"K-1 {doc.entity_name}",
                            property_type="K-1",
                            fair_rental_days=365,
                            rental_income=rental_income,
                            expenses=RentalExpenses(),
                        )
                    )
        schedule_e_data = (
            ScheduleEData(
                properties=rental_properties,
                actively_participates=True,
            )
            if rental_properties
            else None
        )

        transactions: list[CapitalTransaction] = []
        missing_basis: list[Form1099B] = []
        if forms_1099b:
            converted, missing = convert_1099b_to_transactions(forms_1099b)
            transactions.extend(converted)
            missing_basis.extend(missing)

        for doc in documents:
            if not isinstance(doc, FormK1):
                continue
            k1_short = doc.net_short_term_capital_gain or Decimal("0")
            k1_long = doc.net_long_term_capital_gain or Decimal("0")
            k1_section_1231 = doc.net_section_1231_gain or Decimal("0")
            for amount, label, is_long in (
                (k1_short, "Short-term", False),
                (k1_long, "Long-term", True),
                (k1_section_1231, "Section 1231", True),
            ):
                if amount == Decimal("0"):
                    continue
                proceeds = amount if amount > 0 else Decimal("0")
                cost_basis = Decimal("0") if amount > 0 else abs(amount)
                transactions.append(
                    CapitalTransaction(
                        description=f"K-1 {doc.entity_name} {label}",
                        date_acquired=None,
                        date_sold="Various",
                        proceeds=proceeds,
                        cost_basis=cost_basis,
                        is_short_term=not is_long,
                        is_long_term=is_long,
                        basis_reported_to_irs=True,
                        wash_sale_disallowed=Decimal("0"),
                    )
                )

        schedule_d_data = (
            ScheduleDData(transactions=transactions) if transactions else None
        )

        for form in missing_basis:
            self.escalations.append(
                "1099-B transaction missing cost basis for "
                f"{form.description} (proceeds ${form.proceeds:.2f}). "
                "Client basis is required to compute gains/losses."
            )

        # Aggregate income
        income_summary = aggregate_income(
            documents=documents,
            schedule_c_data=schedule_c_data or None,
            schedule_e_data=schedule_e_data,
            schedule_d_data=schedule_d_data,
            filing_status=filing_status_enum,
            tax_year=tax_year,
        )

        # Calculate itemized deductions and select best option
        itemized_breakdown = compute_itemized_deductions(documents, filing_status)
        deduction_result = calculate_deductions(
            income_summary,
            filing_status,
            tax_year,
            itemized_total=itemized_breakdown.total,
        )

        # Calculate taxable income
        taxable_income = max(
            Decimal("0"),
            income_summary.total_income - deduction_result.amount,
        )

        # Apply QBI deduction (Section 199A)
        qbi_components = []
        if schedule_c_data:
            schedule_c_profit = sum(
                max(Decimal("0"), sch_c.net_profit_or_loss)
                for sch_c in schedule_c_data
            )
            for sch_c in schedule_c_data:
                if sch_c.net_profit_or_loss <= Decimal("0"):
                    continue
                allocated_se_tax = (
                    income_summary.se_tax_deduction
                    * (sch_c.net_profit_or_loss / schedule_c_profit)
                    if schedule_c_profit > 0
                    else Decimal("0")
                )
                qbi_components.append(
                    build_qbi_from_schedule_c(sch_c, allocated_se_tax)
                )
        for doc in documents:
            if isinstance(doc, FormK1):
                qbi_components.append(build_qbi_from_k1(doc))
        if schedule_e_data:
            for prop in schedule_e_data.properties:
                qbi_component = build_qbi_from_rental(
                    prop.net_income_loss,
                    prop.property_address,
                    prop.qbi_eligible,
                )
                if qbi_component:
                    qbi_components.append(qbi_component)

        net_capital_gains = Decimal("0")
        if schedule_d_data:
            schedule_d_result = calculate_schedule_d(
                schedule_d_data,
                filing_status_enum,
                tax_year,
            )
            net_capital_gains = max(
                Decimal("0"), schedule_d_result.net_capital_gain_loss
            )

        qbi_deduction = Decimal("0")
        if qbi_components and taxable_income > Decimal("0"):
            qbi_result = calculate_qbi_deduction(
                qbi_components,
                taxable_income,
                net_capital_gains,
                filing_status_enum,
                tax_year,
            )
            qbi_deduction = qbi_result.final_qbi_deduction

        taxable_income = max(Decimal("0"), taxable_income - qbi_deduction)

        # Calculate tax
        tax_result = calculate_tax(taxable_income, filing_status, tax_year)

        # Evaluate credits (requires pre-credit tax liability for ACTC)
        credit_inputs = build_credit_inputs(documents)
        situation = TaxSituation(
            agi=income_summary.total_income,
            filing_status=filing_status,
            tax_year=tax_year,
            education_expenses=credit_inputs.education_expenses,
            education_credit_type=credit_inputs.education_credit_type,
            retirement_contributions=credit_inputs.retirement_contributions,
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

        # Apply Premium Tax Credit (Form 8962) reconciliation
        form_1095a_data = [
            doc
            for doc in documents
            if isinstance(doc, Form1095A)
        ]
        if form_1095a_data:
            additional_credit_total = Decimal("0")
            repayment_total = Decimal("0")
            for form in form_1095a_data:
                ptc_result = calculate_premium_tax_credit(
                    income_summary.total_income,
                    1,
                    form,
                    filing_status_enum,
                    tax_year,
                )
                additional_credit_total += ptc_result.additional_credit
                repayment_total += ptc_result.repayment_amount
                if ptc_result.repayment_required:
                    self.escalations.append(
                        "Premium tax credit repayment required "
                        f"(${ptc_result.repayment_amount:.2f}). "
                        "Confirm household income and coverage details."
                    )
                if not ptc_result.is_eligible:
                    self.escalations.append(
                        "Premium tax credit ineligible: "
                        f"{ptc_result.ineligibility_reason}."
                    )

            tax_result.refundable_credits += additional_credit_total
            tax_result.final_liability = max(
                Decimal("0"), tax_result.final_liability + repayment_total
            )

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
        mortgage_1098_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1098)
        ]
        income_1099_r_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099R)
        ]
        income_1099_g_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099G)
        ]
        education_1098_t_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1098T)
        ]
        retirement_5498_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form5498)
        ]
        real_estate_1099_s_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1099S)
        ]
        k1_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), FormK1)
        ]
        # 1099-B extraction returns list of transactions per form
        transactions_1099_b = []
        for e in extractions:
            data = e.get("data")
            if isinstance(data, list) and all(isinstance(t, Form1099B) for t in data):
                transactions_1099_b.extend(data)
            elif isinstance(data, Form1099B):
                transactions_1099_b.append(data)
        form_1095a_data = [
            e["data"] for e in extractions if isinstance(e.get("data"), Form1095A)
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
            mortgage_1098=mortgage_1098_data,
            income_1099_r=income_1099_r_data,
            income_1099_g=income_1099_g_data,
            education_1098_t=education_1098_t_data,
            retirement_5498=retirement_5498_data,
            real_estate_1099_s=real_estate_1099_s_data,
            k1_data=k1_data,
            transactions_1099_b=transactions_1099_b,
            form_1095a_data=form_1095a_data,
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
        task.completed_at = datetime.now(UTC)

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
            escalated_at=datetime.now(UTC),
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
