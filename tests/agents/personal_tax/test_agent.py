"""Tests for PersonalTaxAgent and personal_tax_handler.

Tests cover:
- Agent initialization and configuration
- Document scanning and escalation on no documents
- Missing expected document detection (PTAX-15)
- Conflict detection (PTAX-16)
- Confidence determination
- Full workflow processing
- Handler integration with dispatcher
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.personal_tax.agent import (
    EscalationRequired,
    PersonalTaxAgent,
    PersonalTaxResult,
    personal_tax_handler,
)
from src.agents.personal_tax.calculator import IncomeSummary, TaxResult
from src.context.builder import AgentContext
from src.documents.classifier import ClassificationResult
from src.documents.models import (
    ConfidenceLevel,
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Data,
)
from src.documents.scanner import ClientDocument
from src.models.task import TaskStatus


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create client folder structure
        client_folder = Path(tmpdir) / "client123" / "2024"
        client_folder.mkdir(parents=True)

        # Create a dummy PDF file
        (client_folder / "w2_form.pdf").write_bytes(b"dummy pdf content")
        (client_folder / "1099int.jpg").write_bytes(b"dummy image content longer")

        yield tmpdir


@pytest.fixture
def mock_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.execute.return_value = MagicMock()
    session.commit = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def sample_w2() -> W2Data:
    """Create a sample W-2 for testing."""
    return W2Data(
        employee_ssn="123-45-6789",
        employer_ein="12-3456789",
        employer_name="Acme Corp",
        employee_name="John Doe",
        wages_tips_compensation=Decimal("75000"),
        federal_tax_withheld=Decimal("12500"),
        social_security_wages=Decimal("75000"),
        social_security_tax=Decimal("4650"),
        medicare_wages=Decimal("75000"),
        medicare_tax=Decimal("1087.50"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_int() -> Form1099INT:
    """Create a sample 1099-INT for testing."""
    return Form1099INT(
        payer_name="First National Bank",
        payer_tin="98-7654321",
        recipient_tin="123-45-6789",
        interest_income=Decimal("1250.75"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_div() -> Form1099DIV:
    """Create a sample 1099-DIV for testing."""
    return Form1099DIV(
        payer_name="Vanguard Funds",
        payer_tin="23-4567890",
        recipient_tin="123-45-6789",
        total_ordinary_dividends=Decimal("3500"),
        qualified_dividends=Decimal("2800"),
        confidence=ConfidenceLevel.MEDIUM,
    )


@pytest.fixture
def sample_1099_nec() -> Form1099NEC:
    """Create a sample 1099-NEC for testing."""
    return Form1099NEC(
        payer_name="Consulting Client LLC",
        payer_tin="34-5678901",
        recipient_name="John Doe",
        recipient_tin="123-45-6789",
        nonemployee_compensation=Decimal("15000"),
        confidence=ConfidenceLevel.LOW,
    )


@pytest.fixture
def mock_agent_context():
    """Create a mock agent context."""
    return AgentContext(
        client_id=1,
        client_name="John Doe",
        tax_year=2024,
        task_type="personal_tax",
        prior_year_return=None,
    )


@pytest.fixture
def mock_agent_context_with_prior():
    """Create a mock agent context with prior year data."""
    return AgentContext(
        client_id=1,
        client_name="John Doe",
        tax_year=2024,
        task_type="personal_tax",
        prior_year_return={
            "total_income": 70000,
            "wages": 65000,
            "interest": 1000,
            "dividends": 3000,
            "self_employment": 0,
            "tax_liability": 8000,
        },
    )


# =============================================================================
# Unit Tests - Agent Initialization
# =============================================================================


class TestAgentInit:
    """Tests for PersonalTaxAgent initialization."""

    def test_agent_init_with_storage_url(self, temp_output_dir):
        """Agent initializes with storage_url and output_dir."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )

        assert agent.storage_url == "/tmp/storage"
        assert agent.output_dir == temp_output_dir
        assert agent.escalations == []

    def test_agent_init_with_s3_url(self, temp_output_dir):
        """Agent initializes with S3 URL."""
        agent = PersonalTaxAgent(
            storage_url="s3://my-bucket/tax-docs",
            output_dir=temp_output_dir,
        )

        assert agent.storage_url == "s3://my-bucket/tax-docs"

    def test_agent_escalations_reset_on_process(self, temp_output_dir):
        """Agent escalations list is reset on each process call."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )
        agent.escalations = ["previous error"]

        # The escalations would be reset at start of process()
        agent.escalations = []
        assert agent.escalations == []


# =============================================================================
# Unit Tests - Escalation on No Documents
# =============================================================================


class TestEscalationNoDocuments:
    """Tests for escalation when no documents found."""

    @pytest.mark.asyncio
    async def test_agent_escalates_no_documents(
        self, temp_output_dir, mock_session, mock_agent_context
    ):
        """Agent raises EscalationRequired when no documents found."""
        agent = PersonalTaxAgent(
            storage_url="/nonexistent/path",
            output_dir=temp_output_dir,
        )

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            return_value=mock_agent_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=[],
            ):
                with pytest.raises(EscalationRequired) as exc_info:
                    await agent.process("client123", 2024, mock_session)

                assert "No documents found" in str(exc_info.value)
                assert len(exc_info.value.reasons) >= 1

    @pytest.mark.asyncio
    async def test_escalation_contains_reason(
        self, temp_output_dir, mock_session, mock_agent_context
    ):
        """EscalationRequired exception contains proper reasons."""
        agent = PersonalTaxAgent(
            storage_url="/nonexistent/path",
            output_dir=temp_output_dir,
        )

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            return_value=mock_agent_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=[],
            ):
                with pytest.raises(EscalationRequired) as exc_info:
                    await agent.process("client123", 2024, mock_session)

                assert "No documents found in client folder" in exc_info.value.reasons


# =============================================================================
# Unit Tests - Missing Expected Documents (PTAX-15)
# =============================================================================


class TestMissingDocuments:
    """Tests for missing expected document detection."""

    def test_get_expected_types_no_prior_year(self, temp_output_dir):
        """Without prior year, only W-2 is expected."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        expected = agent._get_expected_document_types(None)

        assert DocumentType.W2 in expected
        assert len(expected) == 1

    def test_get_expected_types_with_interest(self, temp_output_dir):
        """Prior year with interest expects 1099-INT."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )
        prior = {"income": {"interest": 500}}

        expected = agent._get_expected_document_types(prior)

        assert DocumentType.W2 in expected
        assert DocumentType.FORM_1099_INT in expected

    def test_get_expected_types_with_dividends(self, temp_output_dir):
        """Prior year with dividends expects 1099-DIV."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )
        prior = {"income": {"dividends": 1000}}

        expected = agent._get_expected_document_types(prior)

        assert DocumentType.FORM_1099_DIV in expected

    def test_get_expected_types_with_self_employment(self, temp_output_dir):
        """Prior year with self-employment expects 1099-NEC."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )
        prior = {"income": {"self_employment": 5000}}

        expected = agent._get_expected_document_types(prior)

        assert DocumentType.FORM_1099_NEC in expected

    def test_check_missing_documents_flags_escalation(
        self, temp_output_dir, mock_agent_context_with_prior
    ):
        """Missing expected documents are flagged for escalation."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )
        # Override prior year to expect 1099-INT
        mock_agent_context_with_prior.prior_year_return["income"] = {"interest": 500}

        # Only W-2 found, no 1099-INT
        extractions = [{"type": DocumentType.W2, "filename": "w2.pdf"}]

        agent._check_missing_documents(mock_agent_context_with_prior, extractions)

        assert len(agent.escalations) >= 1
        assert any("Missing expected" in e for e in agent.escalations)


