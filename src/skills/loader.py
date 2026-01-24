"""Skill file loader with YAML parsing and validation.

This module provides functions to load skill files from YAML format
into Pydantic models with full validation.
"""

from pathlib import Path
from typing import Any

from pydantic import ValidationError
from ruamel.yaml import YAML

from src.skills.models import SkillContent, SkillFileModel, SkillMetadata


class SkillLoadError(Exception):
    """Exception raised when a skill file cannot be loaded or validated."""

    def __init__(self, message: str, path: Path | None = None, errors: list[str] | None = None):
        """Initialize SkillLoadError.

        Args:
            message: Human-readable error message
            path: Path to the skill file that failed to load
            errors: List of specific validation errors
        """
        self.path = path
        self.errors = errors or []
        super().__init__(message)


def _parse_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file and return its contents as a dictionary.

    Args:
        path: Path to the YAML file

    Returns:
        Dictionary containing the parsed YAML content

    Raises:
        SkillLoadError: If the file cannot be read or parsed
    """
    yaml = YAML()
    yaml.preserve_quotes = True

    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.load(f)
    except FileNotFoundError:
        raise SkillLoadError(f"Skill file not found: {path}", path=path)
    except Exception as e:
        raise SkillLoadError(f"Failed to parse YAML: {e}", path=path)

    if data is None:
        raise SkillLoadError("Empty skill file", path=path)

    if not isinstance(data, dict):
        raise SkillLoadError(
            f"Skill file must be a YAML mapping, got {type(data).__name__}",
            path=path,
        )

    return dict(data)


def load_skill_from_yaml(path: str | Path) -> SkillFileModel:
    """Load a skill file from a YAML file path.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed and validated SkillFileModel

    Raises:
        SkillLoadError: If the file cannot be loaded or validation fails
    """
    path = Path(path)
    data = _parse_yaml(path)
    return load_skill_from_dict(data, path=path)


def load_skill_from_dict(
    data: dict[str, Any], path: Path | None = None
) -> SkillFileModel:
    """Load a skill file from a dictionary.

    Args:
        data: Dictionary containing skill data
        path: Optional path for error reporting

    Returns:
        Parsed and validated SkillFileModel

    Raises:
        SkillLoadError: If validation fails
    """
    try:
        # Extract metadata section
        metadata_data = data.get("metadata")
        if metadata_data is None:
            raise SkillLoadError(
                "Missing required 'metadata' section",
                path=path,
                errors=["Missing required 'metadata' section"],
            )

        # Extract content section
        content_data = data.get("content")
        if content_data is None:
            raise SkillLoadError(
                "Missing required 'content' section",
                path=path,
                errors=["Missing required 'content' section"],
            )

        # Parse metadata
        try:
            metadata = SkillMetadata.model_validate(metadata_data)
        except ValidationError as e:
            errors = [err["msg"] for err in e.errors()]
            raise SkillLoadError(
                f"Invalid metadata: {errors[0]}",
                path=path,
                errors=errors,
            )

        # Parse content
        try:
            content = SkillContent.model_validate(content_data)
        except ValidationError as e:
            errors = [err["msg"] for err in e.errors()]
            raise SkillLoadError(
                f"Invalid content: {errors[0]}",
                path=path,
                errors=errors,
            )

        return SkillFileModel(metadata=metadata, content=content)

    except SkillLoadError:
        raise
    except ValidationError as e:
        errors = [err["msg"] for err in e.errors()]
        raise SkillLoadError(
            f"Skill validation failed: {errors[0]}",
            path=path,
            errors=errors,
        )
    except Exception as e:
        raise SkillLoadError(f"Unexpected error loading skill: {e}", path=path)


def load_skills_from_directory(
    directory: str | Path, pattern: str = "*.yaml"
) -> list[SkillFileModel]:
    """Load all skill files from a directory matching a glob pattern.

    Args:
        directory: Directory to search for skill files
        pattern: Glob pattern for matching files (default: "*.yaml")

    Returns:
        List of loaded SkillFileModel instances

    Raises:
        SkillLoadError: If the directory does not exist
    """
    directory = Path(directory)

    if not directory.exists():
        raise SkillLoadError(f"Directory not found: {directory}", path=directory)

    if not directory.is_dir():
        raise SkillLoadError(f"Path is not a directory: {directory}", path=directory)

    skills: list[SkillFileModel] = []
    for yaml_file in sorted(directory.glob(pattern)):
        if yaml_file.is_file():
            skill = load_skill_from_yaml(yaml_file)
            skills.append(skill)

    return skills


def validate_skill_yaml(path: str | Path) -> list[str]:
    """Validate a skill YAML file and return any errors.

    This function attempts to load and validate a skill file,
    returning a list of validation errors (empty if valid).

    Args:
        path: Path to the YAML file to validate

    Returns:
        List of validation error messages (empty if valid)
    """
    path = Path(path)
    errors: list[str] = []

    try:
        data = _parse_yaml(path)
    except SkillLoadError as e:
        return [str(e)]

    # Check for required top-level sections
    if "metadata" not in data:
        errors.append("Missing required 'metadata' section")
    if "content" not in data:
        errors.append("Missing required 'content' section")

    if errors:
        return errors

    # Validate metadata
    metadata_data = data.get("metadata", {})
    required_metadata_fields = ["name", "version", "effective_date"]
    for field in required_metadata_fields:
        if field not in metadata_data:
            errors.append(f"Missing required metadata field: {field}")

    # Validate content
    content_data = data.get("content", {})
    if "instructions" not in content_data:
        errors.append("Missing required content field: instructions")

    if errors:
        return errors

    # Full validation via Pydantic
    try:
        load_skill_from_dict(data, path=path)
    except SkillLoadError as e:
        return e.errors or [str(e)]

    return []
