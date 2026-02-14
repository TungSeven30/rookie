"""Tests for document validation module.

Tests cover:
- W-2 validation (withholding, SS wage cap, tax rate checks)
- K-1 validation (ownership percentage, entity type, guaranteed payments)
- 1099-B validation (proceeds, term classification, wash sales)
- Cross-document validation (TIN consistency)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.documents.models import (
    ConfidenceLevel,
    Form1099B,
    FormK1,
    W2Data,
)
from src.documents.validation import DocumentValidator, ValidationResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator() -> DocumentValidator:
    """Return a DocumentValidator instance."""
    return DocumentValidator()


@pytest.fixture
def valid_w2() -> W2Data:
    """Return a valid W2Data instance."""
    return W2Data(
        employee_ssn="123-45-6789",
        employer_ein="12-3456789",
        employer_name="Acme Corporation",
        employee_name="John Taxpayer",
        wages_tips_compensation=Decimal("75000.00"),
        federal_tax_withheld=Decimal("12500.00"),
        social_security_wages=Decimal("75000.00"),
        social_security_tax=Decimal("4650.00"),  # 6.2%
        medicare_wages=Decimal("75000.00"),
        medicare_tax=Decimal("1087.50"),  # 1.45%
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def valid_k1() -> FormK1:
    """Return a valid FormK1 instance."""
    return FormK1(
        entity_name="Demo Partnership LLC",
        entity_ein="12-3456789",
        entity_type="partnership",
        tax_year=2024,
        recipient_name="John Taxpayer",
        recipient_tin="123-45-6789",
        ownership_percentage=Decimal("25.0"),
        ordinary_business_income=Decimal("45000.00"),
        guaranteed_payments=Decimal("12000.00"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def valid_1099b() -> Form1099B:
    """Return a valid Form1099B instance."""
    return Form1099B(
        payer_name="Fidelity Investments",
        payer_tin="12-3456789",
        recipient_tin="123-45-6789",
        description="AAPL - Apple Inc (100 shares)",
        date_sold="2024-06-20",
        proceeds=Decimal("19500.00"),
        cost_basis=Decimal("15000.00"),
        is_long_term=True,
        basis_reported_to_irs=True,
        confidence=ConfidenceLevel.HIGH,
    )


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """ValidationResult can be created with all fields."""
        result = ValidationResult(
            is_valid=True,
            errors=["error1"],
            warnings=["warning1"],
            corrections_applied=["correction1"],
        )
        assert result.is_valid is True
        assert result.errors == ["error1"]
        assert result.warnings == ["warning1"]
        assert result.corrections_applied == ["correction1"]

    def test_validation_result_defaults(self) -> None:
        """ValidationResult has default empty lists."""
        result = ValidationResult(is_valid=True)
        assert result.errors == []
        assert result.warnings == []
        assert result.corrections_applied == []


# =============================================================================
# W-2 Validation Tests
# =============================================================================


class TestW2Validation:
    """Tests for W-2 validation."""

    def test_valid_w2_passes(self, validator: DocumentValidator, valid_w2: W2Data) -> None:
        """Valid W-2 data passes validation."""
        result = validator.validate_w2(valid_w2)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_federal_withholding_exceeds_wages(self, validator: DocumentValidator) -> None:
        """Error when federal withholding exceeds wages."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("50000.00"),
            federal_tax_withheld=Decimal("60000.00"),  # More than wages!
            social_security_wages=Decimal("50000.00"),
            social_security_tax=Decimal("3100.00"),
            medicare_wages=Decimal("50000.00"),
            medicare_tax=Decimal("725.00"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_w2(w2)
        assert result.is_valid is False
        assert any("exceeds wages" in e for e in result.errors)

    def test_ss_wages_exceed_cap_warning(self, validator: DocumentValidator) -> None:
        """Warning when Social Security wages exceed annual cap."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("200000.00"),
            federal_tax_withheld=Decimal("35000.00"),
            social_security_wages=Decimal("200000.00"),  # Over 2024 cap of $168,600
            social_security_tax=Decimal("10453.20"),  # 6.2% of cap
            medicare_wages=Decimal("200000.00"),
            medicare_tax=Decimal("2900.00"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_w2(w2)
        # This is a warning, not an error
        assert result.is_valid is True
        assert any("exceed" in w.lower() and "cap" in w.lower() for w in result.warnings)

    def test_ss_tax_rate_mismatch_warning(self, validator: DocumentValidator) -> None:
        """Warning when SS tax doesn't match expected rate."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("75000.00"),
            federal_tax_withheld=Decimal("12500.00"),
            social_security_wages=Decimal("75000.00"),
            social_security_tax=Decimal("1000.00"),  # Way off from 6.2%
            medicare_wages=Decimal("75000.00"),
            medicare_tax=Decimal("1087.50"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_w2(w2)
        assert result.is_valid is True  # Warning, not error
        assert any("doesn't match expected" in w for w in result.warnings)

    def test_w2_2025_uses_2025_ss_wage_cap(self, validator: DocumentValidator) -> None:
        """2025 validation should use the 2025 SSA wage base."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("170000.00"),
            federal_tax_withheld=Decimal("25000.00"),
            social_security_wages=Decimal("170000.00"),  # Above 2024 cap, below 2025 cap
            social_security_tax=Decimal("10540.00"),
            medicare_wages=Decimal("170000.00"),
            medicare_tax=Decimal("2465.00"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_w2(w2, tax_year=2025)
        assert result.is_valid is True
        assert not any("cap" in warning.lower() for warning in result.warnings)


# =============================================================================
# K-1 Validation Tests
# =============================================================================


class TestK1Validation:
    """Tests for K-1 validation."""

    def test_valid_k1_passes(self, validator: DocumentValidator, valid_k1: FormK1) -> None:
        """Valid K-1 data passes validation."""
        result = validator.validate_k1(valid_k1)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_ownership_percentage(self, validator: DocumentValidator) -> None:
        """Error when ownership percentage is out of range."""
        k1 = FormK1(
            entity_name="Test",
            entity_ein="12-3456789",
            entity_type="partnership",
            tax_year=2024,
            recipient_name="John",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("150.0"),  # Invalid!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_k1(k1)
        assert result.is_valid is False
        assert any("ownership percentage" in e.lower() for e in result.errors)

    def test_invalid_entity_type(self, validator: DocumentValidator) -> None:
        """Error when entity type is invalid."""
        k1 = FormK1(
            entity_name="Test",
            entity_ein="12-3456789",
            entity_type="llc",  # Invalid - should be partnership or s_corp
            tax_year=2024,
            recipient_name="John",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("25.0"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_k1(k1)
        assert result.is_valid is False
        assert any("entity type" in e.lower() for e in result.errors)

    def test_scorp_with_guaranteed_payments_warning(self, validator: DocumentValidator) -> None:
        """Warning when S-corp K-1 has guaranteed payments."""
        k1 = FormK1(
            entity_name="Test S-Corp",
            entity_ein="12-3456789",
            entity_type="s_corp",
            tax_year=2024,
            recipient_name="John",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("100.0"),
            guaranteed_payments=Decimal("50000.00"),  # S-corps don't have GP!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_k1(k1)
        assert result.is_valid is True  # Warning, not error
        assert any("s-corp" in w.lower() and "guaranteed" in w.lower() for w in result.warnings)

    def test_large_loss_warning(self, validator: DocumentValidator) -> None:
        """Warning when K-1 has large losses."""
        k1 = FormK1(
            entity_name="Loss Partnership",
            entity_ein="12-3456789",
            entity_type="partnership",
            tax_year=2024,
            recipient_name="John",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("50.0"),
            ordinary_business_income=Decimal("-150000.00"),  # Large loss
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_k1(k1)
        assert result.is_valid is True  # Warning, not error
        assert any("loss" in w.lower() for w in result.warnings)


# =============================================================================
# 1099-B Validation Tests
# =============================================================================


class TestForm1099BValidation:
    """Tests for Form 1099-B validation."""

    def test_valid_1099b_passes(self, validator: DocumentValidator, valid_1099b: Form1099B) -> None:
        """Valid 1099-B data passes validation."""
        result = validator.validate_1099b(valid_1099b)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_invalid_proceeds(self, validator: DocumentValidator) -> None:
        """Error when proceeds are zero or negative."""
        txn = Form1099B(
            payer_name="Broker",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="AAPL",
            date_sold="2024-06-20",
            proceeds=Decimal("-100.00"),  # Invalid!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_1099b(txn)
        assert result.is_valid is False
        assert any("proceeds" in e.lower() for e in result.errors)

    def test_both_short_and_long_term(self, validator: DocumentValidator) -> None:
        """Error when transaction is marked both short-term and long-term."""
        txn = Form1099B(
            payer_name="Broker",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="AAPL",
            date_sold="2024-06-20",
            proceeds=Decimal("10000.00"),
            is_short_term=True,
            is_long_term=True,  # Can't be both!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_1099b(txn)
        assert result.is_valid is False
        assert any("short-term" in e.lower() and "long-term" in e.lower() for e in result.errors)

    def test_basis_reported_but_missing_warning(self, validator: DocumentValidator) -> None:
        """Warning when basis reported to IRS but not extracted."""
        txn = Form1099B(
            payer_name="Broker",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="AAPL",
            date_sold="2024-06-20",
            proceeds=Decimal("10000.00"),
            cost_basis=None,  # Missing
            basis_reported_to_irs=True,  # But says it's reported!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_1099b(txn)
        assert result.is_valid is True  # Warning, not error
        assert any("basis reported" in w.lower() for w in result.warnings)

    def test_wash_sale_exceeds_loss(self, validator: DocumentValidator) -> None:
        """Error when wash sale disallowed exceeds actual loss."""
        txn = Form1099B(
            payer_name="Broker",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="AAPL",
            date_sold="2024-06-20",
            proceeds=Decimal("9000.00"),
            cost_basis=Decimal("10000.00"),  # Loss of $1000
            wash_sale_loss_disallowed=Decimal("2000.00"),  # More than the loss!
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_1099b(txn)
        assert result.is_valid is False
        assert any("wash sale" in e.lower() for e in result.errors)


# =============================================================================
# Cross-Document Validation Tests
# =============================================================================


class TestCrossDocumentValidation:
    """Tests for cross-document validation."""

    def test_consistent_tins_pass(
        self, validator: DocumentValidator, valid_w2: W2Data, valid_k1: FormK1
    ) -> None:
        """Documents with consistent TINs pass validation."""
        # Both have TIN ending in 6789
        result = validator.validate_cross_document(
            w2s=[valid_w2],
            k1s=[valid_k1],
            forms_1099=[],
        )
        assert result.is_valid is True
        assert len(result.warnings) == 0

    def test_inconsistent_tins_warning(self, validator: DocumentValidator) -> None:
        """Warning when documents have different TINs."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("75000.00"),
            federal_tax_withheld=Decimal("12500.00"),
            social_security_wages=Decimal("75000.00"),
            social_security_tax=Decimal("4650.00"),
            medicare_wages=Decimal("75000.00"),
            medicare_tax=Decimal("1087.50"),
            confidence=ConfidenceLevel.HIGH,
        )
        k1 = FormK1(
            entity_name="Partnership",
            entity_ein="12-3456789",
            entity_type="partnership",
            tax_year=2024,
            recipient_name="Different Person",
            recipient_tin="987-65-4321",  # Different TIN!
            ownership_percentage=Decimal("25.0"),
            confidence=ConfidenceLevel.HIGH,
        )
        result = validator.validate_cross_document(
            w2s=[w2],
            k1s=[k1],
            forms_1099=[],
        )
        assert result.is_valid is True  # Warning, not error
        assert any("multiple tin" in w.lower() for w in result.warnings)

    def test_empty_documents_pass(self, validator: DocumentValidator) -> None:
        """Empty document lists pass validation."""
        result = validator.validate_cross_document(
            w2s=[],
            k1s=[],
            forms_1099=[],
        )
        assert result.is_valid is True