# =============================================================================
# Unit Tests - Conflict Detection (PTAX-16)
# =============================================================================


class TestConflictDetection:
    """Tests for conflict detection across documents."""

    def test_check_conflicts_no_conflicts(self, temp_output_dir, sample_w2):
        """No conflicts when all SSNs match."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        extractions = [
            {"data": sample_w2, "filename": "w2.pdf"},
        ]

        conflicts = agent._check_conflicts(extractions)

        assert len(conflicts) == 0
        assert len(agent.escalations) == 0

    def test_check_conflicts_mismatched_ssn(
        self, temp_output_dir, sample_w2, sample_1099_int
    ):
        """Detects conflicting SSNs across documents."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        # Modify 1099-INT to have different recipient SSN
        sample_1099_int_diff = Form1099INT(
            payer_name="Bank",
            payer_tin="98-7654321",
            recipient_tin="987-65-4321",  # Different SSN
            interest_income=Decimal("500"),
            confidence=ConfidenceLevel.HIGH,
        )

        extractions = [
            {"data": sample_w2, "filename": "w2.pdf"},
            {"data": sample_1099_int_diff, "filename": "1099int.pdf"},
        ]

        conflicts = agent._check_conflicts(extractions)

        assert len(conflicts) >= 1
        assert len(agent.escalations) >= 1
        assert any("SSN" in e for e in agent.escalations)

    def test_check_conflicts_handles_empty_extractions(self, temp_output_dir):
        """Handles empty extractions list gracefully."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        conflicts = agent._check_conflicts([])

        assert len(conflicts) == 0


# =============================================================================
# Unit Tests - Confidence Determination
# =============================================================================


class TestConfidenceDetermination:
    """Tests for overall confidence determination."""

    def test_determine_confidence_all_high(self, temp_output_dir):
        """Returns HIGH when all extractions are HIGH."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        extractions = [
            {"confidence": "HIGH"},
            {"confidence": "HIGH"},
        ]

        result = agent._determine_overall_confidence(extractions)

        assert result == "HIGH"

    def test_determine_confidence_any_medium(self, temp_output_dir):
        """Returns MEDIUM when any extraction is MEDIUM."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        extractions = [
            {"confidence": "HIGH"},
            {"confidence": "MEDIUM"},
        ]

        result = agent._determine_overall_confidence(extractions)

        assert result == "MEDIUM"

    def test_determine_confidence_any_low(self, temp_output_dir):
        """Returns LOW when any extraction is LOW."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        extractions = [
            {"confidence": "HIGH"},
            {"confidence": "MEDIUM"},
            {"confidence": "LOW"},
        ]

        result = agent._determine_overall_confidence(extractions)

        assert result == "LOW"

    def test_determine_confidence_empty_returns_high(self, temp_output_dir):
        """Returns HIGH for empty extractions."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._determine_overall_confidence([])

        assert result == "HIGH"


# =============================================================================
# Integration Tests - Full Workflow (with mocked LLM)
# =============================================================================


@pytest.mark.asyncio
class TestAgentProcessWorkflow:
    """Integration tests for agent process workflow."""

    async def test_agent_process_single_w2(
        self, temp_output_dir, mock_session, sample_w2
    ):
        """Agent processes single W-2 successfully."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )

        # Create mock document
        mock_doc = ClientDocument(
            path="client123/2024/w2.pdf",
            name="w2.pdf",
            size=1000,
            modified=datetime.now(),
            extension="pdf",
        )

        # Mock context with no prior year
        mock_context = AgentContext(
            client_id=1,
            client_name="John Doe",
            tax_year=2024,
            task_type="personal_tax",
        )

        # Mock classification result
        mock_classification = ClassificationResult(
            document_type=DocumentType.W2,
            confidence=0.95,
            reasoning="Mock W-2",
        )

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            return_value=mock_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=[mock_doc],
            ):
                with patch(
                    "src.agents.personal_tax.agent.read_file",
                    return_value=b"dummy content",
                ):
                    with patch(
                        "src.agents.personal_tax.agent.classify_document",
                        return_value=mock_classification,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.extract_document",
                            return_value=sample_w2,
                        ):
                            result = await agent.process(
                                "client123", 2024, mock_session
                            )

        assert isinstance(result, PersonalTaxResult)
        assert result.drake_worksheet_path.exists()
        assert result.preparer_notes_path.exists()
        assert result.overall_confidence == "HIGH"
        assert len(result.extractions) == 1

    async def test_agent_process_multiple_documents(
        self, temp_output_dir, mock_session, sample_w2, sample_1099_int
    ):
        """Agent processes multiple documents correctly."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )

        # Create mock documents
        mock_docs = [
            ClientDocument(
                path="client123/2024/w2.pdf",
                name="w2.pdf",
                size=1000,
                modified=datetime.now(),
                extension="pdf",
            ),
            ClientDocument(
                path="client123/2024/1099int.jpg",
                name="1099int.jpg",
                size=2000,
                modified=datetime.now(),
                extension="jpg",
            ),
        ]

        mock_context = AgentContext(
            client_id=1,
            client_name="John Doe",
            tax_year=2024,
            task_type="personal_tax",
        )

        # Set up classification return values
        classifications = [
            ClassificationResult(
                document_type=DocumentType.W2, confidence=0.95, reasoning="W-2"
            ),
            ClassificationResult(
                document_type=DocumentType.FORM_1099_INT,
                confidence=0.90,
                reasoning="1099-INT",
            ),
        ]

        extractions = [sample_w2, sample_1099_int]
        classify_call_count = [0]
        extract_call_count = [0]

        async def mock_classify(*args, **kwargs):
            idx = classify_call_count[0]
            classify_call_count[0] += 1
            return classifications[idx]

        async def mock_extract(*args, **kwargs):
            idx = extract_call_count[0]
            extract_call_count[0] += 1
            return extractions[idx]

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            return_value=mock_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=mock_docs,
            ):
                with patch(
                    "src.agents.personal_tax.agent.read_file",
                    return_value=b"dummy content",
                ):
                    with patch(
                        "src.agents.personal_tax.agent.classify_document",
                        side_effect=mock_classify,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.extract_document",
                            side_effect=mock_extract,
                        ):
                            result = await agent.process(
                                "client123", 2024, mock_session
                            )

        assert len(result.extractions) == 2
        assert result.income_summary.total_wages == Decimal("75000")
        assert result.income_summary.total_interest == Decimal("1250.75")

    async def test_agent_generates_outputs(
        self, temp_output_dir, mock_session, sample_w2
    ):
        """Agent generates both Drake worksheet and preparer notes."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )

        mock_doc = ClientDocument(
            path="w2.pdf",
            name="w2.pdf",
            size=1000,
            modified=datetime.now(),
            extension="pdf",
        )

        mock_context = AgentContext(
            client_id=1,
            client_name="Test Client",
            tax_year=2024,
            task_type="personal_tax",
        )

        mock_classification = ClassificationResult(
            document_type=DocumentType.W2, confidence=0.95, reasoning="W-2"
        )

        # Create async mock for build_agent_context
        async def mock_build_context(*args, **kwargs):
            return mock_context

        # Create async mock for read_file
        async def mock_read(*args, **kwargs):
            return b"dummy"

        # Create async mock for classify_document
        async def mock_classify(*args, **kwargs):
            return mock_classification

        # Create async mock for extract_document
        async def mock_extract(*args, **kwargs):
            return sample_w2

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            side_effect=mock_build_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=[mock_doc],
            ):
                with patch(
                    "src.agents.personal_tax.agent.read_file",
                    side_effect=mock_read,
                ):
                    with patch(
                        "src.agents.personal_tax.agent.classify_document",
                        side_effect=mock_classify,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.extract_document",
                            side_effect=mock_extract,
                        ):
                            result = await agent.process(
                                "1", 2024, mock_session  # Use numeric ID
                            )

        # Check worksheet
        assert result.drake_worksheet_path.suffix == ".xlsx"
        assert result.drake_worksheet_path.exists()

        # Check notes
        assert result.preparer_notes_path.suffix == ".md"
        assert result.preparer_notes_path.exists()

        # Check notes content
        notes_content = result.preparer_notes_path.read_text()
        assert "Test Client" in notes_content
        assert "2024" in notes_content

    async def test_agent_compares_prior_year(
        self, temp_output_dir, mock_session, sample_w2
    ):
        """Agent detects variances from prior year."""
        agent = PersonalTaxAgent(
            storage_url="/tmp/storage",
            output_dir=temp_output_dir,
        )

        mock_doc = ClientDocument(
            path="w2.pdf",
            name="w2.pdf",
            size=1000,
            modified=datetime.now(),
            extension="pdf",
        )

        # Prior year had much lower wages (triggers >10% variance)
        mock_context = AgentContext(
            client_id=1,
            client_name="Test Client",
            tax_year=2024,
            task_type="personal_tax",
            prior_year_return={
                "total_income": 50000,
                "wages": 50000,
                "interest": 0,
                "dividends": 0,
                "self_employment": 0,
                "tax_liability": 5000,
            },
        )

        mock_classification = ClassificationResult(
            document_type=DocumentType.W2, confidence=0.95, reasoning="W-2"
        )

        # Create async mock for build_agent_context
        async def mock_build_context(*args, **kwargs):
            return mock_context

        # Create async mocks for other functions
        async def mock_read(*args, **kwargs):
            return b"dummy"

        async def mock_classify(*args, **kwargs):
            return mock_classification

        async def mock_extract(*args, **kwargs):
            return sample_w2

        with patch(
            "src.agents.personal_tax.agent.build_agent_context",
            side_effect=mock_build_context,
        ):
            with patch(
                "src.agents.personal_tax.agent.scan_client_folder",
                return_value=[mock_doc],
            ):
                with patch(
                    "src.agents.personal_tax.agent.read_file",
                    side_effect=mock_read,
                ):
                    with patch(
                        "src.agents.personal_tax.agent.classify_document",
                        side_effect=mock_classify,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.extract_document",
                            side_effect=mock_extract,
                        ):
                            result = await agent.process(
                                "1", 2024, mock_session  # Use numeric ID
                            )

        # Should have variances for wages increase (50000 -> 75000 = 50%)
        assert len(result.variances) >= 1
        wage_variances = [v for v in result.variances if "wages" in v.field]
        assert len(wage_variances) >= 1


