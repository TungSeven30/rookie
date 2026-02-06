"""Tests for 1120-S Page 1 and Schedule K calculator functions.

TDD tests for compute_page1 and compute_schedule_k pure functions.
Tests cover basic computation, zero amounts, missing keys, and
Schedule K Box 1 linkage to Page 1 ordinary business income.
"""

from decimal import Decimal

import pytest

from src.agents.business_tax.calculator import (
    Page1Result,
    ScheduleM1Result,
    ScheduleM2Result,
    compute_page1,
    compute_schedule_k,
)
from src.agents.business_tax.models import ScheduleK


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def basic_mapped_amounts() -> dict[str, Decimal]:
    """Mapped amounts for a typical small S-Corp."""
    return {
        "page1_line1a": Decimal("500000"),  # Gross receipts
        "page1_line1b": Decimal("5000"),  # Returns and allowances
        "page1_line2": Decimal("200000"),  # COGS
        "page1_line7": Decimal("80000"),  # Officer compensation
        "page1_line8": Decimal("60000"),  # Salaries/wages
        "page1_line9": Decimal("3000"),  # Repairs
        "page1_line12": Decimal("8000"),  # Taxes and licenses
        "page1_line13": Decimal("24000"),  # Rents
        "page1_line14": Decimal("2000"),  # Interest
        "page1_line15": Decimal("10000"),  # Depreciation
        "page1_line17": Decimal("5000"),  # Advertising
        "page1_line18": Decimal("4000"),  # Pension/profit-sharing
        "page1_line19": Decimal("6000"),  # Employee benefits
        "page1_line20": Decimal("3000"),  # Other deductions
    }


# =============================================================================
# Page 1: Basic income/deductions computation
# =============================================================================


