"""Demo API endpoints for production-ready personal tax prep workflow."""

from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import orjson
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.personal_tax.agent import (
    EscalationRequired,
    PersonalTaxAgent,
    PersonalTaxResult,
)
from src.agents.personal_tax.calculator import calculate_deductions
from src.api.deps import get_db, verify_demo_api_key
from src.core.config import settings
from src.core.logging import get_logger
from src.documents.models import (
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
    W2Data,
)
from src.integrations.storage import build_full_path, get_filesystem, write_file
from src.models.client import Client
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/demo",
    tags=["demo"],
    dependencies=[Depends(verify_demo_api_key)],
)

DEMO_TASK_TYPE = "demo_personal_tax"
DEMO_ARTIFACT_METADATA = "demo_metadata"
DEMO_ARTIFACT_RESULTS = "results"
DEMO_ARTIFACT_PROGRESS = "progress"
DEMO_ARTIFACT_EXTRACTION_PREVIEW = "extraction_preview"
DEMO_ARTIFACT_UPLOADED = "uploaded_document"
DEMO_ARTIFACT_WORKSHEET = "drake_worksheet"
DEMO_ARTIFACT_NOTES = "preparer_notes"
DEMO_DOCUMENT_MODELS = frozenset(
    {"claude-opus-4-6", "claude-sonnet-4-5-20250929"}
)
DEMO_CALCULATION_TIMEOUT_SECONDS = 90
DEMO_OUTPUT_GENERATION_TIMEOUT_SECONDS = 90
DEMO_OUTPUT_UPLOAD_TIMEOUT_SECONDS = 45


class ProcessingStage(str, Enum):
    """Processing stage for progress tracking."""

    UPLOADING = "uploading"
    SCANNING = "scanning"
    EXTRACTING = "extracting"
    REVIEW = "review"
    CALCULATING = "calculating"
    GENERATING = "generating"
    COMPLETE = "complete"


@dataclass
class ProgressEvent:
    """Progress event for SSE streaming."""

    stage: ProcessingStage
    progress: int
    message: str
    document: str | None = None
    document_type: str | None = None
    confidence: float | None = None
    status: str | None = None


class UploadResponse(BaseModel):
    """Response for file upload."""

    job_id: str
    message: str
    files_received: int


class ProcessResponse(BaseModel):
    """Response for process initiation."""

    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status check."""

    job_id: str
    status: str
    progress: int
    current_stage: str
    message: str | None = None


class IncomeBreakdown(BaseModel):
    """Income breakdown for results."""

    total_wages: str
    total_interest: str
    total_dividends: str
    total_qualified_dividends: str
    total_nec: str
    total_retirement_distributions: str
    total_unemployment: str
    total_state_tax_refund: str
    total_income: str
    federal_withholding: str


class TaxCalculation(BaseModel):
    """Tax calculation for results."""

    taxable_income: str
    gross_tax: str
    credits_applied: str
    final_liability: str
    refundable_credits: str
    effective_rate: str


class VarianceItem(BaseModel):
    """Prior year variance item."""

    field: str
    current_value: str
    prior_value: str
    variance_pct: str
    direction: str


class ExtractionItem(BaseModel):
    """Extracted document info."""

    filename: str
    document_type: str
    confidence: str
    classification_confidence: float | None = None
    classification_reasoning: str | None = None
    classification_overridden: bool = False
    classification_override_source: str | None = None
    classification_original_type: str | None = None
    classification_original_confidence: float | None = None
    classification_original_reasoning: str | None = None
    key_fields: dict[str, str]


class ExtractionPreviewResponse(BaseModel):
    """Extraction preview payload for user verification."""

    job_id: str
    status: str
    message: str
    extractions: list[ExtractionItem]
    escalations: list[str]


class UploadedDocumentItem(BaseModel):
    """Uploaded source document metadata."""

    artifact_id: int
    filename: str
    content_type: str
    size: int | None = None
    uploaded_at: str


class UploadedDocumentsResponse(BaseModel):
    """Uploaded source documents for a demo job."""

    job_id: str
    files: list[UploadedDocumentItem]


class ResultsResponse(BaseModel):
    """Full results response."""

    job_id: str
    status: str
    client_name: str
    tax_year: int
    filing_status: str
    overall_confidence: str
    income: IncomeBreakdown
    tax: TaxCalculation
    extractions: list[ExtractionItem]
    variances: list[VarianceItem]
    escalations: list[str]
    drake_worksheet_available: bool
    preparer_notes_available: bool


def _json_dumps(payload: dict[str, Any]) -> str:
    """Serialize payload to JSON string."""
    return orjson.dumps(payload).decode("utf-8")


def _json_loads(payload: str | None) -> dict[str, Any]:
    """Deserialize JSON string to dict."""
    if not payload:
        return {}
    return orjson.loads(payload)


def _format_currency(value: Decimal | float | int) -> str:
    """Format value as currency string."""
    if isinstance(value, Decimal):
        return f"${value:,.2f}"
    return f"${float(value):,.2f}"


def _format_percentage(value: Decimal | float) -> str:
    """Format value as percentage string."""
    if isinstance(value, Decimal):
        return f"{float(value) * 100:.1f}%"
    return f"{value * 100:.1f}%"


def _to_decimal(value: str | int | float | Decimal) -> Decimal:
    """Convert value to Decimal."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def _build_storage_prefix(client_id: int, tax_year: int) -> str:
    """Build base storage prefix for demo files."""
    return f"{client_id}/{tax_year}"


def _build_output_prefix(client_id: int, tax_year: int) -> str:
    """Build output prefix for generated artifacts."""
    return f"{client_id}/{tax_year}/outputs"


async def _create_task(session: AsyncSession, client_name: str) -> Task:
    """Create demo client and task entry."""
    client = Client(name=client_name)
    session.add(client)
    await session.flush()

    task = Task(
        client_id=client.id,
        task_type=DEMO_TASK_TYPE,
        status=TaskStatus.PENDING,
        assigned_agent="personal_tax_agent",
    )
    session.add(task)
    await session.flush()
    return task


