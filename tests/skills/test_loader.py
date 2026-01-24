"""Tests for skill loader module."""

import tempfile
from pathlib import Path

import pytest

from src.skills import SkillLoadError, load_skill_from_yaml
from src.skills.loader import (
    load_skill_from_dict,
    load_skills_from_directory,
    validate_skill_yaml,
)


class TestLoadSkillFromYaml:
    """Tests for load_skill_from_yaml function."""

    def test_load_valid_skill_file(self, tmp_path: Path) -> None:
        """Test loading a valid skill YAML file."""
        skill_yaml = tmp_path / "test_skill.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: test_skill
  version: "2024.1"
  effective_date: 2024-01-01
  description: Test skill description
  tags:
    - test
    - example

content:
  instructions: "Do the thing correctly."
  examples: []
  constraints:
    - "Must follow rules"
  escalation_triggers:
    - "When unsure"
"""
        )

        skill = load_skill_from_yaml(skill_yaml)

        assert skill.name == "test_skill"
        assert skill.version == "2024.1"
        assert skill.effective_date.year == 2024
        assert skill.metadata.description == "Test skill description"
        assert skill.tags == ["test", "example"]
        assert "Do the thing correctly" in skill.instructions
        assert skill.content.constraints == ["Must follow rules"]
        assert skill.content.escalation_triggers == ["When unsure"]

    def test_load_skill_file_not_found(self) -> None:
        """Test error when skill file does not exist."""
        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_yaml("/nonexistent/path/skill.yaml")

        assert "not found" in str(exc_info.value).lower()

    def test_load_skill_invalid_yaml(self, tmp_path: Path) -> None:
        """Test error when YAML is malformed."""
        skill_yaml = tmp_path / "bad.yaml"
        skill_yaml.write_text("{ invalid yaml : : : }")

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_yaml(skill_yaml)

        assert exc_info.value.path == skill_yaml

    def test_load_skill_empty_file(self, tmp_path: Path) -> None:
        """Test error when YAML file is empty."""
        skill_yaml = tmp_path / "empty.yaml"
        skill_yaml.write_text("")

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_yaml(skill_yaml)

        assert "empty" in str(exc_info.value).lower()

    def test_load_skill_missing_metadata(self, tmp_path: Path) -> None:
        """Test error when metadata section is missing."""
        skill_yaml = tmp_path / "no_metadata.yaml"
        skill_yaml.write_text(
            """
content:
  instructions: "Do something"
"""
        )

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_yaml(skill_yaml)

        assert "metadata" in str(exc_info.value).lower()

    def test_load_skill_missing_content(self, tmp_path: Path) -> None:
        """Test error when content section is missing."""
        skill_yaml = tmp_path / "no_content.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: test
  version: "1.0"
  effective_date: 2024-01-01
"""
        )

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_yaml(skill_yaml)

        assert "content" in str(exc_info.value).lower()

    def test_load_skill_missing_required_field(self, tmp_path: Path) -> None:
        """Test error when required metadata field is missing."""
        skill_yaml = tmp_path / "missing_name.yaml"
        skill_yaml.write_text(
            """
metadata:
  version: "1.0"
  effective_date: 2024-01-01

content:
  instructions: "Do something"
"""
        )

        with pytest.raises(SkillLoadError):
            load_skill_from_yaml(skill_yaml)

    def test_load_skill_with_examples(self, tmp_path: Path) -> None:
        """Test loading skill with examples."""
        skill_yaml = tmp_path / "with_examples.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: example_skill
  version: "1.0"
  effective_date: 2024-01-01

content:
  instructions: "Process the input"
  examples:
    - input: "sample input"
      output: "expected output"
      explanation: "Why this is correct"
    - input: "another input"
      output: "another output"
"""
        )

        skill = load_skill_from_yaml(skill_yaml)

        assert len(skill.content.examples) == 2
        assert skill.content.examples[0].input == "sample input"
        assert skill.content.examples[0].output == "expected output"
        assert skill.content.examples[0].explanation == "Why this is correct"
        assert skill.content.examples[1].explanation is None


class TestLoadSkillFromDict:
    """Tests for load_skill_from_dict function."""

    def test_load_valid_dict(self) -> None:
        """Test loading skill from valid dictionary."""
        data = {
            "metadata": {
                "name": "dict_skill",
                "version": "2.0",
                "effective_date": "2024-06-01",
            },
            "content": {
                "instructions": "Follow these steps",
            },
        }

        skill = load_skill_from_dict(data)

        assert skill.name == "dict_skill"
        assert skill.version == "2.0"
        assert skill.effective_date.month == 6

    def test_load_dict_missing_metadata(self) -> None:
        """Test error when metadata is missing from dict."""
        data = {"content": {"instructions": "Do something"}}

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_dict(data)

        assert "metadata" in str(exc_info.value).lower()

    def test_load_dict_missing_content(self) -> None:
        """Test error when content is missing from dict."""
        data = {
            "metadata": {
                "name": "test",
                "version": "1.0",
                "effective_date": "2024-01-01",
            }
        }

        with pytest.raises(SkillLoadError) as exc_info:
            load_skill_from_dict(data)

        assert "content" in str(exc_info.value).lower()

    def test_load_dict_invalid_name(self) -> None:
        """Test error when name contains invalid characters."""
        data = {
            "metadata": {
                "name": "invalid name!",
                "version": "1.0",
                "effective_date": "2024-01-01",
            },
            "content": {"instructions": "Do something"},
        }

        with pytest.raises(SkillLoadError):
            load_skill_from_dict(data)


class TestLoadSkillsFromDirectory:
    """Tests for load_skills_from_directory function."""

    def test_load_multiple_skills(self, tmp_path: Path) -> None:
        """Test loading multiple skill files from directory."""
        for i in range(3):
            skill_file = tmp_path / f"skill_{i}.yaml"
            skill_file.write_text(
                f"""
