"""Comprehensive tests for shareholder basis tracking (Form 7203).

Tests IRS ordering rules for S-Corp shareholder basis adjustments:
1. INCREASE stock basis for income items
2. DECREASE for distributions (not below zero; excess = taxable capital gain)
3. DECREASE for nondeductible expenses (not below zero)
4. DECREASE for losses (stock first, then debt; excess suspended)

All arithmetic is Decimal. No floating point allowed.
"""

from decimal import Decimal

import pytest

from src.agents.business_tax.basis import (
    BasisAdjustmentInputs,
    BasisResult,
    calculate_shareholder_basis,
)


# =============================================================================
# Helpers
# =============================================================================

D = Decimal


def _inputs(**kwargs) -> BasisAdjustmentInputs:
    """Build BasisAdjustmentInputs with sensible defaults (all zeros)."""
    defaults = {
        "ordinary_income": D("0"),
        "separately_stated_income": D("0"),
        "tax_exempt_income": D("0"),
        "excess_depletion": D("0"),
        "non_dividend_distributions": D("0"),
        "nondeductible_expenses": D("0"),
        "oil_gas_depletion": D("0"),
        "ordinary_loss": D("0"),
        "separately_stated_losses": D("0"),
    }
    defaults.update(kwargs)
    return BasisAdjustmentInputs(**defaults)


# =============================================================================
# BasisAdjustmentInputs immutability
# =============================================================================


class TestBasisAdjustmentInputsImmutability:
    """BasisAdjustmentInputs is a frozen dataclass -- no mutation allowed."""

    def test_frozen_rejects_mutation(self) -> None:
        adj = _inputs(ordinary_income=D("100"))
        with pytest.raises(AttributeError):
            adj.ordinary_income = D("999")  # type: ignore[misc]

    def test_all_fields_default_to_zero(self) -> None:
        adj = _inputs()
        assert adj.ordinary_income == D("0")
        assert adj.separately_stated_income == D("0")
        assert adj.tax_exempt_income == D("0")
        assert adj.excess_depletion == D("0")
        assert adj.non_dividend_distributions == D("0")
        assert adj.nondeductible_expenses == D("0")
        assert adj.oil_gas_depletion == D("0")
        assert adj.ordinary_loss == D("0")
        assert adj.separately_stated_losses == D("0")


# =============================================================================
# Basic income tests (Step 1)
# =============================================================================


class TestIncomeIncreasesBasis:
    """Income items increase stock basis in Step 1."""

    def test_ordinary_income_increases_stock_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_income=D("50")),
        )
        assert result.ending_stock_basis == D("150")

    def test_tax_exempt_income_increases_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(tax_exempt_income=D("25")),
        )
        assert result.ending_stock_basis == D("125")

    def test_multiple_income_types_sum_correctly(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_income=D("50"),
                separately_stated_income=D("30"),
                tax_exempt_income=D("20"),
                excess_depletion=D("10"),
            ),
        )
        # 100 + 50 + 30 + 20 + 10 = 210
        assert result.ending_stock_basis == D("210")

    def test_separately_stated_income_increases_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(separately_stated_income=D("75")),
        )
        assert result.ending_stock_basis == D("75")

    def test_excess_depletion_increases_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("200"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(excess_depletion=D("15")),
        )
        assert result.ending_stock_basis == D("215")


# =============================================================================
# Distribution tests (Step 2)
# =============================================================================


