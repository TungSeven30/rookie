"""Skill engine module.

This module provides functionality for loading, parsing, and selecting
versioned skill files that describe how to perform specific tasks.
"""

from src.skills.loader import (
    SkillLoadError,
    load_skill_from_dict,
    load_skill_from_yaml,
    load_skills_from_directory,
    validate_skill_yaml,
)
from src.skills.models import (
    SkillContent,
    SkillExample,
    SkillFileModel,
    SkillMetadata,
)
from src.skills.selector import (
    get_latest_skill,
    get_skills_for_tax_year,
    group_skills_by_name,
    select_skill_version,
    select_skill_version_by_date,
)

__all__ = [
    # Models
    "SkillFileModel",
    "SkillMetadata",
    "SkillContent",
    "SkillExample",
    # Loader
    "SkillLoadError",
    "load_skill_from_yaml",
    "load_skill_from_dict",
    "load_skills_from_directory",
    "validate_skill_yaml",
    # Selector
    "select_skill_version",
    "select_skill_version_by_date",
    "group_skills_by_name",
    "get_latest_skill",
    "get_skills_for_tax_year",
]
