"""Tests for confidence scoring module."""

from __future__ import annotations

import pytest

from src.documents.confidence import (
    CRITICAL_FIELDS,
    THRESHOLD_HIGH,
    THRESHOLD_MEDIUM,
    WEIGHT_CRITICAL,
    WEIGHT_LLM,
    WEIGHT_VALIDATION,
    ConfidenceResult,
    calculate_confidence,
    get_critical_fields,
)
from src.documents.models import ConfidenceLevel, DocumentType


class TestConfidenceResult:
    """Tests for ConfidenceResult dataclass."""

    def test_confidence_result_creation(self) -> None:
        """Test ConfidenceResult can be created with required fields."""
        result = ConfidenceResult(
            level=ConfidenceLevel.HIGH,
            score=0.95,
        )
        assert result.level == ConfidenceLevel.HIGH
        assert result.score == 0.95
        assert result.factors == {}
        assert result.notes == []

    def test_confidence_result_with_all_fields(self) -> None:
        """Test ConfidenceResult with all optional fields."""
        result = ConfidenceResult(
            level=ConfidenceLevel.MEDIUM,
            score=0.75,
            factors={"llm": 0.8, "validation": 0.7},
            notes=["Some fields failed validation"],
        )
        assert result.factors == {"llm": 0.8, "validation": 0.7}
        assert "Some fields failed validation" in result.notes


class TestGetCriticalFields:
    """Tests for get_critical_fields function."""

    def test_w2_critical_fields(self) -> None:
        """Test W2 has correct critical fields."""
        fields = get_critical_fields(DocumentType.W2)
        assert "employee_ssn" in fields
        assert "employer_ein" in fields
        assert "wages_tips_compensation" in fields
        assert "federal_tax_withheld" in fields
        assert len(fields) == 4

    def test_1099_int_critical_fields(self) -> None:
        """Test 1099-INT has correct critical fields."""
        fields = get_critical_fields(DocumentType.FORM_1099_INT)
        assert "payer_tin" in fields
        assert "recipient_tin" in fields
        assert "interest_income" in fields
        assert len(fields) == 3

    def test_1099_div_critical_fields(self) -> None:
        """Test 1099-DIV has correct critical fields."""
        fields = get_critical_fields(DocumentType.FORM_1099_DIV)
        assert "payer_tin" in fields
        assert "recipient_tin" in fields
        assert "total_ordinary_dividends" in fields
        assert len(fields) == 3

    def test_1099_nec_critical_fields(self) -> None:
        """Test 1099-NEC has correct critical fields."""
        fields = get_critical_fields(DocumentType.FORM_1099_NEC)
        assert "payer_tin" in fields
        assert "recipient_tin" in fields
        assert "nonemployee_compensation" in fields
        assert len(fields) == 3

    def test_unknown_has_no_critical_fields(self) -> None:
        """Test UNKNOWN document type has no critical fields."""
        fields = get_critical_fields(DocumentType.UNKNOWN)
        assert fields == []


class TestCalculateConfidenceHighLevel:
    """Tests for HIGH confidence level scenarios."""

    def test_high_confidence_all_perfect(self) -> None:
        """Test HIGH when all factors are perfect."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"field1": True, "field2": True},
            critical_fields_present={"crit1": True, "crit2": True},
        )
        assert result.level == ConfidenceLevel.HIGH
        assert result.score >= THRESHOLD_HIGH

    def test_high_confidence_requires_all_critical_fields(self) -> None:
        """Test HIGH requires all critical fields present."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"field1": True, "field2": True},
            critical_fields_present={"crit1": True, "crit2": False},  # One missing
        )
        # Score might be high but level should not be HIGH
        assert result.level != ConfidenceLevel.HIGH

    def test_high_confidence_w2_scenario(self) -> None:
        """Test HIGH confidence for typical W2 extraction."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={
                "ssn_format": True,
                "ein_format": True,
                "wage_numeric": True,
            },
            critical_fields_present={
                "employee_ssn": True,
                "employer_ein": True,
                "wages_tips_compensation": True,
                "federal_tax_withheld": True,
            },
        )
        assert result.level == ConfidenceLevel.HIGH
        assert result.score == 1.0


class TestCalculateConfidenceMediumLevel:
    """Tests for MEDIUM confidence level scenarios."""

    def test_medium_confidence_some_validations_fail(self) -> None:
        """Test MEDIUM when some validations fail."""
        result = calculate_confidence(
            llm_reported_confidence="MEDIUM",
            field_validations={"field1": True, "field2": False, "field3": True},
            critical_fields_present={"crit1": True},
        )
        assert result.level == ConfidenceLevel.MEDIUM

    def test_medium_confidence_threshold_boundary(self) -> None:
        """Test score at MEDIUM threshold boundary."""
        # Create scenario that gives MEDIUM (missing a critical field)
        result = calculate_confidence(
            llm_reported_confidence="MEDIUM",  # 0.6 score
            field_validations={"f1": True, "f2": True},  # 1.0 score
            critical_fields_present={"c1": True, "c2": False},  # 0.5 score, missing critical
        )
        # 0.3*0.6 + 0.4*1.0 + 0.3*0.5 = 0.18 + 0.4 + 0.15 = 0.73 -> MEDIUM
        assert result.level == ConfidenceLevel.MEDIUM  # Missing critical prevents HIGH

    def test_medium_when_high_score_but_missing_critical(self) -> None:
        """Test MEDIUM when score is high but critical field missing."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True, "f2": True},
            critical_fields_present={"crit1": True, "crit2": False},
        )
        # Score would be high but missing critical prevents HIGH
        if result.score >= THRESHOLD_HIGH:
            assert result.level == ConfidenceLevel.MEDIUM
            assert any("critical fields are missing" in note for note in result.notes)


