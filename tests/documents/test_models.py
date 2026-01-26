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
    Form1095A,
    Form1099B,
    Form1099BSummary,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    FormK1,
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

    def test_1099int_recipient_tin_accepts_ein(self, valid_1099int_data: dict) -> None:
        """Recipient TIN accepts EIN format when provided."""
        valid_1099int_data["recipient_tin"] = "12-3456789"
        form = Form1099INT(**valid_1099int_data)
        assert form.recipient_tin == "12-3456789"

    def test_1099int_payer_tin_accepts_ssn(self, valid_1099int_data: dict) -> None:
        """Payer TIN accepts SSN format when provided."""
        valid_1099int_data["payer_tin"] = "123-45-6789"
        form = Form1099INT(**valid_1099int_data)
        assert form.payer_tin == "123-45-6789"


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
        # W2, 1099-INT, 1099-DIV, 1099-NEC, 1098, 1099-R, 1099-G, 1098-T, 5498, 1099-S,
        # K-1, 1099-B, 1095-A, UNKNOWN = 14 types
        assert len(DocumentType) == 14


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


class TestFormK1:
    """Tests for FormK1 model."""

    @pytest.fixture
    def valid_k1_data(self) -> dict:
        """Return valid K-1 data for testing."""
        return {
            "entity_name": "ABC Partnership",
            "entity_ein": "12-3456789",
            "entity_type": "partnership",
            "tax_year": 2024,
            "recipient_name": "John Smith",
            "recipient_tin": "123-45-6789",
            "ownership_percentage": Decimal("25.0"),
        }

    def test_k1_basic_creation(self, valid_k1_data: dict) -> None:
        """K-1 can be created with required fields."""
        k1 = FormK1(**valid_k1_data)
        assert k1.entity_name == "ABC Partnership"
        assert k1.entity_ein == "12-3456789"
        assert k1.entity_type == "partnership"
        assert k1.tax_year == 2024
        assert k1.recipient_name == "John Smith"
        assert k1.ownership_percentage == Decimal("25.0")

    def test_k1_ein_validation(self, valid_k1_data: dict) -> None:
        """K-1 validates entity EIN format."""
        valid_k1_data["entity_ein"] = "123456789"  # Without dash
        k1 = FormK1(**valid_k1_data)
        assert k1.entity_ein == "12-3456789"

    def test_k1_ein_invalid(self, valid_k1_data: dict) -> None:
        """K-1 rejects invalid EIN."""
        valid_k1_data["entity_ein"] = "12345"
        with pytest.raises(ValidationError):
            FormK1(**valid_k1_data)

    def test_k1_recipient_tin_validation(self, valid_k1_data: dict) -> None:
        """K-1 validates recipient TIN format."""
        valid_k1_data["recipient_tin"] = "123456789"  # Without dashes
        k1 = FormK1(**valid_k1_data)
        assert k1.recipient_tin == "123-45-6789"

    def test_k1_default_income_values(self, valid_k1_data: dict) -> None:
        """K-1 income fields default to zero."""
        k1 = FormK1(**valid_k1_data)
        assert k1.ordinary_business_income == Decimal("0")
        assert k1.net_rental_real_estate == Decimal("0")
        assert k1.guaranteed_payments == Decimal("0")
        assert k1.interest_income == Decimal("0")
        assert k1.dividend_income == Decimal("0")
        assert k1.net_short_term_capital_gain == Decimal("0")
        assert k1.net_long_term_capital_gain == Decimal("0")
        assert k1.distributions == Decimal("0")

    def test_k1_entity_types(self, valid_k1_data: dict) -> None:
        """K-1 accepts partnership and s_corp entity types."""
        valid_k1_data["entity_type"] = "partnership"
        k1 = FormK1(**valid_k1_data)
        assert k1.entity_type == "partnership"

        valid_k1_data["entity_type"] = "s_corp"
        k1 = FormK1(**valid_k1_data)
        assert k1.entity_type == "s_corp"

    def test_k1_total_income(self, valid_k1_data: dict) -> None:
        """K-1 total_k1_income property calculates correctly."""
        valid_k1_data["ordinary_business_income"] = Decimal("50000")
        valid_k1_data["interest_income"] = Decimal("1000")
        valid_k1_data["dividend_income"] = Decimal("500")
        k1 = FormK1(**valid_k1_data)
        assert k1.total_k1_income == Decimal("51500")

    def test_k1_requires_basis_escalation_no_loss(self, valid_k1_data: dict) -> None:
        """K-1 with no loss does not require basis escalation."""
        valid_k1_data["ordinary_business_income"] = Decimal("50000")
        k1 = FormK1(**valid_k1_data)
        assert k1.requires_basis_escalation is False

    def test_k1_requires_basis_escalation_small_loss(self, valid_k1_data: dict) -> None:
        """K-1 with small loss (<$10k) does not require basis escalation."""
        valid_k1_data["ordinary_business_income"] = Decimal("-5000")
        k1 = FormK1(**valid_k1_data)
        assert k1.requires_basis_escalation is False

    def test_k1_requires_basis_escalation_large_loss_no_basis(
        self, valid_k1_data: dict
    ) -> None:
        """K-1 with large loss (>$10k) and no capital account requires escalation."""
        valid_k1_data["ordinary_business_income"] = Decimal("-15000")
        k1 = FormK1(**valid_k1_data)
        assert k1.requires_basis_escalation is True

    def test_k1_requires_basis_escalation_large_loss_with_basis(
        self, valid_k1_data: dict
    ) -> None:
        """K-1 with large loss but capital account info does not require escalation."""
        valid_k1_data["ordinary_business_income"] = Decimal("-15000")
        valid_k1_data["capital_account_ending"] = Decimal("50000")
        k1 = FormK1(**valid_k1_data)
        assert k1.requires_basis_escalation is False

    def test_k1_capital_account_fields(self, valid_k1_data: dict) -> None:
        """K-1 capital account fields work correctly."""
        valid_k1_data["capital_account_beginning"] = Decimal("100000")
        valid_k1_data["capital_account_ending"] = Decimal("120000")
        valid_k1_data["current_year_increase"] = Decimal("30000")
        valid_k1_data["current_year_decrease"] = Decimal("10000")
        k1 = FormK1(**valid_k1_data)
        assert k1.capital_account_beginning == Decimal("100000")
        assert k1.capital_account_ending == Decimal("120000")

    def test_k1_debt_basis_fields(self, valid_k1_data: dict) -> None:
        """K-1 debt basis fields work correctly."""
        valid_k1_data["share_of_recourse_liabilities"] = Decimal("25000")
        valid_k1_data["share_of_nonrecourse_liabilities"] = Decimal("75000")
        k1 = FormK1(**valid_k1_data)
        assert k1.share_of_recourse_liabilities == Decimal("25000")
        assert k1.share_of_nonrecourse_liabilities == Decimal("75000")


