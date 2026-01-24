"""Tests for skill version selector module."""

from datetime import date

import pytest

from src.skills import SkillFileModel
from src.skills.models import SkillContent, SkillMetadata
from src.skills.selector import (
    get_latest_skill,
    get_skills_for_tax_year,
    group_skills_by_name,
    select_skill_version,
    select_skill_version_by_date,
)


def make_skill(
    name: str, version: str, effective_date: date, instructions: str = "Default"
) -> SkillFileModel:
    """Helper to create a SkillFileModel for testing."""
    return SkillFileModel(
        metadata=SkillMetadata(
            name=name,
            version=version,
            effective_date=effective_date,
        ),
        content=SkillContent(instructions=instructions),
    )


class TestSelectSkillVersion:
    """Tests for select_skill_version function."""

    def test_select_version_for_tax_year(self) -> None:
        """Test selecting correct version for a tax year."""
        skills = [
            make_skill("w2", "2023.1", date(2023, 1, 1)),
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2025.1", date(2025, 1, 1)),
        ]

        result = select_skill_version(skills, 2024)

        assert result is not None
        assert result.version == "2024.1"

    def test_select_mid_year_version(self) -> None:
        """Test selecting version when newer version is released mid-year."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2024.2", date(2024, 6, 1)),  # Mid-year update
        ]

        result = select_skill_version(skills, 2024)

        # Should get the later version since both are before Dec 31
        assert result is not None
        assert result.version == "2024.2"

    def test_select_no_applicable_version(self) -> None:
        """Test returns None when no version applies to tax year."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2025.1", date(2025, 1, 1)),
        ]

        result = select_skill_version(skills, 2023)

        assert result is None

    def test_select_older_year(self) -> None:
        """Test selecting version for older tax year."""
        skills = [
            make_skill("w2", "2022.1", date(2022, 1, 1)),
            make_skill("w2", "2023.1", date(2023, 1, 1)),
            make_skill("w2", "2024.1", date(2024, 1, 1)),
        ]

        result = select_skill_version(skills, 2022)

        assert result is not None
        assert result.version == "2022.1"

    def test_select_empty_list(self) -> None:
        """Test returns None for empty skill list."""
        result = select_skill_version([], 2024)
        assert result is None

    def test_select_uses_year_end_date(self) -> None:
        """Test that selection uses December 31 of tax year."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 12, 31)),  # Exactly year end
        ]

        result = select_skill_version(skills, 2024)

        assert result is not None
        assert result.version == "2024.1"

    def test_select_excludes_next_year(self) -> None:
        """Test that version effective Jan 1 next year is excluded."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2025.1", date(2025, 1, 1)),
        ]

        result = select_skill_version(skills, 2024)

        assert result is not None
        assert result.version == "2024.1"


class TestSelectSkillVersionByDate:
    """Tests for select_skill_version_by_date function."""

    def test_select_by_exact_date(self) -> None:
        """Test selecting version by exact effective date."""
        skills = [
            make_skill("w2", "1.0", date(2024, 1, 1)),
            make_skill("w2", "2.0", date(2024, 6, 1)),
        ]

        result = select_skill_version_by_date(skills, date(2024, 6, 1))

        assert result is not None
        assert result.version == "2.0"

    def test_select_by_date_between_versions(self) -> None:
        """Test selecting version when date falls between versions."""
        skills = [
            make_skill("w2", "1.0", date(2024, 1, 1)),
            make_skill("w2", "2.0", date(2024, 6, 1)),
        ]

        result = select_skill_version_by_date(skills, date(2024, 3, 15))

        assert result is not None
        assert result.version == "1.0"

    def test_select_by_date_before_all(self) -> None:
        """Test returns None when date is before all versions."""
        skills = [
            make_skill("w2", "1.0", date(2024, 1, 1)),
        ]

        result = select_skill_version_by_date(skills, date(2023, 12, 31))

        assert result is None

    def test_select_by_date_empty_list(self) -> None:
        """Test returns None for empty list."""
        result = select_skill_version_by_date([], date(2024, 6, 1))
        assert result is None