class TestDistributions:
    """Distributions decrease stock basis (not below zero) in Step 2."""

    def test_distribution_within_basis_reduces_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("150"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(non_dividend_distributions=D("50")),
        )
        assert result.ending_stock_basis == D("100")
        assert result.distributions_nontaxable == D("50")
        assert result.distributions_taxable == D("0")

    def test_distribution_exceeding_basis_creates_taxable_gain(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(non_dividend_distributions=D("150")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.distributions_nontaxable == D("100")
        assert result.distributions_taxable == D("50")

    def test_zero_basis_shareholder_all_distributions_taxable(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(non_dividend_distributions=D("100")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.distributions_nontaxable == D("0")
        assert result.distributions_taxable == D("100")

    def test_distribution_applied_after_income_increase(self) -> None:
        """Income first (Step 1) makes more distributions nontaxable (Step 2)."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_income=D("100"),
                non_dividend_distributions=D("120"),
            ),
        )
        # After Step 1: 50 + 100 = 150
        # Step 2: 150 - 120 = 30, all nontaxable
        assert result.ending_stock_basis == D("30")
        assert result.distributions_nontaxable == D("120")
        assert result.distributions_taxable == D("0")

    def test_distribution_exactly_equals_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(non_dividend_distributions=D("100")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.distributions_nontaxable == D("100")
        assert result.distributions_taxable == D("0")


# =============================================================================
# Nondeductible expense tests (Step 3)
# =============================================================================


class TestNondeductibleExpenses:
    """Nondeductible expenses decrease basis after distributions (Step 3)."""

    def test_nondeductible_expenses_reduce_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("200"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(nondeductible_expenses=D("30")),
        )
        assert result.ending_stock_basis == D("170")

    def test_nondeductible_not_below_zero(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("20"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(nondeductible_expenses=D("50")),
        )
        assert result.ending_stock_basis == D("0")

    def test_oil_gas_depletion_reduces_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(oil_gas_depletion=D("25")),
        )
        assert result.ending_stock_basis == D("75")

    def test_nondeductible_plus_oil_gas_combined(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                nondeductible_expenses=D("40"),
                oil_gas_depletion=D("20"),
            ),
        )
        # 100 - 40 - 20 = 40
        assert result.ending_stock_basis == D("40")

    def test_ordering_distributions_before_nondeductible(self) -> None:
        """Distributions (Step 2) come before nondeductible (Step 3)."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                non_dividend_distributions=D("80"),
                nondeductible_expenses=D("30"),
            ),
        )
        # Step 2: 100 - 80 = 20
        # Step 3: 20 - 30 -> clamped to 0
        assert result.ending_stock_basis == D("0")
        assert result.distributions_nontaxable == D("80")
        assert result.distributions_taxable == D("0")


# =============================================================================
# Loss tests (Step 4)
# =============================================================================


class TestLosses:
    """Losses decrease stock basis, then debt basis, then suspend (Step 4)."""

    def test_losses_reduce_stock_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("200"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_loss=D("80")),
        )
        assert result.ending_stock_basis == D("120")
        assert result.losses_allowed == D("80")
        assert result.losses_limited_by_basis == D("0")

    def test_losses_not_below_zero_stock(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_loss=D("80")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.losses_allowed == D("50")
        assert result.losses_limited_by_basis == D("30")
        assert result.suspended_losses == D("30")

    def test_losses_spill_to_debt_basis(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("100"),
            adjustments=_inputs(ordinary_loss=D("120")),
        )
        # Stock absorbs 50, debt absorbs 70
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("30")
        assert result.losses_allowed == D("120")
        assert result.losses_limited_by_basis == D("0")

    def test_losses_exceed_stock_and_debt_suspended(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("30"),
            adjustments=_inputs(ordinary_loss=D("100")),
        )
        # Stock absorbs 50, debt absorbs 30, 20 suspended
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("0")
        assert result.losses_allowed == D("80")
        assert result.losses_limited_by_basis == D("20")
        assert result.suspended_losses == D("20")

    def test_stock_exhausted_before_debt(self) -> None:
        """Stock basis must reach zero before debt basis absorbs losses."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("30"),
            beginning_debt_basis=D("70"),
            adjustments=_inputs(ordinary_loss=D("60")),
        )
        # Stock absorbs 30, debt absorbs 30
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("40")
        assert result.losses_allowed == D("60")

    def test_multiple_loss_types_sum(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("200"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_loss=D("60"),
                separately_stated_losses=D("40"),
            ),
        )
        # 200 - 60 - 40 = 100
        assert result.ending_stock_basis == D("100")
        assert result.losses_allowed == D("100")

    def test_suspended_losses_carry_forward(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_loss=D("50")),
        )
        assert result.suspended_losses == D("50")
        assert result.losses_allowed == D("0")
        assert result.losses_limited_by_basis == D("50")

    def test_prior_suspended_losses_applied_in_step_4(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("200"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_loss=D("50")),
            prior_suspended_losses=D("30"),
        )
        # Step 4: total losses = 50 + 30 = 80
        # 200 - 80 = 120
        assert result.ending_stock_basis == D("120")
        assert result.losses_allowed == D("80")
        assert result.suspended_losses == D("0")


# =============================================================================
# Multi-year tests
# =============================================================================


class TestMultiYear:
    """Multi-year basis tracking: ending = next year's beginning."""

    def test_year1_ending_is_year2_beginning(self) -> None:
        yr1 = calculate_shareholder_basis(
            beginning_stock_basis=D("1000"),
            beginning_debt_basis=D("500"),
            adjustments=_inputs(
                ordinary_income=D("200"),
                non_dividend_distributions=D("100"),
            ),
        )
        yr2 = calculate_shareholder_basis(
            beginning_stock_basis=yr1.ending_stock_basis,
            beginning_debt_basis=yr1.ending_debt_basis,
            adjustments=_inputs(ordinary_income=D("50")),
            prior_suspended_losses=yr1.suspended_losses,
        )
        # Year 1: 1000 + 200 - 100 = 1100
        assert yr1.ending_stock_basis == D("1100")
        # Year 2: 1100 + 50 = 1150
        assert yr2.ending_stock_basis == D("1150")

    def test_suspended_losses_from_year1_applied_in_year2(self) -> None:
        yr1 = calculate_shareholder_basis(
            beginning_stock_basis=D("30"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_loss=D("100")),
        )
        assert yr1.suspended_losses == D("70")

        yr2 = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_income=D("200")),
            prior_suspended_losses=yr1.suspended_losses,
        )
        # Step 1: 0 + 200 = 200
        # Step 4: 200 - 70 (prior) = 130
        assert yr2.ending_stock_basis == D("130")
        assert yr2.suspended_losses == D("0")

    def test_debt_basis_restoration_after_losses(self) -> None:
        """Income in Year 2 restores stock basis; debt stays unchanged."""
        yr1 = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("100"),
            adjustments=_inputs(ordinary_loss=D("150")),
        )
        # Stock absorbs 100, debt absorbs 50
        assert yr1.ending_stock_basis == D("0")
        assert yr1.ending_debt_basis == D("50")

        yr2 = calculate_shareholder_basis(
            beginning_stock_basis=yr1.ending_stock_basis,
            beginning_debt_basis=yr1.ending_debt_basis,
            adjustments=_inputs(ordinary_income=D("80")),
        )
        # Stock: 0 + 80 = 80 (income restores stock first)
        # Debt stays at 50 (income doesn't restore debt)
        assert yr2.ending_stock_basis == D("80")
        assert yr2.ending_debt_basis == D("50")


