"""TDD tests for personal tax calculator.

Tests are written BEFORE implementation following TDD approach.
These tests cover:
- Income aggregation (PTAX-03)
- Deduction calculation (PTAX-04)
- Credits evaluation (PTAX-05)
- Tax bracket calculation (PTAX-06)
- Prior year variance detection (PTAX-12)
"""

from decimal import Decimal

import pytest

from src.agents.personal_tax.calculator import (
    CreditItem,
    CreditsResult,
    DeductionResult,
    IncomeSummary,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    calculate_deductions,
    calculate_tax,
    compare_years,
    evaluate_credits,
    get_standard_deduction,
)
from src.documents.models import (
    ConfidenceLevel,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    W2Data,
)


# =============================================================================
# Helper fixtures
# =============================================================================


@pytest.fixture
def sample_w2() -> W2Data:
    """Create a sample W-2 for testing."""
    return W2Data(
        employee_ssn="123-45-6789",
        employer_ein="12-3456789",
        employer_name="Acme Corp",
        employee_name="John Doe",
        wages_tips_compensation=Decimal("50000"),
        federal_tax_withheld=Decimal("7500"),
        social_security_wages=Decimal("50000"),
        social_security_tax=Decimal("3100"),
        medicare_wages=Decimal("50000"),
        medicare_tax=Decimal("725"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_int() -> Form1099INT:
    """Create a sample 1099-INT for testing."""
    return Form1099INT(
        payer_name="First National Bank",
        payer_tin="12-3456789",
        recipient_tin="123-45-6789",
        interest_income=Decimal("500"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_div() -> Form1099DIV:
    """Create a sample 1099-DIV for testing."""
    return Form1099DIV(
        payer_name="Vanguard Funds",
        payer_tin="23-4567890",
        recipient_tin="123-45-6789",
        total_ordinary_dividends=Decimal("1000"),
        qualified_dividends=Decimal("800"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_nec() -> Form1099NEC:
    """Create a sample 1099-NEC for testing."""
    return Form1099NEC(
        payer_name="Consulting Client LLC",
        payer_tin="34-5678901",
        recipient_name="John Doe",
        recipient_tin="123-45-6789",
        nonemployee_compensation=Decimal("5000"),
        confidence=ConfidenceLevel.HIGH,
    )


# =============================================================================
# Income Aggregation Tests (PTAX-03)
# =============================================================================


class TestAggregateIncome:
    """Tests for income aggregation from various document types."""

    def test_aggregate_income_single_w2(self, sample_w2: W2Data) -> None:
        """Single W-2 should produce correct wage totals."""
        result = aggregate_income([sample_w2])

        assert result.total_wages == Decimal("50000")
        assert result.total_income == Decimal("50000")
        assert result.federal_withholding == Decimal("7500")

    def test_aggregate_income_multiple_w2(self) -> None:
        """Multiple W-2s should sum wages from all employers."""
        w2_1 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Employer A",
            employee_name="Jane Doe",
            wages_tips_compensation=Decimal("50000"),
            federal_tax_withheld=Decimal("7500"),
            social_security_wages=Decimal("50000"),
            social_security_tax=Decimal("3100"),
            medicare_wages=Decimal("50000"),
            medicare_tax=Decimal("725"),
            confidence=ConfidenceLevel.HIGH,
        )
        w2_2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="98-7654321",
            employer_name="Employer B",
            employee_name="Jane Doe",
            wages_tips_compensation=Decimal("30000"),
            federal_tax_withheld=Decimal("4500"),
            social_security_wages=Decimal("30000"),
            social_security_tax=Decimal("1860"),
            medicare_wages=Decimal("30000"),
            medicare_tax=Decimal("435"),
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income([w2_1, w2_2])

        assert result.total_wages == Decimal("80000")
        assert result.total_income == Decimal("80000")
        assert result.federal_withholding == Decimal("12000")

    def test_aggregate_income_single_1099_int(self, sample_1099_int: Form1099INT) -> None:
        """Single 1099-INT should produce correct interest total."""
        result = aggregate_income([sample_1099_int])

        assert result.total_interest == Decimal("500")
        assert result.total_income == Decimal("500")

    def test_aggregate_income_single_1099_div(self, sample_1099_div: Form1099DIV) -> None:
        """Single 1099-DIV should produce correct dividend totals."""
        result = aggregate_income([sample_1099_div])

        assert result.total_dividends == Decimal("1000")
        assert result.total_qualified_dividends == Decimal("800")
        assert result.total_income == Decimal("1000")

    def test_aggregate_income_single_1099_nec(self, sample_1099_nec: Form1099NEC) -> None:
        """Single 1099-NEC should produce correct NEC total."""
        result = aggregate_income([sample_1099_nec])

        assert result.total_nec == Decimal("5000")
        assert result.total_income == Decimal("5000")

    def test_aggregate_income_mixed_documents(
        self,
        sample_w2: W2Data,
        sample_1099_int: Form1099INT,
        sample_1099_div: Form1099DIV,
        sample_1099_nec: Form1099NEC,
    ) -> None:
        """Mix of all document types should categorize correctly."""
        result = aggregate_income([sample_w2, sample_1099_int, sample_1099_div, sample_1099_nec])

        assert result.total_wages == Decimal("50000")
        assert result.total_interest == Decimal("500")
        assert result.total_dividends == Decimal("1000")
        assert result.total_nec == Decimal("5000")
        # Total income = 50000 + 500 + 1000 + 5000 = 56500
        assert result.total_income == Decimal("56500")

    def test_aggregate_income_multiple_1099_int(self) -> None:
        """Multiple 1099-INTs should sum interest."""
        int_1 = Form1099INT(
            payer_name="Bank A",
            payer_tin="11-1111111",
            recipient_tin="123-45-6789",
            interest_income=Decimal("100"),
            confidence=ConfidenceLevel.HIGH,
        )
        int_2 = Form1099INT(
            payer_name="Bank B",
            payer_tin="22-2222222",
            recipient_tin="123-45-6789",
            interest_income=Decimal("50"),
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income([int_1, int_2])

        assert result.total_interest == Decimal("150")
        assert result.total_income == Decimal("150")


# =============================================================================
# Deduction Tests (PTAX-04)
# =============================================================================


class TestStandardDeduction:
    """Tests for standard deduction lookup."""

    def test_standard_deduction_single_2024(self) -> None:
        """Single filer 2024 standard deduction is $14,600."""
        result = get_standard_deduction("single", 2024)
        assert result == Decimal("14600")

    def test_standard_deduction_mfj_2024(self) -> None:
        """MFJ 2024 standard deduction is $29,200."""
        result = get_standard_deduction("mfj", 2024)
        assert result == Decimal("29200")

    def test_standard_deduction_mfs_2024(self) -> None:
        """MFS 2024 standard deduction is $14,600."""
        result = get_standard_deduction("mfs", 2024)
        assert result == Decimal("14600")

    def test_standard_deduction_hoh_2024(self) -> None:
        """HOH 2024 standard deduction is $21,900."""
        result = get_standard_deduction("hoh", 2024)
        assert result == Decimal("21900")

    def test_standard_deduction_2023(self) -> None:
        """2023 single standard deduction is $13,850."""
        result = get_standard_deduction("single", 2023)
        assert result == Decimal("13850")


class TestCalculateDeductions:
    """Tests for deduction method selection."""

    def test_calculate_deductions_standard_selected(self) -> None:
        """Standard deduction selected when itemized is lower."""
        income = IncomeSummary(
            total_wages=Decimal("75000"),
            total_interest=Decimal("0"),
            total_dividends=Decimal("0"),
            total_qualified_dividends=Decimal("0"),
            total_nec=Decimal("0"),
            total_other=Decimal("0"),
            total_income=Decimal("75000"),
            federal_withholding=Decimal("10000"),
        )

        result = calculate_deductions(income, "single", 2024, itemized_total=Decimal("10000"))

        assert result.method == "standard"
        assert result.amount == Decimal("14600")
        assert result.standard_amount == Decimal("14600")
        assert result.itemized_amount == Decimal("10000")

    def test_calculate_deductions_itemized_selected(self) -> None:
        """Itemized deduction selected when it exceeds standard."""
        income = IncomeSummary(
            total_wages=Decimal("150000"),
            total_interest=Decimal("0"),
            total_dividends=Decimal("0"),
            total_qualified_dividends=Decimal("0"),
            total_nec=Decimal("0"),
            total_other=Decimal("0"),
            total_income=Decimal("150000"),
            federal_withholding=Decimal("25000"),
        )

        result = calculate_deductions(income, "mfj", 2024, itemized_total=Decimal("35000"))

        assert result.method == "itemized"
        assert result.amount == Decimal("35000")
        assert result.standard_amount == Decimal("29200")
        assert result.itemized_amount == Decimal("35000")

    def test_calculate_deductions_no_itemized(self) -> None:
        """Standard selected when no itemized deductions provided."""
        income = IncomeSummary(
            total_wages=Decimal("60000"),
            total_interest=Decimal("0"),
            total_dividends=Decimal("0"),
            total_qualified_dividends=Decimal("0"),
            total_nec=Decimal("0"),
            total_other=Decimal("0"),
            total_income=Decimal("60000"),
            federal_withholding=Decimal("8000"),
        )

        result = calculate_deductions(income, "single", 2024)

        assert result.method == "standard"
        assert result.amount == Decimal("14600")
        assert result.itemized_amount == Decimal("0")


# =============================================================================
# Credits Tests (PTAX-05)
# =============================================================================


class TestChildTaxCredit:
    """Tests for Child Tax Credit evaluation."""

    def test_child_tax_credit_basic(self) -> None:
        """CTC is $2,000 per qualifying child under 17."""
        situation = TaxSituation(
            agi=Decimal("100000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=2,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is not None
        assert ctc.amount == Decimal("4000")
        assert ctc.refundable is False
        assert ctc.form == "Schedule 8812"

    def test_child_tax_credit_single_child(self) -> None:
        """CTC for single child is $2,000."""
        situation = TaxSituation(
            agi=Decimal("80000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is not None
        assert ctc.amount == Decimal("2000")

    def test_child_tax_credit_phaseout_single(self) -> None:
        """CTC phases out completely for single filer at high income."""
        # $200k threshold, $50 per $1k over, $2000 credit
        # At $240k, credit should be fully phased out (40 * 50 = 2000)
        situation = TaxSituation(
            agi=Decimal("250000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        # Should be zero or not present
        assert ctc is None or ctc.amount == Decimal("0")

    def test_child_tax_credit_phaseout_mfj(self) -> None:
        """CTC phases out for MFJ at $400k threshold."""
        situation = TaxSituation(
            agi=Decimal("450000"),
            filing_status="mfj",
            tax_year=2024,
            num_qualifying_children=1,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is None or ctc.amount == Decimal("0")

    def test_child_tax_credit_no_children(self) -> None:
        """No CTC when no qualifying children."""
        situation = TaxSituation(
            agi=Decimal("80000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is None


class TestEducationCredit:
    """Tests for Education Credits (American Opportunity Credit)."""

    def test_education_credit_aoc_full(self) -> None:
        """AOC is up to $2,500 for first $4,000 in expenses."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("4000"),
        )

        result = evaluate_credits(situation)

        edu = next(
            (c for c in result.credits if "Education" in c.name or "Opportunity" in c.name),
            None,
        )
        assert edu is not None
        # AOC: 100% of first $2000 + 25% of next $2000 = $2000 + $500 = $2500
        assert edu.amount == Decimal("2500")
        assert edu.form == "Form 8863"

    def test_education_credit_aoc_partial(self) -> None:
        """AOC for less than $4,000 in expenses."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("2000"),
        )

        result = evaluate_credits(situation)

        edu = next(
            (c for c in result.credits if "Education" in c.name or "Opportunity" in c.name),
            None,
        )
        assert edu is not None
        # AOC: 100% of first $2000 = $2000
        assert edu.amount == Decimal("2000")

    def test_education_credit_no_expenses(self) -> None:
        """No education credit when no expenses."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("0"),
        )

        result = evaluate_credits(situation)

        edu = next(
            (c for c in result.credits if "Education" in c.name or "Opportunity" in c.name),
            None,
        )
        assert edu is None


class TestSaversCredit:
    """Tests for Retirement Savings Contribution Credit (Saver's Credit)."""

    def test_savers_credit_mfj_20_percent(self) -> None:
        """Saver's Credit at 20% rate for MFJ AGI in mid-tier."""
        situation = TaxSituation(
            agi=Decimal("48000"),
            filing_status="mfj",
            tax_year=2024,
            retirement_contributions=Decimal("2000"),
        )

        result = evaluate_credits(situation)

        savers = next((c for c in result.credits if c.name == "Saver's Credit"), None)
        assert savers is not None
        # 20% rate, max $2000 contribution = $400
        assert savers.amount == Decimal("400")
        assert savers.form == "Form 8880"

    def test_savers_credit_single_50_percent(self) -> None:
        """Saver's Credit at 50% rate for low-income single filer."""
        situation = TaxSituation(
            agi=Decimal("20000"),
            filing_status="single",
            tax_year=2024,
            retirement_contributions=Decimal("1000"),
        )

        result = evaluate_credits(situation)

        savers = next((c for c in result.credits if c.name == "Saver's Credit"), None)
        assert savers is not None
        # 50% rate, $1000 contribution = $500
        assert savers.amount == Decimal("500")

    def test_savers_credit_no_contributions(self) -> None:
        """No Saver's Credit when no retirement contributions."""
        situation = TaxSituation(
            agi=Decimal("30000"),
            filing_status="single",
            tax_year=2024,
            retirement_contributions=Decimal("0"),
        )

        result = evaluate_credits(situation)

        savers = next((c for c in result.credits if c.name == "Saver's Credit"), None)
        assert savers is None


class TestEITC:
    """Tests for Earned Income Tax Credit."""

    def test_eitc_basic_eligibility(self) -> None:
        """EITC for low-income earner with no children."""
        situation = TaxSituation(
            agi=Decimal("15000"),
            filing_status="single",
            tax_year=2024,
            earned_income=Decimal("15000"),
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)

        eitc = next((c for c in result.credits if c.name == "Earned Income Credit"), None)
        assert eitc is not None
        assert eitc.refundable is True
        assert eitc.amount > Decimal("0")
        assert eitc.form == "Schedule EIC"

    def test_eitc_above_income_limit(self) -> None:
        """No EITC above income limit."""
        situation = TaxSituation(
            agi=Decimal("25000"),
            filing_status="single",
            tax_year=2024,
            earned_income=Decimal("25000"),
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)

        eitc = next((c for c in result.credits if c.name == "Earned Income Credit"), None)
        assert eitc is None

    def test_eitc_no_earned_income(self) -> None:
        """No EITC when no earned income."""
        situation = TaxSituation(
            agi=Decimal("10000"),
            filing_status="single",
            tax_year=2024,
            earned_income=Decimal("0"),
        )

        result = evaluate_credits(situation)

        eitc = next((c for c in result.credits if c.name == "Earned Income Credit"), None)
        assert eitc is None


class TestCreditsResult:
    """Tests for credits result aggregation."""

    def test_credits_total_calculation(self) -> None:
        """Total credits should sum all applicable credits."""
        situation = TaxSituation(
            agi=Decimal("40000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
            education_expenses=Decimal("4000"),
        )

        result = evaluate_credits(situation)

        # Should have CTC ($2000) + AOC ($2500)
        assert result.total_credits == result.total_nonrefundable + result.total_refundable
        assert result.total_credits >= Decimal("4500")

    def test_credits_refundable_vs_nonrefundable(self) -> None:
        """Refundable and non-refundable credits should be tracked separately."""
        situation = TaxSituation(
            agi=Decimal("15000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
            earned_income=Decimal("15000"),
        )

        result = evaluate_credits(situation)

        # CTC is non-refundable, EITC is refundable
        assert result.total_nonrefundable >= Decimal("0")
        assert result.total_refundable >= Decimal("0")

    def test_credits_no_qualifying_situations(self) -> None:
        """No credits if no qualifying situations exist."""
        situation = TaxSituation(
            agi=Decimal("150000"),
            filing_status="single",
            tax_year=2024,
        )

        result = evaluate_credits(situation)

        assert result.total_credits == Decimal("0")
        assert len(result.credits) == 0


# =============================================================================
# Tax Calculation Tests (PTAX-06)
# =============================================================================


class TestCalculateTax:
    """Tests for tax bracket calculation."""

    def test_tax_10_percent_bracket_only(self) -> None:
        """Income under $11,600 is taxed at 10%."""
        result = calculate_tax(Decimal("10000"), "single", 2024)

        assert result.gross_tax == Decimal("1000")
        assert len(result.bracket_breakdown) == 1
        assert result.bracket_breakdown[0]["rate"] == Decimal("0.10")

    def test_tax_crosses_into_12_percent(self) -> None:
        """Income crossing into 12% bracket."""
        # $20,000 taxable: 10% on $11,600 = $1,160, 12% on $8,400 = $1,008
        result = calculate_tax(Decimal("20000"), "single", 2024)

        expected = Decimal("1160") + Decimal("1008")
        assert result.gross_tax == expected
        assert len(result.bracket_breakdown) == 2

    def test_tax_50000_single(self) -> None:
        """$50,000 taxable income for single filer."""
        # 10% on $11,600 = $1,160
        # 12% on ($47,150 - $11,600) = $4,266
        # 22% on ($50,000 - $47,150) = $627
        result = calculate_tax(Decimal("50000"), "single", 2024)

        expected = Decimal("1160") + Decimal("4266") + Decimal("627")
        assert result.gross_tax == expected
        assert len(result.bracket_breakdown) == 3

    def test_tax_100000_single(self) -> None:
        """$100,000 taxable income for single filer."""
        # Should be within 22% bracket
        result = calculate_tax(Decimal("100000"), "single", 2024)

        # Approximate check - should be around $17,000-$18,000
        assert Decimal("17000") < result.gross_tax < Decimal("18000")
        assert len(result.bracket_breakdown) == 3

    def test_tax_effective_rate(self) -> None:
        """Effective rate should be calculated correctly."""
        result = calculate_tax(Decimal("50000"), "single", 2024)

        expected_rate = result.gross_tax / Decimal("50000")
        assert abs(result.effective_rate - expected_rate) < Decimal("0.0001")

    def test_tax_mfj_brackets(self) -> None:
        """MFJ uses different bracket thresholds."""
        # $50,000 MFJ: all in 10% and 12% brackets
        # 10% on $23,200 = $2,320
        # 12% on ($50,000 - $23,200) = $3,216
        result = calculate_tax(Decimal("50000"), "mfj", 2024)

        expected = Decimal("2320") + Decimal("3216")
        assert result.gross_tax == expected


# =============================================================================
# Prior Year Variance Tests (PTAX-12)
# =============================================================================


class TestCompareYears:
    """Tests for prior year variance detection."""

    def test_variance_flags_increase_over_10_percent(self) -> None:
        """Increase over 10% should be flagged."""
        variances = compare_years(
            {"wages": Decimal("80000")},
            {"wages": Decimal("70000")},
        )

        assert len(variances) == 1
        assert variances[0].field == "wages"
        assert variances[0].direction == "increase"
        # 14.3% increase
        assert variances[0].variance_pct > Decimal("10")

    def test_variance_flags_decrease_over_10_percent(self) -> None:
        """Decrease over 10% should be flagged."""
        variances = compare_years(
            {"wages": Decimal("60000")},
            {"wages": Decimal("80000")},
        )

        assert len(variances) == 1
        assert variances[0].field == "wages"
        assert variances[0].direction == "decrease"
        # 25% decrease
        assert variances[0].variance_pct > Decimal("10")

    def test_variance_ignores_small_changes(self) -> None:
        """Changes under 10% should not be flagged."""
        variances = compare_years(
            {"wages": Decimal("75000")},
            {"wages": Decimal("70000")},
        )

        # 7.14% increase - should not be flagged
        assert len(variances) == 0

    def test_variance_new_income_source(self) -> None:
        """New income source (prior=0) should be flagged."""
        variances = compare_years(
            {"wages": Decimal("50000"), "interest": Decimal("1000")},
            {"wages": Decimal("50000")},
        )

        # New interest income should be flagged
        assert len(variances) == 1
        assert variances[0].field == "interest"

    def test_variance_multiple_fields(self) -> None:
        """Multiple fields with significant changes should all be flagged."""
        variances = compare_years(
            {"wages": Decimal("100000"), "interest": Decimal("2000")},
            {"wages": Decimal("80000"), "interest": Decimal("500")},
        )

        assert len(variances) == 2
        fields = {v.field for v in variances}
        assert "wages" in fields
        assert "interest" in fields

    def test_variance_custom_threshold(self) -> None:
        """Custom threshold should be respected."""
        # 7% change with 5% threshold should be flagged
        variances = compare_years(
            {"wages": Decimal("75000")},
            {"wages": Decimal("70000")},
            threshold=Decimal("5"),
        )

        assert len(variances) == 1

    def test_variance_exact_threshold(self) -> None:
        """Exactly 10% change should not be flagged (must exceed)."""
        variances = compare_years(
            {"wages": Decimal("110000")},
            {"wages": Decimal("100000")},
        )

        # Exactly 10% - should not be flagged (must be greater than threshold)
        assert len(variances) == 0

    def test_variance_empty_prior(self) -> None:
        """All current values flagged when prior is empty."""
        variances = compare_years(
            {"wages": Decimal("50000")},
            {},
        )

        assert len(variances) == 1
        assert variances[0].field == "wages"


# =============================================================================
# Data Structure Tests
# =============================================================================


class TestDataStructures:
    """Tests for dataclass structures."""

    def test_income_summary_structure(self) -> None:
        """IncomeSummary should have all required fields."""
        summary = IncomeSummary(
            total_wages=Decimal("50000"),
            total_interest=Decimal("100"),
            total_dividends=Decimal("200"),
            total_qualified_dividends=Decimal("150"),
            total_nec=Decimal("5000"),
            total_other=Decimal("0"),
            total_income=Decimal("55300"),
            federal_withholding=Decimal("7500"),
        )

        assert summary.total_wages == Decimal("50000")
        assert summary.total_income == Decimal("55300")

    def test_deduction_result_structure(self) -> None:
        """DeductionResult should have all required fields."""
        result = DeductionResult(
            method="standard",
            amount=Decimal("14600"),
            standard_amount=Decimal("14600"),
            itemized_amount=Decimal("0"),
        )

        assert result.method == "standard"
        assert result.amount == Decimal("14600")

    def test_credit_item_structure(self) -> None:
        """CreditItem should have all required fields."""
        credit = CreditItem(
            name="Child Tax Credit",
            amount=Decimal("2000"),
            refundable=False,
            form="Schedule 8812",
        )

        assert credit.name == "Child Tax Credit"
        assert credit.refundable is False

    def test_credits_result_structure(self) -> None:
        """CreditsResult should have all required fields."""
        result = CreditsResult(
            credits=[],
            total_nonrefundable=Decimal("0"),
            total_refundable=Decimal("0"),
            total_credits=Decimal("0"),
        )

        assert result.total_credits == Decimal("0")

    def test_tax_result_structure(self) -> None:
        """TaxResult should have all required fields."""
        result = TaxResult(
            gross_tax=Decimal("1000"),
            bracket_breakdown=[{"bracket": Decimal("11600"), "rate": Decimal("0.10"), "tax_in_bracket": Decimal("1000")}],
            effective_rate=Decimal("0.10"),
        )

        assert result.gross_tax == Decimal("1000")
        assert len(result.bracket_breakdown) == 1

    def test_variance_item_structure(self) -> None:
        """VarianceItem should have all required fields."""
        item = VarianceItem(
            field="wages",
            current_value=Decimal("80000"),
            prior_value=Decimal("70000"),
            variance_pct=Decimal("14.29"),
            direction="increase",
        )

        assert item.field == "wages"
        assert item.direction == "increase"

    def test_tax_situation_structure(self) -> None:
        """TaxSituation should have all required fields with defaults."""
        situation = TaxSituation(
            agi=Decimal("100000"),
            filing_status="single",
            tax_year=2024,
        )

        assert situation.agi == Decimal("100000")
        assert situation.num_qualifying_children == 0
        assert situation.education_expenses == Decimal("0")
        assert situation.retirement_contributions == Decimal("0")
        assert situation.earned_income == Decimal("0")