async def _create_artifact(
    session: AsyncSession,
    task_id: int,
    artifact_type: str,
    content: dict[str, Any] | None = None,
    file_path: str | None = None,
) -> TaskArtifact:
    """Create a TaskArtifact entry."""
    artifact = TaskArtifact(
        task_id=task_id,
        artifact_type=artifact_type,
        content=_json_dumps(content) if content else None,
        file_path=file_path,
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def _emit_progress(
    session: AsyncSession,
    task_id: int,
    event: ProgressEvent,
) -> None:
    """Record progress event for SSE streaming."""
    await _create_artifact(
        session=session,
        task_id=task_id,
        artifact_type=DEMO_ARTIFACT_PROGRESS,
        content={
            "stage": event.stage.value,
            "progress": event.progress,
            "message": event.message,
            "document": event.document,
            "document_type": event.document_type,
            "confidence": event.confidence,
            "status": event.status,
        },
    )
    logger.info(
        "demo_progress",
        task_id=task_id,
        stage=event.stage.value,
        progress=event.progress,
        message=event.message,
    )


async def _get_task(session: AsyncSession, task_id: int) -> Task | None:
    """Fetch task by ID."""
    return await session.get(Task, task_id)


async def _get_latest_artifact(
    session: AsyncSession,
    task_id: int,
    artifact_type: str,
) -> TaskArtifact | None:
    """Get latest artifact by type."""
    stmt = (
        select(TaskArtifact)
        .where(TaskArtifact.task_id == task_id)
        .where(TaskArtifact.artifact_type == artifact_type)
        .order_by(TaskArtifact.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def _get_metadata(session: AsyncSession, task_id: int) -> dict[str, Any]:
    """Load demo metadata for a task."""
    artifact = await _get_latest_artifact(session, task_id, DEMO_ARTIFACT_METADATA)
    return _json_loads(artifact.content if artifact else None)


async def _get_user_form_type_overrides(
    session: AsyncSession, task_id: int
) -> dict[str, str]:
    """Get user-selected form type overrides from uploaded document artifacts.
    
    Returns:
        Dict mapping filename -> user-selected form type.
        Only includes entries where user explicitly selected a form type.
    """
    result = await session.execute(
        select(TaskArtifact)
        .where(TaskArtifact.task_id == task_id)
        .where(TaskArtifact.artifact_type == DEMO_ARTIFACT_UPLOADED)
    )
    artifacts = result.scalars().all()
    
    overrides: dict[str, str] = {}
    for artifact in artifacts:
        content = _json_loads(artifact.content)
        filename = content.get("filename")
        user_form_type = content.get("user_selected_form_type")
        if filename and user_form_type:
            overrides[filename] = user_form_type
    
    return overrides


def _build_key_fields(extraction: dict[str, Any]) -> dict[str, str]:
    """Build CPA-friendly key fields for an extraction."""
    data = extraction.get("data")
    key_fields: dict[str, str] = {}

    if isinstance(data, W2Data):
        key_fields = {
            "wages": _format_currency(data.wages_tips_compensation),
            "federal_withholding": _format_currency(data.federal_tax_withheld),
        }
    elif isinstance(data, Form1099INT):
        key_fields = {
            "interest_income": _format_currency(data.interest_income),
            "federal_withholding": _format_currency(data.federal_tax_withheld),
        }
    elif isinstance(data, Form1099DIV):
        key_fields = {
            "ordinary_dividends": _format_currency(data.total_ordinary_dividends),
            "qualified_dividends": _format_currency(data.qualified_dividends),
        }
    elif isinstance(data, Form1099NEC):
        key_fields = {
            "nonemployee_compensation": _format_currency(data.nonemployee_compensation),
            "federal_withholding": _format_currency(data.federal_tax_withheld),
        }
    elif isinstance(data, Form1098):
        key_fields = {
            "mortgage_interest": _format_currency(data.mortgage_interest),
            "points_paid": _format_currency(data.points_paid),
            "property_taxes": _format_currency(data.property_taxes_paid),
        }
    elif isinstance(data, Form1099R):
        key_fields = {
            "gross_distribution": _format_currency(data.gross_distribution),
            "taxable_amount": (
                _format_currency(data.taxable_amount)
                if data.taxable_amount is not None
                else "Not determined"
            ),
            "distribution_code": data.distribution_code,
            "federal_withholding": _format_currency(data.federal_tax_withheld),
        }
    elif isinstance(data, Form1099G):
        key_fields = {
            "unemployment": _format_currency(data.unemployment_compensation),
            "state_tax_refund": _format_currency(data.state_local_tax_refund),
            "federal_withholding": _format_currency(data.federal_tax_withheld),
        }
    elif isinstance(data, Form1098T):
        key_fields = {
            "tuition_payments": _format_currency(data.payments_received),
            "scholarships": _format_currency(data.scholarships_grants),
            "half_time_student": "Yes" if data.at_least_half_time else "No",
        }
    elif isinstance(data, Form5498):
        key_fields = {
            "ira_contributions": _format_currency(data.ira_contributions),
            "roth_contributions": _format_currency(data.roth_ira_contributions),
            "rollover": _format_currency(data.rollover_contributions),
            "recharacterized": _format_currency(data.recharacterized_contributions),
            "fmv": _format_currency(data.fair_market_value),
        }
    elif isinstance(data, Form1099S):
        key_fields = {
            "gross_proceeds": _format_currency(data.gross_proceeds),
            "closing_date": data.closing_date,
            "property": (
                data.property_address[:50] + "..."
                if len(data.property_address) > 50
                else data.property_address
            ),
        }

    if extraction.get("multiple_forms_detected"):
        key_fields["flags"] = "multiple_forms_detected"

    return key_fields


DOCUMENT_MODEL_BY_TYPE: dict[str, type[Any]] = {
    DocumentType.W2.value: W2Data,
    DocumentType.FORM_1099_INT.value: Form1099INT,
    DocumentType.FORM_1099_DIV.value: Form1099DIV,
    DocumentType.FORM_1099_NEC.value: Form1099NEC,
    DocumentType.FORM_1098.value: Form1098,
    DocumentType.FORM_1099_R.value: Form1099R,
    DocumentType.FORM_1099_G.value: Form1099G,
    DocumentType.FORM_1098_T.value: Form1098T,
    DocumentType.FORM_5498.value: Form5498,
    DocumentType.FORM_1099_S.value: Form1099S,
    DocumentType.FORM_K1.value: FormK1,
    DocumentType.FORM_1099_B.value: Form1099B,
    DocumentType.FORM_1095_A.value: Form1095A,
}


def _serialize_extractions(extractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialize extractions for storage between review and calculation phases."""
    serialized: list[dict[str, Any]] = []
    for ext in extractions:
        data = ext.get("data")
        is_list_data = isinstance(data, list)
        serialized_data: Any = None
        if is_list_data:
            serialized_data = [
                item.model_dump(mode="json")
                for item in data
                if hasattr(item, "model_dump")
            ]
        elif data is not None and hasattr(data, "model_dump"):
            serialized_data = data.model_dump(mode="json")

        serialized.append(
            {
                "type": (
                    ext.get("type").value
                    if isinstance(ext.get("type"), DocumentType)
                    else ext.get("document_type")
                ),
                "document_type": ext.get("document_type"),
                "filename": ext.get("filename"),
                "confidence": ext.get("confidence"),
                "classification_confidence": ext.get("classification_confidence"),
                "classification_reasoning": ext.get("classification_reasoning"),
                "classification_overridden": ext.get("classification_overridden", False),
                "classification_override_source": ext.get(
                    "classification_override_source"
                ),
                "multiple_forms_detected": ext.get("multiple_forms_detected", False),
                "classification_original_type": ext.get("classification_original_type"),
                "classification_original_confidence": ext.get(
                    "classification_original_confidence"
                ),
                "classification_original_reasoning": ext.get(
                    "classification_original_reasoning"
                ),
                "data_is_list": is_list_data,
                "data": serialized_data,
            }
        )
    return serialized


def _deserialize_extractions(serialized: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reconstruct extraction records from serialized payload."""
    extractions: list[dict[str, Any]] = []
    for item in serialized:
        document_type = str(item.get("document_type") or item.get("type") or "UNKNOWN")
        model_cls = DOCUMENT_MODEL_BY_TYPE.get(document_type)
        data_payload = item.get("data")
        data: Any = None

        if model_cls is not None and data_payload is not None:
            if item.get("data_is_list") and isinstance(data_payload, list):
                data = [model_cls.model_validate(entry) for entry in data_payload]
            elif isinstance(data_payload, dict):
                data = model_cls.model_validate(data_payload)

        extraction_type: DocumentType = DocumentType.UNKNOWN
        try:
            extraction_type = DocumentType(document_type)
        except ValueError:
            logger.warning("unknown_document_type_in_cache", document_type=document_type)

        extractions.append(
            {
                "type": extraction_type,
                "document_type": document_type,
                "filename": item.get("filename", "unknown"),
                "confidence": item.get("confidence", "LOW"),
                "data": data,
                "classification_confidence": item.get("classification_confidence"),
                "classification_reasoning": item.get("classification_reasoning"),
                "classification_overridden": item.get("classification_overridden", False),
                "classification_override_source": item.get(
                    "classification_override_source"
                ),
                "multiple_forms_detected": item.get("multiple_forms_detected", False),
                "classification_original_type": item.get("classification_original_type"),
                "classification_original_confidence": item.get(
                    "classification_original_confidence"
                ),
                "classification_original_reasoning": item.get(
                    "classification_original_reasoning"
                ),
            }
        )
    return extractions


def _build_extraction_preview_payload(
    task_id: int,
    extractions: list[dict[str, Any]],
    escalations: list[str],
) -> dict[str, Any]:
    """Build extraction preview payload for user verification."""
    return {
        "task_id": task_id,
        "message": "Please verify extracted data before tax calculation.",
        "extractions": [
            {
                "filename": ext.get("filename", "unknown"),
                "document_type": ext.get("document_type", "unknown"),
                "confidence": str(ext.get("confidence", "HIGH")),
                "classification_confidence": ext.get("classification_confidence"),
                "classification_reasoning": ext.get("classification_reasoning"),
                "classification_overridden": ext.get("classification_overridden", False),
                "classification_override_source": ext.get(
                    "classification_override_source"
                ),
                "classification_original_type": ext.get("classification_original_type"),
                "classification_original_confidence": ext.get(
                    "classification_original_confidence"
                ),
                "classification_original_reasoning": ext.get(
                    "classification_original_reasoning"
                ),
                "key_fields": _build_key_fields(ext),
            }
            for ext in extractions
        ],
        "escalations": escalations,
        "serialized_extractions": _serialize_extractions(extractions),
    }


async def _build_results_payload(
    task_id: int,
    client_name: str,
    tax_year: int,
    filing_status: str,
    result: Any | None,
    escalations: list[str] | None = None,
    drake_path: str | None = None,
    notes_path: str | None = None,
) -> dict[str, Any]:
    """Build results payload for storage."""
    escalations = escalations or []
    if result is None:
        return {
            "task_id": task_id,
            "client_name": client_name,
            "tax_year": tax_year,
            "filing_status": filing_status,
            "overall_confidence": "LOW",
            "income": {
                "total_wages": "0",
                "total_interest": "0",
                "total_dividends": "0",
                "total_qualified_dividends": "0",
                "total_nec": "0",
                "total_income": "0",
                "federal_withholding": "0",
            },
            "tax": {
                "taxable_income": "0",
                "gross_tax": "0",
                "credits_applied": "0",
                "final_liability": "0",
                "refundable_credits": "0",
                "effective_rate": "0",
            },
            "extractions": [],
            "variances": [],
            "escalations": escalations,
            "drake_worksheet_path": drake_path,
            "preparer_notes_path": notes_path,
        }

    deduction_result = calculate_deductions(
        result.income_summary,
        filing_status,
        tax_year,
    )
    taxable_income = max(
        Decimal("0"),
        result.income_summary.total_income - deduction_result.amount,
    )

    combined_escalations: list[str] = []
    for reason in [*escalations, *result.escalations]:
        if reason and reason not in combined_escalations:
            combined_escalations.append(reason)

    return {
        "task_id": task_id,
        "client_name": client_name,
        "tax_year": tax_year,
        "filing_status": filing_status,
        "overall_confidence": result.overall_confidence,
        "income": {
            "total_wages": str(result.income_summary.total_wages),
            "total_interest": str(result.income_summary.total_interest),
            "total_dividends": str(result.income_summary.total_dividends),
            "total_qualified_dividends": str(result.income_summary.total_qualified_dividends),
            "total_nec": str(result.income_summary.total_nec),
            "total_retirement_distributions": str(
                result.income_summary.total_retirement_distributions
            ),
            "total_unemployment": str(result.income_summary.total_unemployment),
            "total_state_tax_refund": str(result.income_summary.total_state_tax_refund),
            "total_income": str(result.income_summary.total_income),
            "federal_withholding": str(result.income_summary.federal_withholding),
        },
        "tax": {
            "taxable_income": str(taxable_income),
            "gross_tax": str(result.tax_result.gross_tax),
            "credits_applied": str(result.tax_result.credits_applied),
            "final_liability": str(result.tax_result.final_liability),
            "refundable_credits": str(result.tax_result.refundable_credits),
            "effective_rate": str(result.tax_result.effective_rate),
        },
        "extractions": [
            {
                "filename": ext.get("filename", "unknown"),
                "document_type": ext.get("document_type", "unknown"),
                "confidence": ext.get("confidence", "HIGH"),
                "classification_confidence": ext.get("classification_confidence"),
                "classification_reasoning": ext.get("classification_reasoning"),
                "classification_overridden": ext.get("classification_overridden", False),
                "classification_override_source": ext.get(
                    "classification_override_source"
                ),
                "classification_original_type": ext.get("classification_original_type"),
                "classification_original_confidence": ext.get(
                    "classification_original_confidence"
                ),
                "classification_original_reasoning": ext.get(
                    "classification_original_reasoning"
                ),
                "key_fields": _build_key_fields(ext),
            }
            for ext in result.extractions
        ],
        "variances": [
            {
                "field": v.field,
                "current_value": str(v.current_value),
                "prior_value": str(v.prior_value),
                "variance_pct": str(v.variance_pct),
                "direction": v.direction,
            }
            for v in result.variances
        ],
        "escalations": combined_escalations,
        "drake_worksheet_path": drake_path,
        "preparer_notes_path": notes_path,
    }


async def _save_results(
    session: AsyncSession,
    task_id: int,
    payload: dict[str, Any],
) -> None:
    """Persist results payload in TaskArtifact."""
    await _create_artifact(
        session=session,
        task_id=task_id,
        artifact_type=DEMO_ARTIFACT_RESULTS,
        content=payload,
    )


async def _save_extraction_preview(
    session: AsyncSession,
    task_id: int,
    payload: dict[str, Any],
) -> None:
    """Persist extraction preview payload in TaskArtifact."""
    await _create_artifact(
        session=session,
        task_id=task_id,
        artifact_type=DEMO_ARTIFACT_EXTRACTION_PREVIEW,
        content=payload,
    )


async def _upload_output(
    storage_url: str,
    output_prefix: str,
    source_path: Path,
) -> str:
    """Upload output file to storage and return storage path."""
    file_bytes = source_path.read_bytes()
    storage_path = f"{output_prefix}/{source_path.name}"
    await write_file(storage_url, storage_path, file_bytes)
    return storage_path


async def _upload_output_with_timeout(
    storage_url: str,
    output_prefix: str,
    source_path: Path,
    *,
    timeout_seconds: int = DEMO_OUTPUT_UPLOAD_TIMEOUT_SECONDS,
) -> str:
    """Upload output file with timeout protection."""
    try:
        return await asyncio.wait_for(
            _upload_output(storage_url, output_prefix, source_path),
            timeout=timeout_seconds,
        )
    except TimeoutError as exc:
        raise TimeoutError(
            f"Timed out uploading output file: {source_path.name}"
        ) from exc


async def _prepare_job_for_review(task_id: int, session_factory: Any) -> None:
    """Run extraction-only phase and pause for user verification."""
    async with session_factory() as session:
        task = await _get_task(session, task_id)
        if not task:
            logger.error("demo_task_missing", task_id=task_id)
            return

        metadata = await _get_metadata(session, task_id)
        storage_url = metadata.get("storage_url", settings.default_storage_url)
        client_id = int(metadata.get("client_id", 0))
        client_name = metadata.get("client_name", f"Client {client_id}")
        tax_year = int(metadata.get("tax_year", datetime.now(UTC).year))
        filing_status = metadata.get("filing_status", "single")

        output_dir = Path(settings.output_dir) / "demo" / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            task.status = TaskStatus.IN_PROGRESS
            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.SCANNING,
                    progress=10,
                    message="Scanning documents",
                ),
            )
            await session.commit()

            agent = PersonalTaxAgent(
                storage_url=storage_url,
                output_dir=output_dir,
                document_model=metadata.get("document_model"),
            )
            user_form_type_overrides = await _get_user_form_type_overrides(session, task_id)
            agent._user_form_type_overrides = user_form_type_overrides
            agent.document_model = metadata.get("document_model")

            documents = agent._scan_documents(
                client_id=str(client_id),
                tax_year=tax_year,
            )

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.EXTRACTING,
                    progress=40,
                    message="Extracting document data",
                ),
            )
            await session.commit()

            extractions = await agent._extract_documents(documents)
            context = await agent._load_context(session, str(client_id), tax_year)
            agent._check_missing_documents(context, extractions)
            agent._check_conflicts(extractions)
            agent._check_new_form_escalations(extractions)
            preview_payload = _build_extraction_preview_payload(
                task_id=task_id,
                extractions=extractions,
                escalations=agent.escalations,
            )
            await _save_extraction_preview(session, task_id, preview_payload)

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.REVIEW,
                    progress=60,
                    message="Review extracted data and confirm to continue",
                ),
            )
            await session.commit()

        except EscalationRequired as exc:
            task.status = TaskStatus.ESCALATED
            session.add(
                Escalation(
                    task_id=task_id,
                    reason="; ".join(exc.reasons),
                    escalated_at=datetime.now(UTC),
                )
            )

            payload = await _build_results_payload(
                task_id=task_id,
                client_name=client_name,
                tax_year=tax_year,
                filing_status=filing_status,
                result=exc.result,
                escalations=exc.reasons,
            )
            await _save_results(session, task_id, payload)

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.COMPLETE,
                    progress=100,
                    message="Escalation required",
                    status=task.status.value,
                ),
            )
            await session.commit()

        except Exception as exc:
            logger.exception("demo_prepare_failed", task_id=task_id, error=str(exc))
            task.status = TaskStatus.FAILED
            failure_message = "Processing failed"
            error_detail = str(exc).strip()
            if error_detail:
                failure_message = f"Processing failed: {error_detail[:180]}"
            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.COMPLETE,
                    progress=100,
                    message=failure_message,
                    status=task.status.value,
                ),
            )
            await session.commit()


