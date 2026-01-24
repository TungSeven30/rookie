"""Skill version selector for tax year-based selection.

This module provides functions to select the correct skill version
based on effective dates and tax years.
"""

from datetime import date

from src.skills.models import SkillFileModel


def select_skill_version(
    skills: list[SkillFileModel], tax_year: int
) -> SkillFileModel | None:
    """Select the correct skill version for a given tax year.

    This function finds the skill version with the most recent effective_date
    that is on or before December 31 of the tax year.

    Args:
        skills: List of skill versions to choose from
        tax_year: The tax year (e.g., 2024)

    Returns:
        The most recent applicable skill version, or None if no version applies

    Example:
        Given skills with effective_dates:
        - 2023-01-01 (v2023.1)
        - 2024-06-01 (v2024.1)
        - 2025-01-01 (v2025.1)

        For tax_year=2024: Returns v2024.1 (effective 2024-06-01)
        For tax_year=2023: Returns v2023.1 (effective 2023-01-01)
        For tax_year=2022: Returns None (no version before 2023)
    """
    if not skills:
        return None

    # Tax year ends on December 31
    year_end = date(tax_year, 12, 31)
    return select_skill_version_by_date(skills, year_end)


def select_skill_version_by_date(
    skills: list[SkillFileModel], target_date: date
) -> SkillFileModel | None:
    """Select the correct skill version for a given target date.

    This function finds the skill version with the most recent effective_date
    that is on or before the target date.

    Args:
        skills: List of skill versions to choose from
        target_date: The date to select a version for

    Returns:
        The most recent applicable skill version, or None if no version applies
    """
    if not skills:
        return None

    # Filter to only skills effective on or before target_date
    applicable_skills = [s for s in skills if s.is_effective_for_date(target_date)]

    if not applicable_skills:
        return None

    # Return the skill with the most recent effective_date
    return max(applicable_skills, key=lambda s: s.effective_date)


def group_skills_by_name(
    skills: list[SkillFileModel],
) -> dict[str, list[SkillFileModel]]:
    """Group skills by their name.

    This is useful when loading multiple skill files and needing to
    select versions for each skill type.

    Args:
        skills: List of skill files to group

    Returns:
        Dictionary mapping skill names to lists of versions

    Example:
        Input: [personal_tax_w2 v2023, personal_tax_w2 v2024, personal_tax_1099 v2024]
        Output: {
            "personal_tax_w2": [v2023, v2024],
            "personal_tax_1099": [v2024]
        }
    """
    grouped: dict[str, list[SkillFileModel]] = {}

    for skill in skills:
        name = skill.name
        if name not in grouped:
            grouped[name] = []
        grouped[name].append(skill)

    # Sort each group by effective_date for consistent ordering
    for name in grouped:
        grouped[name].sort(key=lambda s: s.effective_date)

    return grouped


def get_latest_skill(skills: list[SkillFileModel]) -> SkillFileModel | None:
    """Get the skill with the most recent effective_date.

    This returns the latest version regardless of target date,
    useful for showing "current" versions.

    Args:
        skills: List of skill versions to choose from

    Returns:
        The skill with the most recent effective_date, or None if list is empty
    """
    if not skills:
        return None

    return max(skills, key=lambda s: s.effective_date)


def get_skills_for_tax_year(
    skills: list[SkillFileModel], tax_year: int
) -> dict[str, SkillFileModel]:
    """Get the appropriate version of each skill for a tax year.

    This groups skills by name and selects the correct version
    for each skill type.

    Args:
        skills: List of all skill versions
        tax_year: The tax year to select versions for

    Returns:
        Dictionary mapping skill names to the selected version
        (skills with no applicable version are not included)
    """
    grouped = group_skills_by_name(skills)
    selected: dict[str, SkillFileModel] = {}

    for name, versions in grouped.items():
        version = select_skill_version(versions, tax_year)
        if version is not None:
            selected[name] = version

    return selected
