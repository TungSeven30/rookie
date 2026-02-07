"""Tests for 1120-S Schedule L, M-1, and M-2 calculator functions.

TDD tests for compute_schedule_l, compute_schedule_m1, and compute_schedule_m2.
Tests cover balance sheet balancing, retained earnings updates, book-tax
reconciliation, and AAA tracking.
"""

from decimal import Decimal

import pytest

from src.agents.business_tax.calculator import (
    ScheduleM1Result,
    ScheduleM2Result,
    compute_schedule_l,
    compute_schedule_m1,
    compute_schedule_m2,
)
from src.agents.business_tax.models import ScheduleL, ScheduleLLine


# =============================================================================
# Helpers
# =============================================================================


def _make_schedule_l_line(
    line_number: int,
    description: str,
    beginning: str = "0",
    ending: str = "0",
) -> ScheduleLLine:
    """Create a ScheduleLLine with shorthand amounts."""
    return ScheduleLLine(
        line_number=line_number,
        description=description,
        beginning_amount=Decimal(beginning),
        ending_amount=Decimal(ending),
    )


def _make_zero_schedule_l() -> ScheduleL:
    """Create a ScheduleL with all zero amounts."""
    return ScheduleL(
        cash=_make_schedule_l_line(1, "Cash"),
        trade_receivables=_make_schedule_l_line(2, "Trade receivables"),
        inventories=_make_schedule_l_line(3, "Inventories"),
        us_government_obligations=_make_schedule_l_line(4, "US govt obligations"),
        tax_exempt_securities=_make_schedule_l_line(5, "Tax-exempt securities"),
        other_current_assets=_make_schedule_l_line(6, "Other current assets"),
        loans_to_shareholders=_make_schedule_l_line(7, "Loans to shareholders"),
        mortgage_real_estate=_make_schedule_l_line(8, "Mortgage real estate"),
        other_investments=_make_schedule_l_line(9, "Other investments"),
        buildings_other_depreciable=_make_schedule_l_line(10, "Buildings"),
        depreciable_accumulated_depreciation=_make_schedule_l_line(
            11, "Accum depreciation"
        ),
        depletable_assets=_make_schedule_l_line(12, "Depletable assets"),
        land=_make_schedule_l_line(13, "Land"),
        intangible_assets=_make_schedule_l_line(14, "Intangible assets"),
        other_assets=_make_schedule_l_line(15, "Other assets"),
        accounts_payable=_make_schedule_l_line(16, "Accounts payable"),
        mortgages_bonds_payable_less_1yr=_make_schedule_l_line(17, "Short-term debt"),
        other_current_liabilities=_make_schedule_l_line(18, "Other current liabilities"),
        loans_from_shareholders=_make_schedule_l_line(19, "Loans from shareholders"),
        mortgages_bonds_payable_1yr_plus=_make_schedule_l_line(20, "Long-term debt"),
        other_liabilities=_make_schedule_l_line(21, "Other liabilities"),
        capital_stock=_make_schedule_l_line(22, "Capital stock"),
        additional_paid_in_capital=_make_schedule_l_line(23, "APIC"),
        retained_earnings=_make_schedule_l_line(24, "Retained earnings"),
        adjustments_to_shareholders_equity=_make_schedule_l_line(
            25, "Adjustments to equity"
        ),
        less_cost_treasury_stock=_make_schedule_l_line(26, "Treasury stock"),
    )


# =============================================================================
# Schedule L: Balance sheet tests
# =============================================================================


