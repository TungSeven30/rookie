"""Shareholder basis tracking for S-Corporation (Form 7203).

Implements IRS ordering rules for annual shareholder basis adjustments:

1. INCREASE stock basis for income items (ordinary, separately stated,
   tax-exempt, excess depletion)
2. DECREASE stock basis for non-dividend distributions (not below zero;
   excess is taxable as capital gain)
3. DECREASE stock basis for nondeductible expenses and oil/gas depletion
   (not below zero)
4. DECREASE for losses (ordinary + separately stated + prior suspended):
   - Stock basis absorbs losses first (to zero)
   - Remaining losses reduce debt basis (to zero)
   - Any remaining losses are suspended for carry-forward

All arithmetic uses Decimal. No floating point.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True)
class BasisAdjustmentInputs:
    """All items affecting shareholder basis for the tax year.

    Frozen dataclass enforces immutability -- callers cannot modify inputs
    after construction.

    Args:
        ordinary_income: K-1 Box 1 (if positive).
        separately_stated_income: Boxes 2-10 positive items aggregated.
        tax_exempt_income: Box 16A + 16B.
        excess_depletion: Excess depletion (default 0).
        non_dividend_distributions: Box 16D distributions.
        nondeductible_expenses: Box 16C.
        oil_gas_depletion: Oil and gas depletion (default 0).
        ordinary_loss: Box 1 negative (absolute value).
        separately_stated_losses: Boxes 2-12 losses aggregated (absolute value).
    """

    # Step 1: Income items (increase basis)
    ordinary_income: Decimal = ZERO
    separately_stated_income: Decimal = ZERO
    tax_exempt_income: Decimal = ZERO
    excess_depletion: Decimal = ZERO

    # Step 2: Distributions (decrease basis)
    non_dividend_distributions: Decimal = ZERO

    # Step 3: Nondeductible expenses (decrease basis)
    nondeductible_expenses: Decimal = ZERO
    oil_gas_depletion: Decimal = ZERO

    # Step 4: Loss items (decrease basis)
    ordinary_loss: Decimal = ZERO
    separately_stated_losses: Decimal = ZERO


@dataclass
class BasisResult:
    """Computed basis result after applying IRS ordering rules.

    Args:
        beginning_stock_basis: Stock basis at start of year.
        ending_stock_basis: Stock basis at end of year.
        beginning_debt_basis: Debt basis at start of year.
        ending_debt_basis: Debt basis at end of year.
        suspended_losses: Losses exceeding total basis (carry forward).
        distributions_taxable: Distributions exceeding basis (capital gain).
        distributions_nontaxable: Distributions that reduced basis.
        losses_allowed: Losses deductible against basis.
        losses_limited_by_basis: Losses suspended due to insufficient basis.
    """

    beginning_stock_basis: Decimal
    ending_stock_basis: Decimal
    beginning_debt_basis: Decimal
    ending_debt_basis: Decimal
    suspended_losses: Decimal
    distributions_taxable: Decimal
    distributions_nontaxable: Decimal
    losses_allowed: Decimal
    losses_limited_by_basis: Decimal


def calculate_shareholder_basis(
    beginning_stock_basis: Decimal,
    beginning_debt_basis: Decimal,
    adjustments: BasisAdjustmentInputs,
    prior_suspended_losses: Decimal = ZERO,
) -> BasisResult:
    """Calculate shareholder basis using IRS ordering rules.

    Applies all adjustments as of the last day of the tax year in the
    required IRS order: income -> distributions -> nondeductible -> losses.

    Args:
        beginning_stock_basis: Stock basis at start of year (>= 0).
        beginning_debt_basis: Debt basis at start of year (>= 0).
        adjustments: All adjustment items for the year.
        prior_suspended_losses: Suspended losses carried from prior years.

    Returns:
        BasisResult with all computed values.

    Raises:
        ValueError: If beginning_stock_basis or beginning_debt_basis is negative.
    """
    if beginning_stock_basis < ZERO:
        raise ValueError(
            f"beginning_stock_basis must be >= 0, got {beginning_stock_basis}"
        )
    if beginning_debt_basis < ZERO:
        raise ValueError(
            f"beginning_debt_basis must be >= 0, got {beginning_debt_basis}"
        )

    stock = beginning_stock_basis
    debt = beginning_debt_basis

    # ------------------------------------------------------------------
    # Step 1: INCREASE stock basis for income items
    # ------------------------------------------------------------------
    total_income = (
        adjustments.ordinary_income
        + adjustments.separately_stated_income
        + adjustments.tax_exempt_income
        + adjustments.excess_depletion
    )
    stock += total_income

    # ------------------------------------------------------------------
    # Step 2: DECREASE stock basis for distributions (not below zero)
    # ------------------------------------------------------------------
    distributions = adjustments.non_dividend_distributions
    if distributions <= stock:
        distributions_nontaxable = distributions
        distributions_taxable = ZERO
        stock -= distributions
    else:
        distributions_nontaxable = stock
        distributions_taxable = distributions - stock
        stock = ZERO

    # ------------------------------------------------------------------
    # Step 3: DECREASE stock basis for nondeductible expenses (not below zero)
    # ------------------------------------------------------------------
    total_nondeductible = (
        adjustments.nondeductible_expenses + adjustments.oil_gas_depletion
    )
    stock = max(stock - total_nondeductible, ZERO)

    # ------------------------------------------------------------------
    # Step 4: DECREASE for losses (stock first, then debt, then suspend)
    # ------------------------------------------------------------------
    total_losses = (
        adjustments.ordinary_loss
        + adjustments.separately_stated_losses
        + prior_suspended_losses
    )

    remaining_losses = total_losses

    # Stock absorbs first
    stock_absorbed = min(remaining_losses, stock)
    stock -= stock_absorbed
    remaining_losses -= stock_absorbed

    # Debt absorbs remainder
    debt_absorbed = min(remaining_losses, debt)
    debt -= debt_absorbed
    remaining_losses -= debt_absorbed

    # Anything left is suspended
    losses_allowed = total_losses - remaining_losses
    suspended = remaining_losses

    return BasisResult(
        beginning_stock_basis=beginning_stock_basis,
        ending_stock_basis=stock,
        beginning_debt_basis=beginning_debt_basis,
        ending_debt_basis=debt,
        suspended_losses=suspended,
        distributions_taxable=distributions_taxable,
        distributions_nontaxable=distributions_nontaxable,
        losses_allowed=losses_allowed,
        losses_limited_by_basis=suspended,
    )