class TestCalculateConfidenceLowLevel:
    """Tests for LOW confidence level scenarios."""

    def test_low_confidence_low_llm(self) -> None:
        """Test LOW when LLM reports low confidence."""
        result = calculate_confidence(
            llm_reported_confidence="LOW",
            field_validations={"f1": False, "f2": False},
            critical_fields_present={"c1": False},
        )
        assert result.level == ConfidenceLevel.LOW

    def test_low_confidence_all_validations_fail(self) -> None:
        """Test LOW when all validations fail."""
        result = calculate_confidence(
            llm_reported_confidence="MEDIUM",
            field_validations={"f1": False, "f2": False, "f3": False},
            critical_fields_present={"c1": False, "c2": False},
        )
        assert result.level == ConfidenceLevel.LOW

    def test_low_confidence_missing_all_critical(self) -> None:
        """Test LOW when all critical fields missing."""
        result = calculate_confidence(
            llm_reported_confidence="LOW",
            field_validations={},
            critical_fields_present={"c1": False, "c2": False, "c3": False},
        )
        assert result.level == ConfidenceLevel.LOW


class TestCalculateConfidenceFactors:
    """Tests for factor weight calculations."""

    def test_factor_weights_sum_to_one(self) -> None:
        """Test that factor weights sum to 1.0."""
        assert WEIGHT_LLM + WEIGHT_VALIDATION + WEIGHT_CRITICAL == 1.0

    def test_factors_dict_contains_all_factors(self) -> None:
        """Test factors dict has all three factor scores."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True},
            critical_fields_present={"c1": True},
        )
        assert "llm_confidence" in result.factors
        assert "field_validation" in result.factors
        assert "critical_fields" in result.factors

    def test_llm_confidence_score_high(self) -> None:
        """Test LLM HIGH maps to 1.0."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={},
            critical_fields_present={},
        )
        assert result.factors["llm_confidence"] == 1.0

    def test_llm_confidence_score_medium(self) -> None:
        """Test LLM MEDIUM maps to 0.6."""
        result = calculate_confidence(
            llm_reported_confidence="MEDIUM",
            field_validations={},
            critical_fields_present={},
        )
        assert result.factors["llm_confidence"] == 0.6

    def test_llm_confidence_score_low(self) -> None:
        """Test LLM LOW maps to 0.3."""
        result = calculate_confidence(
            llm_reported_confidence="LOW",
            field_validations={},
            critical_fields_present={},
        )
        assert result.factors["llm_confidence"] == 0.3

    def test_validation_score_all_pass(self) -> None:
        """Test validation score is 1.0 when all pass."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True, "f2": True, "f3": True},
            critical_fields_present={},
        )
        assert result.factors["field_validation"] == 1.0

    def test_validation_score_half_pass(self) -> None:
        """Test validation score is 0.5 when half pass."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True, "f2": False},
            critical_fields_present={},
        )
        assert result.factors["field_validation"] == 0.5

    def test_critical_score_all_present(self) -> None:
        """Test critical score is 1.0 when all present."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={},
            critical_fields_present={"c1": True, "c2": True},
        )
        assert result.factors["critical_fields"] == 1.0

    def test_critical_score_partial_present(self) -> None:
        """Test critical score is 0.5 when half present."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={},
            critical_fields_present={"c1": True, "c2": False},
        )
        assert result.factors["critical_fields"] == 0.5

    def test_score_calculation_correct(self) -> None:
        """Test overall score calculation is weighted correctly."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",  # 1.0
            field_validations={"f1": True, "f2": False},  # 0.5
            critical_fields_present={"c1": True},  # 1.0
        )
        expected = WEIGHT_LLM * 1.0 + WEIGHT_VALIDATION * 0.5 + WEIGHT_CRITICAL * 1.0
        assert abs(result.score - expected) < 0.0001


class TestCalculateConfidenceNotes:
    """Tests for notes population."""

    def test_notes_for_failed_validations(self) -> None:
        """Test notes list failed validation fields."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"ssn_format": False, "ein_format": True},
            critical_fields_present={"c1": True},
        )
        assert any("ssn_format" in note for note in result.notes)

    def test_notes_for_missing_critical_fields(self) -> None:
        """Test notes list missing critical fields."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True},
            critical_fields_present={"employee_ssn": False, "employer_ein": True},
        )
        assert any("employee_ssn" in note for note in result.notes)

    def test_notes_for_unknown_llm_confidence(self) -> None:
        """Test notes for unknown LLM confidence value."""
        result = calculate_confidence(
            llm_reported_confidence="INVALID",
            field_validations={"f1": True},
            critical_fields_present={"c1": True},
        )
        assert any("Unknown LLM confidence" in note for note in result.notes)

    def test_notes_for_no_validations(self) -> None:
        """Test notes when no validations performed."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={},
            critical_fields_present={"c1": True},
        )
        assert any("No field validations" in note for note in result.notes)

    def test_low_confidence_has_notes(self) -> None:
        """Test LOW confidence cases have explanatory notes."""
        result = calculate_confidence(
            llm_reported_confidence="LOW",
            field_validations={"f1": False},
            critical_fields_present={"c1": False},
        )
        # Should have notes about failed validations and missing critical
        assert len(result.notes) > 0