# =============================================================================
# Edge cases
# =============================================================================


class TestEdgeCases:
    """Edge cases: zero activity, large numbers, negative basis guard."""

    def test_zero_beginning_basis_with_income_and_distributions(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_income=D("500"),
                non_dividend_distributions=D("200"),
            ),
        )
        # Step 1: 0 + 500 = 500
        # Step 2: 500 - 200 = 300
        assert result.ending_stock_basis == D("300")
        assert result.distributions_nontaxable == D("200")
        assert result.distributions_taxable == D("0")

    def test_all_zeros_no_change(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("50"),
            adjustments=_inputs(),
        )
        assert result.ending_stock_basis == D("100")
        assert result.ending_debt_basis == D("50")
        assert result.suspended_losses == D("0")
        assert result.distributions_taxable == D("0")
        assert result.distributions_nontaxable == D("0")
        assert result.losses_allowed == D("0")
        assert result.losses_limited_by_basis == D("0")

    def test_very_large_numbers_decimal_precision(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("999999999.99"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(ordinary_income=D("0.01")),
        )
        assert result.ending_stock_basis == D("1000000000.00")

    def test_negative_beginning_stock_basis_rejected(self) -> None:
        with pytest.raises(ValueError, match="beginning_stock_basis"):
            calculate_shareholder_basis(
                beginning_stock_basis=D("-1"),
                beginning_debt_basis=D("0"),
                adjustments=_inputs(),
            )

    def test_negative_beginning_debt_basis_rejected(self) -> None:
        with pytest.raises(ValueError, match="beginning_debt_basis"):
            calculate_shareholder_basis(
                beginning_stock_basis=D("0"),
                beginning_debt_basis=D("-1"),
                adjustments=_inputs(),
            )

    def test_beginning_basis_preserved_in_result(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("500"),
            beginning_debt_basis=D("300"),
            adjustments=_inputs(),
        )
        assert result.beginning_stock_basis == D("500")
        assert result.beginning_debt_basis == D("300")


# =============================================================================
# Ordering rule compliance
# =============================================================================


class TestOrderingRuleCompliance:
    """Prove that IRS ordering rules produce different results from naive ordering."""

    def test_correct_order_vs_losses_before_distributions(self) -> None:
        """If losses applied before distributions, result is different.

        Correct: income -> distributions -> nondeductible -> losses
        Wrong:   income -> losses -> distributions -> nondeductible
        """
        adj = _inputs(
            ordinary_income=D("50"),
            non_dividend_distributions=D("120"),
            ordinary_loss=D("60"),
        )

        correct = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=adj,
        )
        # Correct order:
        # Step 1: 100 + 50 = 150
        # Step 2: 150 - 120 = 30 (all nontaxable)
        # Step 4: 30 - 60 -> stock=0, suspended=30
        assert correct.ending_stock_basis == D("0")
        assert correct.distributions_nontaxable == D("120")
        assert correct.distributions_taxable == D("0")
        assert correct.suspended_losses == D("30")

    def test_distribution_after_income_vs_before(self) -> None:
        """Distribution AFTER income increase: different taxable amount.

        With income first: 50 + 100 = 150, then distribute 120 -> 0 taxable
        Without income first: 50 - 120 -> 70 taxable (wrong if income not applied first)
        """
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_income=D("100"),
                non_dividend_distributions=D("120"),
            ),
        )
        # Income applied first -> 150
        # Distribution -> 150 - 120 = 30, all nontaxable
        assert result.distributions_taxable == D("0")
        assert result.distributions_nontaxable == D("120")

    def test_full_ordering_chain(self) -> None:
        """Complete scenario touching all 4 steps."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("50"),
            adjustments=_inputs(
                ordinary_income=D("80"),
                tax_exempt_income=D("20"),
                non_dividend_distributions=D("150"),
                nondeductible_expenses=D("30"),
                ordinary_loss=D("40"),
                separately_stated_losses=D("20"),
            ),
            prior_suspended_losses=D("10"),
        )
        # Step 1: 100 + 80 + 20 = 200
        # Step 2: 200 - 150 = 50 (all nontaxable)
        # Step 3: 50 - 30 = 20
        # Step 4: losses = 40 + 20 + 10 = 70
        #   stock absorbs 20 -> 0
        #   debt absorbs 50 -> 0
        #   suspended: 0
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("0")
        assert result.distributions_nontaxable == D("150")
        assert result.distributions_taxable == D("0")
        assert result.losses_allowed == D("70")
        assert result.losses_limited_by_basis == D("0")
        assert result.suspended_losses == D("0")

    def test_full_ordering_with_partial_suspension(self) -> None:
        """All 4 steps with some losses suspended."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("20"),
            adjustments=_inputs(
                ordinary_income=D("30"),
                non_dividend_distributions=D("80"),
                nondeductible_expenses=D("10"),
                ordinary_loss=D("50"),
                separately_stated_losses=D("30"),
            ),
        )
        # Step 1: 100 + 30 = 130
        # Step 2: 130 - 80 = 50 (all nontaxable)
        # Step 3: 50 - 10 = 40
        # Step 4: losses = 50 + 30 = 80
        #   stock absorbs 40 -> 0
        #   debt absorbs 20 -> 0
        #   remaining: 80 - 40 - 20 = 20 suspended
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("0")
        assert result.distributions_nontaxable == D("80")
        assert result.distributions_taxable == D("0")
        assert result.losses_allowed == D("60")
        assert result.losses_limited_by_basis == D("20")
        assert result.suspended_losses == D("20")


