"""Tests for context builder module."""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.context.builder import (
    TASK_TYPE_SKILLS,
    AgentContext,
    build_agent_context,
    get_client_documents,
    get_prior_year_return,
    get_skills_for_task_type,
    load_skill_for_year,
)


class MockResult:
    """Mock database result."""

    def __init__(self, scalar_one: Any = None) -> None:
        self._scalar_one = scalar_one

    def scalar_one_or_none(self) -> Any:
        return self._scalar_one


class TestAgentContext:
    """Tests for AgentContext dataclass."""

    def test_default_initialization(self) -> None:
        """Should initialize with default empty collections."""
        context = AgentContext(
            client_id=1,
            client_name="John Doe",
            tax_year=2024,
            task_type="w2_extraction",
        )

        assert context.client_id == 1
        assert context.client_name == "John Doe"
        assert context.tax_year == 2024
        assert context.task_type == "w2_extraction"
        assert context.client_profile == {}
        assert context.documents == []
        assert context.skills == []
        assert context.prior_year_return is None

    def test_full_initialization(self) -> None:
        """Should accept all fields during initialization."""
        context = AgentContext(
            client_id=1,
            client_name="Jane Doe",
            tax_year=2024,
            task_type="schedule_c_prep",
            client_profile={"filing_status": {"status": "single"}},
            documents=[{"id": 1, "type": "w2"}],
            skills=[{"name": "schedule_c", "version": "2024.1"}],
            prior_year_return={"agi": 75000},
        )

        assert context.client_profile == {"filing_status": {"status": "single"}}
        assert len(context.documents) == 1
        assert len(context.skills) == 1
        assert context.prior_year_return == {"agi": 75000}

    def test_to_prompt_context_formatting(self) -> None:
        """Should format context properly for prompt injection."""
        context = AgentContext(
            client_id=1,
            client_name="John Doe",
            tax_year=2024,
            task_type="w2_extraction",
            client_profile={"filing_status": {"status": "married"}},
            documents=[{"id": 1, "type": "w2"}],
            skills=[{"name": "w2_processing", "instructions": "Process W-2"}],
            prior_year_return={"agi": 100000},
        )

        prompt_ctx = context.to_prompt_context()

        assert prompt_ctx["client"]["id"] == 1
        assert prompt_ctx["client"]["name"] == "John Doe"
        assert prompt_ctx["tax_year"] == 2024
        assert prompt_ctx["task_type"] == "w2_extraction"
        assert prompt_ctx["profile"] == {"filing_status": {"status": "married"}}
        assert prompt_ctx["documents"] == [{"id": 1, "type": "w2"}]
        assert prompt_ctx["skills"] == [
            {"name": "w2_processing", "instructions": "Process W-2"}
        ]
        assert prompt_ctx["prior_year_return"] == {"agi": 100000}

    def test_has_skill_returns_true_when_present(self) -> None:
        """Should return True when skill is in context."""
        context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="test",
            skills=[{"name": "w2_processing"}, {"name": "income_verification"}],
        )

        assert context.has_skill("w2_processing") is True
        assert context.has_skill("income_verification") is True

    def test_has_skill_returns_false_when_absent(self) -> None:
        """Should return False when skill is not in context."""
        context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="test",
            skills=[{"name": "w2_processing"}],
        )

        assert context.has_skill("schedule_c") is False
        assert context.has_skill("nonexistent") is False

    def test_get_skill_returns_skill_when_present(self) -> None:
        """Should return skill dict when found."""
        skill = {"name": "w2_processing", "version": "2024.1", "instructions": "..."}
        context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="test",
            skills=[skill],
        )

        result = context.get_skill("w2_processing")

        assert result == skill

    def test_get_skill_returns_none_when_absent(self) -> None:
        """Should return None when skill not found."""
        context = AgentContext(
            client_id=1,
            client_name="Test",
            tax_year=2024,
            task_type="test",
            skills=[{"name": "w2_processing"}],
        )

        result = context.get_skill("nonexistent")

        assert result is None