async def _process_job(
    task_id: int,
    session_factory: Any,
    *,
    from_review: bool = False,
) -> None:
    """Run full tax workflow after verification."""
    async with session_factory() as session:
        task = await _get_task(session, task_id)
        if not task:
            logger.error("demo_task_missing", task_id=task_id)
            return

        metadata = await _get_metadata(session, task_id)
        storage_url = metadata.get("storage_url", settings.default_storage_url)
        client_id = int(metadata.get("client_id", 0))
        client_name = metadata.get("client_name", f"Client {client_id}")
        tax_year = int(metadata.get("tax_year", datetime.now(UTC).year))
        filing_status = metadata.get("filing_status", "single")

        output_dir = Path(settings.output_dir) / "demo" / str(task_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            task.status = TaskStatus.IN_PROGRESS
            if not from_review:
                await _emit_progress(
                    session,
                    task_id,
                    ProgressEvent(
                        stage=ProcessingStage.SCANNING,
                        progress=10,
                        message="Scanning documents",
                    ),
                )
            await session.commit()

            agent = PersonalTaxAgent(
                storage_url=storage_url,
                output_dir=output_dir,
                document_model=metadata.get("document_model"),
            )

            user_form_type_overrides = await _get_user_form_type_overrides(session, task_id)

            if from_review:
                preview_artifact = await _get_latest_artifact(
                    session, task_id, DEMO_ARTIFACT_EXTRACTION_PREVIEW
                )
                preview_payload = _json_loads(
                    preview_artifact.content if preview_artifact else None
                )
                serialized_extractions = preview_payload.get("serialized_extractions", [])
                if not serialized_extractions:
                    raise RuntimeError(
                        "Extraction cache missing for verification flow. Restart processing."
                    )

                await _emit_progress(
                    session,
                    task_id,
                    ProgressEvent(
                        stage=ProcessingStage.CALCULATING,
                        progress=74,
                        message="Preparing verified data for tax calculation",
                    ),
                )
                await session.commit()

                cached_extractions = _deserialize_extractions(serialized_extractions)
                agent.escalations = list(preview_payload.get("escalations", []))
                context = await agent._load_context(session, str(client_id), tax_year)
                try:
                    income_summary, deduction_result, tax_result = await asyncio.wait_for(
                        asyncio.to_thread(
                            agent._calculate_tax,
                            cached_extractions,
                            filing_status,
                            tax_year,
                        ),
                        timeout=DEMO_CALCULATION_TIMEOUT_SECONDS,
                    )
                except TimeoutError as exc:
                    raise TimeoutError("Tax calculation timed out") from exc
                variances = agent._compare_prior_year(
                    context,
                    income_summary,
                    tax_result,
                )

                await _emit_progress(
                    session,
                    task_id,
                    ProgressEvent(
                        stage=ProcessingStage.GENERATING,
                        progress=86,
                        message="Generating worksheet and preparer notes",
                    ),
                )
                await session.commit()

                try:
                    worksheet_path_local, notes_path_local = await asyncio.wait_for(
                        asyncio.to_thread(
                            agent._generate_outputs,
                            context,
                            cached_extractions,
                            income_summary,
                            deduction_result,
                            tax_result,
                            variances,
                            filing_status,
                            tax_year,
                        ),
                        timeout=DEMO_OUTPUT_GENERATION_TIMEOUT_SECONDS,
                    )
                except TimeoutError as exc:
                    raise TimeoutError("Output generation timed out") from exc
                result = PersonalTaxResult(
                    drake_worksheet_path=worksheet_path_local,
                    preparer_notes_path=notes_path_local,
                    income_summary=income_summary,
                    tax_result=tax_result,
                    variances=variances,
                    extractions=cached_extractions,
                    escalations=agent.escalations,
                    overall_confidence=agent._determine_overall_confidence(
                        cached_extractions
                    ),
                )
            else:
                await _emit_progress(
                    session,
                    task_id,
                    ProgressEvent(
                        stage=ProcessingStage.EXTRACTING,
                        progress=40,
                        message="Extracting document data",
                    ),
                )
                await session.commit()
                result = await agent.process(
                    client_id=str(client_id),
                    tax_year=tax_year,
                    session=session,
                    filing_status=filing_status,
                    user_form_type_overrides=user_form_type_overrides,
                    document_model=metadata.get("document_model"),
                )

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.GENERATING,
                    progress=90 if from_review else 80,
                    message="Uploading generated outputs",
                ),
            )
            await session.commit()

            output_prefix = _build_output_prefix(client_id, tax_year)
            worksheet_path = await _upload_output_with_timeout(
                storage_url,
                output_prefix,
                result.drake_worksheet_path,
            )
            notes_path = await _upload_output_with_timeout(
                storage_url,
                output_prefix,
                result.preparer_notes_path,
            )
            for local_path in (
                result.drake_worksheet_path,
                result.preparer_notes_path,
            ):
                try:
                    local_path.unlink(missing_ok=True)
                except OSError:
                    logger.warning(
                        "demo_output_cleanup_failed",
                        task_id=task_id,
                        path=str(local_path),
                    )

            await _create_artifact(
                session,
                task_id,
                DEMO_ARTIFACT_WORKSHEET,
                file_path=worksheet_path,
            )
            await _create_artifact(
                session,
                task_id,
                DEMO_ARTIFACT_NOTES,
                file_path=notes_path,
            )

            payload = await _build_results_payload(
                task_id=task_id,
                client_name=client_name,
                tax_year=tax_year,
                filing_status=filing_status,
                result=result,
                drake_path=worksheet_path,
                notes_path=notes_path,
            )
            await _save_results(session, task_id, payload)

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(UTC)

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.COMPLETE,
                    progress=100,
                    message="Processing complete",
                    status=task.status.value,
                ),
            )
            await session.commit()

        except EscalationRequired as exc:
            task.status = TaskStatus.ESCALATED
            escalation = Escalation(
                task_id=task_id,
                reason="; ".join(exc.reasons),
                escalated_at=datetime.now(UTC),
            )
            session.add(escalation)

            worksheet_path = None
            notes_path = None
            payload_result = exc.result

            if payload_result is not None:
                output_prefix = _build_output_prefix(client_id, tax_year)
                worksheet_path = await _upload_output_with_timeout(
                    storage_url,
                    output_prefix,
                    payload_result.drake_worksheet_path,
                )
                notes_path = await _upload_output_with_timeout(
                    storage_url,
                    output_prefix,
                    payload_result.preparer_notes_path,
                )
                for local_path in (
                    payload_result.drake_worksheet_path,
                    payload_result.preparer_notes_path,
                ):
                    try:
                        local_path.unlink(missing_ok=True)
                    except OSError:
                        logger.warning(
                            "demo_output_cleanup_failed",
                            task_id=task_id,
                            path=str(local_path),
                        )
                await _create_artifact(
                    session,
                    task_id,
                    DEMO_ARTIFACT_WORKSHEET,
                    file_path=worksheet_path,
                )
                await _create_artifact(
                    session,
                    task_id,
                    DEMO_ARTIFACT_NOTES,
                    file_path=notes_path,
                )

            payload = await _build_results_payload(
                task_id=task_id,
                client_name=client_name,
                tax_year=tax_year,
                filing_status=filing_status,
                result=payload_result,
                escalations=exc.reasons,
                drake_path=worksheet_path,
                notes_path=notes_path,
            )
            await _save_results(session, task_id, payload)

            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.COMPLETE,
                    progress=100,
                    message="Escalation required",
                    status=task.status.value,
                ),
            )
            await session.commit()

        except Exception as exc:
            logger.exception("demo_processing_failed", task_id=task_id, error=str(exc))
            task.status = TaskStatus.FAILED
            failure_message = "Processing failed"
            error_detail = str(exc).strip()
            if error_detail:
                failure_message = f"Processing failed: {error_detail[:180]}"
            await _emit_progress(
                session,
                task_id,
                ProgressEvent(
                    stage=ProcessingStage.COMPLETE,
                    progress=100,
                    message=failure_message,
                    status=task.status.value,
                ),
            )
            await session.commit()


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    client_name: str = Form("Demo Client"),
    tax_year: int = Form(2025),
    filing_status: str = Form("single"),
    form_types: str | None = Form(None),
    document_model: str | None = Form(None),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> UploadResponse:
    """Upload tax documents for processing.
    
    Args:
        files: List of documents to upload.
        client_name: Name of the client.
        tax_year: Tax year for the documents.
        filing_status: Filing status (single, mfj, mfs, hoh).
        form_types: Optional JSON array of form types for each file.
            e.g., '["auto", "W2", "1099-INT"]'
            Valid values: auto, W2, 1099-INT, 1099-DIV, 1099-NEC,
                         1098, 1099-R, 1099-G, 1098-T, 5498, 1099-S
        document_model: Optional selected model override for document extraction/classification.
            Must be one of: claude-opus-4-6, claude-sonnet-4-5-20250929.
        db: Database session.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    valid_statuses = {"single", "mfj", "mfs", "hoh"}
    if filing_status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid filing status. Must be one of: {', '.join(valid_statuses)}",
        )
    normalized_model = document_model.strip().lower() if document_model else None
    if normalized_model:
        if normalized_model not in DEMO_DOCUMENT_MODELS:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid document_model. Must be one of: "
                    "claude-opus-4-6, claude-sonnet-4-5-20250929"
                ),
            )

    # Ensure canonical ID is stored (already validated).
    selected_document_model = normalized_model

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    # Parse form_types if provided
    parsed_form_types: list[str | None] = []
    if form_types:
        try:
            parsed_form_types = orjson.loads(form_types)
            if not isinstance(parsed_form_types, list):
                raise HTTPException(
                    status_code=400,
                    detail="form_types must be a JSON array",
                )
        except orjson.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="form_types must be a valid JSON array",
            )
    
    # Pad with None if form_types is shorter than files
    while len(parsed_form_types) < len(files):
        parsed_form_types.append(None)

    task = await _create_task(db, client_name)
    storage_url = settings.default_storage_url
    storage_prefix = _build_storage_prefix(task.client_id, tax_year)

    valid_form_types = {
        "auto", "W2", "1099-INT", "1099-DIV", "1099-NEC",
        "1098", "1099-R", "1099-G", "1098-T", "5498", "1099-S",
    }

    for idx, upload in enumerate(files):
        if upload.content_type not in settings.allowed_upload_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {upload.content_type}",
            )

        content = await upload.read()
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail="File exceeds maximum upload size",
            )

        safe_name = _sanitize_filename(upload.filename or "upload")
        storage_path = f"{storage_prefix}/{safe_name}"
        checksum = hashlib.sha256(content).hexdigest()

        # Get user-selected form type for this file
        user_form_type = parsed_form_types[idx] if idx < len(parsed_form_types) else None
        if user_form_type == "auto":
            user_form_type = None  # Treat 'auto' as no selection
        if user_form_type and user_form_type not in valid_form_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid form type: {user_form_type}. "
                       f"Must be one of: {', '.join(sorted(valid_form_types))}",
            )

        await write_file(storage_url, storage_path, content)
        await _create_artifact(
            session=db,
            task_id=task.id,
            artifact_type=DEMO_ARTIFACT_UPLOADED,
            content={
                "filename": safe_name,
                "content_type": upload.content_type,
                "size": len(content),
                "checksum": checksum,
                "storage_path": storage_path,
                "user_selected_form_type": user_form_type,
            },
            file_path=storage_path,
        )

    await _create_artifact(
        session=db,
        task_id=task.id,
        artifact_type=DEMO_ARTIFACT_METADATA,
        content={
            "client_id": task.client_id,
            "client_name": client_name,
            "tax_year": tax_year,
            "filing_status": filing_status,
            "storage_url": storage_url,
            "document_model": selected_document_model,
        },
    )

    await _emit_progress(
        session=db,
        task_id=task.id,
        event=ProgressEvent(
            stage=ProcessingStage.UPLOADING,
            progress=5,
            message=f"Uploaded {len(files)} document(s)",
        ),
    )
    await db.commit()

    logger.info(
        "demo_upload_complete",
        task_id=task.id,
        files=len(files),
        client_name=client_name,
    )

    return UploadResponse(
        job_id=str(task.id),
        message=f"Successfully uploaded {len(files)} file(s)",
        files_received=len(files),
    )


@router.post("/job/{job_id}/add-documents", response_model=UploadResponse)
async def add_documents_to_job(
    job_id: int,
    files: list[UploadFile] = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> UploadResponse:
    """Add additional documents to an existing job."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.status not in {TaskStatus.COMPLETED, TaskStatus.ESCALATED, TaskStatus.FAILED}:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot add documents to job with status: {task.status.value}",
        )

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    metadata = await _get_metadata(db, job_id)
    storage_url = metadata.get("storage_url", settings.default_storage_url)
    tax_year = int(metadata.get("tax_year", datetime.now(UTC).year))
    storage_prefix = _build_storage_prefix(task.client_id, tax_year)

    for upload in files:
        # Handle missing content_type (some browsers don't send it)
        content_type = upload.content_type
        if not content_type:
            # Infer from filename extension
            filename = upload.filename or "upload"
            if filename.lower().endswith('.pdf'):
                content_type = 'application/pdf'
            elif filename.lower().endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif filename.lower().endswith('.png'):
                content_type = 'image/png'
            else:
                content_type = 'application/octet-stream'
        
        if content_type not in settings.allowed_upload_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {content_type}. Allowed types: {', '.join(settings.allowed_upload_types)}",
            )

        content = await upload.read()
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File {upload.filename} is empty",
            )
        
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File {upload.filename} exceeds maximum upload size of {settings.max_upload_bytes} bytes",
            )

        safe_name = _sanitize_filename(upload.filename or "upload")
        storage_path = f"{storage_prefix}/{safe_name}"
        checksum = hashlib.sha256(content).hexdigest()

        try:
            await write_file(storage_url, storage_path, content)
        except Exception as e:
            logger.error(
                "demo_file_write_failed",
                task_id=task.id,
                filename=safe_name,
                error=str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file {safe_name}: {str(e)}",
            )
        
        await _create_artifact(
            session=db,
            task_id=task.id,
            artifact_type=DEMO_ARTIFACT_UPLOADED,
            content={
                "filename": safe_name,
                "content_type": content_type,
                "size": len(content),
                "checksum": checksum,
                "storage_path": storage_path,
            },
            file_path=storage_path,
        )

    # Reset task status to allow reprocessing
    task.status = TaskStatus.PENDING
    await _emit_progress(
        session=db,
        task_id=task.id,
        event=ProgressEvent(
            stage=ProcessingStage.UPLOADING,
            progress=5,
            message=f"Added {len(files)} additional document(s)",
        ),
    )
    await db.commit()

    logger.info(
        "demo_documents_added",
        task_id=task.id,
        files=len(files),
    )

    return UploadResponse(
        job_id=str(job_id),
        message=f"Successfully added {len(files)} document(s)",
        files_received=len(files),
    )