metadata:
  name: skill_{i}
  version: "1.0"
  effective_date: 2024-01-0{i + 1}

content:
  instructions: "Skill {i} instructions"
"""
            )

        skills = load_skills_from_directory(tmp_path)

        assert len(skills) == 3
        names = {s.name for s in skills}
        assert names == {"skill_0", "skill_1", "skill_2"}

    def test_load_with_pattern(self, tmp_path: Path) -> None:
        """Test loading with custom glob pattern."""
        (tmp_path / "skill.yaml").write_text(
            """
metadata:
  name: yaml_skill
  version: "1.0"
  effective_date: 2024-01-01
content:
  instructions: "YAML skill"
"""
        )
        (tmp_path / "skill.yml").write_text(
            """
metadata:
  name: yml_skill
  version: "1.0"
  effective_date: 2024-01-01
content:
  instructions: "YML skill"
"""
        )

        yaml_only = load_skills_from_directory(tmp_path, pattern="*.yaml")
        yml_only = load_skills_from_directory(tmp_path, pattern="*.yml")

        assert len(yaml_only) == 1
        assert yaml_only[0].name == "yaml_skill"
        assert len(yml_only) == 1
        assert yml_only[0].name == "yml_skill"

    def test_load_empty_directory(self, tmp_path: Path) -> None:
        """Test loading from directory with no matching files."""
        skills = load_skills_from_directory(tmp_path)
        assert skills == []

    def test_load_nonexistent_directory(self) -> None:
        """Test error when directory does not exist."""
        with pytest.raises(SkillLoadError) as exc_info:
            load_skills_from_directory("/nonexistent/directory")

        assert "not found" in str(exc_info.value).lower()


class TestValidateSkillYaml:
    """Tests for validate_skill_yaml function."""

    def test_validate_valid_file(self, tmp_path: Path) -> None:
        """Test validation returns no errors for valid file."""
        skill_yaml = tmp_path / "valid.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: valid_skill
  version: "1.0"
  effective_date: 2024-01-01

content:
  instructions: "Valid instructions"
"""
        )

        errors = validate_skill_yaml(skill_yaml)

        assert errors == []

    def test_validate_missing_metadata(self, tmp_path: Path) -> None:
        """Test validation catches missing metadata."""
        skill_yaml = tmp_path / "no_meta.yaml"
        skill_yaml.write_text(
            """
content:
  instructions: "No metadata"
"""
        )

        errors = validate_skill_yaml(skill_yaml)

        assert len(errors) > 0
        assert any("metadata" in e.lower() for e in errors)

    def test_validate_missing_instructions(self, tmp_path: Path) -> None:
        """Test validation catches missing instructions."""
        skill_yaml = tmp_path / "no_instructions.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: test
  version: "1.0"
  effective_date: 2024-01-01

content:
  constraints:
    - "Some constraint"
"""
        )

        errors = validate_skill_yaml(skill_yaml)

        assert len(errors) > 0
        assert any("instructions" in e.lower() for e in errors)

    def test_validate_nonexistent_file(self) -> None:
        """Test validation handles nonexistent file."""
        errors = validate_skill_yaml("/nonexistent/skill.yaml")

        assert len(errors) > 0
        assert any("not found" in e.lower() for e in errors)

    def test_validate_multiple_errors(self, tmp_path: Path) -> None:
        """Test validation returns multiple errors."""
        skill_yaml = tmp_path / "many_errors.yaml"
        skill_yaml.write_text(
            """
metadata:
  name: test
  version: "1.0"

content:
  examples: []
"""
        )

        errors = validate_skill_yaml(skill_yaml)

        # Should have errors for missing effective_date and missing instructions
        assert len(errors) >= 2


class TestExampleSkillFile:
    """Test loading the actual example skill file."""

    def test_load_example_skill(self) -> None:
        """Test that the example skill file is valid and loads correctly."""
        skill = load_skill_from_yaml("skills/example_skill.yaml")

        assert skill.name == "personal_tax_w2"
        assert skill.version == "2024.1"
        assert skill.effective_date.year == 2024
        assert skill.effective_date.month == 1
        assert skill.effective_date.day == 1
        assert "W-2" in skill.metadata.description
        assert len(skill.tags) > 0
        assert "w2" in skill.tags
        assert "Box 1" in skill.instructions
        assert len(skill.content.examples) == 2
        assert len(skill.content.constraints) > 0
        assert len(skill.content.escalation_triggers) > 0

    def test_validate_example_skill(self) -> None:
        """Test that the example skill file passes validation."""
        errors = validate_skill_yaml("skills/example_skill.yaml")
        assert errors == []