class TestCalculateConfidenceEdgeCases:
    """Tests for edge cases."""

    def test_case_insensitive_llm_confidence(self) -> None:
        """Test LLM confidence is case insensitive."""
        result = calculate_confidence(
            llm_reported_confidence="high",  # lowercase
            field_validations={"f1": True},
            critical_fields_present={"c1": True},
        )
        assert result.factors["llm_confidence"] == 1.0

    def test_empty_critical_fields_allows_high(self) -> None:
        """Test empty critical fields doesn't prevent HIGH."""
        result = calculate_confidence(
            llm_reported_confidence="HIGH",
            field_validations={"f1": True},
            critical_fields_present={},
        )
        # No critical fields to check = all critical present (vacuously true)
        if result.score >= THRESHOLD_HIGH:
            assert result.level == ConfidenceLevel.HIGH

    @pytest.mark.parametrize(
        ("llm", "validations", "criticals", "expected_level"),
        [
            ("HIGH", {"f1": True}, {"c1": True}, ConfidenceLevel.HIGH),
            ("HIGH", {"f1": True}, {"c1": False}, ConfidenceLevel.MEDIUM),
            ("LOW", {"f1": True}, {"c1": True}, ConfidenceLevel.MEDIUM),
            ("LOW", {"f1": False}, {"c1": False}, ConfidenceLevel.LOW),
        ],
    )
    def test_confidence_level_combinations(
        self,
        llm: str,
        validations: dict[str, bool],
        criticals: dict[str, bool],
        expected_level: ConfidenceLevel,
    ) -> None:
        """Test various combinations of factors produce expected levels."""
        result = calculate_confidence(
            llm_reported_confidence=llm,
            field_validations=validations,
            critical_fields_present=criticals,
        )
        assert result.level == expected_level


class TestCriticalFieldsConstant:
    """Tests for CRITICAL_FIELDS constant."""

    def test_all_document_types_have_critical_fields(self) -> None:
        """Test all document types are represented."""
        assert DocumentType.W2 in CRITICAL_FIELDS
        assert DocumentType.FORM_1099_INT in CRITICAL_FIELDS
        assert DocumentType.FORM_1099_DIV in CRITICAL_FIELDS
        assert DocumentType.FORM_1099_NEC in CRITICAL_FIELDS
        assert DocumentType.UNKNOWN in CRITICAL_FIELDS

    def test_critical_fields_are_lists(self) -> None:
        """Test critical fields values are lists of strings."""
        for doc_type, fields in CRITICAL_FIELDS.items():
            assert isinstance(fields, list), f"{doc_type} fields is not a list"
            for field in fields:
                assert isinstance(field, str), f"{doc_type} has non-string field"