# =============================================================================
# BasisResult completeness
# =============================================================================


class TestBasisResultFields:
    """BasisResult contains all required fields."""

    def test_result_has_all_fields(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("50"),
            adjustments=_inputs(ordinary_income=D("10")),
        )
        assert isinstance(result, BasisResult)
        assert hasattr(result, "beginning_stock_basis")
        assert hasattr(result, "ending_stock_basis")
        assert hasattr(result, "beginning_debt_basis")
        assert hasattr(result, "ending_debt_basis")
        assert hasattr(result, "suspended_losses")
        assert hasattr(result, "distributions_taxable")
        assert hasattr(result, "distributions_nontaxable")
        assert hasattr(result, "losses_allowed")
        assert hasattr(result, "losses_limited_by_basis")

    def test_result_decimal_types(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(),
        )
        assert isinstance(result.beginning_stock_basis, Decimal)
        assert isinstance(result.ending_stock_basis, Decimal)
        assert isinstance(result.beginning_debt_basis, Decimal)
        assert isinstance(result.ending_debt_basis, Decimal)
        assert isinstance(result.suspended_losses, Decimal)
        assert isinstance(result.distributions_taxable, Decimal)
        assert isinstance(result.distributions_nontaxable, Decimal)
        assert isinstance(result.losses_allowed, Decimal)
        assert isinstance(result.losses_limited_by_basis, Decimal)