@router.post("/process/{job_id}", response_model=ProcessResponse)
async def start_processing(
    job_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ProcessResponse:
    """Start processing uploaded documents."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    # Allow reprocessing if job is completed, escalated, or failed (for adding new documents)
    if task.status not in {
        TaskStatus.PENDING,
        TaskStatus.FAILED,
        TaskStatus.COMPLETED,
        TaskStatus.ESCALATED,
    }:
        raise HTTPException(
            status_code=400,
            detail=f"Job cannot be started. Current status: {task.status.value}",
        )

    task.status = TaskStatus.IN_PROGRESS
    await db.commit()

    session_factory = request.app.state.async_session
    asyncio.create_task(_prepare_job_for_review(job_id, session_factory))

    return ProcessResponse(
        job_id=str(job_id),
        status="processing",
        message="Extraction started",
    )


@router.get("/preview/{job_id}", response_model=ExtractionPreviewResponse)
async def get_extraction_preview(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ExtractionPreviewResponse:
    """Get extracted fields for user verification before calculation."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    preview_artifact = await _get_latest_artifact(
        db, job_id, DEMO_ARTIFACT_EXTRACTION_PREVIEW
    )
    if not preview_artifact:
        raise HTTPException(status_code=404, detail="Extraction preview not ready")

    preview = _json_loads(preview_artifact.content)
    return ExtractionPreviewResponse(
        job_id=str(job_id),
        status=task.status.value,
        message=preview.get(
            "message", "Please verify extracted data before tax calculation."
        ),
        extractions=[
            ExtractionItem(
                filename=item.get("filename", "unknown"),
                document_type=item.get("document_type", "unknown"),
                confidence=item.get("confidence", "HIGH"),
                classification_confidence=item.get("classification_confidence"),
                classification_reasoning=item.get("classification_reasoning"),
                classification_overridden=item.get("classification_overridden", False),
                classification_override_source=item.get("classification_override_source"),
                classification_original_type=item.get("classification_original_type"),
                classification_original_confidence=item.get(
                    "classification_original_confidence"
                ),
                classification_original_reasoning=item.get(
                    "classification_original_reasoning"
                ),
                key_fields=item.get("key_fields", {}),
            )
            for item in preview.get("extractions", [])
        ],
        escalations=preview.get("escalations", []),
    )