class TestForm1099B:
    """Tests for Form1099B model."""

    @pytest.fixture
    def valid_1099b_data(self) -> dict:
        """Return valid 1099-B data for testing."""
        return {
            "payer_name": "Fidelity Investments",
            "payer_tin": "12-3456789",
            "recipient_tin": "123-45-6789",
            "description": "AAPL - Apple Inc",
            "date_sold": "2024-06-15",
            "proceeds": Decimal("10000"),
        }

    def test_1099b_basic_creation(self, valid_1099b_data: dict) -> None:
        """1099-B can be created with required fields."""
        form = Form1099B(**valid_1099b_data)
        assert form.payer_name == "Fidelity Investments"
        assert form.description == "AAPL - Apple Inc"
        assert form.proceeds == Decimal("10000")

    def test_1099b_tin_validation(self, valid_1099b_data: dict) -> None:
        """1099-B validates TIN formats."""
        valid_1099b_data["payer_tin"] = "123456789"  # Without dash
        valid_1099b_data["recipient_tin"] = "987654321"  # Without dashes
        form = Form1099B(**valid_1099b_data)
        assert form.payer_tin == "12-3456789"
        assert form.recipient_tin == "987-65-4321"

    def test_1099b_optional_cost_basis(self, valid_1099b_data: dict) -> None:
        """1099-B allows None for cost basis (not reported)."""
        form = Form1099B(**valid_1099b_data)
        assert form.cost_basis is None

    def test_1099b_with_cost_basis(self, valid_1099b_data: dict) -> None:
        """1099-B with cost basis works correctly."""
        valid_1099b_data["cost_basis"] = Decimal("8000")
        form = Form1099B(**valid_1099b_data)
        assert form.cost_basis == Decimal("8000")

    def test_1099b_short_long_term(self, valid_1099b_data: dict) -> None:
        """1099-B tracks short-term vs long-term."""
        valid_1099b_data["is_short_term"] = True
        form = Form1099B(**valid_1099b_data)
        assert form.is_short_term is True
        assert form.is_long_term is False

        valid_1099b_data["is_short_term"] = False
        valid_1099b_data["is_long_term"] = True
        form = Form1099B(**valid_1099b_data)
        assert form.is_short_term is False
        assert form.is_long_term is True

    def test_1099b_basis_reported_to_irs(self, valid_1099b_data: dict) -> None:
        """1099-B basis_reported_to_irs flag works correctly."""
        form = Form1099B(**valid_1099b_data)
        assert form.basis_reported_to_irs is True  # Default

        valid_1099b_data["basis_reported_to_irs"] = False
        form = Form1099B(**valid_1099b_data)
        assert form.basis_reported_to_irs is False

    def test_1099b_requires_basis_escalation_with_basis(
        self, valid_1099b_data: dict
    ) -> None:
        """1099-B with cost basis does not require escalation."""
        valid_1099b_data["cost_basis"] = Decimal("8000")
        form = Form1099B(**valid_1099b_data)
        assert form.requires_basis_escalation is False

    def test_1099b_requires_basis_escalation_no_basis_reported(
        self, valid_1099b_data: dict
    ) -> None:
        """1099-B without cost basis but reported does not require escalation."""
        valid_1099b_data["basis_reported_to_irs"] = True
        form = Form1099B(**valid_1099b_data)
        assert form.requires_basis_escalation is False

    def test_1099b_requires_basis_escalation_no_basis_not_reported(
        self, valid_1099b_data: dict
    ) -> None:
        """1099-B without cost basis and not reported requires escalation."""
        valid_1099b_data["basis_reported_to_irs"] = False
        form = Form1099B(**valid_1099b_data)
        assert form.requires_basis_escalation is True

    def test_1099b_wash_sale(self, valid_1099b_data: dict) -> None:
        """1099-B wash sale field works correctly."""
        valid_1099b_data["wash_sale_loss_disallowed"] = Decimal("500")
        form = Form1099B(**valid_1099b_data)
        assert form.wash_sale_loss_disallowed == Decimal("500")

    def test_1099b_special_types(self, valid_1099b_data: dict) -> None:
        """1099-B special type flags work correctly."""
        valid_1099b_data["is_collectibles"] = True
        valid_1099b_data["is_qof"] = True
        form = Form1099B(**valid_1099b_data)
        assert form.is_collectibles is True
        assert form.is_qof is True