class TestComputePage1Basic:
    """Test compute_page1 with typical mapped amounts."""

    def test_gross_receipts(self, basic_mapped_amounts: dict[str, Decimal]) -> None:
        """Gross receipts equals page1_line1a."""
        result = compute_page1(basic_mapped_amounts)
        assert result.gross_receipts == Decimal("500000")

    def test_returns_and_allowances(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Returns and allowances equals page1_line1b."""
        result = compute_page1(basic_mapped_amounts)
        assert result.returns_and_allowances == Decimal("5000")

    def test_cost_of_goods_sold(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """COGS equals page1_line2."""
        result = compute_page1(basic_mapped_amounts)
        assert result.cost_of_goods_sold == Decimal("200000")

    def test_gross_profit(self, basic_mapped_amounts: dict[str, Decimal]) -> None:
        """Gross profit = 1a - 1b - 2 = 500000 - 5000 - 200000 = 295000."""
        result = compute_page1(basic_mapped_amounts)
        assert result.gross_profit == Decimal("295000")

    def test_total_income(self, basic_mapped_amounts: dict[str, Decimal]) -> None:
        """Total income = gross_profit + line4 + line5 = 295000 + 0 + 0."""
        result = compute_page1(basic_mapped_amounts)
        assert result.total_income == Decimal("295000")

    def test_total_income_with_other(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Total income includes Form 4797 gain and other income."""
        basic_mapped_amounts["page1_line4"] = Decimal("10000")
        basic_mapped_amounts["page1_line5"] = Decimal("2000")
        result = compute_page1(basic_mapped_amounts)
        assert result.total_income == Decimal("307000")

    def test_officer_compensation(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Officer compensation from line 7."""
        result = compute_page1(basic_mapped_amounts)
        assert result.officer_compensation == Decimal("80000")

    def test_total_deductions(self, basic_mapped_amounts: dict[str, Decimal]) -> None:
        """Total deductions = sum of lines 7-20."""
        result = compute_page1(basic_mapped_amounts)
        # 80000+60000+3000+8000+24000+2000+10000+5000+4000+6000+3000 = 205000
        assert result.total_deductions == Decimal("205000")

    def test_ordinary_business_income(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Ordinary business income = total income - total deductions."""
        result = compute_page1(basic_mapped_amounts)
        # 295000 - 205000 = 90000
        assert result.ordinary_business_income == Decimal("90000")

    def test_returns_page1_result(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Function returns a Page1Result dataclass."""
        result = compute_page1(basic_mapped_amounts)
        assert isinstance(result, Page1Result)


# =============================================================================
# Page 1: Zero/startup scenario
# =============================================================================


class TestComputePage1Zero:
    """Test compute_page1 with zero or empty mapped amounts."""

    def test_empty_dict(self) -> None:
        """Empty dict produces all-zero result."""
        result = compute_page1({})
        assert result.gross_receipts == Decimal("0")
        assert result.total_income == Decimal("0")
        assert result.total_deductions == Decimal("0")
        assert result.ordinary_business_income == Decimal("0")

    def test_startup_no_revenue(self) -> None:
        """Startup with expenses only yields negative income."""
        amounts = {
            "page1_line7": Decimal("50000"),  # Officer comp
            "page1_line13": Decimal("12000"),  # Rent
        }
        result = compute_page1(amounts)
        assert result.gross_receipts == Decimal("0")
        assert result.gross_profit == Decimal("0")
        assert result.total_deductions == Decimal("62000")
        assert result.ordinary_business_income == Decimal("-62000")


# =============================================================================
# Page 1: Missing line amounts default to zero
# =============================================================================


class TestComputePage1Defaults:
    """Test that missing line amounts default to Decimal('0')."""

    def test_missing_cogs(self) -> None:
        """Missing COGS defaults to zero."""
        amounts = {"page1_line1a": Decimal("100000")}
        result = compute_page1(amounts)
        assert result.cost_of_goods_sold == Decimal("0")
        assert result.gross_profit == Decimal("100000")

    def test_missing_bad_debts(self) -> None:
        """Missing bad debts defaults to zero."""
        result = compute_page1({})
        assert result.bad_debts == Decimal("0")

    def test_missing_depreciation(self) -> None:
        """Missing depreciation defaults to zero."""
        result = compute_page1({})
        assert result.depreciation == Decimal("0")

    def test_all_deduction_lines_default_zero(self) -> None:
        """All deduction lines default to Decimal('0')."""
        result = compute_page1({})
        assert result.officer_compensation == Decimal("0")
        assert result.salaries_wages == Decimal("0")
        assert result.repairs == Decimal("0")
        assert result.bad_debts == Decimal("0")
        assert result.taxes_licenses == Decimal("0")
        assert result.rents == Decimal("0")
        assert result.interest == Decimal("0")
        assert result.depreciation == Decimal("0")
        assert result.advertising == Decimal("0")
        assert result.pension_profit_sharing == Decimal("0")
        assert result.employee_benefits == Decimal("0")
        assert result.other_deductions == Decimal("0")


# =============================================================================
# Schedule K: Box 1 linkage
# =============================================================================


class TestComputeScheduleK:
    """Test compute_schedule_k with Page 1 result and separately stated items."""

    def test_box1_equals_page1_oi(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Schedule K Box 1 equals Page 1 ordinary business income."""
        page1 = compute_page1(basic_mapped_amounts)
        sched_k = compute_schedule_k(page1)
        assert sched_k.ordinary_income == page1.ordinary_business_income

    def test_box1_negative_income(self) -> None:
        """Box 1 reflects negative ordinary business income (loss)."""
        amounts = {"page1_line7": Decimal("50000")}
        page1 = compute_page1(amounts)
        sched_k = compute_schedule_k(page1)
        assert sched_k.ordinary_income == Decimal("-50000")

    def test_separately_stated_items(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Separately stated items populate correct Schedule K boxes."""
        page1 = compute_page1(basic_mapped_amounts)
        separately_stated = {
            "interest_income": Decimal("3000"),
            "dividends": Decimal("1500"),
            "charitable_contributions": Decimal("2000"),
            "tax_exempt_interest": Decimal("500"),
        }
        sched_k = compute_schedule_k(page1, separately_stated)
        assert sched_k.interest_income == Decimal("3000")
        assert sched_k.dividends == Decimal("1500")
        assert sched_k.charitable_contributions == Decimal("2000")
        assert sched_k.tax_exempt_interest == Decimal("500")

    def test_all_defaults_zero(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """All Schedule K boxes except Box 1 default to Decimal('0')."""
        page1 = compute_page1(basic_mapped_amounts)
        sched_k = compute_schedule_k(page1)
        assert sched_k.interest_income == Decimal("0")
        assert sched_k.dividends == Decimal("0")
        assert sched_k.royalties == Decimal("0")
        assert sched_k.net_short_term_capital_gain == Decimal("0")
        assert sched_k.net_long_term_capital_gain == Decimal("0")
        assert sched_k.charitable_contributions == Decimal("0")
        assert sched_k.distributions == Decimal("0")
        assert sched_k.nondeductible_expenses == Decimal("0")
        assert sched_k.tax_exempt_interest == Decimal("0")

    def test_returns_schedule_k_model(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Function returns a ScheduleK Pydantic model."""
        page1 = compute_page1(basic_mapped_amounts)
        sched_k = compute_schedule_k(page1)
        assert isinstance(sched_k, ScheduleK)

    def test_unknown_separately_stated_key_ignored(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Unknown keys in separately_stated dict are ignored."""
        page1 = compute_page1(basic_mapped_amounts)
        separately_stated = {
            "interest_income": Decimal("1000"),
            "unknown_field": Decimal("999"),
        }
        sched_k = compute_schedule_k(page1, separately_stated)
        assert sched_k.interest_income == Decimal("1000")

    def test_distributions_populated(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Distributions flow through to Schedule K."""
        page1 = compute_page1(basic_mapped_amounts)
        separately_stated = {"distributions": Decimal("25000")}
        sched_k = compute_schedule_k(page1, separately_stated)
        assert sched_k.distributions == Decimal("25000")

    def test_nondeductible_expenses_populated(
        self, basic_mapped_amounts: dict[str, Decimal]
    ) -> None:
        """Nondeductible expenses flow through to Schedule K Box 16c."""
        page1 = compute_page1(basic_mapped_amounts)
        separately_stated = {"nondeductible_expenses": Decimal("3500")}
        sched_k = compute_schedule_k(page1, separately_stated)
        assert sched_k.nondeductible_expenses == Decimal("3500")
