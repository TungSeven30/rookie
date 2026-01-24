"""Pydantic models for skill files.

Skill files are YAML documents that describe how to perform specific tasks.
They support versioning via effective_date for tax year selection.
"""

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SkillMetadata(BaseModel):
    """Metadata for a skill file."""

    name: str = Field(..., description="Unique skill identifier")
    version: str = Field(..., description="Semantic version (e.g., '2024.1')")
    effective_date: date = Field(
        ..., description="Date this skill version becomes effective"
    )
    description: str | None = Field(
        None, description="Human-readable description of the skill"
    )
    tags: list[str] = Field(default_factory=list, description="Searchable tags")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Ensure name is a valid identifier (lowercase, underscores, alphanumeric)."""
        if not v:
            raise ValueError("name cannot be empty")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "name must contain only alphanumeric characters, underscores, and hyphens"
            )
        return v.lower()

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Ensure version is non-empty."""
        if not v:
            raise ValueError("version cannot be empty")
        return v


class SkillExample(BaseModel):
    """Example input/output pair for a skill."""

    input: str = Field(..., description="Example input")
    output: str = Field(..., description="Expected output")
    explanation: str | None = Field(
        None, description="Explanation of why this output is correct"
    )


class SkillContent(BaseModel):
    """Content section of a skill file."""

    instructions: str = Field(
        ..., description="Detailed instructions for performing the skill"
    )
    examples: list[SkillExample] = Field(
        default_factory=list, description="Example input/output pairs"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Rules the skill must follow"
    )
    escalation_triggers: list[str] = Field(
        default_factory=list,
        description="Conditions that should trigger escalation to a human",
    )


class SkillFileModel(BaseModel):
    """Complete skill file model combining metadata and content."""

    metadata: SkillMetadata
    content: SkillContent

    # Convenience properties for accessing common fields
    @property
    def name(self) -> str:
        """Get skill name from metadata."""
        return self.metadata.name

    @property
    def version(self) -> str:
        """Get skill version from metadata."""
        return self.metadata.version

    @property
    def effective_date(self) -> date:
        """Get effective date from metadata."""
        return self.metadata.effective_date

    @property
    def instructions(self) -> str:
        """Get instructions from content."""
        return self.content.instructions

    @property
    def tags(self) -> list[str]:
        """Get tags from metadata."""
        return self.metadata.tags

    def is_effective_for_date(self, target_date: date) -> bool:
        """Check if this skill version is effective for the given date.

        A skill is effective if its effective_date is on or before the target_date.

        Args:
            target_date: The date to check against

        Returns:
            True if the skill is effective, False otherwise
        """
        return self.effective_date <= target_date

    def is_effective_for_tax_year(self, tax_year: int) -> bool:
        """Check if this skill version is effective for the given tax year.

        A skill is effective for a tax year if its effective_date is on or before
        December 31 of that tax year.

        Args:
            tax_year: The tax year to check (e.g., 2024)

        Returns:
            True if the skill is effective for the tax year, False otherwise
        """
        year_end = date(tax_year, 12, 31)
        return self.is_effective_for_date(year_end)

    def to_prompt_context(self) -> dict[str, Any]:
        """Convert skill to a dictionary suitable for prompt context.

        Returns:
            Dictionary with skill information for inclusion in prompts
        """
        return {
            "name": self.name,
            "version": self.version,
            "effective_date": self.effective_date.isoformat(),
            "description": self.metadata.description,
            "instructions": self.instructions,
            "examples": [
                {"input": ex.input, "output": ex.output, "explanation": ex.explanation}
                for ex in self.content.examples
            ],
            "constraints": self.content.constraints,
            "escalation_triggers": self.content.escalation_triggers,
        }
