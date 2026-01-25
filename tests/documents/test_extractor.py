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
    extract_1099_div,
    extract_1099_int,
    extract_1099_nec,
    extract_document,
    extract_w2,
)
from src.documents.models import (
    Box12Code,
    ConfidenceLevel,
    DocumentType,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Batch,
    W2Data,
)
from src.documents.prompts import (
    FORM_1099_DIV_PROMPT,
    FORM_1099_INT_PROMPT,
    FORM_1099_NEC_PROMPT,
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

    async def fake_extract_with_vision(*, response_model, **kwargs):
        if response_model is W2Batch:
            return W2Batch(forms=[sample_w2])
        if response_model is Form1099INT:
            return sample_1099_int
        if response_model is Form1099DIV:
            return sample_1099_div
        if response_model is Form1099NEC:
            return sample_1099_nec
        raise AssertionError("Unexpected response_model")

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