class TestComputeScheduleL:
    """Test compute_schedule_l balance sheet computation."""

    def test_balanced_ending(self) -> None:
        """Balance sheet with assets = liabilities + equity is balanced."""
        # Assets: 50000 + 30000 = 80000
        # Liabilities: 20000
        # Equity: capital_stock 10000 + RE (0 + 50000 - 0) = 50000 -> 60000
        # Total L+E = 80000 -> balanced
        mapped = {
            "schedule_l_line1": Decimal("50000"),  # Cash
            "schedule_l_line2": Decimal("30000"),  # Receivables
            "schedule_l_line16": Decimal("20000"),  # AP
            "schedule_l_line22": Decimal("10000"),  # Capital stock
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=None,
            current_year_net_income=Decimal("50000"),
            current_year_distributions=Decimal("0"),
        )
        assert isinstance(result, ScheduleL)
        assert result.is_balanced_ending

    def test_retained_earnings_updated(self) -> None:
        """Retained earnings = beginning + net income - distributions."""
        prior = _make_zero_schedule_l()
        # Set prior year retained earnings ending = 40000
        prior.retained_earnings = _make_schedule_l_line(24, "Retained earnings", "0", "40000")

        mapped = {
            "schedule_l_line1": Decimal("100000"),  # Cash (ending)
            "schedule_l_line22": Decimal("10000"),  # Capital stock
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=prior,
            current_year_net_income=Decimal("30000"),
            current_year_distributions=Decimal("10000"),
        )
        # Retained earnings ending = 40000 + 30000 - 10000 = 60000
        assert result.retained_earnings.ending_amount == Decimal("60000")
        # Beginning should carry forward prior year ending
        assert result.retained_earnings.beginning_amount == Decimal("40000")

    def test_beginning_from_prior_year(self) -> None:
        """Beginning amounts come from prior year ending amounts."""
        prior = _make_zero_schedule_l()
        prior.cash = _make_schedule_l_line(1, "Cash", "0", "25000")
        prior.accounts_payable = _make_schedule_l_line(16, "AP", "0", "10000")
        prior.capital_stock = _make_schedule_l_line(22, "Capital stock", "0", "5000")
        prior.retained_earnings = _make_schedule_l_line(
            24, "Retained earnings", "0", "10000"
        )

        mapped = {
            "schedule_l_line1": Decimal("30000"),
            "schedule_l_line16": Decimal("10000"),
            "schedule_l_line22": Decimal("5000"),
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=prior,
            current_year_net_income=Decimal("5000"),
            current_year_distributions=Decimal("0"),
        )
        assert result.cash.beginning_amount == Decimal("25000")
        assert result.accounts_payable.beginning_amount == Decimal("10000")
        assert result.capital_stock.beginning_amount == Decimal("5000")

    def test_first_year_zero_beginning(self) -> None:
        """First year (no prior) has zero beginning amounts."""
        mapped = {
            "schedule_l_line1": Decimal("50000"),
            "schedule_l_line22": Decimal("10000"),
            "schedule_l_line24": Decimal("40000"),
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=None,
            current_year_net_income=Decimal("40000"),
            current_year_distributions=Decimal("0"),
        )
        assert result.cash.beginning_amount == Decimal("0")
        assert result.retained_earnings.beginning_amount == Decimal("0")

    def test_imbalance_detected(self) -> None:
        """Imbalanced schedule L has is_balanced_ending = False."""
        mapped = {
            "schedule_l_line1": Decimal("100000"),  # Assets
            "schedule_l_line16": Decimal("30000"),  # Liabilities
            # No equity -- imbalanced
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=None,
            current_year_net_income=Decimal("0"),
            current_year_distributions=Decimal("0"),
        )
        assert not result.is_balanced_ending

    def test_accumulated_depreciation_negative(self) -> None:
        """Accumulated depreciation is stored as negative on the asset side."""
        mapped = {
            "schedule_l_line1": Decimal("50000"),
            "schedule_l_line10a": Decimal("100000"),
            "schedule_l_line10b": Decimal("-30000"),  # Contra-asset
            "schedule_l_line22": Decimal("10000"),
            "schedule_l_line24": Decimal("110000"),
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=None,
            current_year_net_income=Decimal("0"),
            current_year_distributions=Decimal("0"),
        )
        assert result.depreciable_accumulated_depreciation.ending_amount == Decimal(
            "-30000"
        )
        # Total assets = 50000 + 100000 + (-30000) = 120000
        assert result.total_assets_ending == Decimal("120000")

    def test_liability_and_equity_normalized_to_positive(self) -> None:
        """Credit-sign inputs for liability/equity are normalized to positive values."""
        mapped = {
            "schedule_l_line1": Decimal("100000"),
            "schedule_l_line16": Decimal("-40000"),  # AP from credit-normal TB sign
            "schedule_l_line22": Decimal("-60000"),  # Capital stock from credit sign
        }
        result = compute_schedule_l(
            mapped_amounts=mapped,
            prior_year_schedule_l=None,
            current_year_net_income=Decimal("0"),
            current_year_distributions=Decimal("0"),
        )
        assert result.accounts_payable.ending_amount == Decimal("40000")
        assert result.capital_stock.ending_amount == Decimal("60000")
        assert result.is_balanced_ending


# =============================================================================
# Schedule M-1: Book-to-tax reconciliation
# =============================================================================