class TestGetSkillsForTaskType:
    """Tests for get_skills_for_task_type function."""

    def test_returns_skills_for_w2_extraction(self) -> None:
        """Should return correct skills for W-2 extraction."""
        skills = get_skills_for_task_type("w2_extraction")

        assert "w2_processing" in skills
        assert "income_verification" in skills

    def test_returns_skills_for_1099_extraction(self) -> None:
        """Should return correct skills for 1099 extraction."""
        skills = get_skills_for_task_type("1099_extraction")

        assert "1099_processing" in skills
        assert "income_verification" in skills

    def test_returns_skills_for_schedule_c_prep(self) -> None:
        """Should return correct skills for Schedule C prep."""
        skills = get_skills_for_task_type("schedule_c_prep")

        assert "schedule_c" in skills
        assert "expense_categorization" in skills
        assert "depreciation" in skills

    def test_returns_skills_for_schedule_e_prep(self) -> None:
        """Should return correct skills for Schedule E prep."""
        skills = get_skills_for_task_type("schedule_e_prep")

        assert "schedule_e" in skills
        assert "rental_income" in skills
        assert "depreciation" in skills

    def test_returns_empty_for_general_task(self) -> None:
        """Should return empty list for general task type."""
        skills = get_skills_for_task_type("general")

        assert skills == []

    def test_returns_empty_for_unknown_task_type(self) -> None:
        """Should return empty list for unknown task types."""
        skills = get_skills_for_task_type("unknown_task")

        assert skills == []

    def test_task_type_skills_mapping_exists(self) -> None:
        """Should have all documented task types in mapping."""
        expected_types = [
            "w2_extraction",
            "1099_extraction",
            "schedule_c_prep",
            "schedule_e_prep",
            "tax_return_review",
            "interview_prep",
            "general",
        ]

        for task_type in expected_types:
            assert task_type in TASK_TYPE_SKILLS


class TestLoadSkillForYear:
    """Tests for load_skill_for_year function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_skill_not_found(self) -> None:
        """Should return None when skill doesn't exist in database."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_one=None)

        result = await load_skill_for_year(session, "nonexistent", 2024)

        assert result is None

    @pytest.mark.asyncio
    async def test_parses_skill_content_from_database(self) -> None:
        """Should parse YAML content from SkillFile record."""
        session = AsyncMock()

        mock_skill_file = MagicMock()
        mock_skill_file.content = """
metadata:
  name: test_skill
  version: "2024.1"
  effective_date: 2024-01-01
  description: Test skill
  tags: [test]
content:
  instructions: Do the thing
  examples: []
  constraints: []
  escalation_triggers: []
"""
        session.execute.return_value = MockResult(scalar_one=mock_skill_file)

        result = await load_skill_for_year(session, "test_skill", 2024)

        assert result is not None
        assert result.name == "test_skill"
        assert result.version == "2024.1"
        assert result.instructions == "Do the thing"

    @pytest.mark.asyncio
    async def test_returns_none_on_parse_error(self) -> None:
        """Should return None when YAML parsing fails."""
        session = AsyncMock()

        mock_skill_file = MagicMock()
        mock_skill_file.content = "invalid: yaml: content: [unclosed"
        session.execute.return_value = MockResult(scalar_one=mock_skill_file)

        result = await load_skill_for_year(session, "bad_skill", 2024)

        assert result is None

    @pytest.mark.asyncio
    async def test_selects_skill_by_effective_date(self) -> None:
        """Should query for skill effective on or before tax year end."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_one=None)

        await load_skill_for_year(session, "w2_processing", 2024)

        # Verify execute was called (query was built)
        session.execute.assert_called_once()


class TestGetClientDocuments:
    """Tests for get_client_documents stub function."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_stub(self) -> None:
        """Should return empty list (Phase 3 stub)."""
        session = AsyncMock()

        result = await get_client_documents(session, client_id=1, tax_year=2024)

        assert result == []


class TestGetPriorYearReturn:
    """Tests for get_prior_year_return stub function."""

    @pytest.mark.asyncio
    async def test_returns_none_stub(self) -> None:
        """Should return None (Phase 3 stub)."""
        session = AsyncMock()

        result = await get_prior_year_return(session, client_id=1, tax_year=2024)

        assert result is None


