"""Tests for document extraction module.

Tests cover:
- Mock mode extraction for all document types
- Document type routing via extract_document()
- Validation of mock data structure and realistic values
- Prompt content verification
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.documents.extractor import (
    Form1099BExtraction,
    extract_1095_a,
    extract_1098,
    extract_1098_t,
    extract_1099_b,
    extract_1099_b_summary,
    extract_1099_div,
    extract_1099_g,
    extract_1099_int,
    extract_1099_nec,
    extract_1099_r,
    extract_1099_s,
    extract_5498,
    extract_document,
    extract_k1,
    extract_w2,
)
from src.documents.models import (
    Box12Code,
    ConfidenceLevel,
    DocumentType,
    Form1095A,
    Form1098,
    Form1098T,
    Form1099B,
    Form1099BSummary,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Form1099S,
    Form5498,
    FormK1,
    W2Batch,
    W2Data,
)
from src.documents.prompts import (
    FORM_1095_A_PROMPT,
    FORM_1098_PROMPT,
    FORM_1098_T_PROMPT,
    FORM_1099_B_PROMPT,
    FORM_1099_B_SUMMARY_PROMPT,
    FORM_1099_DIV_PROMPT,
    FORM_1099_G_PROMPT,
    FORM_1099_INT_PROMPT,
    FORM_1099_NEC_PROMPT,
    FORM_1099_R_PROMPT,
    FORM_1099_S_PROMPT,
    FORM_5498_PROMPT,
    FORM_K1_PROMPT,
    W2_MULTI_EXTRACTION_PROMPT,
    W2_EXTRACTION_PROMPT,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def stub_extract_with_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub vision extraction for unit tests."""
    sample_w2 = W2Data(
        employee_ssn="123-45-6789",
        employer_ein="12-3456789",
        employer_name="Acme Corporation",
        employee_name="John Q. Taxpayer",
        wages_tips_compensation=Decimal("75000.00"),
        federal_tax_withheld=Decimal("12500.00"),
        social_security_wages=Decimal("75000.00"),
        social_security_tax=Decimal("4650.00"),
        medicare_wages=Decimal("75000.00"),
        medicare_tax=Decimal("1087.50"),
        box_12_codes=[
            Box12Code(code="D", amount=Decimal("5000.00")),
            Box12Code(code="DD", amount=Decimal("8500.00")),
        ],
        statutory_employee=False,
        retirement_plan=True,
        third_party_sick_pay=False,
        state_wages=Decimal("75000.00"),
        state_tax_withheld=Decimal("3750.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_int = Form1099INT(
        payer_name="First National Bank",
        payer_tin="98-7654321",
        recipient_tin="123-45-6789",
        interest_income=Decimal("1250.75"),
        early_withdrawal_penalty=Decimal("0"),
        interest_us_savings_bonds=Decimal("125.00"),
        federal_tax_withheld=Decimal("0"),
        investment_expenses=Decimal("0"),
        foreign_tax_paid=Decimal("0"),
        tax_exempt_interest=Decimal("0"),
        private_activity_bond_interest=Decimal("0"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_div = Form1099DIV(
        payer_name="Vanguard Brokerage Services",
        payer_tin="23-1234567",
        recipient_tin="123-45-6789",
        total_ordinary_dividends=Decimal("3500.00"),
        qualified_dividends=Decimal("2800.00"),
        total_capital_gain_distributions=Decimal("500.00"),
        unrecaptured_1250_gain=Decimal("0"),
        section_1202_gain=Decimal("0"),
        collectibles_gain=Decimal("0"),
        nondividend_distributions=Decimal("0"),
        federal_tax_withheld=Decimal("0"),
        section_199a_dividends=Decimal("350.00"),
        foreign_tax_paid=Decimal("25.00"),
        exempt_interest_dividends=Decimal("0"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_nec = Form1099NEC(
        payer_name="Tech Consulting LLC",
        payer_tin="45-6789012",
        recipient_name="Jane Contractor",
        recipient_tin="987-65-4321",
        nonemployee_compensation=Decimal("25000.00"),
        direct_sales=False,
        federal_tax_withheld=Decimal("0"),
        state_tax_withheld=Decimal("0"),
        confidence=ConfidenceLevel.MEDIUM,
        uncertain_fields=["state_tax_withheld"],
    )
    sample_1098 = Form1098(
        lender_name="ABC Mortgage Co",
        lender_tin="11-1111111",
        borrower_name="John Homeowner",
        borrower_tin="123-45-6789",
        mortgage_interest=Decimal("12500.00"),
        points_paid=Decimal("500.00"),
        mortgage_insurance_premiums=Decimal("1200.00"),
        property_taxes_paid=Decimal("4500.00"),
        outstanding_mortgage_principal=Decimal("250000.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_r = Form1099R(
        payer_name="Fidelity Investments",
        payer_tin="04-3523567",
        recipient_name="Retired Worker",
        recipient_tin="123-45-6789",
        gross_distribution=Decimal("15000.00"),
        taxable_amount=Decimal("15000.00"),
        distribution_code="7",
        ira_sep_simple=True,
        federal_tax_withheld=Decimal("2250.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_g = Form1099G(
        payer_name="State of California",
        payer_tin="94-6000574",
        recipient_name="John Taxpayer",
        recipient_tin="123-45-6789",
        unemployment_compensation=Decimal("8500.00"),
        state_local_tax_refund=Decimal("1200.00"),
        federal_tax_withheld=Decimal("850.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1098_t = Form1098T(
        institution_name="State University",
        institution_tin="12-3456789",
        student_name="Student Name",
        student_tin="123-45-6789",
        payments_received=Decimal("15000.00"),
        scholarships_grants=Decimal("5000.00"),
        at_least_half_time=True,
        graduate_student=False,
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_5498 = Form5498(
        trustee_name="Vanguard",
        trustee_tin="23-1234567",
        participant_name="IRA Owner",
        participant_tin="123-45-6789",
        ira_contributions=Decimal("6500.00"),
        roth_ira_contributions=Decimal("0.00"),
        rollover_contributions=Decimal("0.00"),
        fair_market_value=Decimal("150000.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_s = Form1099S(
        filer_name="Title Company LLC",
        filer_tin="55-5555555",
        transferor_name="Home Seller",
        transferor_tin="123-45-6789",
        closing_date="2024-06-15",
        gross_proceeds=Decimal("450000.00"),
        property_address="123 Main St, Anytown, CA 90210",
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_k1 = FormK1(
        entity_name="Demo Partnership LLC",
        entity_ein="12-3456789",
        entity_type="partnership",
        tax_year=2024,
        recipient_name="John Q. Taxpayer",
        recipient_tin="123-45-6789",
        ownership_percentage=Decimal("25.0"),
        ordinary_business_income=Decimal("45000.00"),
        guaranteed_payments=Decimal("12000.00"),
        interest_income=Decimal("500.00"),
        dividend_income=Decimal("1200.00"),
        net_long_term_capital_gain=Decimal("3500.00"),
        distributions=Decimal("15000.00"),
        self_employment_earnings=Decimal("57000.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1099_b_list = [
        Form1099B(
            payer_name="Fidelity Investments",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            account_number="X12345",
            description="AAPL - Apple Inc (100 shares)",
            date_acquired="2023-01-15",
            date_sold="2024-06-20",
            proceeds=Decimal("19500.00"),
            cost_basis=Decimal("15000.00"),
            is_long_term=True,
            basis_reported_to_irs=True,
            confidence=ConfidenceLevel.HIGH,
            uncertain_fields=[],
        ),
        Form1099B(
            payer_name="Fidelity Investments",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            account_number="X12345",
            description="MSFT - Microsoft Corp (50 shares)",
            date_acquired="2024-03-01",
            date_sold="2024-09-15",
            proceeds=Decimal("21000.00"),
            cost_basis=Decimal("18500.00"),
            is_short_term=True,
            basis_reported_to_irs=True,
            confidence=ConfidenceLevel.HIGH,
            uncertain_fields=[],
        ),
    ]
    sample_1099_b_summary = Form1099BSummary(
        payer_name="Fidelity Investments",
        payer_tin="12-3456789",
        recipient_tin="123-45-6789",
        cat_a_proceeds=Decimal("150000.00"),
        cat_a_cost_basis=Decimal("125000.00"),
        cat_a_adjustments=Decimal("500.00"),
        cat_a_gain_loss=Decimal("24500.00"),
        cat_a_transaction_count=75,
        cat_d_proceeds=Decimal("200000.00"),
        cat_d_cost_basis=Decimal("150000.00"),
        cat_d_adjustments=Decimal("0.00"),
        cat_d_gain_loss=Decimal("50000.00"),
        cat_d_transaction_count=50,
        total_wash_sale_disallowed=Decimal("500.00"),
        total_transaction_count=125,
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )
    sample_1095_a = Form1095A(
        marketplace_name="Covered California",
        marketplace_id="CA123456",
        policy_number="POL-2024-001",
        policy_start_date="2024-01-01",
        policy_end_date="2024-12-31",
        recipient_name="John Q. Taxpayer",
        recipient_tin="123-45-6789",
        recipient_address="123 Main St, Anytown, CA 90210",
        covered_individuals=2,
        annual_monthly_premium=Decimal("1200.00"),
        annual_slcsp_premium=Decimal("1400.00"),
        annual_advance_ptc=Decimal("400.00"),
        confidence=ConfidenceLevel.HIGH,
        uncertain_fields=[],
    )

    async def fake_extract_with_vision(*, response_model, **kwargs):
        if response_model is W2Batch:
            return W2Batch(forms=[sample_w2])
        if response_model is Form1099INT:
            return sample_1099_int
        if response_model is Form1099DIV:
            return sample_1099_div
        if response_model is Form1099NEC:
            return sample_1099_nec
        if response_model is Form1098:
            return sample_1098
        if response_model is Form1099R:
            return sample_1099_r
        if response_model is Form1099G:
            return sample_1099_g
        if response_model is Form1098T:
            return sample_1098_t
        if response_model is Form5498:
            return sample_5498
        if response_model is Form1099S:
            return sample_1099_s
        if response_model is FormK1:
            return sample_k1
        if response_model is Form1099BExtraction:
            return Form1099BExtraction(transactions=sample_1099_b_list)
        if response_model is Form1099BSummary:
            return sample_1099_b_summary
        if response_model is Form1095A:
            return sample_1095_a
        raise AssertionError(f"Unexpected response_model: {response_model}")

    monkeypatch.setattr(
        "src.documents.extractor._extract_with_vision",
        fake_extract_with_vision,
    )


@pytest.fixture
def fake_image_bytes() -> bytes:
    """Return fake image bytes for testing."""
    return b"fake image data for testing"


# =============================================================================
# W-2 Extraction Tests
# =============================================================================


class TestExtractW2:
    """Tests for W-2 extraction."""

    @pytest.mark.asyncio
    async def test_returns_w2_data(self, fake_image_bytes: bytes) -> None:
        """extract_w2 returns W2Data instance."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        assert isinstance(result, W2Batch)
        assert isinstance(result.forms[0], W2Data)

    @pytest.mark.asyncio
    async def test_w2_has_required_identity_fields(self, fake_image_bytes: bytes) -> None:
        """W2Data has all required identity fields populated."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        w2 = result.forms[0]
        assert w2.employee_ssn  # Non-empty
        assert w2.employer_ein
        assert w2.employer_name
        assert w2.employee_name

    @pytest.mark.asyncio
    async def test_w2_has_required_compensation_fields(self, fake_image_bytes: bytes) -> None:
        """W2Data has all required compensation fields."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        w2 = result.forms[0]
        assert w2.wages_tips_compensation >= Decimal("0")
        assert w2.federal_tax_withheld >= Decimal("0")
        assert w2.social_security_wages >= Decimal("0")
        assert w2.social_security_tax >= Decimal("0")
        assert w2.medicare_wages >= Decimal("0")
        assert w2.medicare_tax >= Decimal("0")

    @pytest.mark.asyncio
    async def test_w2_ssn_properly_formatted(self, fake_image_bytes: bytes) -> None:
        """SSN is formatted as XXX-XX-XXXX."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        import re

        w2 = result.forms[0]
        assert re.match(r"^\d{3}-\d{2}-\d{4}$", w2.employee_ssn)

    @pytest.mark.asyncio
    async def test_w2_ein_properly_formatted(self, fake_image_bytes: bytes) -> None:
        """EIN is formatted as XX-XXXXXXX."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        import re

        w2 = result.forms[0]
        assert re.match(r"^\d{2}-\d{7}$", w2.employer_ein)

    @pytest.mark.asyncio
    async def test_w2_has_confidence(self, fake_image_bytes: bytes) -> None:
        """W2Data includes confidence level."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        w2 = result.forms[0]
        assert w2.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_w2_box_12_codes(self, fake_image_bytes: bytes) -> None:
        """W2Data can contain Box 12 codes."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        w2 = result.forms[0]
        # Mock data has box 12 codes
        assert isinstance(w2.box_12_codes, list)
        if w2.box_12_codes:
            code = w2.box_12_codes[0]
            assert hasattr(code, "code")
            assert hasattr(code, "amount")


# =============================================================================
# 1099-INT Extraction Tests
# =============================================================================


class TestExtract1099Int:
    """Tests for 1099-INT extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099int(self, fake_image_bytes: bytes) -> None:
        """extract_1099_int returns Form1099INT instance."""
        result = await extract_1099_int(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099INT)

    @pytest.mark.asyncio
    async def test_1099_int_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099INT has all required fields populated."""
        result = await extract_1099_int(fake_image_bytes, "image/jpeg")
        assert result.payer_name
        assert result.payer_tin
        assert result.recipient_tin
        assert result.interest_income >= Decimal("0")

    @pytest.mark.asyncio
    async def test_1099_int_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Form1099INT includes confidence level."""
        result = await extract_1099_int(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_1099_int_realistic_values(self, fake_image_bytes: bytes) -> None:
        """Mock data has realistic interest income values."""
        result = await extract_1099_int(fake_image_bytes, "image/jpeg")
        # Interest income should be positive and reasonable
        assert result.interest_income > Decimal("0")
        assert result.interest_income < Decimal("1000000")  # Less than $1M


# =============================================================================
# 1099-DIV Extraction Tests
# =============================================================================


class TestExtract1099Div:
    """Tests for 1099-DIV extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099div(self, fake_image_bytes: bytes) -> None:
        """extract_1099_div returns Form1099DIV instance."""
        result = await extract_1099_div(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099DIV)

    @pytest.mark.asyncio
    async def test_1099_div_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099DIV has all required fields populated."""
        result = await extract_1099_div(fake_image_bytes, "image/jpeg")
        assert result.payer_name
        assert result.payer_tin
        assert result.recipient_tin
        assert result.total_ordinary_dividends >= Decimal("0")

    @pytest.mark.asyncio
    async def test_1099_div_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Form1099DIV includes confidence level."""
        result = await extract_1099_div(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_1099_div_qualified_less_than_total(self, fake_image_bytes: bytes) -> None:
        """Qualified dividends should not exceed total ordinary dividends."""
        result = await extract_1099_div(fake_image_bytes, "image/jpeg")
        assert result.qualified_dividends <= result.total_ordinary_dividends


# =============================================================================
# 1099-NEC Extraction Tests
# =============================================================================


class TestExtract1099Nec:
    """Tests for 1099-NEC extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099nec(self, fake_image_bytes: bytes) -> None:
        """extract_1099_nec returns Form1099NEC instance."""
        result = await extract_1099_nec(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099NEC)

    @pytest.mark.asyncio
    async def test_1099_nec_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099NEC has all required fields populated."""
        result = await extract_1099_nec(fake_image_bytes, "image/jpeg")
        assert result.payer_name
        assert result.payer_tin
        assert result.recipient_name
        assert result.recipient_tin
        assert result.nonemployee_compensation >= Decimal("0")

    @pytest.mark.asyncio
    async def test_1099_nec_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Form1099NEC includes confidence level."""
        result = await extract_1099_nec(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_1099_nec_direct_sales_is_bool(self, fake_image_bytes: bytes) -> None:
        """Direct sales field is a boolean."""
        result = await extract_1099_nec(fake_image_bytes, "image/jpeg")
        assert isinstance(result.direct_sales, bool)


# =============================================================================
# Document Router Tests
# =============================================================================


class TestExtractDocument:
    """Tests for the extract_document router function."""

    @pytest.mark.asyncio
    async def test_routes_to_w2(self, fake_image_bytes: bytes) -> None:
        """extract_document routes W2 to extract_w2."""
        result = await extract_document(fake_image_bytes, DocumentType.W2, "image/jpeg")
        assert isinstance(result, W2Batch)
        assert isinstance(result.forms[0], W2Data)

    @pytest.mark.asyncio
    async def test_routes_to_1099_int(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-INT to extract_1099_int."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_INT, "image/jpeg")
        assert isinstance(result, Form1099INT)

    @pytest.mark.asyncio
    async def test_routes_to_1099_div(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-DIV to extract_1099_div."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_DIV, "image/jpeg")
        assert isinstance(result, Form1099DIV)

    @pytest.mark.asyncio
    async def test_routes_to_1099_nec(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-NEC to extract_1099_nec."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_NEC, "image/jpeg")
        assert isinstance(result, Form1099NEC)

    @pytest.mark.asyncio
    async def test_raises_for_unknown_type(self, fake_image_bytes: bytes) -> None:
        """extract_document raises ValueError for UNKNOWN type."""
        with pytest.raises(ValueError, match="Cannot extract data from UNKNOWN"):
            await extract_document(fake_image_bytes, DocumentType.UNKNOWN, "image/jpeg")


# =============================================================================
# Prompt Tests
# =============================================================================


class TestPrompts:
    """Tests for extraction prompts."""

    def test_w2_prompt_mentions_critical_boxes(self) -> None:
        """W2 prompt mentions all critical boxes."""
        assert "Box 1" in W2_EXTRACTION_PROMPT
        assert "Box 2" in W2_EXTRACTION_PROMPT
        assert "Social Security" in W2_EXTRACTION_PROMPT
        assert "Medicare" in W2_EXTRACTION_PROMPT
        assert "SSN" in W2_EXTRACTION_PROMPT or "Social Security Number" in W2_EXTRACTION_PROMPT
        assert "EIN" in W2_EXTRACTION_PROMPT or "Employer Identification Number" in W2_EXTRACTION_PROMPT

    def test_w2_multi_prompt_mentions_multiple_forms(self) -> None:
        """Multi W-2 prompt requires extracting all forms."""
        assert "Extract ALL W-2 forms" in W2_MULTI_EXTRACTION_PROMPT
        assert "multiple" in W2_MULTI_EXTRACTION_PROMPT.lower()

    def test_1099_int_prompt_mentions_interest(self) -> None:
        """1099-INT prompt mentions interest income."""
        assert "interest" in FORM_1099_INT_PROMPT.lower()
        assert "Box 1" in FORM_1099_INT_PROMPT

    def test_1099_div_prompt_mentions_dividends(self) -> None:
        """1099-DIV prompt mentions dividends."""
        assert "dividend" in FORM_1099_DIV_PROMPT.lower()
        assert "Box 1a" in FORM_1099_DIV_PROMPT
        assert "qualified" in FORM_1099_DIV_PROMPT.lower()

    def test_1099_nec_prompt_mentions_nonemployee(self) -> None:
        """1099-NEC prompt mentions nonemployee compensation."""
        assert "nonemployee" in FORM_1099_NEC_PROMPT.lower()
        assert "Box 1" in FORM_1099_NEC_PROMPT

    def test_all_prompts_request_confidence(self) -> None:
        """All prompts request confidence assessment."""
        for prompt in [W2_EXTRACTION_PROMPT, FORM_1099_INT_PROMPT, FORM_1099_DIV_PROMPT, FORM_1099_NEC_PROMPT]:
            assert "confidence" in prompt.lower() or "CONFIDENCE" in prompt

    def test_all_prompts_mention_high_medium_low(self) -> None:
        """All prompts specify HIGH/MEDIUM/LOW confidence levels."""
        for prompt in [W2_EXTRACTION_PROMPT, FORM_1099_INT_PROMPT, FORM_1099_DIV_PROMPT, FORM_1099_NEC_PROMPT]:
            assert "HIGH" in prompt
            assert "MEDIUM" in prompt
            assert "LOW" in prompt


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_w2_uncertain_fields_is_list(self, fake_image_bytes: bytes) -> None:
        """uncertain_fields is always a list."""
        result = await extract_w2(fake_image_bytes, "image/jpeg")
        w2 = result.forms[0]
        assert isinstance(w2.uncertain_fields, list)

    @pytest.mark.asyncio
    async def test_empty_bytes_still_works(self) -> None:
        """Empty bytes still return a W-2 batch."""
        result = await extract_w2(b"", "image/jpeg")
        assert isinstance(result, W2Batch)

    @pytest.mark.asyncio
    async def test_different_media_types_work(self) -> None:
        """Different media types work for W-2 extraction."""
        for media_type in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
            result = await extract_w2(b"test", media_type)
            assert isinstance(result, W2Batch)


# =============================================================================
# New Form Extraction Tests
# =============================================================================


class TestExtract1098:
    """Tests for Form 1098 extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1098(self, fake_image_bytes: bytes) -> None:
        """extract_1098 returns Form1098 instance."""
        result = await extract_1098(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1098)

    @pytest.mark.asyncio
    async def test_1098_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1098 has all required fields populated."""
        result = await extract_1098(fake_image_bytes, "image/jpeg")
        assert result.lender_name
        assert result.lender_tin
        assert result.borrower_name
        assert result.borrower_tin
        assert result.mortgage_interest >= Decimal("0")

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1098(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1098 to extract_1098."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1098, "image/jpeg")
        assert isinstance(result, Form1098)


class TestExtract1099R:
    """Tests for Form 1099-R extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099r(self, fake_image_bytes: bytes) -> None:
        """extract_1099_r returns Form1099R instance."""
        result = await extract_1099_r(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099R)

    @pytest.mark.asyncio
    async def test_1099_r_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099R has all required fields populated."""
        result = await extract_1099_r(fake_image_bytes, "image/jpeg")
        assert result.payer_name
        assert result.payer_tin
        assert result.recipient_name
        assert result.recipient_tin
        assert result.gross_distribution >= Decimal("0")
        assert result.distribution_code

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1099_r(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-R to extract_1099_r."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_R, "image/jpeg")
        assert isinstance(result, Form1099R)


class TestExtract1099G:
    """Tests for Form 1099-G extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099g(self, fake_image_bytes: bytes) -> None:
        """extract_1099_g returns Form1099G instance."""
        result = await extract_1099_g(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099G)

    @pytest.mark.asyncio
    async def test_1099_g_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099G has all required fields populated."""
        result = await extract_1099_g(fake_image_bytes, "image/jpeg")
        assert result.payer_name
        assert result.payer_tin
        assert result.recipient_name
        assert result.recipient_tin

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1099_g(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-G to extract_1099_g."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_G, "image/jpeg")
        assert isinstance(result, Form1099G)


class TestExtract1098T:
    """Tests for Form 1098-T extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1098t(self, fake_image_bytes: bytes) -> None:
        """extract_1098_t returns Form1098T instance."""
        result = await extract_1098_t(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1098T)

    @pytest.mark.asyncio
    async def test_1098_t_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1098T has all required fields populated."""
        result = await extract_1098_t(fake_image_bytes, "image/jpeg")
        assert result.institution_name
        assert result.institution_tin
        assert result.student_name
        assert result.student_tin

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1098_t(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1098-T to extract_1098_t."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1098_T, "image/jpeg")
        assert isinstance(result, Form1098T)


class TestExtract5498:
    """Tests for Form 5498 extraction."""

    @pytest.mark.asyncio
    async def test_returns_form5498(self, fake_image_bytes: bytes) -> None:
        """extract_5498 returns Form5498 instance."""
        result = await extract_5498(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form5498)

    @pytest.mark.asyncio
    async def test_5498_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form5498 has all required fields populated."""
        result = await extract_5498(fake_image_bytes, "image/jpeg")
        assert result.trustee_name
        assert result.trustee_tin
        assert result.participant_name
        assert result.participant_tin

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_5498(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 5498 to extract_5498."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_5498, "image/jpeg")
        assert isinstance(result, Form5498)


class TestExtract1099S:
    """Tests for Form 1099-S extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099s(self, fake_image_bytes: bytes) -> None:
        """extract_1099_s returns Form1099S instance."""
        result = await extract_1099_s(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099S)

    @pytest.mark.asyncio
    async def test_1099_s_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1099S has all required fields populated."""
        result = await extract_1099_s(fake_image_bytes, "image/jpeg")
        assert result.filer_name
        assert result.filer_tin
        assert result.transferor_name
        assert result.transferor_tin
        assert result.gross_proceeds >= Decimal("0")
        assert result.closing_date
        assert result.property_address

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1099_s(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-S to extract_1099_s."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_S, "image/jpeg")
        assert isinstance(result, Form1099S)


# =============================================================================
# K-1 Extraction Tests
# =============================================================================


class TestExtractK1:
    """Tests for Schedule K-1 extraction."""

    @pytest.mark.asyncio
    async def test_returns_formk1(self, fake_image_bytes: bytes) -> None:
        """extract_k1 returns FormK1 instance."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        assert isinstance(result, FormK1)

    @pytest.mark.asyncio
    async def test_k1_has_required_entity_fields(self, fake_image_bytes: bytes) -> None:
        """FormK1 has all required entity fields populated."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        assert result.entity_name
        assert result.entity_ein
        assert result.entity_type in ["partnership", "s_corp"]
        assert result.tax_year >= 2020

    @pytest.mark.asyncio
    async def test_k1_has_required_recipient_fields(self, fake_image_bytes: bytes) -> None:
        """FormK1 has all required recipient fields populated."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        assert result.recipient_name
        assert result.recipient_tin

    @pytest.mark.asyncio
    async def test_k1_has_confidence(self, fake_image_bytes: bytes) -> None:
        """FormK1 includes confidence level."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_k1_ownership_percentage_valid(self, fake_image_bytes: bytes) -> None:
        """K-1 ownership percentage is between 0 and 100."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        assert Decimal("0") <= result.ownership_percentage <= Decimal("100")

    @pytest.mark.asyncio
    async def test_k1_income_fields(self, fake_image_bytes: bytes) -> None:
        """K-1 has income fields populated."""
        result = await extract_k1(fake_image_bytes, "image/jpeg")
        # At least ordinary business income should be present
        assert result.ordinary_business_income is not None

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_k1(self, fake_image_bytes: bytes) -> None:
        """extract_document routes K-1 to extract_k1."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_K1, "image/jpeg")
        assert isinstance(result, FormK1)


# =============================================================================
# 1099-B Extraction Tests
# =============================================================================


class TestExtract1099B:
    """Tests for Form 1099-B extraction."""

    @pytest.mark.asyncio
    async def test_returns_list_of_form1099b(self, fake_image_bytes: bytes) -> None:
        """extract_1099_b returns list of Form1099B instances."""
        result = await extract_1099_b(fake_image_bytes, "image/jpeg")
        assert isinstance(result, list)
        assert len(result) >= 1
        assert all(isinstance(t, Form1099B) for t in result)

    @pytest.mark.asyncio
    async def test_1099_b_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Each Form1099B has required fields populated."""
        result = await extract_1099_b(fake_image_bytes, "image/jpeg")
        for txn in result:
            assert txn.payer_name
            assert txn.description
            assert txn.date_sold
            assert txn.proceeds > Decimal("0")

    @pytest.mark.asyncio
    async def test_1099_b_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Each Form1099B includes confidence level."""
        result = await extract_1099_b(fake_image_bytes, "image/jpeg")
        for txn in result:
            assert txn.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_1099_b_term_classification(self, fake_image_bytes: bytes) -> None:
        """1099-B transactions have valid short/long term classification."""
        result = await extract_1099_b(fake_image_bytes, "image/jpeg")
        for txn in result:
            # Can't be both short-term and long-term
            assert not (txn.is_short_term and txn.is_long_term)

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1099_b(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1099-B to extract_1099_b."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1099_B, "image/jpeg")
        assert isinstance(result, list)
        assert all(isinstance(t, Form1099B) for t in result)


# =============================================================================
# 1099-B Summary Extraction Tests
# =============================================================================


class TestExtract1099BSummary:
    """Tests for Form 1099-B summary extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1099bsummary(self, fake_image_bytes: bytes) -> None:
        """extract_1099_b_summary returns Form1099BSummary instance."""
        result = await extract_1099_b_summary(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1099BSummary)

    @pytest.mark.asyncio
    async def test_1099_b_summary_has_category_totals(self, fake_image_bytes: bytes) -> None:
        """Form1099BSummary has category totals for Form 8949."""
        result = await extract_1099_b_summary(fake_image_bytes, "image/jpeg")
        # Should have at least one category populated
        has_cat_a = result.cat_a_proceeds is not None
        has_cat_d = result.cat_d_proceeds is not None
        assert has_cat_a or has_cat_d

    @pytest.mark.asyncio
    async def test_1099_b_summary_has_total_count(self, fake_image_bytes: bytes) -> None:
        """Form1099BSummary has total transaction count."""
        result = await extract_1099_b_summary(fake_image_bytes, "image/jpeg")
        assert result.total_transaction_count > 0

    @pytest.mark.asyncio
    async def test_1099_b_summary_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Form1099BSummary includes confidence level."""
        result = await extract_1099_b_summary(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]


# =============================================================================
# 1095-A Extraction Tests
# =============================================================================


class TestExtract1095A:
    """Tests for Form 1095-A extraction."""

    @pytest.mark.asyncio
    async def test_returns_form1095a(self, fake_image_bytes: bytes) -> None:
        """extract_1095_a returns Form1095A instance."""
        result = await extract_1095_a(fake_image_bytes, "image/jpeg")
        assert isinstance(result, Form1095A)

    @pytest.mark.asyncio
    async def test_1095_a_has_required_fields(self, fake_image_bytes: bytes) -> None:
        """Form1095A has all required fields populated."""
        result = await extract_1095_a(fake_image_bytes, "image/jpeg")
        assert result.recipient_name
        assert result.recipient_tin
        assert result.policy_number

    @pytest.mark.asyncio
    async def test_1095_a_has_premium_data(self, fake_image_bytes: bytes) -> None:
        """Form1095A has premium and credit data for Form 8962."""
        result = await extract_1095_a(fake_image_bytes, "image/jpeg")
        assert result.annual_slcsp_premium is not None
        assert result.annual_advance_ptc is not None

    @pytest.mark.asyncio
    async def test_1095_a_has_confidence(self, fake_image_bytes: bytes) -> None:
        """Form1095A includes confidence level."""
        result = await extract_1095_a(fake_image_bytes, "image/jpeg")
        assert result.confidence in [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW]

    @pytest.mark.asyncio
    async def test_extract_document_routes_to_1095_a(self, fake_image_bytes: bytes) -> None:
        """extract_document routes 1095-A to extract_1095_a."""
        result = await extract_document(fake_image_bytes, DocumentType.FORM_1095_A, "image/jpeg")
        assert isinstance(result, Form1095A)


# =============================================================================
# K-1, 1099-B, 1095-A Prompt Tests
# =============================================================================


class TestNewFormPrompts:
    """Tests for K-1, 1099-B, and 1095-A extraction prompts."""

    def test_k1_prompt_mentions_critical_boxes(self) -> None:
        """K-1 prompt mentions all critical boxes."""
        assert "Box 1" in FORM_K1_PROMPT
        assert "ordinary_business_income" in FORM_K1_PROMPT.lower() or "ordinary business income" in FORM_K1_PROMPT.lower()
        assert "guaranteed_payments" in FORM_K1_PROMPT.lower() or "guaranteed payments" in FORM_K1_PROMPT.lower()
        assert "entity_type" in FORM_K1_PROMPT.lower() or "partnership" in FORM_K1_PROMPT.lower()

    def test_1099_b_prompt_mentions_transaction_fields(self) -> None:
        """1099-B prompt mentions key transaction fields."""
        assert "proceeds" in FORM_1099_B_PROMPT.lower()
        assert "cost_basis" in FORM_1099_B_PROMPT.lower() or "cost basis" in FORM_1099_B_PROMPT.lower()
        assert "date_sold" in FORM_1099_B_PROMPT.lower() or "date sold" in FORM_1099_B_PROMPT.lower()
        assert "short" in FORM_1099_B_PROMPT.lower()  # short-term
        assert "long" in FORM_1099_B_PROMPT.lower()   # long-term

    def test_1099_b_summary_prompt_mentions_categories(self) -> None:
        """1099-B summary prompt mentions Form 8949 categories."""
        prompt_lower = FORM_1099_B_SUMMARY_PROMPT.lower()
        assert "category" in prompt_lower or "cat_a" in prompt_lower
        assert "8949" in FORM_1099_B_SUMMARY_PROMPT
        assert "summary" in prompt_lower or "total" in prompt_lower

    def test_1095_a_prompt_mentions_ptc_fields(self) -> None:
        """1095-A prompt mentions Premium Tax Credit fields."""
        prompt_lower = FORM_1095_A_PROMPT.lower()
        assert "slcsp" in prompt_lower or "second lowest cost silver plan" in prompt_lower
        assert "advance" in prompt_lower  # advance PTC
        assert "premium" in prompt_lower
