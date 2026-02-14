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
    CapitalTransaction,
    CreditItem,
    CreditsResult,
    DeductionResult,
    FilingStatus,
    IncomeSummary,
    ItemizedDeductionBreakdown,
    PremiumTaxCredit,
    QBIComponent,
    RentalExpenses,
    RentalProperty,
    ScheduleCData,
    ScheduleCExpenses,
    ScheduleDData,
    ScheduleEData,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    build_credit_inputs,
    build_qbi_from_k1,
    build_qbi_from_rental,
    build_qbi_from_schedule_c,
    calculate_deductions,
    calculate_premium_tax_credit,
    calculate_qbi_deduction,
    calculate_schedule_c,
    calculate_schedule_d,
    calculate_schedule_e,
    calculate_self_employment_tax,
    calculate_tax,
    compute_itemized_deductions,
    compare_years,
    convert_1099b_to_transactions,
    evaluate_credits,
    get_applicable_percentage,
    get_capital_gains_rate,
    get_fpl,
    get_ptc_repayment_limit,
    get_standard_deduction,
)
from src.documents.models import (
    ConfidenceLevel,
    Form1095A,
    Form1098,
    Form1098T,
    Form1099B,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Form5498,
    FormK1,
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


@pytest.fixture
def sample_1098() -> Form1098:
    """Create a sample 1098 for testing."""
    return Form1098(
        lender_name="ABC Mortgage",
        lender_tin="12-3456789",
        borrower_name="John Doe",
        borrower_tin="123-45-6789",
        mortgage_interest=Decimal("8000"),
        points_paid=Decimal("500"),
        mortgage_insurance_premiums=Decimal("300"),
        property_taxes_paid=Decimal("6000"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_r() -> Form1099R:
    """Create a sample 1099-R for testing."""
    return Form1099R(
        payer_name="Retirement Plan Inc",
        payer_tin="98-7654321",
        recipient_name="John Doe",
        recipient_tin="123-45-6789",
        gross_distribution=Decimal("12000"),
        taxable_amount=Decimal("10000"),
        distribution_code="1",
        state_tax_withheld=Decimal("1500"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1099_g() -> Form1099G:
    """Create a sample 1099-G for testing."""
    return Form1099G(
        payer_name="State Agency",
        payer_tin="11-1111111",
        recipient_name="John Doe",
        recipient_tin="123-45-6789",
        unemployment_compensation=Decimal("3000"),
        state_local_tax_refund=Decimal("0"),
        state_tax_withheld=Decimal("800"),
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_1098_t() -> Form1098T:
    """Create a sample 1098-T for testing."""
    return Form1098T(
        institution_name="State University",
        institution_tin="22-2222222",
        student_name="John Doe",
        student_tin="123-45-6789",
        payments_received=Decimal("10000"),
        scholarships_grants=Decimal("2500"),
        adjustments_prior_year=Decimal("500"),
        scholarships_adjustments_prior_year=Decimal("0"),
        at_least_half_time=True,
        confidence=ConfidenceLevel.HIGH,
    )


@pytest.fixture
def sample_5498() -> Form5498:
    """Create a sample 5498 for testing."""
    return Form5498(
        trustee_name="IRA Trustee",
        trustee_tin="33-3333333",
        participant_name="John Doe",
        participant_tin="123-45-6789",
        ira_contributions=Decimal("2000"),
        sep_contributions=Decimal("1000"),
        simple_contributions=Decimal("500"),
        roth_ira_contributions=Decimal("1500"),
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

    def test_aggregate_income_single_1099_int(
        self, sample_1099_int: Form1099INT
    ) -> None:
        """Single 1099-INT should produce correct interest total."""
        result = aggregate_income([sample_1099_int])

        assert result.total_interest == Decimal("500")
        assert result.total_income == Decimal("500")

    def test_aggregate_income_single_1099_div(
        self, sample_1099_div: Form1099DIV
    ) -> None:
        """Single 1099-DIV should produce correct dividend totals."""
        result = aggregate_income([sample_1099_div])

        assert result.total_dividends == Decimal("1000")
        assert result.total_qualified_dividends == Decimal("800")
        assert result.total_income == Decimal("1000")

    def test_aggregate_income_single_1099_nec(
        self, sample_1099_nec: Form1099NEC
    ) -> None:
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
        result = aggregate_income(
            [sample_w2, sample_1099_int, sample_1099_div, sample_1099_nec]
        )

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

    def test_aggregate_income_1099_r_and_1099_g(
        self,
        sample_1099_r: Form1099R,
        sample_1099_g: Form1099G,
    ) -> None:
        """1099-R and 1099-G add retirement and unemployment income."""
        result = aggregate_income([sample_1099_r, sample_1099_g])

        assert result.total_retirement_distributions == Decimal("10000")
        assert result.total_unemployment == Decimal("3000")
        assert result.total_income == Decimal("13000")


# =============================================================================
# Deduction Tests (PTAX-04)
# =============================================================================


class TestStandardDeduction:
    """Tests for standard deduction lookup."""

    def test_standard_deduction_single_2024(self) -> None:
        """Single filer 2024 standard deduction is $14,600."""
        result = get_standard_deduction("single", 2024)
        assert result == Decimal("14600")

    def test_standard_deduction_single_2025(self) -> None:
        """Single filer 2025 standard deduction is $15,750."""
        result = get_standard_deduction("single", 2025)
        assert result == Decimal("15750")

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

        result = calculate_deductions(
            income, "single", 2024, itemized_total=Decimal("10000")
        )

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

        result = calculate_deductions(
            income, "mfj", 2024, itemized_total=Decimal("35000")
        )

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


class TestItemizedDeductions:
    """Tests for itemized deduction computation from new forms."""

    def test_compute_itemized_deductions_applies_salt_cap(
        self,
        sample_1098: Form1098,
        sample_1099_r: Form1099R,
        sample_1099_g: Form1099G,
    ) -> None:
        """SALT cap applies to property + state tax total."""
        w2 = W2Data(
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
            state_tax_withheld=Decimal("5000"),
            confidence=ConfidenceLevel.HIGH,
        )

        breakdown = compute_itemized_deductions(
            [w2, sample_1098, sample_1099_r, sample_1099_g], filing_status="single"
        )

        assert isinstance(breakdown, ItemizedDeductionBreakdown)
        assert breakdown.salt_total == Decimal("13300")
        assert breakdown.salt_deduction == Decimal("10000")
        assert breakdown.total == Decimal("18800")


class TestCreditInputs:
    """Tests for credit input aggregation from forms."""

    def test_build_credit_inputs_education_and_retirement(
        self,
        sample_1098_t: Form1098T,
        sample_5498: Form5498,
    ) -> None:
        """Education expenses and retirement contributions are aggregated."""
        inputs = build_credit_inputs([sample_1098_t, sample_5498])

        assert inputs.education_expenses == Decimal("7000")
        assert inputs.education_credit_type == "aoc"
        assert inputs.retirement_contributions == Decimal("5000")

    def test_build_credit_inputs_llc_when_not_half_time(
        self,
        sample_1098_t: Form1098T,
    ) -> None:
        """LLC used when student is not at least half-time."""
        modified = sample_1098_t.model_copy(update={"at_least_half_time": False})
        inputs = build_credit_inputs([modified])

        assert inputs.education_credit_type == "llc"


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

    def test_child_tax_credit_2025_amount_update(self) -> None:
        """2025 CTC base amount is $2,200 per child."""
        situation = TaxSituation(
            agi=Decimal("100000"),
            filing_status="single",
            tax_year=2025,
            num_qualifying_children=1,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is not None
        assert ctc.amount == Decimal("2200")

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


class TestAdditionalChildTaxCredit:
    """Tests for Additional Child Tax Credit (ACTC)."""

    def test_actc_refundable_when_tax_liability_low(self) -> None:
        """ACTC provides refundable credit when CTC exceeds liability."""
        situation = TaxSituation(
            agi=Decimal("60000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
            tax_liability=Decimal("500"),
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        actc = next(
            (c for c in result.credits if c.name == "Additional Child Tax Credit"),
            None,
        )
        assert ctc is not None
        assert ctc.amount == Decimal("500")
        assert actc is not None
        assert actc.refundable is True
        assert actc.amount == Decimal("1500")
        assert result.total_nonrefundable == Decimal("500")
        assert result.total_refundable == Decimal("1500")


class TestEducationCredit:
    """Tests for Education Credits (AOC and LLC)."""

    def test_education_credit_aoc_full(self) -> None:
        """AOC is up to $2,500 for first $4,000 in expenses."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("4000"),
        )

        result = evaluate_credits(situation)

        # AOC: 100% of first $2000 + 25% of next $2000 = $2000 + $500 = $2500
        assert result.total_credits == Decimal("2500")
        # 40% refundable (max $1000), 60% non-refundable
        assert result.total_refundable == Decimal("1000")
        assert result.total_nonrefundable == Decimal("1500")
        assert any(
            "American Opportunity Credit" in credit.name for credit in result.credits
        )

    def test_education_credit_aoc_partial(self) -> None:
        """AOC for less than $4,000 in expenses."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("2000"),
        )

        result = evaluate_credits(situation)

        # AOC: 100% of first $2000 = $2000
        assert result.total_credits == Decimal("2000")
        assert result.total_refundable == Decimal("800")
        assert result.total_nonrefundable == Decimal("1200")

    def test_education_credit_llc(self) -> None:
        """LLC is 20% of up to $10,000 of expenses (max $2,000)."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("5000"),
            education_credit_type="llc",
        )

        result = evaluate_credits(situation)

        assert result.total_credits == Decimal("1000")
        assert result.total_refundable == Decimal("0")
        assert result.total_nonrefundable == Decimal("1000")
        llc = next(
            (c for c in result.credits if "Lifetime Learning Credit" in c.name),
            None,
        )
        assert llc is not None
        assert llc.form == "Form 8863"

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
            (
                c
                for c in result.credits
                if "Education" in c.name or "Opportunity" in c.name
            ),
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

        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
        assert eitc is not None
        assert eitc.refundable is True
        assert eitc.amount > Decimal("0")
        assert eitc.form == "Schedule EIC"

    def test_eitc_mfj_agi_above_limit(self) -> None:
        """MFJ should not qualify when AGI exceeds the income limit."""
        situation = TaxSituation(
            agi=Decimal("30000"),
            filing_status="mfj",
            tax_year=2024,
            earned_income=Decimal("15000"),
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)

        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
        assert eitc is None

    def test_eitc_mfj_2024_limit_allows_mid_income_case(self) -> None:
        """MFJ uses higher no-child income limit than single."""
        situation = TaxSituation(
            agi=Decimal("20000"),
            filing_status="mfj",
            tax_year=2024,
            earned_income=Decimal("12000"),
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)
        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
        assert eitc is not None
        assert eitc.amount > Decimal("0")

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

        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
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

        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
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
        assert (
            result.total_credits == result.total_nonrefundable + result.total_refundable
        )
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

    def test_tax_10_percent_bracket_only_2025(self) -> None:
        """Income under $11,925 is taxed at 10% for 2025 singles."""
        result = calculate_tax(Decimal("10000"), "single", 2025)

        assert result.gross_tax == Decimal("1000")
        assert len(result.bracket_breakdown) == 1
        assert result.bracket_breakdown[0]["rate"] == Decimal("0.10")

    def test_tax_2025_mfj_crosses_into_12_percent(self) -> None:
        """MFJ 2025 brackets should include both 10% and 12% for 50,000 income."""
        result = calculate_tax(Decimal("50000"), "mfj", 2025)

        expected = Decimal("2385") + Decimal("3138")
        assert result.gross_tax == expected

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

    def test_tax_mfj_2023_brackets(self) -> None:
        """MFJ 2023 brackets should be available."""
        # 2023 MFJ: 10% up to $22,000, 12% up to $89,450
        result = calculate_tax(Decimal("50000"), "mfj", 2023)

        expected = Decimal("2200") + Decimal("3360")
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
            bracket_breakdown=[
                {
                    "bracket": Decimal("11600"),
                    "rate": Decimal("0.10"),
                    "tax_in_bracket": Decimal("1000"),
                }
            ],
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


# =============================================================================
# Edge Case Tests (REFACTOR Phase)
# =============================================================================


class TestEdgeCases:
    """Additional edge case tests added during REFACTOR phase."""

    def test_aggregate_income_empty_list(self) -> None:
        """Empty document list should return zero totals."""
        result = aggregate_income([])

        assert result.total_wages == Decimal("0")
        assert result.total_interest == Decimal("0")
        assert result.total_dividends == Decimal("0")
        assert result.total_nec == Decimal("0")
        assert result.total_income == Decimal("0")
        assert result.federal_withholding == Decimal("0")

    def test_aggregate_income_with_withholding(self) -> None:
        """Federal withholding should be summed from all documents."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme",
            employee_name="John",
            wages_tips_compensation=Decimal("50000"),
            federal_tax_withheld=Decimal("7500"),
            social_security_wages=Decimal("50000"),
            social_security_tax=Decimal("3100"),
            medicare_wages=Decimal("50000"),
            medicare_tax=Decimal("725"),
            confidence=ConfidenceLevel.HIGH,
        )
        int_1099 = Form1099INT(
            payer_name="Bank",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            interest_income=Decimal("1000"),
            federal_tax_withheld=Decimal("200"),
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income([w2, int_1099])

        assert result.federal_withholding == Decimal("7700")

    def test_deduction_unknown_filing_status(self) -> None:
        """Unknown filing status should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown filing status"):
            get_standard_deduction("unknown", 2024)

    def test_deduction_unknown_year(self) -> None:
        """Unknown tax year should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown filing status"):
            get_standard_deduction("single", 2020)

    def test_tax_zero_income(self) -> None:
        """Zero taxable income should return zero tax."""
        result = calculate_tax(Decimal("0"), "single", 2024)

        assert result.gross_tax == Decimal("0")
        assert result.effective_rate == Decimal("0")
        assert len(result.bracket_breakdown) == 0

    def test_tax_at_bracket_boundary(self) -> None:
        """Tax at exact bracket boundary should be calculated correctly."""
        # Exactly $11,600 - should be 10% = $1,160
        result = calculate_tax(Decimal("11600"), "single", 2024)

        assert result.gross_tax == Decimal("1160")
        assert len(result.bracket_breakdown) == 1

    def test_tax_unknown_filing_status(self) -> None:
        """Unknown filing status should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown filing status"):
            calculate_tax(Decimal("50000"), "invalid", 2024)

    def test_variance_both_zero(self) -> None:
        """Both values zero should not produce variance."""
        variances = compare_years(
            {"wages": Decimal("0")},
            {"wages": Decimal("0")},
        )

        # 0 to 0 is not a new source, so no variance
        assert len(variances) == 0

    def test_variance_decrease_to_zero(self) -> None:
        """Decrease to zero is 100% decrease."""
        variances = compare_years(
            {"wages": Decimal("0")},
            {"wages": Decimal("50000")},
        )

        assert len(variances) == 1
        assert variances[0].direction == "decrease"
        assert variances[0].variance_pct == Decimal("100")

    def test_ctc_partial_phaseout(self) -> None:
        """CTC should partially phase out between threshold and full phaseout."""
        # Single filer at $220k: $20k over threshold, $20 * $50 = $1000 reduction
        # $2000 base - $1000 = $1000 remaining (for 1 child)
        situation = TaxSituation(
            agi=Decimal("220000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
        )

        result = evaluate_credits(situation)

        ctc = next((c for c in result.credits if c.name == "Child Tax Credit"), None)
        assert ctc is not None
        assert ctc.amount == Decimal("1000")

    def test_aoc_over_max_expenses(self) -> None:
        """AOC caps at $2,500 even for expenses over $4,000."""
        situation = TaxSituation(
            agi=Decimal("50000"),
            filing_status="single",
            tax_year=2024,
            education_expenses=Decimal("10000"),
        )

        result = evaluate_credits(situation)

        assert result.total_credits == Decimal("2500")
        assert result.total_refundable == Decimal("1000")
        assert result.total_nonrefundable == Decimal("1500")

    def test_savers_credit_above_limit(self) -> None:
        """No Saver's Credit above AGI threshold."""
        situation = TaxSituation(
            agi=Decimal("80000"),
            filing_status="mfj",
            tax_year=2024,
            retirement_contributions=Decimal("2000"),
        )

        result = evaluate_credits(situation)

        savers = next((c for c in result.credits if c.name == "Saver's Credit"), None)
        assert savers is None

    def test_savers_credit_max_contribution(self) -> None:
        """Saver's Credit limited to max $2,000 contribution."""
        situation = TaxSituation(
            agi=Decimal("20000"),
            filing_status="single",
            tax_year=2024,
            retirement_contributions=Decimal("5000"),
        )

        result = evaluate_credits(situation)

        savers = next((c for c in result.credits if c.name == "Saver's Credit"), None)
        assert savers is not None
        # 50% rate on max $2000 = $1000
        assert savers.amount == Decimal("1000")

    def test_multiple_credits_combined(self) -> None:
        """Multiple credits should sum correctly."""
        situation = TaxSituation(
            agi=Decimal("30000"),
            filing_status="single",
            tax_year=2024,
            num_qualifying_children=1,
            education_expenses=Decimal("4000"),
            retirement_contributions=Decimal("1000"),
        )

        result = evaluate_credits(situation)

        # CTC: $2,000, AOC: $2,500, Saver's: $200 (20% of $1000)
        assert len(result.credits) >= 3
        assert result.total_credits == sum(c.amount for c in result.credits)

    def test_high_income_tax_brackets(self) -> None:
        """High income should use all brackets correctly."""
        # $700,000 single - goes into 37% bracket
        result = calculate_tax(Decimal("700000"), "single", 2024)

        assert len(result.bracket_breakdown) == 7
        assert result.bracket_breakdown[-1]["rate"] == Decimal("0.37")

    def test_mfs_brackets(self) -> None:
        """MFS filing status should use correct brackets."""
        result = calculate_tax(Decimal("50000"), "mfs", 2024)

        # MFS has same brackets as single for 2024
        expected = Decimal("1160") + Decimal("4266") + Decimal("627")
        assert result.gross_tax == expected

    def test_hoh_brackets(self) -> None:
        """HOH filing status should use correct brackets."""
        # HOH has 10% up to $16,550, 12% up to $63,100
        result = calculate_tax(Decimal("50000"), "hoh", 2024)

        # 10% on $16,550 = $1,655
        # 12% on ($50,000 - $16,550) = $4,014
        expected = Decimal("1655") + Decimal("4014")
        assert result.gross_tax == expected

    def test_deduction_equal_values(self) -> None:
        """When itemized equals standard, standard should be selected."""
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

        result = calculate_deductions(
            income, "single", 2024, itemized_total=Decimal("14600")
        )

        # Equal should default to standard
        assert result.method == "standard"

    def test_eitc_phase_in_region(self) -> None:
        """EITC in phase-in region should be proportional to income."""
        situation = TaxSituation(
            agi=Decimal("5000"),
            filing_status="single",
            tax_year=2024,
            earned_income=Decimal("5000"),
            num_qualifying_children=0,
        )

        result = evaluate_credits(situation)

        eitc = next(
            (c for c in result.credits if c.name == "Earned Income Credit"), None
        )
        assert eitc is not None
        # Phase-in: $5000 * 0.0765 = ~$382.50
        assert Decimal("300") < eitc.amount < Decimal("450")


# =============================================================================
# Schedule C Tests (PTAX-04-03)
# =============================================================================


class TestScheduleCExpenses:
    """Tests for Schedule C expense tracking."""

    def test_schedule_c_expenses_total(self) -> None:
        """ScheduleCExpenses computes total correctly."""
        expenses = ScheduleCExpenses(
            advertising=Decimal("500"),
            supplies=Decimal("1200"),
            utilities=Decimal("3000"),
            office_expense=Decimal("2500"),
        )

        assert expenses.total == Decimal("7200")

    def test_schedule_c_expenses_default_zero(self) -> None:
        """ScheduleCExpenses defaults all fields to zero."""
        expenses = ScheduleCExpenses()
        assert expenses.total == Decimal("0")

    def test_schedule_c_expenses_all_categories(self) -> None:
        """ScheduleCExpenses includes all IRS categories."""
        expenses = ScheduleCExpenses(
            advertising=Decimal("100"),
            car_truck=Decimal("100"),
            commissions_fees=Decimal("100"),
            contract_labor=Decimal("100"),
            depletion=Decimal("100"),
            depreciation=Decimal("100"),
            employee_benefits=Decimal("100"),
            insurance=Decimal("100"),
            interest_mortgage=Decimal("100"),
            interest_other=Decimal("100"),
            legal_professional=Decimal("100"),
            office_expense=Decimal("100"),
            pension_profit_sharing=Decimal("100"),
            rent_vehicles_machinery=Decimal("100"),
            rent_other=Decimal("100"),
            repairs_maintenance=Decimal("100"),
            supplies=Decimal("100"),
            taxes_licenses=Decimal("100"),
            travel=Decimal("100"),
            deductible_meals=Decimal("100"),
            utilities=Decimal("100"),
            wages=Decimal("100"),
            other_expenses=Decimal("100"),
        )

        # 23 categories * $100 = $2300
        assert expenses.total == Decimal("2300")


class TestScheduleCData:
    """Tests for Schedule C calculations."""

    def test_schedule_c_net_profit(self) -> None:
        """Schedule C calculates net profit correctly."""
        sch_c = ScheduleCData(
            business_name="Test Business",
            business_activity="Consulting",
            principal_business_code="541611",
            gross_receipts=Decimal("100000"),
            cost_of_goods_sold=Decimal("20000"),
            expenses=ScheduleCExpenses(
                office_expense=Decimal("5000"),
                supplies=Decimal("2000"),
            ),
        )

        result = calculate_schedule_c(sch_c)

        # 100000 - 20000 - 5000 - 2000 = 73000
        assert result["net_profit_or_loss"] == Decimal("73000")

    def test_schedule_c_with_loss(self) -> None:
        """Schedule C handles business loss."""
        sch_c = ScheduleCData(
            business_name="Startup",
            business_activity="Tech",
            principal_business_code="541511",
            gross_receipts=Decimal("10000"),
            expenses=ScheduleCExpenses(
                office_expense=Decimal("15000"),
            ),
        )

        result = calculate_schedule_c(sch_c)

        assert result["net_profit_or_loss"] == Decimal("-5000")
        # QBI cannot be negative
        assert result["qualified_business_income"] == Decimal("0")

    def test_schedule_c_gross_income_calculation(self) -> None:
        """Schedule C computes gross income (receipts - returns)."""
        sch_c = ScheduleCData(
            business_name="Retail",
            business_activity="Sales",
            principal_business_code="441110",
            gross_receipts=Decimal("50000"),
            returns_allowances=Decimal("3000"),
        )

        assert sch_c.gross_income == Decimal("47000")

    def test_schedule_c_gross_profit_calculation(self) -> None:
        """Schedule C computes gross profit (gross income - COGS)."""
        sch_c = ScheduleCData(
            business_name="Wholesale",
            business_activity="Distribution",
            principal_business_code="423110",
            gross_receipts=Decimal("100000"),
            returns_allowances=Decimal("5000"),
            cost_of_goods_sold=Decimal("40000"),
        )

        assert sch_c.gross_profit == Decimal("55000")

    def test_schedule_c_with_home_office(self) -> None:
        """Schedule C includes home office deduction in expenses."""
        sch_c = ScheduleCData(
            business_name="Freelance",
            business_activity="Writing",
            principal_business_code="711510",
            gross_receipts=Decimal("80000"),
            expenses=ScheduleCExpenses(
                supplies=Decimal("1000"),
            ),
            home_office_deduction=Decimal("5000"),
        )

        # Total expenses include home office
        assert sch_c.total_expenses == Decimal("6000")
        assert sch_c.net_profit_or_loss == Decimal("74000")


# =============================================================================
# Self-Employment Tax Tests (PTAX-04-03)
# =============================================================================


class TestSelfEmploymentTax:
    """Tests for self-employment tax calculations."""

    def test_se_tax_basic(self) -> None:
        """SE tax calculated correctly for typical income."""
        result = calculate_self_employment_tax(
            Decimal("100000"),
            FilingStatus.SINGLE,
        )

        # Net = 100000 * 0.9235 = 92350
        assert result.net_earnings == Decimal("92350.00")
        # SS = 92350 * 0.124 = 11451.40
        assert result.social_security_tax == Decimal("11451.40")
        # Medicare = 92350 * 0.029 = 2678.15
        assert result.medicare_tax == Decimal("2678.15")
        # No additional Medicare (under threshold)
        assert result.additional_medicare_tax == Decimal("0.00")
        # Total = 14129.55
        assert result.total_se_tax == Decimal("14129.55")
        # Deductible = 50%
        assert result.deductible_portion == Decimal("7064.78")

    def test_se_tax_above_ss_wage_base(self) -> None:
        """SE tax respects Social Security wage base cap."""
        result = calculate_self_employment_tax(
            Decimal("200000"),
            FilingStatus.SINGLE,
        )

        # SS capped at wage base * rate
        max_ss_tax = Decimal("168600") * Decimal("0.124")
        assert result.social_security_tax == max_ss_tax.quantize(Decimal("0.01"))

    def test_se_tax_additional_medicare_single(self) -> None:
        """Additional Medicare applies above $200k threshold for single."""
        result = calculate_self_employment_tax(
            Decimal("250000"),
            FilingStatus.SINGLE,
        )

        # Net earnings = 250000 * 0.9235 = 230875
        # Excess over $200k = 30875
        # Additional Medicare = 30875 * 0.009 = 277.88
        assert result.additional_medicare_tax > Decimal("0")
        assert result.additional_medicare_threshold == Decimal("200000")

    def test_se_tax_additional_medicare_mfj(self) -> None:
        """Additional Medicare threshold is $250k for MFJ."""
        result = calculate_self_employment_tax(
            Decimal("280000"),
            FilingStatus.MARRIED_FILING_JOINTLY,
        )

        # MFJ threshold is $250k
        assert result.additional_medicare_threshold == Decimal("250000")
        # Net earnings = 280000 * 0.9235 = 258580, which exceeds $250k
        assert result.additional_medicare_tax > Decimal("0")

    def test_se_tax_additional_medicare_mfs(self) -> None:
        """Additional Medicare threshold is $125k for MFS."""
        result = calculate_self_employment_tax(
            Decimal("150000"),
            FilingStatus.MARRIED_FILING_SEPARATELY,
        )

        # MFS has lower threshold of $125k
        assert result.additional_medicare_threshold == Decimal("125000")

    def test_se_tax_deductible_portion(self) -> None:
        """SE tax deduction is exactly 50% of total."""
        result = calculate_self_employment_tax(
            Decimal("100000"),
            FilingStatus.SINGLE,
        )

        expected_deductible = (result.total_se_tax * Decimal("0.5")).quantize(
            Decimal("0.01")
        )
        assert result.deductible_portion == expected_deductible

    def test_se_tax_zero_income(self) -> None:
        """SE tax is zero for zero income."""
        result = calculate_self_employment_tax(
            Decimal("0"),
            FilingStatus.SINGLE,
        )

        assert result.net_earnings == Decimal("0.00")
        assert result.total_se_tax == Decimal("0.00")

    def test_se_tax_negative_income(self) -> None:
        """SE tax is zero for negative income (loss)."""
        result = calculate_self_employment_tax(
            Decimal("-10000"),
            FilingStatus.SINGLE,
        )

        assert result.net_earnings == Decimal("0.00")
        assert result.total_se_tax == Decimal("0.00")


# =============================================================================
# Aggregate Income with Business Income Tests
# =============================================================================


class TestAggregateIncomeWithBusiness:
    """Tests for aggregate_income with Schedule C and K-1 data."""

    def test_aggregate_with_schedule_c(self) -> None:
        """Aggregate income includes Schedule C profit."""
        sch_c = ScheduleCData(
            business_name="Consulting",
            business_activity="IT",
            principal_business_code="541511",
            gross_receipts=Decimal("90000"),
            expenses=ScheduleCExpenses(office_expense=Decimal("10000")),
        )

        result = aggregate_income(
            documents=[],
            schedule_c_data=[sch_c],
            filing_status=FilingStatus.SINGLE,
        )

        assert result.schedule_c_profit == Decimal("80000")
        assert result.self_employment_income == Decimal("80000")
        assert result.se_tax > Decimal("0")
        assert result.se_tax_deduction > Decimal("0")
        assert result.total_income == Decimal("80000")

    def test_aggregate_with_multiple_schedule_c(self) -> None:
        """Aggregate income sums multiple Schedule C businesses."""
        sch_c1 = ScheduleCData(
            business_name="Consulting",
            business_activity="IT",
            principal_business_code="541511",
            gross_receipts=Decimal("50000"),
        )
        sch_c2 = ScheduleCData(
            business_name="Freelance",
            business_activity="Writing",
            principal_business_code="711510",
            gross_receipts=Decimal("30000"),
        )

        result = aggregate_income(
            documents=[],
            schedule_c_data=[sch_c1, sch_c2],
            filing_status=FilingStatus.SINGLE,
        )

        assert result.schedule_c_profit == Decimal("80000")
        assert result.self_employment_income == Decimal("80000")

    def test_aggregate_schedule_c_avoids_double_count_1099_nec(self) -> None:
        """Schedule C profit should not double count 1099-NEC income."""
        nec = Form1099NEC(
            payer_name="Consulting Client LLC",
            payer_tin="34-5678901",
            recipient_name="John Doe",
            recipient_tin="123-45-6789",
            nonemployee_compensation=Decimal("10000"),
            confidence=ConfidenceLevel.HIGH,
        )
        sch_c = ScheduleCData(
            business_name="Consulting Client LLC",
            business_activity="Independent contractor",
            principal_business_code="999999",
            gross_receipts=Decimal("10000"),
        )

        result = aggregate_income(
            documents=[nec],
            schedule_c_data=[sch_c],
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_nec == Decimal("10000")
        assert result.schedule_c_profit == Decimal("10000")
        assert result.total_income == Decimal("10000")

    def test_aggregate_with_k1_partnership(self) -> None:
        """K-1 from partnership with Box 14 SE earnings."""
        k1 = FormK1(
            entity_name="ABC Partnership",
            entity_ein="12-3456789",
            entity_type="partnership",
            tax_year=2024,
            recipient_name="John Doe",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("25.0"),
            ordinary_business_income=Decimal("40000"),
            guaranteed_payments=Decimal("10000"),
            self_employment_earnings=Decimal("45000"),  # Box 14
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income(
            documents=[k1],
            filing_status=FilingStatus.SINGLE,
        )

        # K-1 ordinary income goes to total_other
        assert result.k1_ordinary_income == Decimal("40000")
        assert result.k1_guaranteed_payments == Decimal("10000")
        # SE income from Box 14 (not Box 1 + Box 4)
        assert result.self_employment_income == Decimal("45000")
        assert result.se_tax > Decimal("0")

    def test_aggregate_k1_income_components(self) -> None:
        """K-1 interest, dividends, and guaranteed payments flow into totals."""
        k1 = FormK1(
            entity_name="ABC Partnership",
            entity_ein="12-3456789",
            entity_type="partnership",
            tax_year=2024,
            recipient_name="John Doe",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("25.0"),
            ordinary_business_income=Decimal("40000"),
            guaranteed_payments=Decimal("10000"),
            interest_income=Decimal("500"),
            dividend_income=Decimal("300"),
            royalties=Decimal("200"),
            net_short_term_capital_gain=Decimal("1000"),
            net_long_term_capital_gain=Decimal("2000"),
            net_section_1231_gain=Decimal("500"),
            other_income=Decimal("100"),
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income(
            documents=[k1],
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_interest == Decimal("500")
        assert result.total_dividends == Decimal("300")
        assert result.total_other == Decimal("53800")

    def test_aggregate_with_k1_scorp(self) -> None:
        """S-corp K-1 should NOT generate SE tax."""
        k1 = FormK1(
            entity_name="XYZ S-Corp",
            entity_ein="12-3456789",
            entity_type="s_corp",
            tax_year=2024,
            recipient_name="John Doe",
            recipient_tin="123-45-6789",
            ownership_percentage=Decimal("50.0"),
            ordinary_business_income=Decimal("100000"),
            confidence=ConfidenceLevel.HIGH,
        )

        result = aggregate_income(
            documents=[k1],
            filing_status=FilingStatus.SINGLE,
        )

        # S-corp income is NOT subject to SE tax
        assert result.k1_ordinary_income == Decimal("100000")
        assert result.self_employment_income == Decimal("0")
        assert result.se_tax == Decimal("0")

    def test_aggregate_mixed_w2_and_schedule_c(self) -> None:
        """Aggregate income correctly combines W-2 and Schedule C."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("75000"),
            federal_tax_withheld=Decimal("10000"),
            social_security_wages=Decimal("75000"),
            social_security_tax=Decimal("4650"),
            medicare_wages=Decimal("75000"),
            medicare_tax=Decimal("1087.50"),
            confidence=ConfidenceLevel.HIGH,
        )
        sch_c = ScheduleCData(
            business_name="Side Gig",
            business_activity="Consulting",
            principal_business_code="541611",
            gross_receipts=Decimal("25000"),
            expenses=ScheduleCExpenses(supplies=Decimal("5000")),
        )

        result = aggregate_income(
            documents=[w2],
            schedule_c_data=[sch_c],
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_wages == Decimal("75000")
        assert result.schedule_c_profit == Decimal("20000")
        assert result.total_income == Decimal("95000")
        assert result.federal_withholding == Decimal("10000")
        assert result.se_tax > Decimal("0")

    def test_aggregate_schedule_c_loss_offsets_income(self) -> None:
        """Schedule C loss reduces total income."""
        w2 = W2Data(
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
        sch_c = ScheduleCData(
            business_name="Failed Startup",
            business_activity="Tech",
            principal_business_code="541511",
            gross_receipts=Decimal("5000"),
            expenses=ScheduleCExpenses(
                office_expense=Decimal("10000"),
                advertising=Decimal("5000"),
            ),
        )

        result = aggregate_income(
            documents=[w2],
            schedule_c_data=[sch_c],
            filing_status=FilingStatus.SINGLE,
        )

        # Loss is -10000
        assert result.schedule_c_profit == Decimal("-10000")
        # Total income includes the loss
        assert result.total_income == Decimal("40000")
        # No SE tax on loss
        assert result.self_employment_income == Decimal("-10000")
        assert result.se_tax == Decimal("0")


# =============================================================================
# Schedule E Tests (PTAX-04-04)
# =============================================================================


class TestRentalExpenses:
    """Tests for RentalExpenses dataclass."""

    def test_rental_expenses_total(self) -> None:
        """RentalExpenses computes total correctly."""
        expenses = RentalExpenses(
            mortgage_interest=Decimal("8000"),
            taxes=Decimal("3000"),
            insurance=Decimal("1500"),
            depreciation=Decimal("5000"),
        )

        assert expenses.total == Decimal("17500")

    def test_rental_expenses_default_zero(self) -> None:
        """RentalExpenses defaults all fields to zero."""
        expenses = RentalExpenses()
        assert expenses.total == Decimal("0")

    def test_rental_expenses_all_categories(self) -> None:
        """RentalExpenses includes all IRS categories."""
        expenses = RentalExpenses(
            advertising=Decimal("100"),
            auto_travel=Decimal("100"),
            cleaning_maintenance=Decimal("100"),
            commissions=Decimal("100"),
            insurance=Decimal("100"),
            legal_professional=Decimal("100"),
            management_fees=Decimal("100"),
            mortgage_interest=Decimal("100"),
            other_interest=Decimal("100"),
            repairs=Decimal("100"),
            supplies=Decimal("100"),
            taxes=Decimal("100"),
            utilities=Decimal("100"),
            depreciation=Decimal("100"),
            other_expenses=Decimal("100"),
        )

        # 15 categories * $100 = $1500
        assert expenses.total == Decimal("1500")


class TestRentalProperty:
    """Tests for RentalProperty dataclass."""

    def test_rental_property_net_income(self) -> None:
        """RentalProperty calculates net income correctly."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("24000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("6000"),
                taxes=Decimal("3000"),
                depreciation=Decimal("5000"),
            ),
        )

        assert prop.net_income_loss == Decimal("10000")

    def test_rental_property_net_loss(self) -> None:
        """RentalProperty handles loss correctly."""
        prop = RentalProperty(
            property_address="456 Oak Ave",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("10000"),
                taxes=Decimal("5000"),
                depreciation=Decimal("10000"),
            ),
        )

        assert prop.net_income_loss == Decimal("-13000")

    def test_rental_property_not_personal_use(self) -> None:
        """Property with minimal personal use passes rental test."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            personal_use_days=10,
            rental_income=Decimal("24000"),
        )

        assert prop.is_personal_use_property is False

    def test_rental_property_personal_use_over_14_days(self) -> None:
        """Property with >14 personal days fails rental test."""
        prop = RentalProperty(
            property_address="Beach House",
            property_type="Vacation",
            fair_rental_days=100,
            personal_use_days=15,  # Over 14 days
            rental_income=Decimal("15000"),
        )

        assert prop.is_personal_use_property is True

    def test_rental_property_personal_use_over_10_percent(self) -> None:
        """Property with >10% personal use fails rental test."""
        prop = RentalProperty(
            property_address="Vacation Condo",
            property_type="Vacation",
            fair_rental_days=200,
            personal_use_days=25,  # 12.5% > 10%
            rental_income=Decimal("25000"),
        )

        assert prop.is_personal_use_property is True

    def test_rental_property_personal_use_under_10_percent(self) -> None:
        """Property with <10% personal use passes rental test."""
        prop = RentalProperty(
            property_address="Vacation Condo",
            property_type="Vacation",
            fair_rental_days=200,
            personal_use_days=15,  # 7.5% < 10%
            rental_income=Decimal("25000"),
        )

        assert prop.is_personal_use_property is False


class TestScheduleEData:
    """Tests for ScheduleEData dataclass."""

    def test_schedule_e_data_totals(self) -> None:
        """ScheduleEData aggregates multiple properties."""
        prop1 = RentalProperty(
            property_address="Property A",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("18000"),
            expenses=RentalExpenses(taxes=Decimal("3000")),
        )
        prop2 = RentalProperty(
            property_address="Property B",
            property_type="Multi-Family",
            fair_rental_days=365,
            rental_income=Decimal("30000"),
            expenses=RentalExpenses(taxes=Decimal("5000")),
        )

        sch_e = ScheduleEData(properties=[prop1, prop2])

        assert sch_e.total_rental_income == Decimal("48000")
        assert sch_e.total_expenses == Decimal("8000")
        assert sch_e.net_before_limitations == Decimal("40000")

    def test_schedule_e_data_net_loss(self) -> None:
        """ScheduleEData handles aggregate loss."""
        prop = RentalProperty(
            property_address="Property A",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("15000"),
                depreciation=Decimal("10000"),
            ),
        )

        sch_e = ScheduleEData(properties=[prop])

        assert sch_e.net_before_limitations == Decimal("-13000")


class TestCalculateScheduleE:
    """Tests for calculate_schedule_e function."""

    def test_schedule_e_net_income(self) -> None:
        """Profitable rental has no limitations."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("30000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("6000"),
                taxes=Decimal("4000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = calculate_schedule_e(sch_e, Decimal("80000"), FilingStatus.SINGLE)

        assert result.net_rental_income_loss == Decimal("20000")
        assert result.loss_limited is False
        assert result.suspended_loss == Decimal("0")

    def test_schedule_e_loss_under_100k_magi(self) -> None:
        """Rental loss fully allowed under $100k MAGI with active participation."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("10000"),
                taxes=Decimal("5000"),
                depreciation=Decimal("10000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = calculate_schedule_e(sch_e, Decimal("80000"), FilingStatus.SINGLE)

        # Loss of $13000, under $25k allowance
        assert result.net_before_limitations == Decimal("-13000")
        assert result.net_rental_income_loss == Decimal("-13000")
        assert result.loss_limited is False
        assert result.suspended_loss == Decimal("0")

    def test_schedule_e_loss_at_125k_magi(self) -> None:
        """Rental loss partially limited at $125k MAGI (phaseout region)."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("12000"),
                taxes=Decimal("6000"),
                depreciation=Decimal("12000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = calculate_schedule_e(sch_e, Decimal("125000"), FilingStatus.SINGLE)

        # At $125k: $25k over threshold, $12.5k reduction
        # Allowance = $25k - $12.5k = $12.5k
        # Loss of $18k limited to $12.5k
        assert result.net_before_limitations == Decimal("-18000")
        assert result.allowed_loss == Decimal("12500")
        assert result.suspended_loss == Decimal("5500")
        assert result.net_rental_income_loss == Decimal("-12500")
        assert result.loss_limited is True

    def test_schedule_e_loss_at_150k_magi(self) -> None:
        """Rental loss fully limited at $150k MAGI (no allowance)."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("15000"),
                taxes=Decimal("6000"),
                depreciation=Decimal("12000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = calculate_schedule_e(sch_e, Decimal("160000"), FilingStatus.SINGLE)

        # At $160k: phaseout complete, no allowance
        assert result.net_before_limitations == Decimal("-21000")
        assert result.allowed_loss == Decimal("0")
        assert result.suspended_loss == Decimal("21000")
        assert result.net_rental_income_loss == Decimal("0")
        assert result.loss_limited is True

    def test_schedule_e_no_active_participation(self) -> None:
        """Rental loss fully suspended without active participation."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("15000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=False)

        result = calculate_schedule_e(sch_e, Decimal("50000"), FilingStatus.SINGLE)

        # No active participation = no allowance
        assert result.allowed_loss == Decimal("0")
        assert result.suspended_loss == Decimal("3000")
        assert result.net_rental_income_loss == Decimal("0")
        assert result.loss_limited is True

    def test_schedule_e_real_estate_professional(self) -> None:
        """Real estate professional has no passive loss limitations."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("30000"),
            ),
        )
        sch_e = ScheduleEData(
            properties=[prop],
            actively_participates=True,
            is_real_estate_professional=True,
        )

        result = calculate_schedule_e(sch_e, Decimal("200000"), FilingStatus.SINGLE)

        # RE professional can deduct full loss
        assert result.net_before_limitations == Decimal("-18000")
        assert result.allowed_loss == Decimal("18000")
        assert result.suspended_loss == Decimal("0")
        assert result.net_rental_income_loss == Decimal("-18000")
        assert result.loss_limited is False

    def test_schedule_e_loss_limited_to_actual_loss(self) -> None:
        """Loss allowed cannot exceed actual loss."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("20000"),
            expenses=RentalExpenses(taxes=Decimal("25000")),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = calculate_schedule_e(sch_e, Decimal("80000"), FilingStatus.SINGLE)

        # Loss of $5k, allowance is $25k
        # Should allow full $5k, not $25k
        assert result.allowed_loss == Decimal("5000")
        assert result.suspended_loss == Decimal("0")

    def test_schedule_e_qbi_income(self) -> None:
        """QBI rental income includes eligible profitable properties."""
        prop1 = RentalProperty(
            property_address="Property A",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("20000"),
            expenses=RentalExpenses(taxes=Decimal("5000")),
            qbi_eligible=True,
        )
        prop2 = RentalProperty(
            property_address="Property B",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("10000"),
            expenses=RentalExpenses(taxes=Decimal("15000")),
            qbi_eligible=True,
        )
        sch_e = ScheduleEData(properties=[prop1, prop2])

        result = calculate_schedule_e(sch_e, Decimal("80000"), FilingStatus.SINGLE)

        # Only profitable properties contribute to QBI
        # prop1: $15000 profit, prop2: -$5000 loss
        assert result.qbi_rental_income == Decimal("15000")


class TestAggregateIncomeWithScheduleE:
    """Tests for aggregate_income with Schedule E data."""

    def test_aggregate_with_schedule_e_income(self) -> None:
        """Aggregate income includes Schedule E rental income."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("24000"),
            expenses=RentalExpenses(taxes=Decimal("4000")),
        )
        sch_e = ScheduleEData(properties=[prop])

        result = aggregate_income(
            documents=[],
            schedule_e_data=sch_e,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.schedule_e_rental_income == Decimal("24000")
        assert result.schedule_e_expenses == Decimal("4000")
        assert result.schedule_e_net == Decimal("20000")
        assert result.total_income == Decimal("20000")

    def test_aggregate_with_schedule_e_loss(self) -> None:
        """Aggregate income handles Schedule E loss correctly."""
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("10000"),
                taxes=Decimal("5000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = aggregate_income(
            documents=[],
            schedule_e_data=sch_e,
            filing_status=FilingStatus.SINGLE,
        )

        # Loss of $3000 should be fully allowed at low MAGI
        assert result.schedule_e_net == Decimal("-3000")
        assert result.total_income == Decimal("-3000")

    def test_aggregate_with_w2_and_schedule_e(self) -> None:
        """Aggregate income combines W-2 and Schedule E."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("75000"),
            federal_tax_withheld=Decimal("10000"),
            social_security_wages=Decimal("75000"),
            social_security_tax=Decimal("4650"),
            medicare_wages=Decimal("75000"),
            medicare_tax=Decimal("1088"),
            confidence=ConfidenceLevel.HIGH,
        )
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("18000"),
            expenses=RentalExpenses(taxes=Decimal("3000")),
        )
        sch_e = ScheduleEData(properties=[prop])

        result = aggregate_income(
            documents=[w2],
            schedule_e_data=sch_e,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_wages == Decimal("75000")
        assert result.schedule_e_net == Decimal("15000")
        assert result.total_income == Decimal("90000")

    def test_aggregate_with_high_magi_limits_rental_loss(self) -> None:
        """High MAGI limits rental loss deduction."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("150000"),
            federal_tax_withheld=Decimal("25000"),
            social_security_wages=Decimal("150000"),
            social_security_tax=Decimal("9300"),
            medicare_wages=Decimal("150000"),
            medicare_tax=Decimal("2175"),
            confidence=ConfidenceLevel.HIGH,
        )
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("12000"),
            expenses=RentalExpenses(
                mortgage_interest=Decimal("18000"),
                taxes=Decimal("6000"),
            ),
        )
        sch_e = ScheduleEData(properties=[prop], actively_participates=True)

        result = aggregate_income(
            documents=[w2],
            schedule_e_data=sch_e,
            filing_status=FilingStatus.SINGLE,
            modified_agi_for_pal=Decimal("150000"),  # Above phaseout end
        )

        # At $150k MAGI, no loss allowance
        assert result.schedule_e_net == Decimal("0")
        assert result.schedule_e_suspended_loss == Decimal("12000")
        assert result.total_income == Decimal("150000")

    def test_aggregate_with_all_business_types(self) -> None:
        """Aggregate income handles W-2 + Schedule C + Schedule E."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("60000"),
            federal_tax_withheld=Decimal("9000"),
            social_security_wages=Decimal("60000"),
            social_security_tax=Decimal("3720"),
            medicare_wages=Decimal("60000"),
            medicare_tax=Decimal("870"),
            confidence=ConfidenceLevel.HIGH,
        )
        sch_c = ScheduleCData(
            business_name="Side Consulting",
            business_activity="IT",
            principal_business_code="541511",
            gross_receipts=Decimal("20000"),
            expenses=ScheduleCExpenses(supplies=Decimal("5000")),
        )
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("18000"),
            expenses=RentalExpenses(taxes=Decimal("3000")),
        )
        sch_e = ScheduleEData(properties=[prop])

        result = aggregate_income(
            documents=[w2],
            schedule_c_data=[sch_c],
            schedule_e_data=sch_e,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_wages == Decimal("60000")
        assert result.schedule_c_profit == Decimal("15000")
        assert result.schedule_e_net == Decimal("15000")
        # W-2 + Schedule C + Schedule E
        assert result.total_income == Decimal("90000")
        # SE tax on Schedule C profit
        assert result.se_tax > Decimal("0")


# =============================================================================
# Schedule D (Capital Gains/Losses) Tests - PTAX-04-05
# =============================================================================


class TestCapitalTransaction:
    """Tests for CapitalTransaction dataclass."""

    def test_capital_transaction_long_term_gain(self) -> None:
        """CapitalTransaction calculates long-term gain correctly."""
        txn = CapitalTransaction(
            description="100 sh AAPL",
            date_acquired="2023-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        assert txn.gain_loss == Decimal("5000")
        assert txn.is_long_term is True
        assert txn.is_short_term is False
        assert txn.requires_basis_escalation is False

    def test_capital_transaction_short_term_gain(self) -> None:
        """CapitalTransaction calculates short-term gain correctly."""
        txn = CapitalTransaction(
            description="50 sh TSLA",
            date_acquired="2024-03-01",
            date_sold="2024-06-15",
            proceeds=Decimal("8000"),
            cost_basis=Decimal("6000"),
            is_short_term=True,
        )
        assert txn.gain_loss == Decimal("2000")
        assert txn.is_short_term is True
        assert txn.is_long_term is False

    def test_capital_transaction_loss(self) -> None:
        """CapitalTransaction calculates loss correctly."""
        txn = CapitalTransaction(
            description="100 sh GOOG",
            date_acquired="2023-06-01",
            date_sold="2024-01-15",
            proceeds=Decimal("12000"),
            cost_basis=Decimal("15000"),
            is_long_term=True,
        )
        assert txn.gain_loss == Decimal("-3000")

    def test_capital_transaction_with_wash_sale(self) -> None:
        """CapitalTransaction adjusts gain/loss for wash sale disallowed."""
        txn = CapitalTransaction(
            description="100 sh NVDA",
            date_acquired="2024-01-01",
            date_sold="2024-03-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("12000"),
            is_short_term=True,
            wash_sale_disallowed=Decimal("500"),  # $500 loss disallowed
        )
        # Loss is -2000 but 500 disallowed, so adjusted = -1500
        assert txn.gain_loss == Decimal("-1500")

    def test_capital_transaction_missing_basis(self) -> None:
        """CapitalTransaction with missing basis requires escalation."""
        txn = CapitalTransaction(
            description="Various securities",
            date_acquired="Various",
            date_sold="2024-06-15",
            proceeds=Decimal("25000"),
            cost_basis=None,  # Not reported
            is_long_term=True,
            basis_reported_to_irs=False,
        )
        assert txn.cost_basis is None
        assert txn.gain_loss is None  # Cannot calculate
        assert txn.requires_basis_escalation is True

    def test_capital_transaction_collectibles(self) -> None:
        """CapitalTransaction handles collectibles flag."""
        txn = CapitalTransaction(
            description="Gold coins",
            date_acquired="2020-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("50000"),
            cost_basis=Decimal("30000"),
            is_long_term=True,
            is_collectibles=True,
        )
        assert txn.gain_loss == Decimal("20000")
        assert txn.is_collectibles is True


class TestScheduleDData:
    """Tests for ScheduleDData dataclass."""

    def test_schedule_d_data_filters_short_term(self) -> None:
        """ScheduleDData filters short-term transactions."""
        st_txn = CapitalTransaction(
            description="ST",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("4000"),
            is_short_term=True,
        )
        lt_txn = CapitalTransaction(
            description="LT",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[st_txn, lt_txn])
        assert len(data.short_term_transactions) == 1
        assert data.short_term_transactions[0].description == "ST"

    def test_schedule_d_data_filters_long_term(self) -> None:
        """ScheduleDData filters long-term transactions."""
        st_txn = CapitalTransaction(
            description="ST",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("4000"),
            is_short_term=True,
        )
        lt_txn = CapitalTransaction(
            description="LT",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[st_txn, lt_txn])
        assert len(data.long_term_transactions) == 1
        assert data.long_term_transactions[0].description == "LT"

    def test_schedule_d_data_net_short_term(self) -> None:
        """ScheduleDData calculates net short-term gain/loss."""
        st_gain = CapitalTransaction(
            description="ST Gain",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("3000"),
            is_short_term=True,
        )
        st_loss = CapitalTransaction(
            description="ST Loss",
            date_acquired="2024-02-01",
            date_sold="2024-06-15",
            proceeds=Decimal("4000"),
            cost_basis=Decimal("5500"),
            is_short_term=True,
        )
        data = ScheduleDData(transactions=[st_gain, st_loss])
        # Gain 2000 + Loss -1500 = Net 500
        assert data.net_short_term == Decimal("500")

    def test_schedule_d_data_net_long_term(self) -> None:
        """ScheduleDData calculates net long-term gain/loss."""
        lt_gain = CapitalTransaction(
            description="LT Gain",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("20000"),
            cost_basis=Decimal("15000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[lt_gain])
        assert data.net_long_term == Decimal("5000")

    def test_schedule_d_data_identifies_missing_basis(self) -> None:
        """ScheduleDData identifies transactions with missing basis."""
        good_txn = CapitalTransaction(
            description="Good",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        bad_txn = CapitalTransaction(
            description="Missing basis",
            date_acquired="Various",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=None,
            is_long_term=True,
            basis_reported_to_irs=False,
        )
        data = ScheduleDData(transactions=[good_txn, bad_txn])
        assert len(data.transactions_with_missing_basis) == 1
        assert data.transactions_with_missing_basis[0].description == "Missing basis"

    def test_schedule_d_data_collectibles_gain(self) -> None:
        """ScheduleDData calculates collectibles gain separately."""
        regular = CapitalTransaction(
            description="Stock",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        collectible = CapitalTransaction(
            description="Gold",
            date_acquired="2020-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("50000"),
            cost_basis=Decimal("30000"),
            is_long_term=True,
            is_collectibles=True,
        )
        data = ScheduleDData(transactions=[regular, collectible])
        assert data.collectibles_gain == Decimal("20000")


class TestGetCapitalGainsRate:
    """Tests for get_capital_gains_rate() function."""

    def test_capital_gains_rate_0_percent_single(self) -> None:
        """Single filer gets 0% rate below threshold."""
        rate = get_capital_gains_rate(Decimal("40000"), FilingStatus.SINGLE)
        assert rate == Decimal("0")

    def test_capital_gains_rate_15_percent_single(self) -> None:
        """Single filer gets 15% rate in middle bracket."""
        rate = get_capital_gains_rate(Decimal("100000"), FilingStatus.SINGLE)
        assert rate == Decimal("0.15")

    def test_capital_gains_rate_20_percent_single(self) -> None:
        """Single filer gets 20% rate above high threshold."""
        rate = get_capital_gains_rate(Decimal("550000"), FilingStatus.SINGLE)
        assert rate == Decimal("0.20")

    def test_capital_gains_rate_0_percent_mfj(self) -> None:
        """MFJ gets 0% rate below threshold."""
        rate = get_capital_gains_rate(
            Decimal("80000"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert rate == Decimal("0")

    def test_capital_gains_rate_15_percent_mfj(self) -> None:
        """MFJ gets 15% rate in middle bracket."""
        rate = get_capital_gains_rate(
            Decimal("200000"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert rate == Decimal("0.15")

    def test_capital_gains_rate_20_percent_mfj(self) -> None:
        """MFJ gets 20% rate above high threshold."""
        rate = get_capital_gains_rate(
            Decimal("600000"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert rate == Decimal("0.20")

    def test_capital_gains_rate_mfs_half_thresholds(self) -> None:
        """MFS has half the MFJ thresholds."""
        # MFJ 0% threshold ~94050, so MFS ~47025
        rate = get_capital_gains_rate(
            Decimal("50000"), FilingStatus.MARRIED_FILING_SEPARATELY
        )
        assert rate == Decimal("0.15")  # Above MFS 0% threshold

    def test_capital_gains_rate_2025_hoh_uses_2025_thresholds(self) -> None:
        """HOH 2025 thresholds should be used instead of hardcoded 2024 values."""
        rate = get_capital_gains_rate(
            Decimal("64000"),
            FilingStatus.HEAD_OF_HOUSEHOLD,
            tax_year=2025,
        )
        assert rate == Decimal("0")


class TestCalculateScheduleD:
    """Tests for calculate_schedule_d() function."""

    def test_calculate_schedule_d_basic_gain(self) -> None:
        """Basic long-term gain calculation."""
        txn = CapitalTransaction(
            description="100 sh AAPL",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[txn])
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        assert result.net_long_term_gain_loss == Decimal("5000")
        assert result.net_short_term_gain_loss == Decimal("0")
        assert result.net_included_in_income == Decimal("5000")
        assert result.capital_loss_limitation_applied is False
        assert result.new_loss_carryforward == Decimal("0")

    def test_calculate_schedule_d_loss_within_limit(self) -> None:
        """Capital loss within $3k limit."""
        txn = CapitalTransaction(
            description="100 sh GOOG",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("12000"),
            cost_basis=Decimal("14500"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[txn])
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        assert result.net_long_term_gain_loss == Decimal("-2500")
        assert result.allowed_capital_loss == Decimal("2500")
        assert result.net_included_in_income == Decimal("-2500")
        assert result.capital_loss_limitation_applied is False
        assert result.new_loss_carryforward == Decimal("0")

    def test_calculate_schedule_d_loss_exceeds_limit(self) -> None:
        """Capital loss exceeding $3k limit creates carryforward."""
        txn = CapitalTransaction(
            description="100 sh META",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("8000"),
            cost_basis=Decimal("20000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[txn])
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        assert result.net_long_term_gain_loss == Decimal("-12000")
        assert result.allowed_capital_loss == Decimal("3000")
        assert result.net_included_in_income == Decimal("-3000")
        assert result.capital_loss_limitation_applied is True
        assert result.new_loss_carryforward == Decimal("9000")

    def test_calculate_schedule_d_mfs_1500_limit(self) -> None:
        """MFS has $1500 capital loss limit."""
        txn = CapitalTransaction(
            description="Loss",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[txn])
        result = calculate_schedule_d(data, FilingStatus.MARRIED_FILING_SEPARATELY)

        assert result.allowed_capital_loss == Decimal("1500")
        assert result.net_included_in_income == Decimal("-1500")
        assert result.new_loss_carryforward == Decimal("3500")

    def test_calculate_schedule_d_mixed_st_lt(self) -> None:
        """Mixed short-term and long-term transactions."""
        st_gain = CapitalTransaction(
            description="ST Gain",
            date_acquired="2024-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("8000"),
            cost_basis=Decimal("6000"),
            is_short_term=True,
        )
        lt_loss = CapitalTransaction(
            description="LT Loss",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        data = ScheduleDData(transactions=[st_gain, lt_loss])
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        assert result.net_short_term_gain_loss == Decimal("2000")
        assert result.net_long_term_gain_loss == Decimal("-3000")
        # Net: 2000 - 3000 = -1000
        assert result.net_capital_gain_loss == Decimal("-1000")
        assert result.net_included_in_income == Decimal("-1000")

    def test_calculate_schedule_d_prior_year_carryover(self) -> None:
        """Prior year carryover applied to current gains."""
        txn = CapitalTransaction(
            description="Gain",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        data = ScheduleDData(
            transactions=[txn],
            prior_year_loss_carryover=Decimal("3000"),
        )
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        # 5000 gain - 3000 carryover = 2000 net
        assert result.gross_long_term == Decimal("5000")
        assert result.capital_loss_carryover_used == Decimal("3000")
        assert result.net_included_in_income == Decimal("2000")

    def test_calculate_schedule_d_carryover_exceeds_gain(self) -> None:
        """Prior carryover exceeding gain allows partial use."""
        txn = CapitalTransaction(
            description="Small gain",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("11000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        data = ScheduleDData(
            transactions=[txn],
            prior_year_loss_carryover=Decimal("5000"),
        )
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        # 1000 gain, 5000 carryover = uses 1000, net = 0
        # Remaining 4000 carryover treated as new loss, limited to 3000
        assert result.capital_loss_carryover_used == Decimal("1000")

    def test_calculate_schedule_d_missing_basis_count(self) -> None:
        """Tracks transactions with missing basis for escalation."""
        good_txn = CapitalTransaction(
            description="Good",
            date_acquired="2022-01-01",
            date_sold="2024-06-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("8000"),
            is_long_term=True,
        )
        missing_txn = CapitalTransaction(
            description="Missing",
            date_acquired="Various",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=None,
            is_long_term=True,
            basis_reported_to_irs=False,
        )
        data = ScheduleDData(transactions=[good_txn, missing_txn])
        result = calculate_schedule_d(data, FilingStatus.SINGLE)

        assert result.transactions_missing_basis == 1


class TestConvert1099BToTransactions:
    """Tests for convert_1099b_to_transactions() function."""

    def test_convert_1099b_basic(self) -> None:
        """Converts basic 1099-B to CapitalTransaction."""
        form = Form1099B(
            payer_name="Broker Inc",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="100 sh AAPL",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
            basis_reported_to_irs=True,
        )
        transactions, missing = convert_1099b_to_transactions([form])

        assert len(transactions) == 1
        assert len(missing) == 0
        assert transactions[0].description == "100 sh AAPL"
        assert transactions[0].proceeds == Decimal("15000")
        assert transactions[0].cost_basis == Decimal("10000")
        assert transactions[0].gain_loss == Decimal("5000")
        assert transactions[0].is_long_term is True

    def test_convert_1099b_with_wash_sale(self) -> None:
        """Converts 1099-B with wash sale adjustment."""
        form = Form1099B(
            payer_name="Broker Inc",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="50 sh NVDA",
            date_acquired="2024-01-01",
            date_sold="2024-03-15",
            proceeds=Decimal("10000"),
            cost_basis=Decimal("12000"),
            is_short_term=True,
            wash_sale_loss_disallowed=Decimal("500"),
            basis_reported_to_irs=True,
        )
        transactions, missing = convert_1099b_to_transactions([form])

        assert len(transactions) == 1
        assert transactions[0].wash_sale_disallowed == Decimal("500")
        # Loss -2000, wash sale +500 = -1500
        assert transactions[0].gain_loss == Decimal("-1500")

    def test_convert_1099b_missing_basis_tracked(self) -> None:
        """Tracks 1099-B with missing basis for escalation."""
        form = Form1099B(
            payer_name="Broker Inc",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="Various securities",
            date_acquired="Various",
            date_sold="2024-06-15",
            proceeds=Decimal("25000"),
            cost_basis=None,
            is_long_term=True,
            basis_reported_to_irs=False,
        )
        transactions, missing = convert_1099b_to_transactions([form])

        assert len(transactions) == 1
        assert len(missing) == 1
        assert missing[0].description == "Various securities"
        assert transactions[0].requires_basis_escalation is True

    def test_convert_1099b_collectibles(self) -> None:
        """Converts 1099-B for collectibles."""
        form = Form1099B(
            payer_name="Precious Metals LLC",
            payer_tin="12-3456789",
            recipient_tin="123-45-6789",
            description="Gold bullion",
            date_acquired="2020-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("50000"),
            cost_basis=Decimal("30000"),
            is_long_term=True,
            is_collectibles=True,
            basis_reported_to_irs=True,
        )
        transactions, missing = convert_1099b_to_transactions([form])

        assert len(transactions) == 1
        assert transactions[0].is_collectibles is True
        assert transactions[0].gain_loss == Decimal("20000")

    def test_convert_1099b_multiple_forms(self) -> None:
        """Converts multiple 1099-B forms."""
        forms = [
            Form1099B(
                payer_name="Broker A",
                payer_tin="12-3456789",
                recipient_tin="123-45-6789",
                description="Stock A",
                date_sold="2024-06-15",
                proceeds=Decimal("5000"),
                cost_basis=Decimal("4000"),
                is_short_term=True,
                basis_reported_to_irs=True,
            ),
            Form1099B(
                payer_name="Broker B",
                payer_tin="98-7654321",
                recipient_tin="123-45-6789",
                description="Stock B",
                date_acquired="2022-01-01",
                date_sold="2024-06-15",
                proceeds=Decimal("20000"),
                cost_basis=Decimal("15000"),
                is_long_term=True,
                basis_reported_to_irs=True,
            ),
        ]
        transactions, missing = convert_1099b_to_transactions(forms)

        assert len(transactions) == 2
        assert len(missing) == 0


class TestAggregateIncomeWithScheduleD:
    """Tests for aggregate_income with Schedule D capital gains."""

    def test_aggregate_with_schedule_d_gain(self) -> None:
        """aggregate_income includes capital gains in total income."""
        txn = CapitalTransaction(
            description="100 sh AAPL",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        sch_d = ScheduleDData(transactions=[txn])

        result = aggregate_income(
            documents=[],
            schedule_d_data=sch_d,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.capital_gains_long_term == Decimal("5000")
        assert result.capital_gains_short_term == Decimal("0")
        assert result.capital_gains_net == Decimal("5000")
        assert result.total_income == Decimal("5000")

    def test_aggregate_with_schedule_d_loss(self) -> None:
        """aggregate_income handles capital loss (limited to $3k)."""
        txn = CapitalTransaction(
            description="Loss",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("15000"),
            is_long_term=True,
        )
        sch_d = ScheduleDData(transactions=[txn])

        result = aggregate_income(
            documents=[],
            schedule_d_data=sch_d,
            filing_status=FilingStatus.SINGLE,
        )

        # 10k loss, but limited to 3k
        assert result.capital_gains_net == Decimal("-3000")
        assert result.capital_loss_carryforward == Decimal("7000")
        assert result.total_income == Decimal("-3000")

    def test_aggregate_with_w2_and_schedule_d(self) -> None:
        """aggregate_income combines W-2 and capital gains."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("75000"),
            federal_tax_withheld=Decimal("10000"),
            social_security_wages=Decimal("75000"),
            social_security_tax=Decimal("4650"),
            medicare_wages=Decimal("75000"),
            medicare_tax=Decimal("1087.50"),
            confidence=ConfidenceLevel.HIGH,
        )
        txn = CapitalTransaction(
            description="LTCG",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("25000"),
            cost_basis=Decimal("20000"),
            is_long_term=True,
        )
        sch_d = ScheduleDData(transactions=[txn])

        result = aggregate_income(
            documents=[w2],
            schedule_d_data=sch_d,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_wages == Decimal("75000")
        assert result.capital_gains_net == Decimal("5000")
        assert result.total_income == Decimal("80000")

    def test_aggregate_with_all_income_types_including_capital_gains(self) -> None:
        """aggregate_income handles W-2 + Schedule C + Schedule E + Schedule D."""
        w2 = W2Data(
            employee_ssn="123-45-6789",
            employer_ein="12-3456789",
            employer_name="Acme Corp",
            employee_name="John Doe",
            wages_tips_compensation=Decimal("60000"),
            federal_tax_withheld=Decimal("9000"),
            social_security_wages=Decimal("60000"),
            social_security_tax=Decimal("3720"),
            medicare_wages=Decimal("60000"),
            medicare_tax=Decimal("870"),
            confidence=ConfidenceLevel.HIGH,
        )
        sch_c = ScheduleCData(
            business_name="Consulting",
            business_activity="IT",
            principal_business_code="541511",
            gross_receipts=Decimal("20000"),
            expenses=ScheduleCExpenses(supplies=Decimal("5000")),
        )
        prop = RentalProperty(
            property_address="123 Main St",
            property_type="Single Family",
            fair_rental_days=365,
            rental_income=Decimal("18000"),
            expenses=RentalExpenses(taxes=Decimal("3000")),
        )
        sch_e = ScheduleEData(properties=[prop])
        txn = CapitalTransaction(
            description="LTCG",
            date_acquired="2022-01-15",
            date_sold="2024-06-15",
            proceeds=Decimal("15000"),
            cost_basis=Decimal("10000"),
            is_long_term=True,
        )
        sch_d = ScheduleDData(transactions=[txn])

        result = aggregate_income(
            documents=[w2],
            schedule_c_data=[sch_c],
            schedule_e_data=sch_e,
            schedule_d_data=sch_d,
            filing_status=FilingStatus.SINGLE,
        )

        assert result.total_wages == Decimal("60000")
        assert result.schedule_c_profit == Decimal("15000")
        assert result.schedule_e_net == Decimal("15000")
        assert result.capital_gains_net == Decimal("5000")
        # W-2 + Schedule C + Schedule E + Capital Gains
        assert result.total_income == Decimal("95000")


# =============================================================================
# QBI Deduction (Section 199A) Tests - PTAX-04-06
# =============================================================================


class TestQBIComponent:
    """Tests for QBIComponent dataclass."""

    def test_qbi_component_tentative_deduction(self) -> None:
        """QBIComponent calculates 20% tentative deduction."""
        qbi = QBIComponent(
            business_name="Test Business",
            qualified_business_income=Decimal("100000"),
        )
        assert qbi.tentative_qbi_deduction == Decimal("20000.00")

    def test_qbi_component_w2_wage_limit(self) -> None:
        """QBIComponent calculates 50% W-2 wage limit."""
        qbi = QBIComponent(
            business_name="Test Business",
            qualified_business_income=Decimal("100000"),
            w2_wages=Decimal("60000"),
        )
        assert qbi.w2_wage_limit == Decimal("30000.00")

    def test_qbi_component_wage_plus_property_limit(self) -> None:
        """QBIComponent calculates 25% wages + 2.5% property limit."""
        qbi = QBIComponent(
            business_name="Test Business",
            qualified_business_income=Decimal("100000"),
            w2_wages=Decimal("40000"),
            unadjusted_basis_qualified_property=Decimal("200000"),
        )
        # 25% of 40k = 10k + 2.5% of 200k = 5k = 15k
        assert qbi.wage_plus_property_limit == Decimal("15000.00")

    def test_qbi_component_wage_limit_greater_of_two(self) -> None:
        """QBIComponent.wage_limit is greater of the two limits."""
        qbi = QBIComponent(
            business_name="Test Business",
            qualified_business_income=Decimal("100000"),
            w2_wages=Decimal("60000"),  # 50% = 30k, 25% = 15k
            unadjusted_basis_qualified_property=Decimal("100000"),  # 2.5% = 2.5k
        )
        # 50% of wages (30k) > 25% + 2.5% (17.5k)
        assert qbi.wage_limit == Decimal("30000.00")

    def test_qbi_component_negative_income_zero_deduction(self) -> None:
        """QBIComponent with negative income gives zero deduction."""
        qbi = QBIComponent(
            business_name="Loss Business",
            qualified_business_income=Decimal("-10000"),
        )
        assert qbi.tentative_qbi_deduction == Decimal("0")


class TestQBIDeduction:
    """Tests for calculate_qbi_deduction() function."""

    def test_qbi_below_threshold(self) -> None:
        """QBI below threshold gets full 20% deduction."""
        components = [
            QBIComponent(
                business_name="Test Business",
                qualified_business_income=Decimal("100000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("150000"),
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        assert result.final_qbi_deduction == Decimal("20000.00")
        assert not result.is_above_threshold
        assert not result.wage_limit_applied

    def test_qbi_above_threshold_with_wages(self) -> None:
        """QBI above threshold applies W-2 wage limitation."""
        components = [
            QBIComponent(
                business_name="Test Business",
                qualified_business_income=Decimal("100000"),
                w2_wages=Decimal("30000"),  # 50% = 15k
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("300000"),  # Above phaseout
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_fully_phased_out
        assert result.final_qbi_deduction == Decimal("15000.00")
        assert result.wage_limit_applied

    def test_qbi_sstb_exclusion_above_threshold(self) -> None:
        """SSTB excluded above threshold."""
        components = [
            QBIComponent(
                business_name="Law Firm",
                qualified_business_income=Decimal("200000"),
                is_sstb=True,
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("300000"),  # Fully phased out
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        assert result.sstb_exclusion_applied
        assert result.final_qbi_deduction == Decimal("0.00")

    def test_qbi_taxable_income_limit(self) -> None:
        """QBI limited to 20% of taxable income."""
        components = [
            QBIComponent(
                business_name="Test Business",
                qualified_business_income=Decimal("200000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("50000"),  # 20% = 10k
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        # Tentative = 40k, but limited to 20% of TI = 10k
        assert result.final_qbi_deduction == Decimal("10000.00")
        assert result.taxable_income_limit_applied

    def test_qbi_multiple_businesses(self) -> None:
        """Multiple QBI components aggregated."""
        components = [
            QBIComponent(
                business_name="Business 1",
                qualified_business_income=Decimal("50000"),
            ),
            QBIComponent(
                business_name="Business 2",
                qualified_business_income=Decimal("30000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("150000"),
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        # Total QBI = 80k, deduction = 20% = 16k
        assert result.total_qbi == Decimal("80000")
        assert result.final_qbi_deduction == Decimal("16000.00")

    def test_qbi_mfj_higher_threshold(self) -> None:
        """MFJ has higher threshold ($383,900)."""
        components = [
            QBIComponent(
                business_name="Test Business",
                qualified_business_income=Decimal("100000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("350000"),  # Below MFJ threshold
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        )
        assert not result.is_above_threshold
        assert result.final_qbi_deduction == Decimal("20000.00")

    def test_qbi_with_capital_gains_limit(self) -> None:
        """QBI limited by 20% of (TI - capital gains)."""
        components = [
            QBIComponent(
                business_name="Test Business",
                qualified_business_income=Decimal("50000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("60000"),
            net_capital_gains=Decimal("30000"),  # High cap gains
            filing_status=FilingStatus.SINGLE,
        )
        # 20% of (60k - 30k) = 6k < tentative 10k
        assert result.final_qbi_deduction == Decimal("6000.00")
        assert result.taxable_income_limit_applied

    def test_qbi_2025_threshold_is_higher_than_2024(self) -> None:
        """2025 single threshold should avoid phaseout at $195,000 TI."""
        components = [
            QBIComponent(
                business_name="Service Business",
                qualified_business_income=Decimal("100000"),
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=Decimal("195000"),
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
            tax_year=2025,
        )
        assert result.final_qbi_deduction == Decimal("20000.00")
        assert not result.is_above_threshold


class TestQBIHelpers:
    """Tests for QBI helper functions."""

    def test_build_qbi_from_schedule_c(self) -> None:
        """Build QBI from Schedule C with auto SSTB detection."""
        sch_c = ScheduleCData(
            business_name="Tech Consulting",
            business_activity="Management consulting",
            principal_business_code="541611",  # SSTB
            gross_receipts=Decimal("150000"),
            expenses=ScheduleCExpenses(office_expense=Decimal("10000")),
        )
        qbi = build_qbi_from_schedule_c(sch_c, Decimal("7000"))
        # Net = 140k, minus SE deduction 7k = 133k
        assert qbi.qualified_business_income == Decimal("133000")
        assert qbi.is_sstb is True
        assert qbi.source == "schedule_c"

    def test_build_qbi_from_schedule_c_non_sstb(self) -> None:
        """Build QBI from non-SSTB Schedule C."""
        sch_c = ScheduleCData(
            business_name="Johns Plumbing",
            business_activity="Plumbing services",
            principal_business_code="238220",  # Not SSTB
            gross_receipts=Decimal("100000"),
            expenses=ScheduleCExpenses(),
        )
        qbi = build_qbi_from_schedule_c(sch_c, Decimal("5000"))
        assert qbi.is_sstb is False

    def test_build_qbi_from_k1_partnership(self) -> None:
        """Build QBI from partnership K-1."""
        k1 = FormK1(
            entity_name="ABC Partners",
            entity_ein="12-3456789",
            entity_type="partnership",
            recipient_tin="111-22-3333",
            recipient_name="John Doe",
            tax_year=2024,
            ownership_percentage=Decimal("10"),
            ordinary_business_income=Decimal("50000"),
            guaranteed_payments=Decimal("20000"),  # NOT QBI
        )
        qbi = build_qbi_from_k1(k1)
        # Only Box 1 (ordinary income) is QBI
        assert qbi.qualified_business_income == Decimal("50000")
        assert qbi.source == "k1_partnership"

    def test_build_qbi_from_k1_scorp(self) -> None:
        """Build QBI from S-corp K-1."""
        k1 = FormK1(
            entity_name="XYZ Corp",
            entity_ein="98-7654321",
            entity_type="s_corp",
            recipient_tin="111-22-3333",
            recipient_name="Jane Doe",
            tax_year=2024,
            ownership_percentage=Decimal("25"),
            ordinary_business_income=Decimal("100000"),
        )
        qbi = build_qbi_from_k1(k1)
        assert qbi.qualified_business_income == Decimal("100000")
        assert qbi.source == "k1_s_corp"

    def test_build_qbi_from_rental(self) -> None:
        """Build QBI from qualifying rental income."""
        qbi = build_qbi_from_rental(Decimal("15000"), "123 Main St")
        assert qbi is not None
        assert qbi.qualified_business_income == Decimal("15000")
        assert qbi.is_sstb is False  # Rentals never SSTB
        assert qbi.source == "rental"

    def test_build_qbi_from_rental_loss_returns_none(self) -> None:
        """Rental with loss returns None (no QBI)."""
        qbi = build_qbi_from_rental(Decimal("-5000"), "456 Oak Ave")
        assert qbi is None

    def test_build_qbi_from_rental_not_qualifying(self) -> None:
        """Non-qualifying rental returns None."""
        qbi = build_qbi_from_rental(
            Decimal("15000"), "789 Elm St", qualifies_safe_harbor=False
        )
        assert qbi is None


# =============================================================================
# Premium Tax Credit Tests (04-07)
# =============================================================================


class TestGetFPL:
    """Tests for get_fpl() function."""

    def test_fpl_single_person(self) -> None:
        """FPL for 1 person household."""
        fpl = get_fpl(1)
        assert fpl == Decimal("14580")

    def test_fpl_family_of_four(self) -> None:
        """FPL for standard family of 4."""
        fpl = get_fpl(4)
        assert fpl == Decimal("30000")

    def test_fpl_household_of_eight(self) -> None:
        """FPL for maximum standard size of 8."""
        fpl = get_fpl(8)
        assert fpl == Decimal("50560")

    def test_fpl_large_household(self) -> None:
        """FPL for household > 8 adds additional per person."""
        # 8-person base + 2 additional @ $5,140 each
        fpl = get_fpl(10)
        expected = Decimal("50560") + Decimal("5140") * 2
        assert fpl == expected

    def test_fpl_2025_single_person(self) -> None:
        """2025 FPL baseline reflects updated 2025 guideline."""
        fpl = get_fpl(1, tax_year=2025)
        assert fpl == Decimal("15650")


class TestGetApplicablePercentage:
    """Tests for get_applicable_percentage() function."""

    def test_below_150_fpl_zero_percent(self) -> None:
        """Income below 150% FPL contributes 0%."""
        pct = get_applicable_percentage(Decimal("100"))
        assert pct == Decimal("0")

        pct = get_applicable_percentage(Decimal("149"))
        assert pct == Decimal("0")

    def test_at_150_fpl_zero_percent(self) -> None:
        """At exactly 150% FPL, contribution is 0%."""
        pct = get_applicable_percentage(Decimal("150"))
        assert pct == Decimal("0")

    def test_175_fpl_linear_interpolation(self) -> None:
        """At 175% FPL (midpoint 150-200), contribution is 1%."""
        pct = get_applicable_percentage(Decimal("175"))
        assert pct == Decimal("0.01")

    def test_200_fpl_two_percent(self) -> None:
        """At 200% FPL, contribution is 2%."""
        pct = get_applicable_percentage(Decimal("200"))
        assert pct == Decimal("0.02")

    def test_250_fpl_four_percent(self) -> None:
        """At 250% FPL, contribution is 4%."""
        pct = get_applicable_percentage(Decimal("250"))
        assert pct == Decimal("0.04")

    def test_300_fpl_six_percent(self) -> None:
        """At 300% FPL, contribution is 6%."""
        pct = get_applicable_percentage(Decimal("300"))
        assert pct == Decimal("0.06")

    def test_400_fpl_eight_point_five_percent(self) -> None:
        """At 400% FPL, contribution is 8.5%."""
        pct = get_applicable_percentage(Decimal("400"))
        assert pct == Decimal("0.085")

    def test_above_400_fpl_capped(self) -> None:
        """Above 400% FPL, contribution stays at 8.5% (ARP extension)."""
        pct = get_applicable_percentage(Decimal("500"))
        assert pct == Decimal("0.085")


class TestGetPTCRepaymentLimit:
    """Tests for get_ptc_repayment_limit() function."""

    def test_below_200_fpl_single(self) -> None:
        """Single filer below 200% FPL has $375 limit."""
        limit = get_ptc_repayment_limit(Decimal("175"), FilingStatus.SINGLE)
        assert limit == Decimal("375")

    def test_below_200_fpl_mfj(self) -> None:
        """MFJ below 200% FPL has $750 limit."""
        limit = get_ptc_repayment_limit(
            Decimal("175"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert limit == Decimal("750")

    def test_200_to_300_fpl_single(self) -> None:
        """Single filer 200-300% FPL has $975 limit."""
        limit = get_ptc_repayment_limit(Decimal("250"), FilingStatus.SINGLE)
        assert limit == Decimal("975")

    def test_200_to_300_fpl_mfj(self) -> None:
        """MFJ 200-300% FPL has $1,950 limit."""
        limit = get_ptc_repayment_limit(
            Decimal("250"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert limit == Decimal("1950")

    def test_300_to_400_fpl_single(self) -> None:
        """Single filer 300-400% FPL has $1,625 limit."""
        limit = get_ptc_repayment_limit(Decimal("350"), FilingStatus.SINGLE)
        assert limit == Decimal("1625")

    def test_300_to_400_fpl_mfj(self) -> None:
        """MFJ 300-400% FPL has $3,250 limit."""
        limit = get_ptc_repayment_limit(
            Decimal("350"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert limit == Decimal("3250")

    def test_above_400_fpl_no_limit(self) -> None:
        """Above 400% FPL, no repayment limit."""
        limit = get_ptc_repayment_limit(Decimal("450"), FilingStatus.SINGLE)
        assert limit is None

        limit = get_ptc_repayment_limit(
            Decimal("450"), FilingStatus.MARRIED_FILING_JOINTLY
        )
        assert limit is None

    def test_hoh_same_as_single(self) -> None:
        """Head of Household uses same limits as Single."""
        limit = get_ptc_repayment_limit(Decimal("250"), FilingStatus.HEAD_OF_HOUSEHOLD)
        assert limit == Decimal("975")

    def test_qualifying_widow_same_as_mfj(self) -> None:
        """Qualifying Widow uses same limits as MFJ."""
        limit = get_ptc_repayment_limit(Decimal("250"), FilingStatus.QUALIFYING_WIDOW)
        assert limit == Decimal("1950")


class TestPremiumTaxCreditDataclass:
    """Tests for PremiumTaxCredit dataclass."""

    def test_dataclass_creation(self) -> None:
        """PremiumTaxCredit stores all fields correctly."""
        ptc = PremiumTaxCredit(
            household_size=2,
            household_income=Decimal("40000"),
            federal_poverty_level=Decimal("19720"),
            income_as_fpl_percent=Decimal("202.84"),
            annual_enrollment_premium=Decimal("7800"),
            annual_slcsp_premium=Decimal("9600"),
            applicable_percentage=Decimal("0.0211"),
            annual_contribution=Decimal("844"),
            calculated_ptc=Decimal("8756"),
            advance_ptc_received=Decimal("4800"),
            net_ptc=Decimal("3956"),
            repayment_required=False,
            repayment_amount=Decimal("0"),
            repayment_limitation=None,
            additional_credit=Decimal("3956"),
            is_eligible=True,
            ineligibility_reason=None,
            is_partial_year=False,
            coverage_months=12,
        )
        assert ptc.household_size == 2
        assert ptc.is_eligible is True
        assert ptc.additional_credit == Decimal("3956")


class TestCalculatePremiumTaxCredit:
    """Tests for calculate_premium_tax_credit() function."""

    @pytest.fixture
    def sample_1095a(self) -> Form1095A:
        """Create sample Form 1095-A for testing."""
        return Form1095A(
            recipient_name="John Smith",
            recipient_tin="123-45-6789",
            marketplace_id="FFM123456",
            policy_number="POL123",
            policy_start_date="2024-01-01",
            annual_enrollment_premium=Decimal("7800"),
            annual_slcsp_premium=Decimal("9600"),
            annual_advance_ptc=Decimal("4800"),
            monthly_enrollment_premium=[Decimal("650")] * 12,
            monthly_slcsp_premium=[Decimal("800")] * 12,
            monthly_advance_ptc=[Decimal("400")] * 12,
        )

    def test_eligible_additional_credit_due(self, sample_1095a: Form1095A) -> None:
        """Taxpayer owes no repayment, gets additional credit."""
        result = calculate_premium_tax_credit(
            household_income=Decimal("40000"),  # ~203% FPL for 2
            household_size=2,
            form_1095a=sample_1095a,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_eligible is True
        assert result.repayment_required is False
        assert result.additional_credit > Decimal("0")

    def test_repayment_required(self, sample_1095a: Form1095A) -> None:
        """Higher income means repayment required."""
        # Create 1095-A with more advance credit than should have been received
        form = Form1095A(
            recipient_name="Jane Doe",
            recipient_tin="987-65-4321",
            marketplace_id="FFM999999",
            policy_number="POL999",
            policy_start_date="2024-01-01",
            annual_enrollment_premium=Decimal("6000"),
            annual_slcsp_premium=Decimal("7200"),
            annual_advance_ptc=Decimal("5000"),  # Received too much
            monthly_enrollment_premium=[Decimal("500")] * 12,
            monthly_slcsp_premium=[Decimal("600")] * 12,
            monthly_advance_ptc=[Decimal("417")] * 12,
        )
        result = calculate_premium_tax_credit(
            household_income=Decimal("75000"),  # ~380% FPL for 2
            household_size=2,
            form_1095a=form,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_eligible is True
        assert result.repayment_required is True
        assert result.repayment_amount > Decimal("0")

    def test_repayment_limited(self) -> None:
        """Repayment capped at limitation amount."""
        form = Form1095A(
            recipient_name="Test User",
            recipient_tin="111-22-3333",
            marketplace_id="FFM111222",
            policy_number="POL111",
            policy_start_date="2024-01-01",
            annual_enrollment_premium=Decimal("6000"),
            annual_slcsp_premium=Decimal("7200"),
            annual_advance_ptc=Decimal("6000"),  # Large advance
            monthly_enrollment_premium=[Decimal("500")] * 12,
            monthly_slcsp_premium=[Decimal("600")] * 12,
            monthly_advance_ptc=[Decimal("500")] * 12,
        )
        result = calculate_premium_tax_credit(
            household_income=Decimal("35000"),  # ~237% FPL for 1
            household_size=1,
            form_1095a=form,
            filing_status=FilingStatus.SINGLE,
        )
        # Should be limited
        assert result.repayment_required is True
        assert result.repayment_limitation == Decimal("975")
        assert result.repayment_amount <= Decimal("975")

    def test_ineligible_below_100_fpl(self, sample_1095a: Form1095A) -> None:
        """Income below 100% FPL is ineligible (Medicaid territory)."""
        result = calculate_premium_tax_credit(
            household_income=Decimal("10000"),  # Below FPL
            household_size=2,
            form_1095a=sample_1095a,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_eligible is False
        assert result.ineligibility_reason is not None
        assert "100% FPL" in result.ineligibility_reason

    def test_partial_year_coverage(self) -> None:
        """Partial year coverage detected from monthly data."""
        form = Form1095A(
            recipient_name="Part Year",
            recipient_tin="555-55-5555",
            marketplace_id="FFM555555",
            policy_number="POL555",
            policy_start_date="2024-07-01",
            annual_enrollment_premium=Decimal("3900"),  # 6 months
            annual_slcsp_premium=Decimal("4800"),  # 6 months
            annual_advance_ptc=Decimal("2400"),  # 6 months
            # Only 6 months with premiums
            monthly_enrollment_premium=[Decimal("0")] * 6 + [Decimal("650")] * 6,
            monthly_slcsp_premium=[Decimal("0")] * 6 + [Decimal("800")] * 6,
            monthly_advance_ptc=[Decimal("0")] * 6 + [Decimal("400")] * 6,
        )
        result = calculate_premium_tax_credit(
            household_income=Decimal("40000"),
            household_size=2,
            form_1095a=form,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_partial_year is True
        assert result.coverage_months == 6

    def test_full_year_coverage(self, sample_1095a: Form1095A) -> None:
        """Full year coverage correctly identified."""
        result = calculate_premium_tax_credit(
            household_income=Decimal("40000"),
            household_size=2,
            form_1095a=sample_1095a,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.is_partial_year is False
        assert result.coverage_months == 12

    def test_high_income_no_repayment_limit(self) -> None:
        """Above 400% FPL, full repayment required (no limit)."""
        form = Form1095A(
            recipient_name="High Income",
            recipient_tin="999-99-9999",
            marketplace_id="FFM999999",
            policy_number="POL999",
            policy_start_date="2024-01-01",
            annual_enrollment_premium=Decimal("6000"),
            annual_slcsp_premium=Decimal("7200"),
            annual_advance_ptc=Decimal("5000"),
            monthly_enrollment_premium=[Decimal("500")] * 12,
            monthly_slcsp_premium=[Decimal("600")] * 12,
            monthly_advance_ptc=[Decimal("417")] * 12,
        )
        result = calculate_premium_tax_credit(
            household_income=Decimal("100000"),  # >400% FPL
            household_size=2,
            form_1095a=form,
            filing_status=FilingStatus.SINGLE,
        )
        assert result.repayment_limitation is None
        # Should repay full excess (no cap)

    def test_mfj_repayment_limits_higher(self) -> None:
        """MFJ has higher repayment limits than single."""
        form = Form1095A(
            recipient_name="Married Couple",
            recipient_tin="888-88-8888",
            marketplace_id="FFM888888",
            policy_number="POL888",
            policy_start_date="2024-01-01",
            annual_enrollment_premium=Decimal("6000"),
            annual_slcsp_premium=Decimal("7200"),
            annual_advance_ptc=Decimal("6000"),
            monthly_enrollment_premium=[Decimal("500")] * 12,
            monthly_slcsp_premium=[Decimal("600")] * 12,
            monthly_advance_ptc=[Decimal("500")] * 12,
        )
        # Same income, different filing status
        single_result = calculate_premium_tax_credit(
            household_income=Decimal("35000"),
            household_size=1,
            form_1095a=form,
            filing_status=FilingStatus.SINGLE,
        )
        mfj_result = calculate_premium_tax_credit(
            household_income=Decimal("35000"),
            household_size=1,
            form_1095a=form,
            filing_status=FilingStatus.MARRIED_FILING_JOINTLY,
        )
        # MFJ limit is 2x single
        assert mfj_result.repayment_limitation == single_result.repayment_limitation * 2

    def test_ptc_capped_at_enrollment_premium(self, sample_1095a: Form1095A) -> None:
        """PTC cannot exceed actual enrollment premium."""
        # Low income means calculated PTC could be very high
        result = calculate_premium_tax_credit(
            household_income=Decimal("25000"),  # ~127% FPL for 2
            household_size=2,
            form_1095a=sample_1095a,
            filing_status=FilingStatus.SINGLE,
        )
        # Calculated PTC cannot exceed enrolled premium
        assert result.calculated_ptc <= sample_1095a.annual_enrollment_premium
