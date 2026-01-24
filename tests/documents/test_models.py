"""Tests for tax document Pydantic models.

Comprehensive tests covering:
- SSN/EIN validation and formatting
- W2Data model with all fields
- Form1099INT, Form1099DIV, Form1099NEC models
- DocumentType enum
- Edge cases and error handling
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.documents.models import (
    Box12Code,
    ConfidenceLevel,
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Data,
    validate_ein,
    validate_ssn,
)


class TestSSNValidation:
    """Tests for SSN validation and formatting."""

    def test_valid_ssn_with_dashes(self) -> None:
        """SSN with dashes is accepted and formatted correctly."""
        result = validate_ssn("123-45-6789")
        assert result == "123-45-6789"

    def test_valid_ssn_without_dashes(self) -> None:
        """SSN without dashes is accepted and formatted with dashes."""
        result = validate_ssn("123456789")
        assert result == "123-45-6789"

    def test_valid_ssn_with_spaces(self) -> None:
        """SSN with spaces is accepted after cleaning."""
        result = validate_ssn("123 45 6789")
        assert result == "123-45-6789"

    def test_valid_ssn_mixed_separators(self) -> None:
        """SSN with mixed separators is cleaned and formatted."""
        result = validate_ssn("123-45 6789")
        assert result == "123-45-6789"

    def test_invalid_ssn_too_few_digits(self) -> None:
        """SSN with too few digits raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ssn("12345678")

    def test_invalid_ssn_too_many_digits(self) -> None:
        """SSN with too many digits raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ssn("1234567890")

    def test_invalid_ssn_empty(self) -> None:
        """Empty SSN raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ssn("")

    def test_invalid_ssn_letters(self) -> None:
        """SSN with letters (non-digits) raises ValueError if not enough digits."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ssn("123-AB-6789")


class TestEINValidation:
    """Tests for EIN validation and formatting."""

    def test_valid_ein_with_dash(self) -> None:
        """EIN with dash is accepted."""
        result = validate_ein("12-3456789")
        assert result == "12-3456789"

    def test_valid_ein_without_dash(self) -> None:
        """EIN without dash is accepted and formatted with dash."""
        result = validate_ein("123456789")
        assert result == "12-3456789"

    def test_valid_ein_with_spaces(self) -> None:
        """EIN with spaces is cleaned and formatted."""
        result = validate_ein("12 3456789")
        assert result == "12-3456789"

    def test_invalid_ein_too_few_digits(self) -> None:
        """EIN with too few digits raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ein("12345678")

    def test_invalid_ein_too_many_digits(self) -> None:
        """EIN with too many digits raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ein("1234567890")

    def test_invalid_ein_empty(self) -> None:
        """Empty EIN raises ValueError."""
        with pytest.raises(ValueError, match="must be exactly 9 digits"):
            validate_ein("")


class TestW2Data:
    """Tests for W2Data model."""

    @pytest.fixture
    def valid_w2_data(self) -> dict:
        """Return valid W2 data for testing."""
        return {
            "employee_ssn": "123-45-6789",
            "employer_ein": "12-3456789",
            "employer_name": "Test Corporation",
            "employee_name": "John Doe",
            "wages_tips_compensation": Decimal("50000.00"),
            "federal_tax_withheld": Decimal("5000.00"),
            "social_security_wages": Decimal("50000.00"),
            "social_security_tax": Decimal("3100.00"),
            "medicare_wages": Decimal("50000.00"),
            "medicare_tax": Decimal("725.00"),
            "confidence": ConfidenceLevel.HIGH,
        }

    def test_complete_valid_w2(self, valid_w2_data: dict) -> None:
        """Complete valid W2 data creates model successfully."""
        w2 = W2Data(**valid_w2_data)
        assert w2.employee_ssn == "123-45-6789"
        assert w2.employer_ein == "12-3456789"
        assert w2.wages_tips_compensation == Decimal("50000.00")
        assert w2.confidence == ConfidenceLevel.HIGH

    def test_w2_ssn_reformatted(self, valid_w2_data: dict) -> None:
        """SSN without dashes is reformatted."""
        valid_w2_data["employee_ssn"] = "123456789"
        w2 = W2Data(**valid_w2_data)
        assert w2.employee_ssn == "123-45-6789"

    def test_w2_ein_reformatted(self, valid_w2_data: dict) -> None:
        """EIN without dash is reformatted."""
        valid_w2_data["employer_ein"] = "123456789"
        w2 = W2Data(**valid_w2_data)
        assert w2.employer_ein == "12-3456789"

    def test_w2_optional_fields_default(self, valid_w2_data: dict) -> None:
        """Optional fields default to appropriate values."""
        w2 = W2Data(**valid_w2_data)
        assert w2.social_security_tips == Decimal("0")
        assert w2.allocated_tips == Decimal("0")
        assert w2.dependent_care_benefits == Decimal("0")
        assert w2.state_wages == Decimal("0")
        assert w2.state_tax_withheld == Decimal("0")
        assert w2.statutory_employee is False
        assert w2.retirement_plan is False
        assert w2.third_party_sick_pay is False
        assert w2.box_12_codes == []
        assert w2.uncertain_fields == []

    def test_w2_with_box_12_codes(self, valid_w2_data: dict) -> None:
        """W2 with box 12 codes list parses correctly."""
        valid_w2_data["box_12_codes"] = [
            {"code": "D", "amount": Decimal("5000.00")},
            {"code": "DD", "amount": Decimal("12000.00")},
        ]
        w2 = W2Data(**valid_w2_data)
        assert len(w2.box_12_codes) == 2
        assert w2.box_12_codes[0].code == "D"
        assert w2.box_12_codes[0].amount == Decimal("5000.00")
        assert w2.box_12_codes[1].code == "DD"

    def test_w2_with_box_13_flags(self, valid_w2_data: dict) -> None:
        """W2 with box 13 checkboxes set works correctly."""
        valid_w2_data["statutory_employee"] = True
        valid_w2_data["retirement_plan"] = True
        valid_w2_data["third_party_sick_pay"] = False
        w2 = W2Data(**valid_w2_data)
        assert w2.statutory_employee is True
        assert w2.retirement_plan is True
        assert w2.third_party_sick_pay is False

    def test_w2_with_state_fields(self, valid_w2_data: dict) -> None:
        """W2 with state fields populated works correctly."""
        valid_w2_data["state_wages"] = Decimal("48000.00")
        valid_w2_data["state_tax_withheld"] = Decimal("2400.00")
        w2 = W2Data(**valid_w2_data)
        assert w2.state_wages == Decimal("48000.00")
        assert w2.state_tax_withheld == Decimal("2400.00")

    def test_w2_with_uncertain_fields(self, valid_w2_data: dict) -> None:
        """W2 with uncertain fields list works correctly."""
        valid_w2_data["uncertain_fields"] = ["wages_tips_compensation", "state_wages"]
        valid_w2_data["confidence"] = ConfidenceLevel.MEDIUM
        w2 = W2Data(**valid_w2_data)
        assert w2.uncertain_fields == ["wages_tips_compensation", "state_wages"]
        assert w2.confidence == ConfidenceLevel.MEDIUM

    def test_w2_invalid_ssn(self, valid_w2_data: dict) -> None:
        """W2 with invalid SSN raises ValidationError."""
        valid_w2_data["employee_ssn"] = "12345"
        with pytest.raises(ValidationError):
            W2Data(**valid_w2_data)

    def test_w2_invalid_ein(self, valid_w2_data: dict) -> None:
        """W2 with invalid EIN raises ValidationError."""
        valid_w2_data["employer_ein"] = "12345"
        with pytest.raises(ValidationError):
            W2Data(**valid_w2_data)

    def test_w2_missing_required_field(self, valid_w2_data: dict) -> None:
        """W2 missing required field raises ValidationError."""
        del valid_w2_data["wages_tips_compensation"]
        with pytest.raises(ValidationError):
            W2Data(**valid_w2_data)


class TestForm1099INT:
    """Tests for Form1099INT model."""

    @pytest.fixture
    def valid_1099int_data(self) -> dict:
        """Return valid 1099-INT data for testing."""
        return {
            "payer_name": "First National Bank",
            "payer_tin": "12-3456789",
            "recipient_tin": "123-45-6789",
            "interest_income": Decimal("1500.00"),
            "confidence": ConfidenceLevel.HIGH,
        }

    def test_valid_1099int(self, valid_1099int_data: dict) -> None:
        """Valid 1099-INT data creates model successfully."""
        form = Form1099INT(**valid_1099int_data)
        assert form.payer_name == "First National Bank"
        assert form.interest_income == Decimal("1500.00")

    def test_1099int_optional_fields_default(self, valid_1099int_data: dict) -> None:
        """Optional fields default to zero."""
        form = Form1099INT(**valid_1099int_data)
        assert form.early_withdrawal_penalty == Decimal("0")
        assert form.interest_us_savings_bonds == Decimal("0")
        assert form.federal_tax_withheld == Decimal("0")
        assert form.investment_expenses == Decimal("0")
        assert form.foreign_tax_paid == Decimal("0")
        assert form.tax_exempt_interest == Decimal("0")
        assert form.private_activity_bond_interest == Decimal("0")
        assert form.uncertain_fields == []

    def test_1099int_with_all_boxes(self, valid_1099int_data: dict) -> None:
        """1099-INT with all boxes populated works correctly."""
        valid_1099int_data["early_withdrawal_penalty"] = Decimal("50.00")
        valid_1099int_data["interest_us_savings_bonds"] = Decimal("200.00")
        valid_1099int_data["federal_tax_withheld"] = Decimal("150.00")
        valid_1099int_data["foreign_tax_paid"] = Decimal("25.00")
        form = Form1099INT(**valid_1099int_data)
        assert form.early_withdrawal_penalty == Decimal("50.00")
        assert form.federal_tax_withheld == Decimal("150.00")

    def test_1099int_recipient_tin_reformatted(self, valid_1099int_data: dict) -> None:
        """Recipient TIN is reformatted as SSN."""
        valid_1099int_data["recipient_tin"] = "123456789"
        form = Form1099INT(**valid_1099int_data)
        assert form.recipient_tin == "123-45-6789"


class TestForm1099DIV:
    """Tests for Form1099DIV model."""

    @pytest.fixture
    def valid_1099div_data(self) -> dict:
        """Return valid 1099-DIV data for testing."""
        return {
            "payer_name": "Vanguard Investments",
            "payer_tin": "23-1234567",
            "recipient_tin": "123-45-6789",
            "total_ordinary_dividends": Decimal("2500.00"),
            "confidence": ConfidenceLevel.HIGH,
        }

    def test_valid_1099div(self, valid_1099div_data: dict) -> None:
        """Valid 1099-DIV data creates model successfully."""
        form = Form1099DIV(**valid_1099div_data)
        assert form.payer_name == "Vanguard Investments"
        assert form.total_ordinary_dividends == Decimal("2500.00")

    def test_1099div_optional_fields_default(self, valid_1099div_data: dict) -> None:
        """Optional fields default to zero."""
        form = Form1099DIV(**valid_1099div_data)
        assert form.qualified_dividends == Decimal("0")
        assert form.total_capital_gain_distributions == Decimal("0")
        assert form.unrecaptured_1250_gain == Decimal("0")
        assert form.section_1202_gain == Decimal("0")
        assert form.collectibles_gain == Decimal("0")
        assert form.nondividend_distributions == Decimal("0")
        assert form.federal_tax_withheld == Decimal("0")
        assert form.section_199a_dividends == Decimal("0")
        assert form.foreign_tax_paid == Decimal("0")
        assert form.exempt_interest_dividends == Decimal("0")

    def test_1099div_with_capital_gains(self, valid_1099div_data: dict) -> None:
        """1099-DIV with capital gain distributions works correctly."""
        valid_1099div_data["qualified_dividends"] = Decimal("2000.00")
        valid_1099div_data["total_capital_gain_distributions"] = Decimal("500.00")
        valid_1099div_data["unrecaptured_1250_gain"] = Decimal("100.00")
        form = Form1099DIV(**valid_1099div_data)
        assert form.qualified_dividends == Decimal("2000.00")
        assert form.total_capital_gain_distributions == Decimal("500.00")
        assert form.unrecaptured_1250_gain == Decimal("100.00")

    def test_1099div_with_section_199a(self, valid_1099div_data: dict) -> None:
        """1099-DIV with Section 199A dividends works correctly."""
        valid_1099div_data["section_199a_dividends"] = Decimal("300.00")
        form = Form1099DIV(**valid_1099div_data)
        assert form.section_199a_dividends == Decimal("300.00")


class TestForm1099NEC:
    """Tests for Form1099NEC model."""

    @pytest.fixture
    def valid_1099nec_data(self) -> dict:
        """Return valid 1099-NEC data for testing."""
        return {
            "payer_name": "ABC Consulting LLC",
            "payer_tin": "34-5678901",
            "recipient_name": "Jane Smith",
            "recipient_tin": "987-65-4321",
            "nonemployee_compensation": Decimal("15000.00"),
            "confidence": ConfidenceLevel.HIGH,
        }

    def test_valid_1099nec(self, valid_1099nec_data: dict) -> None:
        """Valid 1099-NEC data creates model successfully."""
        form = Form1099NEC(**valid_1099nec_data)
        assert form.payer_name == "ABC Consulting LLC"
        assert form.recipient_name == "Jane Smith"
        assert form.nonemployee_compensation == Decimal("15000.00")

    def test_1099nec_optional_fields_default(self, valid_1099nec_data: dict) -> None:
        """Optional fields default correctly."""
        form = Form1099NEC(**valid_1099nec_data)
        assert form.direct_sales is False
        assert form.federal_tax_withheld == Decimal("0")
        assert form.state_tax_withheld == Decimal("0")

    def test_1099nec_with_direct_sales(self, valid_1099nec_data: dict) -> None:
        """1099-NEC with direct sales flag works correctly."""
        valid_1099nec_data["direct_sales"] = True
        form = Form1099NEC(**valid_1099nec_data)
        assert form.direct_sales is True

    def test_1099nec_with_withholding(self, valid_1099nec_data: dict) -> None:
        """1099-NEC with tax withholding works correctly."""
        valid_1099nec_data["federal_tax_withheld"] = Decimal("1500.00")
        valid_1099nec_data["state_tax_withheld"] = Decimal("750.00")
        form = Form1099NEC(**valid_1099nec_data)
        assert form.federal_tax_withheld == Decimal("1500.00")
        assert form.state_tax_withheld == Decimal("750.00")


class TestDocumentType:
    """Tests for DocumentType enum."""

    def test_all_document_types_accessible(self) -> None:
        """All DocumentType values are accessible."""
        assert DocumentType.W2 == "W2"
        assert DocumentType.FORM_1099_INT == "1099-INT"
        assert DocumentType.FORM_1099_DIV == "1099-DIV"
        assert DocumentType.FORM_1099_NEC == "1099-NEC"
        assert DocumentType.UNKNOWN == "UNKNOWN"

    def test_document_type_from_string(self) -> None:
        """DocumentType can be created from string value."""
        assert DocumentType("W2") == DocumentType.W2
        assert DocumentType("1099-INT") == DocumentType.FORM_1099_INT

    def test_document_type_count(self) -> None:
        """DocumentType has expected number of values."""
        assert len(DocumentType) == 5


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_all_confidence_levels_accessible(self) -> None:
        """All ConfidenceLevel values are accessible."""
        assert ConfidenceLevel.HIGH == "HIGH"
        assert ConfidenceLevel.MEDIUM == "MEDIUM"
        assert ConfidenceLevel.LOW == "LOW"

    def test_confidence_level_count(self) -> None:
        """ConfidenceLevel has expected number of values."""
        assert len(ConfidenceLevel) == 3


class TestBox12Code:
    """Tests for Box12Code model."""

    def test_valid_box12_code(self) -> None:
        """Valid Box12Code creates successfully."""
        code = Box12Code(code="D", amount=Decimal("5000.00"))
        assert code.code == "D"
        assert code.amount == Decimal("5000.00")

    def test_box12_code_dd(self) -> None:
        """Box12Code with DD (health insurance) works correctly."""
        code = Box12Code(code="DD", amount=Decimal("12500.00"))
        assert code.code == "DD"
        assert code.amount == Decimal("12500.00")