class TestComputeScheduleM1:
    """Test compute_schedule_m1 book-tax reconciliation."""

    def test_book_equals_tax_simplest(self) -> None:
        """When book income equals tax income, no adjustments needed."""
        result = compute_schedule_m1(
            book_income=Decimal("90000"),
            tax_income=Decimal("90000"),
        )
        assert isinstance(result, ScheduleM1Result)
        assert result.book_income == Decimal("90000")
        assert result.income_per_return == Decimal("90000")

    def test_tax_exempt_income_difference(self) -> None:
        """Tax-exempt interest is on books but not on the return (Line 5)."""
        result = compute_schedule_m1(
            book_income=Decimal("95000"),
            tax_income=Decimal("90000"),
            tax_exempt_income=Decimal("5000"),
        )
        assert result.book_income == Decimal("95000")
        # Tax-exempt income goes on subtraction side (IRS Line 5)
        assert result.income_on_return_not_on_books == Decimal("5000")
        assert result.income_per_return == Decimal("90000")

    def test_nondeductible_expenses(self) -> None:
        """Nondeductible expenses reduce book income but not tax income."""
        result = compute_schedule_m1(
            book_income=Decimal("87000"),
            tax_income=Decimal("90000"),
            nondeductible_expenses=Decimal("3000"),
        )
        assert result.book_income == Decimal("87000")
        assert result.expenses_on_books_not_on_return == Decimal("3000")
        assert result.income_per_return == Decimal("90000")

    def test_combined_differences(self) -> None:
        """Both tax-exempt income and nondeductible expenses."""
        # Book income = 92000 (includes 5000 tax-exempt, minus 3000 nondeductible)
        # Tax income = 90000
        result = compute_schedule_m1(
            book_income=Decimal("92000"),
            tax_income=Decimal("90000"),
            tax_exempt_income=Decimal("5000"),
            nondeductible_expenses=Decimal("3000"),
        )
        assert result.book_income == Decimal("92000")
        assert result.income_per_return == Decimal("90000")

    def test_m1_line_totals(self) -> None:
        """Verify intermediate line totals."""
        result = compute_schedule_m1(
            book_income=Decimal("100000"),
            tax_income=Decimal("100000"),
        )
        assert result.total_lines_1_3 == (
            result.book_income
            + result.income_on_books_not_on_return
            + result.expenses_on_return_not_on_books
        )
        assert result.total_lines_5_6 == (
            result.income_on_return_not_on_books
            + result.expenses_on_books_not_on_return
        )


# =============================================================================
# Schedule M-2: AAA tracking
# =============================================================================


class TestComputeScheduleM2:
    """Test compute_schedule_m2 AAA tracking."""

    def test_aaa_increases_from_income(self) -> None:
        """AAA increases from ordinary income and other additions."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("50000"),
            ordinary_income=Decimal("90000"),
            separately_stated_net=Decimal("5000"),
            nondeductible_expenses=Decimal("0"),
            distributions=Decimal("0"),
        )
        assert isinstance(result, ScheduleM2Result)
        assert result.aaa_ending == Decimal("145000")

    def test_aaa_decreases_from_distributions(self) -> None:
        """AAA decreases from distributions."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("100000"),
            ordinary_income=Decimal("50000"),
            separately_stated_net=Decimal("0"),
            nondeductible_expenses=Decimal("0"),
            distributions=Decimal("40000"),
        )
        assert result.aaa_ending == Decimal("110000")
        assert result.distributions == Decimal("40000")

    def test_aaa_negative_from_losses(self) -> None:
        """AAA can go negative from losses (but not from distributions)."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("10000"),
            ordinary_income=Decimal("-30000"),
            separately_stated_net=Decimal("0"),
            nondeductible_expenses=Decimal("0"),
            distributions=Decimal("0"),
        )
        assert result.aaa_ending == Decimal("-20000")

    def test_aaa_nondeductible_reduces(self) -> None:
        """Nondeductible expenses reduce AAA."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("80000"),
            ordinary_income=Decimal("20000"),
            separately_stated_net=Decimal("0"),
            nondeductible_expenses=Decimal("5000"),
            distributions=Decimal("0"),
        )
        # 80000 + 20000 - 5000 = 95000
        assert result.aaa_ending == Decimal("95000")

    def test_aaa_first_year(self) -> None:
        """First year starts at zero."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("0"),
            ordinary_income=Decimal("90000"),
            separately_stated_net=Decimal("3000"),
            nondeductible_expenses=Decimal("1000"),
            distributions=Decimal("20000"),
        )
        # 0 + 90000 + 3000 - 1000 - 20000 = 72000
        assert result.aaa_ending == Decimal("72000")
        assert result.aaa_beginning == Decimal("0")

    def test_aaa_fields_populated(self) -> None:
        """All ScheduleM2Result fields are populated correctly."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("50000"),
            ordinary_income=Decimal("30000"),
            separately_stated_net=Decimal("5000"),
            nondeductible_expenses=Decimal("2000"),
            distributions=Decimal("10000"),
        )
        assert result.aaa_beginning == Decimal("50000")
        assert result.ordinary_income == Decimal("30000")
        assert result.other_additions == Decimal("5000")
        assert result.other_reductions is not None
        assert result.other_reductions == Decimal("2000")
        assert result.distributions == Decimal("10000")

    def test_distributions_do_not_drive_aaa_below_zero(self) -> None:
        """Distributions are limited so they do not create negative AAA by themselves."""
        result = compute_schedule_m2(
            aaa_beginning=Decimal("100"),
            ordinary_income=Decimal("0"),
            separately_stated_net=Decimal("0"),
            nondeductible_expenses=Decimal("0"),
            distributions=Decimal("300"),
        )
        assert result.distributions == Decimal("100")
        assert result.aaa_ending == Decimal("0")