class TestForm1099BSummary:
    """Tests for Form1099BSummary model."""

    @pytest.fixture
    def valid_summary_data(self) -> dict:
        """Return valid 1099-B summary data for testing."""
        return {
            "payer_name": "Fidelity Investments",
            "payer_tin": "12-3456789",
            "recipient_tin": "123-45-6789",
        }

    def test_summary_basic_creation(self, valid_summary_data: dict) -> None:
        """Summary can be created with required fields."""
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.payer_name == "Fidelity Investments"

    def test_summary_category_a_fields(self, valid_summary_data: dict) -> None:
        """Summary Category A fields work correctly."""
        valid_summary_data["cat_a_proceeds"] = Decimal("50000")
        valid_summary_data["cat_a_cost_basis"] = Decimal("45000")
        valid_summary_data["cat_a_gain_loss"] = Decimal("5000")
        valid_summary_data["cat_a_transaction_count"] = 75
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.cat_a_proceeds == Decimal("50000")
        assert summary.cat_a_gain_loss == Decimal("5000")
        assert summary.cat_a_transaction_count == 75

    def test_summary_category_d_fields(self, valid_summary_data: dict) -> None:
        """Summary Category D fields work correctly."""
        valid_summary_data["cat_d_proceeds"] = Decimal("100000")
        valid_summary_data["cat_d_cost_basis"] = Decimal("80000")
        valid_summary_data["cat_d_gain_loss"] = Decimal("20000")
        valid_summary_data["cat_d_transaction_count"] = 120
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.cat_d_proceeds == Decimal("100000")
        assert summary.cat_d_gain_loss == Decimal("20000")
        assert summary.cat_d_transaction_count == 120

    def test_summary_has_missing_basis_false(self, valid_summary_data: dict) -> None:
        """Summary has_missing_basis is False when no B/E transactions."""
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.has_missing_basis is False

    def test_summary_has_missing_basis_true_cat_b(
        self, valid_summary_data: dict
    ) -> None:
        """Summary has_missing_basis is True when Cat B has no basis."""
        valid_summary_data["cat_b_transaction_count"] = 10
        valid_summary_data["cat_b_proceeds"] = Decimal("5000")
        # cat_b_cost_basis is None by default
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.has_missing_basis is True

    def test_summary_has_missing_basis_false_with_basis(
        self, valid_summary_data: dict
    ) -> None:
        """Summary has_missing_basis is False when Cat B has basis."""
        valid_summary_data["cat_b_transaction_count"] = 10
        valid_summary_data["cat_b_proceeds"] = Decimal("5000")
        valid_summary_data["cat_b_cost_basis"] = Decimal("4000")
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.has_missing_basis is False

    def test_summary_total_short_term_gain_loss(
        self, valid_summary_data: dict
    ) -> None:
        """Summary total_short_term_gain_loss calculates correctly."""
        valid_summary_data["cat_a_gain_loss"] = Decimal("5000")
        valid_summary_data["cat_b_proceeds"] = Decimal("10000")
        valid_summary_data["cat_b_cost_basis"] = Decimal("8000")
        valid_summary_data["cat_b_transaction_count"] = 5
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.total_short_term_gain_loss == Decimal("7000")

    def test_summary_total_long_term_gain_loss(self, valid_summary_data: dict) -> None:
        """Summary total_long_term_gain_loss calculates correctly."""
        valid_summary_data["cat_d_gain_loss"] = Decimal("20000")
        valid_summary_data["cat_e_proceeds"] = Decimal("15000")
        valid_summary_data["cat_e_cost_basis"] = Decimal("10000")
        valid_summary_data["cat_e_transaction_count"] = 3
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.total_long_term_gain_loss == Decimal("25000")

    def test_summary_total_transaction_count(self, valid_summary_data: dict) -> None:
        """Summary total_transaction_count tracks all categories."""
        valid_summary_data["cat_a_transaction_count"] = 50
        valid_summary_data["cat_d_transaction_count"] = 100
        valid_summary_data["total_transaction_count"] = 150
        summary = Form1099BSummary(**valid_summary_data)
        assert summary.total_transaction_count == 150