# =============================================================================
# Additional edge cases for robustness
# =============================================================================


class TestAdditionalEdgeCases:
    """Supplementary edge cases for comprehensive coverage."""

    def test_only_distributions_no_income(self) -> None:
        """Distributions with no income -- pure basis reduction."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("300"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(non_dividend_distributions=D("300")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.distributions_nontaxable == D("300")
        assert result.distributions_taxable == D("0")

    def test_only_losses_exhaust_both_bases(self) -> None:
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("100"),
            adjustments=_inputs(ordinary_loss=D("200")),
        )
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("0")
        assert result.losses_allowed == D("200")
        assert result.suspended_losses == D("0")

    def test_nondeductible_cannot_go_negative_after_distributions(self) -> None:
        """Distributions + nondeductible combo -- stock can't go below zero."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                non_dividend_distributions=D("90"),
                nondeductible_expenses=D("20"),
            ),
        )
        # Step 2: 100 - 90 = 10
        # Step 3: 10 - 20 -> 0 (clamped)
        assert result.ending_stock_basis == D("0")

    def test_prior_suspended_losses_partial_use(self) -> None:
        """Prior suspended losses partially consumed when basis limited."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("30"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(),
            prior_suspended_losses=D("50"),
        )
        # No new activity except prior suspended losses
        # Step 4: 50 losses against 30 stock -> allowed=30, suspended=20
        assert result.ending_stock_basis == D("0")
        assert result.losses_allowed == D("30")
        assert result.suspended_losses == D("20")

    def test_debt_basis_untouched_by_distributions(self) -> None:
        """Distributions only reduce stock basis, never debt basis."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("50"),
            beginning_debt_basis=D("200"),
            adjustments=_inputs(non_dividend_distributions=D("100")),
        )
        # Stock: 50 - 50 = 0 (capped), 50 taxable
        # Debt: unchanged at 200
        assert result.ending_stock_basis == D("0")
        assert result.ending_debt_basis == D("200")
        assert result.distributions_nontaxable == D("50")
        assert result.distributions_taxable == D("50")

    def test_income_does_not_restore_debt_basis(self) -> None:
        """Income only increases stock basis, not debt basis."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("0"),
            beginning_debt_basis=D("50"),
            adjustments=_inputs(ordinary_income=D("100")),
        )
        assert result.ending_stock_basis == D("100")
        assert result.ending_debt_basis == D("50")

    def test_cents_precision(self) -> None:
        """Decimal handles cents accurately."""
        result = calculate_shareholder_basis(
            beginning_stock_basis=D("100.50"),
            beginning_debt_basis=D("0"),
            adjustments=_inputs(
                ordinary_income=D("33.33"),
                non_dividend_distributions=D("22.22"),
            ),
        )
        # 100.50 + 33.33 = 133.83
        # 133.83 - 22.22 = 111.61
        assert result.ending_stock_basis == D("111.61")