class TestGroupSkillsByName:
    """Tests for group_skills_by_name function."""

    def test_group_by_name(self) -> None:
        """Test grouping skills by their name."""
        skills = [
            make_skill("w2", "2023.1", date(2023, 1, 1)),
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("1099", "2024.1", date(2024, 1, 1)),
        ]

        grouped = group_skills_by_name(skills)

        assert len(grouped) == 2
        assert "w2" in grouped
        assert "1099" in grouped
        assert len(grouped["w2"]) == 2
        assert len(grouped["1099"]) == 1

    def test_group_sorts_by_effective_date(self) -> None:
        """Test that versions are sorted by effective date within group."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2022.1", date(2022, 1, 1)),  # Out of order
            make_skill("w2", "2023.1", date(2023, 1, 1)),
        ]

        grouped = group_skills_by_name(skills)

        dates = [s.effective_date for s in grouped["w2"]]
        assert dates == sorted(dates)

    def test_group_empty_list(self) -> None:
        """Test grouping empty list returns empty dict."""
        grouped = group_skills_by_name([])
        assert grouped == {}

    def test_group_single_skill(self) -> None:
        """Test grouping single skill."""
        skills = [make_skill("w2", "2024.1", date(2024, 1, 1))]

        grouped = group_skills_by_name(skills)

        assert len(grouped) == 1
        assert len(grouped["w2"]) == 1


class TestGetLatestSkill:
    """Tests for get_latest_skill function."""

    def test_get_latest_from_multiple(self) -> None:
        """Test getting latest skill from multiple versions."""
        skills = [
            make_skill("w2", "2022.1", date(2022, 1, 1)),
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("w2", "2023.1", date(2023, 1, 1)),
        ]

        result = get_latest_skill(skills)

        assert result is not None
        assert result.version == "2024.1"

    def test_get_latest_single(self) -> None:
        """Test getting latest from single skill."""
        skills = [make_skill("w2", "2024.1", date(2024, 1, 1))]

        result = get_latest_skill(skills)

        assert result is not None
        assert result.version == "2024.1"

    def test_get_latest_empty_list(self) -> None:
        """Test returns None for empty list."""
        result = get_latest_skill([])
        assert result is None

    def test_get_latest_same_date(self) -> None:
        """Test behavior when multiple skills have same date."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("1099", "2024.1", date(2024, 1, 1)),
        ]

        result = get_latest_skill(skills)

        # Should return one of them (either is valid)
        assert result is not None
        assert result.effective_date == date(2024, 1, 1)


class TestGetSkillsForTaxYear:
    """Tests for get_skills_for_tax_year function."""

    def test_get_skills_multiple_types(self) -> None:
        """Test getting skills for multiple skill types."""
        skills = [
            make_skill("w2", "2023.1", date(2023, 1, 1)),
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("1099", "2024.1", date(2024, 1, 1)),
            make_skill("schedule_c", "2024.1", date(2024, 1, 1)),
        ]

        result = get_skills_for_tax_year(skills, 2024)

        assert len(result) == 3
        assert "w2" in result
        assert "1099" in result
        assert "schedule_c" in result
        assert result["w2"].version == "2024.1"

    def test_get_skills_excludes_inapplicable(self) -> None:
        """Test that skills without applicable version are excluded."""
        skills = [
            make_skill("w2", "2024.1", date(2024, 1, 1)),
            make_skill("new_form", "2025.1", date(2025, 1, 1)),  # Future
        ]

        result = get_skills_for_tax_year(skills, 2024)

        assert len(result) == 1
        assert "w2" in result
        assert "new_form" not in result

    def test_get_skills_empty_list(self) -> None:
        """Test returns empty dict for empty input."""
        result = get_skills_for_tax_year([], 2024)
        assert result == {}

    def test_get_skills_no_applicable(self) -> None:
        """Test returns empty dict when no skills apply."""
        skills = [
            make_skill("w2", "2025.1", date(2025, 1, 1)),
        ]

        result = get_skills_for_tax_year(skills, 2024)

        assert result == {}


class TestSkillModelHelpers:
    """Tests for SkillFileModel helper methods."""

    def test_is_effective_for_date(self) -> None:
        """Test is_effective_for_date method."""
        skill = make_skill("w2", "2024.1", date(2024, 6, 1))

        assert skill.is_effective_for_date(date(2024, 6, 1)) is True
        assert skill.is_effective_for_date(date(2024, 12, 31)) is True
        assert skill.is_effective_for_date(date(2024, 5, 31)) is False

    def test_is_effective_for_tax_year(self) -> None:
        """Test is_effective_for_tax_year method."""
        skill = make_skill("w2", "2024.1", date(2024, 6, 1))

        assert skill.is_effective_for_tax_year(2024) is True
        assert skill.is_effective_for_tax_year(2025) is True
        assert skill.is_effective_for_tax_year(2023) is False

    def test_to_prompt_context(self) -> None:
        """Test to_prompt_context method."""
        skill = make_skill("w2", "2024.1", date(2024, 1, 1), "Process W-2 forms")

        context = skill.to_prompt_context()

        assert context["name"] == "w2"
        assert context["version"] == "2024.1"
        assert context["effective_date"] == "2024-01-01"
        assert context["instructions"] == "Process W-2 forms"
        assert "examples" in context
        assert "constraints" in context
        assert "escalation_triggers" in context