@router.post("/verify/{job_id}", response_model=ProcessResponse)
async def verify_extraction_preview(
    job_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ProcessResponse:
    """Continue full processing after user verifies extraction preview."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    progress_artifact = await _get_latest_artifact(db, job_id, DEMO_ARTIFACT_PROGRESS)
    progress_data = _json_loads(progress_artifact.content if progress_artifact else None)
    if progress_data.get("stage") != ProcessingStage.REVIEW.value:
        raise HTTPException(
            status_code=409,
            detail="Job is not waiting for extraction verification",
        )

    if task.status not in {TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED}:
        raise HTTPException(
            status_code=409,
            detail=f"Job cannot be verified from status: {task.status.value}",
        )

    preview_artifact = await _get_latest_artifact(
        db, job_id, DEMO_ARTIFACT_EXTRACTION_PREVIEW
    )
    preview_payload = _json_loads(preview_artifact.content if preview_artifact else None)
    if not preview_payload.get("serialized_extractions"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Verification cache unavailable for this job. "
                "Please restart processing from upload."
            ),
        )

    await _emit_progress(
        db,
        job_id,
        ProgressEvent(
            stage=ProcessingStage.CALCULATING,
            progress=70,
            message="Verification received. Running tax calculation",
        ),
    )
    await db.commit()

    session_factory = request.app.state.async_session
    asyncio.create_task(_process_job(job_id, session_factory, from_review=True))

    return ProcessResponse(
        job_id=str(job_id),
        status="processing",
        message="Verification received. Continuing processing.",
    )


@router.get("/stream/{job_id}")
async def stream_progress(job_id: int, request: Request) -> StreamingResponse:
    """Stream processing progress via Server-Sent Events."""
    session_factory = request.app.state.async_session

    async def event_generator():
        last_id = 0
        while True:
            async with session_factory() as session:
                task = await _get_task(session, job_id)
                if not task:
                    yield "data: {\"error\": \"Job not found\"}\n\n"
                    return

                stmt = (
                    select(TaskArtifact)
                    .where(TaskArtifact.task_id == job_id)
                    .where(TaskArtifact.artifact_type == DEMO_ARTIFACT_PROGRESS)
                    .where(TaskArtifact.id > last_id)
                    .order_by(TaskArtifact.id.asc())
                )
                result = await session.execute(stmt)
                artifacts = list(result.scalars().all())

            for artifact in artifacts:
                last_id = artifact.id
                data = _json_loads(artifact.content)
                yield f"data: {orjson.dumps(data).decode('utf-8')}\n\n"

            if task.status in {
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.ESCALATED,
            }:
                status_message = "Processing complete"
                if task.status == TaskStatus.FAILED:
                    status_message = "Processing failed"
                if task.status == TaskStatus.ESCALATED:
                    status_message = "Escalation required"
                final_data = {
                    "stage": "complete",
                    "progress": 100,
                    "status": task.status.value,
                    "message": status_message,
                }
                yield f"data: {orjson.dumps(final_data).decode('utf-8')}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> JobStatusResponse:
    """Get current job status."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    progress_artifact = await _get_latest_artifact(
        db, job_id, DEMO_ARTIFACT_PROGRESS
    )
    progress_data = _json_loads(progress_artifact.content if progress_artifact else None)
    status_value = task.status.value
    if task.status in {TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED}:
        status_value = "processing"

    return JobStatusResponse(
        job_id=str(job_id),
        status=status_value,
        progress=int(progress_data.get("progress", 0)),
        current_stage=progress_data.get("stage", ProcessingStage.UPLOADING.value),
        message=progress_data.get("message"),
    )