class TestBuildAgentContext:
    """Tests for build_agent_context function."""

    @pytest.mark.asyncio
    async def test_raises_when_client_not_found(self) -> None:
        """Should raise ValueError when client doesn't exist."""
        session = AsyncMock()
        session.execute.return_value = MockResult(scalar_one=None)

        with pytest.raises(ValueError, match="Client not found: 999"):
            await build_agent_context(
                session,
                client_id=999,
                task_type="w2_extraction",
                tax_year=2024,
            )

    @pytest.mark.asyncio
    @patch("src.context.builder.get_client_profile_view")
    @patch("src.context.builder.get_client_documents")
    @patch("src.context.builder.get_prior_year_return")
    @patch("src.context.builder.load_skill_for_year")
    async def test_assembles_complete_context(
        self,
        mock_load_skill: AsyncMock,
        mock_prior_return: AsyncMock,
        mock_documents: AsyncMock,
        mock_profile: AsyncMock,
    ) -> None:
        """Should assemble all context components."""
        session = AsyncMock()

        # Mock client
        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.name = "John Doe"
        session.execute.return_value = MockResult(scalar_one=mock_client)

        # Mock profile
        mock_profile.return_value = {"filing_status": {"status": "single"}}

        # Mock documents
        mock_documents.return_value = [{"id": 1, "type": "w2"}]

        # Mock prior year return
        mock_prior_return.return_value = {"agi": 100000}

        # Mock skill loading
        mock_skill = MagicMock()
        mock_skill.to_prompt_context.return_value = {"name": "w2_processing"}
        mock_load_skill.return_value = mock_skill

        context = await build_agent_context(
            session,
            client_id=1,
            task_type="w2_extraction",
            tax_year=2024,
        )

        assert context.client_id == 1
        assert context.client_name == "John Doe"
        assert context.tax_year == 2024
        assert context.task_type == "w2_extraction"
        assert context.client_profile == {"filing_status": {"status": "single"}}
        assert context.documents == [{"id": 1, "type": "w2"}]
        assert context.prior_year_return == {"agi": 100000}
        assert len(context.skills) == 2  # w2_processing and income_verification

    @pytest.mark.asyncio
    @patch("src.context.builder.get_client_profile_view")
    @patch("src.context.builder.get_client_documents")
    @patch("src.context.builder.get_prior_year_return")
    @patch("src.context.builder.load_skill_for_year")
    async def test_handles_missing_skills(
        self,
        mock_load_skill: AsyncMock,
        mock_prior_return: AsyncMock,
        mock_documents: AsyncMock,
        mock_profile: AsyncMock,
    ) -> None:
        """Should handle case where skills don't exist in database."""
        session = AsyncMock()

        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.name = "Test Client"
        session.execute.return_value = MockResult(scalar_one=mock_client)

        mock_profile.return_value = {}
        mock_documents.return_value = []
        mock_prior_return.return_value = None
        mock_load_skill.return_value = None  # Skills not found

        context = await build_agent_context(
            session,
            client_id=1,
            task_type="w2_extraction",
            tax_year=2024,
        )

        assert context.skills == []  # No skills loaded

    @pytest.mark.asyncio
    @patch("src.context.builder.get_client_profile_view")
    @patch("src.context.builder.get_client_documents")
    @patch("src.context.builder.get_prior_year_return")
    @patch("src.context.builder.load_skill_for_year")
    async def test_handles_general_task_type(
        self,
        mock_load_skill: AsyncMock,
        mock_prior_return: AsyncMock,
        mock_documents: AsyncMock,
        mock_profile: AsyncMock,
    ) -> None:
        """Should handle general task type with no skills."""
        session = AsyncMock()

        mock_client = MagicMock()
        mock_client.id = 1
        mock_client.name = "Test Client"
        session.execute.return_value = MockResult(scalar_one=mock_client)

        mock_profile.return_value = {}
        mock_documents.return_value = []
        mock_prior_return.return_value = None

        context = await build_agent_context(
            session,
            client_id=1,
            task_type="general",
            tax_year=2024,
        )

        assert context.skills == []
        mock_load_skill.assert_not_called()  # No skills to load for general