class TestForm1095A:
    """Tests for Form1095A model."""

    @pytest.fixture
    def valid_1095a_data(self) -> dict:
        """Return valid 1095-A data for testing."""
        return {
            "recipient_name": "John Smith",
            "recipient_tin": "123-45-6789",
        }

    def test_1095a_basic_creation(self, valid_1095a_data: dict) -> None:
        """1095-A can be created with required fields."""
        form = Form1095A(**valid_1095a_data)
        assert form.recipient_name == "John Smith"
        assert form.recipient_tin == "123-45-6789"

    def test_1095a_tin_validation(self, valid_1095a_data: dict) -> None:
        """1095-A validates TIN format."""
        valid_1095a_data["recipient_tin"] = "123456789"  # Without dashes
        form = Form1095A(**valid_1095a_data)
        assert form.recipient_tin == "123-45-6789"

    def test_1095a_monthly_data_defaults(self, valid_1095a_data: dict) -> None:
        """1095-A monthly data lists default to 12 zeros."""
        form = Form1095A(**valid_1095a_data)
        assert len(form.monthly_enrollment_premium) == 12
        assert len(form.monthly_slcsp_premium) == 12
        assert len(form.monthly_advance_ptc) == 12
        assert all(p == Decimal("0") for p in form.monthly_enrollment_premium)

    def test_1095a_with_monthly_data(self, valid_1095a_data: dict) -> None:
        """1095-A with monthly data works correctly."""
        monthly_premiums = [Decimal("400")] * 12
        monthly_slcsp = [Decimal("500")] * 12
        monthly_aptc = [Decimal("300")] * 12
        valid_1095a_data["monthly_enrollment_premium"] = monthly_premiums
        valid_1095a_data["monthly_slcsp_premium"] = monthly_slcsp
        valid_1095a_data["monthly_advance_ptc"] = monthly_aptc
        form = Form1095A(**valid_1095a_data)
        assert form.monthly_enrollment_premium[0] == Decimal("400")
        assert form.monthly_slcsp_premium[5] == Decimal("500")
        assert form.monthly_advance_ptc[11] == Decimal("300")

    def test_1095a_annual_totals(self, valid_1095a_data: dict) -> None:
        """1095-A annual totals work correctly."""
        valid_1095a_data["annual_enrollment_premium"] = Decimal("4800")
        valid_1095a_data["annual_slcsp_premium"] = Decimal("6000")
        valid_1095a_data["annual_advance_ptc"] = Decimal("3600")
        form = Form1095A(**valid_1095a_data)
        assert form.annual_enrollment_premium == Decimal("4800")
        assert form.annual_slcsp_premium == Decimal("6000")
        assert form.annual_advance_ptc == Decimal("3600")