@router.get("/results/{job_id}", response_model=ResultsResponse)
async def get_results(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> ResultsResponse:
    """Get processing results."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED}:
        raise HTTPException(status_code=202, detail="Processing still in progress")

    if task.status == TaskStatus.FAILED:
        raise HTTPException(status_code=500, detail="Processing failed")

    metadata = await _get_metadata(db, job_id)
    results_artifact = await _get_latest_artifact(db, job_id, DEMO_ARTIFACT_RESULTS)
    results = _json_loads(results_artifact.content if results_artifact else None)

    income = results.get("income", {})
    tax = results.get("tax", {})

    return ResultsResponse(
        job_id=str(job_id),
        status=task.status.value,
        client_name=metadata.get("client_name", results.get("client_name", "Demo Client")),
        tax_year=int(metadata.get("tax_year", results.get("tax_year", 2025))),
        filing_status=metadata.get(
            "filing_status", results.get("filing_status", "single")
        ),
        overall_confidence=results.get("overall_confidence", "LOW"),
        income=IncomeBreakdown(
            total_wages=_format_currency(_to_decimal(income.get("total_wages", 0))),
            total_interest=_format_currency(_to_decimal(income.get("total_interest", 0))),
            total_dividends=_format_currency(
                _to_decimal(income.get("total_dividends", 0))
            ),
            total_qualified_dividends=_format_currency(
                _to_decimal(income.get("total_qualified_dividends", 0))
            ),
            total_nec=_format_currency(_to_decimal(income.get("total_nec", 0))),
            total_retirement_distributions=_format_currency(
                _to_decimal(income.get("total_retirement_distributions", 0))
            ),
            total_unemployment=_format_currency(
                _to_decimal(income.get("total_unemployment", 0))
            ),
            total_state_tax_refund=_format_currency(
                _to_decimal(income.get("total_state_tax_refund", 0))
            ),
            total_income=_format_currency(_to_decimal(income.get("total_income", 0))),
            federal_withholding=_format_currency(
                _to_decimal(income.get("federal_withholding", 0))
            ),
        ),
        tax=TaxCalculation(
            taxable_income=_format_currency(_to_decimal(tax.get("taxable_income", 0))),
            gross_tax=_format_currency(_to_decimal(tax.get("gross_tax", 0))),
            credits_applied=_format_currency(_to_decimal(tax.get("credits_applied", 0))),
            final_liability=_format_currency(_to_decimal(tax.get("final_liability", 0))),
            refundable_credits=_format_currency(
                _to_decimal(tax.get("refundable_credits", 0))
            ),
            effective_rate=_format_percentage(_to_decimal(tax.get("effective_rate", 0))),
        ),
        extractions=[
            ExtractionItem(
                filename=e.get("filename", "unknown"),
                document_type=e.get("document_type", "unknown"),
                confidence=e.get("confidence", "HIGH"),
                classification_confidence=e.get("classification_confidence"),
                classification_reasoning=e.get("classification_reasoning"),
                classification_overridden=e.get("classification_overridden", False),
                classification_original_type=e.get("classification_original_type"),
                classification_original_confidence=e.get(
                    "classification_original_confidence"
                ),
                classification_original_reasoning=e.get(
                    "classification_original_reasoning"
                ),
                key_fields=e.get("key_fields", {}),
            )
            for e in results.get("extractions", [])
        ],
        variances=[
            VarianceItem(
                field=v.get("field", "unknown"),
                current_value=_format_currency(_to_decimal(v.get("current_value", 0))),
                prior_value=_format_currency(_to_decimal(v.get("prior_value", 0))),
                variance_pct=_format_percentage(_to_decimal(v.get("variance_pct", 0))),
                direction=v.get("direction", "increase"),
            )
            for v in results.get("variances", [])
        ],
        escalations=results.get("escalations", []),
        drake_worksheet_available=bool(results.get("drake_worksheet_path")),
        preparer_notes_available=bool(results.get("preparer_notes_path")),
    )


@router.get("/download/{job_id}/{file_type}")
async def download_file(
    job_id: int,
    file_type: str,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> StreamingResponse:
    """Download generated output file."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task.status not in {TaskStatus.COMPLETED, TaskStatus.ESCALATED}:
        raise HTTPException(status_code=400, detail="Job not completed")

    if file_type == "worksheet":
        artifact_type = DEMO_ARTIFACT_WORKSHEET
        filename = f"drake_worksheet_{job_id}.xlsx"
        media_type = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    elif file_type == "notes":
        artifact_type = DEMO_ARTIFACT_NOTES
        filename = f"preparer_notes_{job_id}.md"
        media_type = "text/markdown"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Must be 'worksheet' or 'notes'",
        )

    artifact = await _get_latest_artifact(db, job_id, artifact_type)
    if not artifact or not artifact.file_path:
        raise HTTPException(status_code=404, detail="File not found")

    metadata = await _get_metadata(db, job_id)
    storage_url = metadata.get("storage_url", settings.default_storage_url)
    fs = get_filesystem(storage_url)
    full_path = build_full_path(storage_url, artifact.file_path)

    if not fs.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    def file_iterator():
        with fs.open(full_path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/job/{job_id}/uploaded-documents",
    response_model=UploadedDocumentsResponse,
)
async def get_uploaded_documents(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> UploadedDocumentsResponse:
    """List uploaded source documents for verification UI."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(TaskArtifact)
        .where(TaskArtifact.task_id == job_id)
        .where(TaskArtifact.artifact_type == DEMO_ARTIFACT_UPLOADED)
        .order_by(TaskArtifact.id.asc())
    )
    artifacts = list(result.scalars().all())

    files: list[UploadedDocumentItem] = []
    for artifact in artifacts:
        content = _json_loads(artifact.content)
        filename = content.get("filename")
        if not filename and artifact.file_path:
            filename = Path(artifact.file_path).name
        files.append(
            UploadedDocumentItem(
                artifact_id=artifact.id,
                filename=filename or f"document_{artifact.id}",
                content_type=content.get("content_type", "application/octet-stream"),
                size=content.get("size"),
                uploaded_at=artifact.created_at.isoformat(),
            )
        )

    return UploadedDocumentsResponse(
        job_id=str(job_id),
        files=files,
    )


@router.get("/job/{job_id}/uploaded-documents/{artifact_id}")
async def view_uploaded_document(
    job_id: int,
    artifact_id: int,
    download: bool = Query(default=False),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> StreamingResponse:
    """Stream an uploaded source document for inline verification."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    artifact = await db.get(TaskArtifact, artifact_id)
    if not artifact or artifact.task_id != job_id:
        raise HTTPException(status_code=404, detail="Uploaded document not found")
    if artifact.artifact_type != DEMO_ARTIFACT_UPLOADED:
        raise HTTPException(status_code=404, detail="Uploaded document not found")
    if not artifact.file_path:
        raise HTTPException(status_code=404, detail="Uploaded document not found")

    metadata = await _get_metadata(db, job_id)
    storage_url = metadata.get("storage_url", settings.default_storage_url)
    fs = get_filesystem(storage_url)
    full_path = build_full_path(storage_url, artifact.file_path)
    if not fs.exists(full_path):
        raise HTTPException(status_code=404, detail="Uploaded document not found")

    content = _json_loads(artifact.content)
    filename = content.get("filename")
    if not filename:
        filename = Path(artifact.file_path).name
    media_type = content.get("content_type", "application/octet-stream")
    disposition = "attachment" if download else "inline"

    def file_iterator():
        with fs.open(full_path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        file_iterator(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.delete("/job/{job_id}")
async def delete_job(
    job_id: int,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
) -> dict[str, str]:
    """Delete a job and its files."""
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")

    task = await _get_task(db, job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    metadata = await _get_metadata(db, job_id)
    storage_url = metadata.get("storage_url", settings.default_storage_url)
    client_id = metadata.get("client_id")
    tax_year = metadata.get("tax_year")

    if client_id and tax_year:
        prefix = _build_storage_prefix(int(client_id), int(tax_year))
        fs = get_filesystem(storage_url)
        storage_path = build_full_path(storage_url, prefix)
        if fs.exists(storage_path):
            fs.rm(storage_path, recursive=True)

    stmt = select(TaskArtifact).where(TaskArtifact.task_id == job_id)
    result = await db.execute(stmt)
    for artifact in result.scalars().all():
        await db.delete(artifact)

    stmt = select(Escalation).where(Escalation.task_id == job_id)
    result = await db.execute(stmt)
    for escalation in result.scalars().all():
        await db.delete(escalation)

    await db.delete(task)
    await db.commit()

    return {"message": f"Job {job_id} deleted"}