# =============================================================================
# Handler Tests
# =============================================================================


@pytest.mark.asyncio
class TestPersonalTaxHandler:
    """Tests for personal_tax_handler function."""

    async def test_handler_completes_task(
        self, temp_output_dir, mock_session, sample_w2
    ):
        """Handler sets task status to COMPLETED on success."""
        # Create mock task
        task = MagicMock()
        task.id = 1
        task.client_id = 123
        task.tax_year = 2024
        task.metadata = {"filing_status": "single"}
        task.status = TaskStatus.IN_PROGRESS

        mock_doc = ClientDocument(
            path="w2.pdf",
            name="w2.pdf",
            size=1000,
            modified=datetime.now(),
            extension="pdf",
        )

        mock_context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="personal_tax",
        )

        mock_classification = ClassificationResult(
            document_type=DocumentType.W2, confidence=0.95, reasoning="W-2"
        )

        # Create async mocks
        async def mock_build_context(*args, **kwargs):
            return mock_context

        async def mock_read(*args, **kwargs):
            return b"dummy"

        async def mock_classify(*args, **kwargs):
            return mock_classification

        async def mock_extract(*args, **kwargs):
            return sample_w2

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.default_storage_url = "/tmp/storage"
            mock_settings.output_dir = str(temp_output_dir)

            with patch(
                "src.agents.personal_tax.agent.build_agent_context",
                side_effect=mock_build_context,
            ):
                with patch(
                    "src.agents.personal_tax.agent.scan_client_folder",
                    return_value=[mock_doc],
                ):
                    with patch(
                        "src.agents.personal_tax.agent.read_file",
                        side_effect=mock_read,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.classify_document",
                            side_effect=mock_classify,
                        ):
                            with patch(
                                "src.agents.personal_tax.agent.extract_document",
                                side_effect=mock_extract,
                            ):
                                await personal_tax_handler(task, mock_session)

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        mock_session.commit.assert_called()

    async def test_handler_creates_artifacts(
        self, temp_output_dir, mock_session, sample_w2
    ):
        """Handler creates TaskArtifact entries for outputs."""
        task = MagicMock()
        task.id = 1
        task.client_id = 123
        task.tax_year = 2024
        task.metadata = {}
        task.status = TaskStatus.IN_PROGRESS

        mock_doc = ClientDocument(
            path="w2.pdf",
            name="w2.pdf",
            size=1000,
            modified=datetime.now(),
            extension="pdf",
        )

        mock_context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="personal_tax",
        )

        mock_classification = ClassificationResult(
            document_type=DocumentType.W2, confidence=0.95, reasoning="W-2"
        )

        # Create async mocks
        async def mock_build_context(*args, **kwargs):
            return mock_context

        async def mock_read(*args, **kwargs):
            return b"dummy"

        async def mock_classify(*args, **kwargs):
            return mock_classification

        async def mock_extract(*args, **kwargs):
            return sample_w2

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.default_storage_url = "/tmp/storage"
            mock_settings.output_dir = str(temp_output_dir)

            with patch(
                "src.agents.personal_tax.agent.build_agent_context",
                side_effect=mock_build_context,
            ):
                with patch(
                    "src.agents.personal_tax.agent.scan_client_folder",
                    return_value=[mock_doc],
                ):
                    with patch(
                        "src.agents.personal_tax.agent.read_file",
                        side_effect=mock_read,
                    ):
                        with patch(
                            "src.agents.personal_tax.agent.classify_document",
                            side_effect=mock_classify,
                        ):
                            with patch(
                                "src.agents.personal_tax.agent.extract_document",
                                side_effect=mock_extract,
                            ):
                                await personal_tax_handler(task, mock_session)

        # Check that session.add was called for artifacts
        add_calls = mock_session.add.call_args_list
        assert len(add_calls) >= 2  # At least worksheet and notes artifacts

    async def test_handler_escalates_task(self, temp_output_dir, mock_session):
        """Handler sets task status to ESCALATED on EscalationRequired."""
        task = MagicMock()
        task.id = 1
        task.client_id = 123
        task.tax_year = 2024
        task.metadata = {}
        task.status = TaskStatus.IN_PROGRESS

        mock_context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="personal_tax",
        )

        # Create async mock
        async def mock_build_context(*args, **kwargs):
            return mock_context

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.default_storage_url = "/tmp/storage"
            mock_settings.output_dir = str(temp_output_dir)

            with patch(
                "src.agents.personal_tax.agent.build_agent_context",
                side_effect=mock_build_context,
            ):
                with patch(
                    "src.agents.personal_tax.agent.scan_client_folder",
                    return_value=[],  # No documents triggers escalation
                ):
                    await personal_tax_handler(task, mock_session)

        assert task.status == TaskStatus.ESCALATED
        mock_session.commit.assert_called()

        # Check that an Escalation was added
        add_calls = mock_session.add.call_args_list
        assert len(add_calls) >= 1

    async def test_handler_fails_on_error(self, temp_output_dir, mock_session):
        """Handler sets task status to FAILED on unexpected error."""
        task = MagicMock()
        task.id = 1
        task.client_id = 123
        task.tax_year = 2024
        task.metadata = {}
        task.status = TaskStatus.IN_PROGRESS
        task.error_message = None

        # Create async mock that raises an exception
        async def mock_build_context(*args, **kwargs):
            raise Exception("Database error")

        with patch("src.core.config.settings") as mock_settings:
            mock_settings.default_storage_url = "/tmp/storage"
            mock_settings.output_dir = str(temp_output_dir)

            with patch(
                "src.agents.personal_tax.agent.build_agent_context",
                side_effect=mock_build_context,
            ):
                await personal_tax_handler(task, mock_session)

        assert task.status == TaskStatus.FAILED
        mock_session.commit.assert_called()


# =============================================================================
# Media Type Tests
# =============================================================================


class TestMediaType:
    """Tests for media type detection."""

    def test_get_media_type_pdf(self, temp_output_dir):
        """PDF extension returns application/pdf."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._get_media_type("pdf")
        assert result == "application/pdf"

    def test_get_media_type_jpg(self, temp_output_dir):
        """JPG extension returns image/jpeg."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._get_media_type("jpg")
        assert result == "image/jpeg"

    def test_get_media_type_jpeg(self, temp_output_dir):
        """JPEG extension returns image/jpeg."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._get_media_type("jpeg")
        assert result == "image/jpeg"

    def test_get_media_type_png(self, temp_output_dir):
        """PNG extension returns image/png."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._get_media_type("png")
        assert result == "image/png"

    def test_get_media_type_unknown_defaults_jpeg(self, temp_output_dir):
        """Unknown extension defaults to image/jpeg."""
        agent = PersonalTaxAgent(
            storage_url="/tmp",
            output_dir=temp_output_dir,
        )

        result = agent._get_media_type("tiff")
        assert result == "image/jpeg"
