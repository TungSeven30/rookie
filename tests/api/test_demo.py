"""Tests for the demo API endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import tempfile
from typing import Any

import orjson
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.agents.personal_tax.agent import PersonalTaxResult
from src.agents.personal_tax.calculator import IncomeSummary, TaxResult
from src.documents.models import W2Data
from src.api.demo import (
    DEMO_ARTIFACT_EXTRACTION_PREVIEW,
    DEMO_ARTIFACT_METADATA,
    DEMO_ARTIFACT_RESULTS,
    DEMO_ARTIFACT_PROGRESS,
    DEMO_TASK_TYPE,
    _build_results_payload,
)
from src.api.deps import get_db
from src.core.config import settings
from src.main import app
from src.models.client import Client
from src.models.task import Escalation, Task, TaskArtifact, TaskStatus


@pytest.fixture
def demo_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set demo API key header."""
    monkeypatch.setattr(settings, "demo_api_key", "test-key")
    return {"X-Demo-Api-Key": "test-key"}


@pytest.fixture
def demo_storage_dir(monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide temporary storage and output directories."""
    temp_dir = Path(tempfile.mkdtemp())
    monkeypatch.setattr(settings, "default_storage_url", str(temp_dir))
    monkeypatch.setattr(settings, "output_dir", str(temp_dir / "output"))
    return temp_dir


@pytest_asyncio.fixture
async def session_factory() -> AsyncGenerator[async_sessionmaker[AsyncSession], None]:
    """Create async session factory backed by sqlite."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Client.__table__.create)
        await conn.run_sync(Task.__table__.create)
        await conn.run_sync(TaskArtifact.__table__.create)
        await conn.run_sync(Escalation.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.async_session = factory
    try:
        yield factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def api_client(
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
    demo_storage_dir: Path,
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async client with DB override."""
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_pdf_file() -> BytesIO:
    """Create a minimal test PDF-like file."""
    return BytesIO(b"%PDF-1.4 test content")


@pytest.mark.asyncio
async def test_requires_api_key(api_client: AsyncClient, test_pdf_file: BytesIO) -> None:
    """Demo endpoints reject missing API key."""
    response = await api_client.post(
        "/api/demo/upload",
        files=[("files", ("test_w2.pdf", test_pdf_file, "application/pdf"))],
        data={"client_name": "Test Client", "tax_year": "2024", "filing_status": "single"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_documents(
    api_client: AsyncClient, demo_headers: dict[str, str], test_pdf_file: BytesIO
) -> None:
    """Upload creates a job."""
    response = await api_client.post(
        "/api/demo/upload",
        headers=demo_headers,
        files=[("files", ("test_w2.pdf", test_pdf_file, "application/pdf"))],
        data={"client_name": "Test Client", "tax_year": "2024", "filing_status": "single"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["files_received"] == 1
    assert data["message"] == "Successfully uploaded 1 file(s)"


@pytest.mark.asyncio
async def test_upload_invalid_filing_status(
    api_client: AsyncClient, demo_headers: dict[str, str], test_pdf_file: BytesIO
) -> None:
    """Upload rejects invalid filing status."""
    response = await api_client.post(
        "/api/demo/upload",
        headers=demo_headers,
        files=[("files", ("test.pdf", test_pdf_file, "application/pdf"))],
        data={"client_name": "Test Client", "tax_year": "2024", "filing_status": "invalid"},
    )

    assert response.status_code == 400
    assert "Invalid filing status" in response.json()["detail"]


@pytest.mark.asyncio
async def test_job_status_not_found(
    api_client: AsyncClient, demo_headers: dict[str, str]
) -> None:
    """Status check for non-existent job."""
    response = await api_client.get("/api/demo/status/9999", headers=demo_headers)

    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_preview_returns_extracted_data(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
) -> None:
    """Preview endpoint returns extraction payload for verification."""
    async with session_factory() as session:
        client = Client(name="Preview Client")
        session.add(client)
        await session.flush()

        task = Task(
            client_id=client.id,
            task_type=DEMO_TASK_TYPE,
            status=TaskStatus.IN_PROGRESS,
        )
        session.add(task)
        await session.flush()

        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_EXTRACTION_PREVIEW,
                content=orjson.dumps(
                    {
                        "message": "Please verify extracted data before tax calculation.",
                        "extractions": [
                            {
                                "filename": "sample_w2.pdf",
                                "document_type": "W2",
                                "confidence": "HIGH",
                                "key_fields": {
                                    "wages": "$75,000.00",
                                    "federal_withholding": "$9,200.00",
                                },
                            }
                        ],
                        "escalations": [],
                    }
                ).decode("utf-8"),
            )
        )
        await session.commit()

    response = await api_client.get(f"/api/demo/preview/{task.id}", headers=demo_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == str(task.id)
    assert payload["extractions"][0]["document_type"] == "W2"
    assert payload["extractions"][0]["key_fields"]["wages"] == "$75,000.00"


@pytest.mark.asyncio
async def test_verify_requires_review_stage(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
) -> None:
    """Verify endpoint rejects jobs that are not at review stage."""
    async with session_factory() as session:
        client = Client(name="Verify Client")
        session.add(client)
        await session.flush()

        task = Task(
            client_id=client.id,
            task_type=DEMO_TASK_TYPE,
            status=TaskStatus.IN_PROGRESS,
        )
        session.add(task)
        await session.flush()

        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_PROGRESS,
                content=orjson.dumps(
                    {
                        "stage": "extracting",
                        "progress": 40,
                        "message": "Extracting document data",
                    }
                ).decode("utf-8"),
            )
        )
        await session.commit()

    response = await api_client.post(f"/api/demo/verify/{task.id}", headers=demo_headers)

    assert response.status_code == 409
    assert "not waiting for extraction verification" in response.json()["detail"]


@pytest.mark.asyncio
async def test_verify_starts_post_review_processing(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify endpoint queues calculation flow when review is complete."""
    async with session_factory() as session:
        client = Client(name="Verify Ready Client")
        session.add(client)
        await session.flush()

        task = Task(
            client_id=client.id,
            task_type=DEMO_TASK_TYPE,
            status=TaskStatus.IN_PROGRESS,
        )
        session.add(task)
        await session.flush()

        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_PROGRESS,
                content=orjson.dumps(
                    {
                        "stage": "review",
                        "progress": 60,
                        "message": "Review extracted data and confirm to continue",
                    }
                ).decode("utf-8"),
            )
        )
        await session.commit()

    captured: dict[str, str] = {}
    original_create_task = asyncio.create_task

    def _capture_task(coro: Any) -> Any:
        coro_name = getattr(getattr(coro, "cr_code", None), "co_name", "")
        if coro_name == "_process_job":
            captured["coro_name"] = coro_name
            coro.close()
            return original_create_task(asyncio.sleep(0))
        return original_create_task(coro)

    monkeypatch.setattr("src.api.demo.asyncio.create_task", _capture_task)

    response = await api_client.post(f"/api/demo/verify/{task.id}", headers=demo_headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Verification received. Continuing processing."
    assert captured["coro_name"] == "_process_job"


@pytest.mark.asyncio
async def test_results_pending_returns_202(
    api_client: AsyncClient, demo_headers: dict[str, str], test_pdf_file: BytesIO
) -> None:
    """Results endpoint returns 202 while pending."""
    upload_response = await api_client.post(
        "/api/demo/upload",
        headers=demo_headers,
        files=[("files", ("test_w2.pdf", test_pdf_file, "application/pdf"))],
        data={"client_name": "Test Client", "tax_year": "2024", "filing_status": "single"},
    )
    job_id = upload_response.json()["job_id"]

    response = await api_client.get(f"/api/demo/results/{job_id}", headers=demo_headers)

    assert response.status_code == 202


@pytest.mark.asyncio
async def test_results_escalated_response(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
) -> None:
    """Escalated jobs return structured results."""
    async with session_factory() as session:
        client = Client(name="Escalated Client")
        session.add(client)
        await session.flush()

        task = Task(
            client_id=client.id,
            task_type=DEMO_TASK_TYPE,
            status=TaskStatus.ESCALATED,
        )
        session.add(task)
        await session.flush()

        metadata = {
            "client_id": client.id,
            "client_name": client.name,
            "tax_year": 2024,
            "filing_status": "single",
            "storage_url": settings.default_storage_url,
        }
        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_METADATA,
                content=orjson.dumps(metadata).decode("utf-8"),
            )
        )
        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_RESULTS,
                content=orjson.dumps({"escalations": ["Missing W-2"]}).decode("utf-8"),
            )
        )
        await session.commit()

        response = await api_client.get(
            f"/api/demo/results/{task.id}", headers=demo_headers
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "escalated"
    assert data["escalations"] == ["Missing W-2"]


@pytest.mark.asyncio
async def test_build_results_payload_includes_classification_details() -> None:
    """Results payload surfaces classification details for CPA review."""
    income_summary = IncomeSummary(
        total_wages=Decimal("0"),
        total_interest=Decimal("0"),
        total_dividends=Decimal("0"),
        total_qualified_dividends=Decimal("0"),
        total_nec=Decimal("0"),
        total_other=Decimal("0"),
        total_income=Decimal("0"),
        federal_withholding=Decimal("0"),
    )
    tax_result = TaxResult(
        gross_tax=Decimal("0"),
        bracket_breakdown=[],
        effective_rate=Decimal("0"),
        credits_applied=Decimal("0"),
        final_liability=Decimal("0"),
        refundable_credits=Decimal("0"),
    )
    result = PersonalTaxResult(
        drake_worksheet_path=Path("worksheet.xlsx"),
        preparer_notes_path=Path("notes.md"),
        income_summary=income_summary,
        tax_result=tax_result,
        variances=[],
        extractions=[
            {
                "filename": "2024_W-2__2_.pdf (page 1)",
                "document_type": "W2",
                "confidence": "MEDIUM",
                "classification_confidence": 0.88,
                "classification_reasoning": "Mock classification",
                "classification_overridden": True,
                "classification_original_type": "1099-NEC",
                "classification_override_source": "user",
            }
        ],
        escalations=["Missing expected document: W2"],
        overall_confidence="LOW",
    )

    payload = await _build_results_payload(
        task_id=1,
        client_name="Test Client",
        tax_year=2024,
        filing_status="single",
        result=result,
        escalations=["Missing expected document: W2"],
    )

    extraction = payload["extractions"][0]
    assert extraction["classification_reasoning"] == "Mock classification"
    assert extraction["classification_original_type"] == "1099-NEC"
    assert extraction["classification_override_source"] == "user"
    assert payload["escalations"] == ["Missing expected document: W2"]


@pytest.mark.asyncio
async def test_build_results_payload_includes_new_income_fields() -> None:
    """Results payload includes retirement and unemployment fields."""
    income_summary = IncomeSummary(
        total_wages=Decimal("1000"),
        total_interest=Decimal("0"),
        total_dividends=Decimal("0"),
        total_qualified_dividends=Decimal("0"),
        total_nec=Decimal("0"),
        total_retirement_distributions=Decimal("4000"),
        total_unemployment=Decimal("2500"),
        total_state_tax_refund=Decimal("300"),
        total_other=Decimal("0"),
        total_income=Decimal("7500"),
        federal_withholding=Decimal("0"),
    )
    tax_result = TaxResult(
        gross_tax=Decimal("0"),
        bracket_breakdown=[],
        effective_rate=Decimal("0"),
        credits_applied=Decimal("0"),
        final_liability=Decimal("0"),
        refundable_credits=Decimal("0"),
    )
    result = PersonalTaxResult(
        drake_worksheet_path=Path("worksheet.xlsx"),
        preparer_notes_path=Path("notes.md"),
        income_summary=income_summary,
        tax_result=tax_result,
        variances=[],
        extractions=[],
        escalations=[],
        overall_confidence="HIGH",
    )

    payload = await _build_results_payload(
        task_id=1,
        client_name="Test Client",
        tax_year=2024,
        filing_status="single",
        result=result,
    )

    income = payload["income"]
    assert income["total_retirement_distributions"] == "4000"
    assert income["total_unemployment"] == "2500"
    assert income["total_state_tax_refund"] == "300"


@pytest.mark.asyncio
async def test_build_results_payload_includes_w2_key_fields() -> None:
    """Results payload includes key W-2 fields for review."""
    income_summary = IncomeSummary(
        total_wages=Decimal("0"),
        total_interest=Decimal("0"),
        total_dividends=Decimal("0"),
        total_qualified_dividends=Decimal("0"),
        total_nec=Decimal("0"),
        total_other=Decimal("0"),
        total_income=Decimal("0"),
        federal_withholding=Decimal("0"),
    )
    tax_result = TaxResult(
        gross_tax=Decimal("0"),
        bracket_breakdown=[],
        effective_rate=Decimal("0"),
        credits_applied=Decimal("0"),
        final_liability=Decimal("0"),
        refundable_credits=Decimal("0"),
    )
    w2 = W2Data(
        employee_ssn="123-45-6789",
        employer_ein="12-3456789",
        employer_name="Test Corp",
        employee_name="John Doe",
        wages_tips_compensation=Decimal("78321.05"),
        federal_tax_withheld=Decimal("13120.45"),
        social_security_wages=Decimal("78321.05"),
        social_security_tax=Decimal("4857.91"),
        medicare_wages=Decimal("78321.05"),
        medicare_tax=Decimal("1135.75"),
        confidence="HIGH",
    )
    result = PersonalTaxResult(
        drake_worksheet_path=Path("worksheet.xlsx"),
        preparer_notes_path=Path("notes.md"),
        income_summary=income_summary,
        tax_result=tax_result,
        variances=[],
        extractions=[
            {
                "filename": "2024_W-2.pdf",
                "document_type": "W2",
                "confidence": "HIGH",
                "data": w2,
            }
        ],
        escalations=[],
        overall_confidence="HIGH",
    )

    payload = await _build_results_payload(
        task_id=1,
        client_name="Test Client",
        tax_year=2024,
        filing_status="single",
        result=result,
    )

    key_fields = payload["extractions"][0]["key_fields"]
    assert key_fields["wages"] == "$78,321.05"
    assert key_fields["federal_withholding"] == "$13,120.45"


@pytest.mark.asyncio
async def test_download_not_found_when_missing_artifact(
    api_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    demo_headers: dict[str, str],
) -> None:
    """Download returns 404 when output artifact is missing."""
    async with session_factory() as session:
        client = Client(name="Output Client")
        session.add(client)
        await session.flush()
        task = Task(
            client_id=client.id,
            task_type=DEMO_TASK_TYPE,
            status=TaskStatus.COMPLETED,
        )
        session.add(task)
        await session.flush()
        metadata = {
            "client_id": client.id,
            "client_name": client.name,
            "tax_year": 2024,
            "filing_status": "single",
            "storage_url": settings.default_storage_url,
        }
        session.add(
            TaskArtifact(
                task_id=task.id,
                artifact_type=DEMO_ARTIFACT_METADATA,
                content=orjson.dumps(metadata).decode("utf-8"),
            )
        )
        await session.commit()

        response = await api_client.get(
            f"/api/demo/download/{task.id}/worksheet",
            headers=demo_headers,
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_upload_and_delete(
    api_client: AsyncClient, demo_headers: dict[str, str], test_pdf_file: BytesIO
) -> None:
    """Upload and delete job."""
    upload_response = await api_client.post(
        "/api/demo/upload",
        headers=demo_headers,
        files=[("files", ("test_w2.pdf", test_pdf_file, "application/pdf"))],
        data={"client_name": "Test Client", "tax_year": "2024", "filing_status": "mfj"},
    )
    job_id = upload_response.json()["job_id"]

    delete_response = await api_client.delete(
        f"/api/demo/job/{job_id}", headers=demo_headers
    )
    assert delete_response.status_code == 200
    assert f"Job {job_id} deleted" in delete_response.json()["message"]

    status_response = await api_client.get(
        f"/api/demo/status/{job_id}", headers=demo_headers
    )
    assert status_response.status_code == 404
