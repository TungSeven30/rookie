"""Tax year carryover tracking and loading.

This module provides dataclasses for tracking amounts that carry forward from
prior tax years, such as capital losses, passive activity losses, and NOLs.

Example:
    >>> from src.agents.personal_tax.carryovers import TaxYearCarryovers
    >>> carryovers = TaxYearCarryovers(
    ...     tax_year=2023,
    ...     capital_loss_carryforward=Decimal("5000"),
    ... )
    >>> carryovers.has_capital_loss_carryover
    True
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class TaxYearCarryovers:
    """Carryover amounts from prior year return.

    Tracks various amounts that carry forward from one tax year to the next.
    These affect current year calculations and must be verified against
    prior year return.

    Attributes:
        tax_year: The year these carryovers are FROM (prior year).
        capital_loss_carryforward: Total capital loss carryforward.
        capital_loss_carryforward_short_term: Short-term portion.
        capital_loss_carryforward_long_term: Long-term portion.
        passive_loss_carryforward: Total passive activity loss carryforward.
        passive_loss_by_activity: PAL by activity name/address.
        nol_carryforward: Net Operating Loss carryforward.
        charitable_carryforward: Excess charitable contribution carryforward.
        investment_interest_carryforward: Investment interest expense carryover.
        amt_credit_carryforward: AMT credit carryforward.
        foreign_tax_credit_carryforward: Foreign tax credit carryforward.
        k1_suspended_losses: K-1 suspended losses by entity EIN.
        source: Where this data came from.
        verified: Whether amounts have been verified against prior return.
    """

    tax_year: int  # Year these carryovers are FROM (prior year)

    # Capital losses (Schedule D)
    capital_loss_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))
    capital_loss_carryforward_short_term: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    capital_loss_carryforward_long_term: Decimal = field(
        default_factory=lambda: Decimal("0")
    )

    # Passive activity losses (Schedule E / Form 8582)
    passive_loss_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))
    passive_loss_by_activity: dict[str, Decimal] = field(default_factory=dict)

    # Net Operating Loss (if applicable)
    nol_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))

    # Charitable contribution carryovers
    charitable_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))

    # Investment interest expense carryover
    investment_interest_carryforward: Decimal = field(
        default_factory=lambda: Decimal("0")
    )

    # AMT credit carryforward
    amt_credit_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))

    # Foreign tax credit carryforward
    foreign_tax_credit_carryforward: Decimal = field(
        default_factory=lambda: Decimal("0")
    )

    # K-1 suspended losses by entity EIN
    k1_suspended_losses: dict[str, Decimal] = field(default_factory=dict)

    # Source tracking
    source: str = "prior_year_return"  # or "client_input", "estimated"
    verified: bool = False

    @property
    def has_capital_loss_carryover(self) -> bool:
        """Check if there's a capital loss carryover to apply."""
        return self.capital_loss_carryforward > Decimal("0")

    @property
    def has_passive_loss_carryover(self) -> bool:
        """Check if there's a passive loss carryover."""
        return self.passive_loss_carryforward > Decimal("0")

    @property
    def has_any_carryover(self) -> bool:
        """Check if any carryover amounts exist."""
        return (
            self.capital_loss_carryforward > Decimal("0")
            or self.passive_loss_carryforward > Decimal("0")
            or self.nol_carryforward > Decimal("0")
            or self.charitable_carryforward > Decimal("0")
            or self.investment_interest_carryforward > Decimal("0")
            or self.amt_credit_carryforward > Decimal("0")
            or self.foreign_tax_credit_carryforward > Decimal("0")
            or bool(self.k1_suspended_losses)
        )
