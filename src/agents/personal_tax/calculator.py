"""Tax calculation functions for personal tax returns.

This module provides pure functions for computing tax-related values:
- Income aggregation from W-2, 1099, K-1, and Schedule C data
- Schedule C (business income) calculations
- Self-employment tax calculations
- Standard vs itemized deduction selection
- Tax credits evaluation (CTC, AOC, Saver's Credit, EITC)
- Federal tax liability using marginal brackets
- Prior year variance detection

All monetary values use Decimal for precision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Union

from src.documents.models import (
    Form1095A,
    Form1098,
    Form1098T,
    Form1099B,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Form1099S,
    Form5498,
    FormK1,
    W2Data,
)
from src.tax.year_config import get_tax_year_config


class FilingStatus(str, Enum):
    """IRS filing status options.

    These determine tax brackets, deduction amounts, and credit thresholds.
    """

    SINGLE = "single"
    MARRIED_FILING_JOINTLY = "mfj"
    MARRIED_FILING_SEPARATELY = "mfs"
    HEAD_OF_HOUSEHOLD = "hoh"
    QUALIFYING_WIDOW = "qw"


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class IncomeSummary:
    """Aggregated income from all tax documents.

    Attributes:
        total_wages: Sum of all W-2 wages, tips, and compensation.
        total_interest: Sum of all 1099-INT interest income.
        total_dividends: Sum of all 1099-DIV ordinary dividends.
        total_qualified_dividends: Sum of qualified dividends (taxed at lower rate).
        total_nec: Sum of all 1099-NEC nonemployee compensation.
        total_retirement_distributions: Sum of taxable 1099-R distributions.
        total_unemployment: Sum of 1099-G unemployment compensation.
        total_state_tax_refund: Sum of 1099-G state tax refunds (may be taxable).
        total_other: Other income not categorized above.
        total_income: Grand total of all income.
        federal_withholding: Sum of all federal tax withheld.
        schedule_c_profit: Net profit (or loss) from Schedule C businesses.
        k1_ordinary_income: K-1 Box 1 ordinary business income.
        k1_guaranteed_payments: K-1 Box 4 guaranteed payments (partnerships).
        self_employment_income: Total SE income (Schedule C + K-1 Box 14).
        se_tax: Total self-employment tax liability.
        se_tax_deduction: Above-the-line deduction (50% of SE tax).
        schedule_e_rental_income: Total rental income from Schedule E.
        schedule_e_expenses: Total rental expenses from Schedule E.
        schedule_e_net: Net rental income/loss after limitations.
        schedule_e_suspended_loss: Suspended loss carried forward.
    """

    total_wages: Decimal
    total_interest: Decimal
    total_dividends: Decimal
    total_qualified_dividends: Decimal
    total_nec: Decimal
    total_retirement_distributions: Decimal = field(
        default_factory=lambda: Decimal("0")
    )
    total_unemployment: Decimal = field(default_factory=lambda: Decimal("0"))
    total_state_tax_refund: Decimal = field(default_factory=lambda: Decimal("0"))
    total_other: Decimal = field(default_factory=lambda: Decimal("0"))
    total_income: Decimal = field(default_factory=lambda: Decimal("0"))
    federal_withholding: Decimal = field(default_factory=lambda: Decimal("0"))

    # Business income fields (Phase 4)
    schedule_c_profit: Decimal = field(default_factory=lambda: Decimal("0"))
    k1_ordinary_income: Decimal = field(default_factory=lambda: Decimal("0"))
    k1_guaranteed_payments: Decimal = field(default_factory=lambda: Decimal("0"))
    self_employment_income: Decimal = field(default_factory=lambda: Decimal("0"))
    se_tax: Decimal = field(default_factory=lambda: Decimal("0"))
    se_tax_deduction: Decimal = field(default_factory=lambda: Decimal("0"))

    # Rental income fields (Schedule E)
    schedule_e_rental_income: Decimal = field(default_factory=lambda: Decimal("0"))
    schedule_e_expenses: Decimal = field(default_factory=lambda: Decimal("0"))
    schedule_e_net: Decimal = field(default_factory=lambda: Decimal("0"))
    schedule_e_suspended_loss: Decimal = field(default_factory=lambda: Decimal("0"))

    # Capital gains fields (Schedule D)
    capital_gains_short_term: Decimal = field(default_factory=lambda: Decimal("0"))
    capital_gains_long_term: Decimal = field(default_factory=lambda: Decimal("0"))
    capital_gains_net: Decimal = field(default_factory=lambda: Decimal("0"))
    capital_loss_carryforward: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class ScheduleCExpenses:
    """Schedule C expense categories (Lines 8-27).

    All IRS Schedule C expense categories with corresponding line numbers.
    All defaults are zero - only populate what applies.

    Example:
        >>> expenses = ScheduleCExpenses(
        ...     advertising=Decimal("500"),
        ...     supplies=Decimal("1200"),
        ...     utilities=Decimal("3000"),
        ... )
        >>> expenses.total
        Decimal('4700')
    """

    advertising: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 8
    car_truck: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 9
    commissions_fees: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 10
    contract_labor: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 11
    depletion: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 12
    depreciation: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 13
    employee_benefits: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 14
    insurance: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 15
    interest_mortgage: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 16a
    interest_other: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 16b
    legal_professional: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 17
    office_expense: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 18
    pension_profit_sharing: Decimal = field(
        default_factory=lambda: Decimal("0")
    )  # Line 19
    rent_vehicles_machinery: Decimal = field(
        default_factory=lambda: Decimal("0")
    )  # Line 20a
    rent_other: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 20b
    repairs_maintenance: Decimal = field(
        default_factory=lambda: Decimal("0")
    )  # Line 21
    supplies: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 22
    taxes_licenses: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 23
    travel: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 24a
    deductible_meals: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 24b
    utilities: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 25
    wages: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 26
    other_expenses: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 27

    @property
    def total(self) -> Decimal:
        """Sum of all expense categories (Line 28)."""
        return (
            self.advertising
            + self.car_truck
            + self.commissions_fees
            + self.contract_labor
            + self.depletion
            + self.depreciation
            + self.employee_benefits
            + self.insurance
            + self.interest_mortgage
            + self.interest_other
            + self.legal_professional
            + self.office_expense
            + self.pension_profit_sharing
            + self.rent_vehicles_machinery
            + self.rent_other
            + self.repairs_maintenance
            + self.supplies
            + self.taxes_licenses
            + self.travel
            + self.deductible_meals
            + self.utilities
            + self.wages
            + self.other_expenses
        )


@dataclass
class ScheduleCData:
    """Schedule C (Profit or Loss from Business) data.

    Complete data for IRS Schedule C calculation including business info,
    income, and expenses.

    Example:
        >>> sch_c = ScheduleCData(
        ...     business_name="Consulting LLC",
        ...     business_activity="Management Consulting",
        ...     principal_business_code="541611",
        ...     gross_receipts=Decimal("150000"),
        ...     expenses=ScheduleCExpenses(office_expense=Decimal("5000")),
        ... )
        >>> sch_c.net_profit_or_loss
        Decimal('145000')
    """

    # Business identification
    business_name: str
    business_activity: str
    principal_business_code: str  # 6-digit NAICS code
    employer_id: str | None = None

    # Accounting method
    accounting_method: str = "cash"  # cash, accrual, or other

    # Income (Part I)
    gross_receipts: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 1
    returns_allowances: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 2
    cost_of_goods_sold: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 4
    other_income: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 6

    # Expenses (Part II)
    expenses: ScheduleCExpenses = field(default_factory=ScheduleCExpenses)

    # Home office (if applicable)
    home_office_deduction: Decimal = field(
        default_factory=lambda: Decimal("0")
    )  # From Form 8829

    @property
    def gross_income(self) -> Decimal:
        """Line 3: Gross receipts minus returns and allowances."""
        return self.gross_receipts - self.returns_allowances

    @property
    def gross_profit(self) -> Decimal:
        """Line 5: Gross income minus cost of goods sold."""
        return self.gross_income - self.cost_of_goods_sold

    @property
    def total_income(self) -> Decimal:
        """Line 7: Gross profit plus other income."""
        return self.gross_profit + self.other_income

    @property
    def total_expenses(self) -> Decimal:
        """Line 28: Total expenses including home office."""
        return self.expenses.total + self.home_office_deduction

    @property
    def net_profit_or_loss(self) -> Decimal:
        """Line 31: Net profit (or loss) from business."""
        return self.total_income - self.total_expenses


@dataclass
class SelfEmploymentTax:
    """Self-employment tax calculation result (Schedule SE).

    Breakdown of SE tax components including Social Security and Medicare portions.
    50% of SE tax is deductible "above the line" on Form 1040.

    Attributes:
        net_earnings: Net SE earnings (92.35% of net SE income).
        social_security_tax: 12.4% on earnings up to wage base.
        medicare_tax: 2.9% on all earnings.
        additional_medicare_tax: 0.9% on earnings above threshold.
        total_se_tax: Sum of all SE tax components.
        deductible_portion: 50% of total SE tax (above-the-line deduction).
    """

    net_earnings: Decimal
    social_security_tax: Decimal
    medicare_tax: Decimal
    additional_medicare_tax: Decimal
    total_se_tax: Decimal
    deductible_portion: Decimal
    social_security_wage_base: Decimal
    additional_medicare_threshold: Decimal


@dataclass
class RentalExpenses:
    """Rental property expense categories (Schedule E Part I).

    All IRS Schedule E Part I expense categories with corresponding line numbers.
    Defaults to zero - only populate what applies to the property.

    Example:
        >>> expenses = RentalExpenses(
        ...     mortgage_interest=Decimal("8000"),
        ...     taxes=Decimal("3000"),
        ...     depreciation=Decimal("5000"),
        ... )
        >>> expenses.total
        Decimal('16000')
    """

    advertising: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 5
    auto_travel: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 6
    cleaning_maintenance: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 7
    commissions: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 8
    insurance: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 9
    legal_professional: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 10
    management_fees: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 11
    mortgage_interest: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 12
    other_interest: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 13
    repairs: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 14
    supplies: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 15
    taxes: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 16
    utilities: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 17
    depreciation: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 18
    other_expenses: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 19

    @property
    def total(self) -> Decimal:
        """Line 20: Total expenses."""
        return (
            self.advertising
            + self.auto_travel
            + self.cleaning_maintenance
            + self.commissions
            + self.insurance
            + self.legal_professional
            + self.management_fees
            + self.mortgage_interest
            + self.other_interest
            + self.repairs
            + self.supplies
            + self.taxes
            + self.utilities
            + self.depreciation
            + self.other_expenses
        )


@dataclass
class RentalProperty:
    """Single rental property data for Schedule E Part I.

    Represents one rental unit with its income, expenses, and rental/personal use days.
    Personal use exceeding limits affects loss deductibility.

    Example:
        >>> prop = RentalProperty(
        ...     property_address="123 Main St, Austin TX",
        ...     property_type="Single Family",
        ...     fair_rental_days=365,
        ...     rental_income=Decimal("24000"),
        ...     expenses=RentalExpenses(taxes=Decimal("3000")),
        ... )
        >>> prop.net_income_loss
        Decimal('21000')
    """

    property_address: str
    property_type: str  # Single Family, Multi-Family, Vacation, Commercial
    fair_rental_days: int
    personal_use_days: int = 0
    rental_income: Decimal = field(default_factory=lambda: Decimal("0"))  # Line 3
    expenses: RentalExpenses = field(default_factory=RentalExpenses)
    qbi_eligible: bool = True  # Rental can qualify for QBI under safe harbor

    @property
    def is_personal_use_property(self) -> bool:
        """Check if property fails rental test due to excessive personal use.

        IRS Rule: Personal use >14 days OR >10% of rental days disqualifies
        certain deductions and converts rental to mixed-use property.
        """
        if self.fair_rental_days == 0:
            return True
        max_personal = max(14, int(self.fair_rental_days * Decimal("0.10")))
        return self.personal_use_days > max_personal

    @property
    def net_income_loss(self) -> Decimal:
        """Net rental income or loss before passive activity limitations."""
        return self.rental_income - self.expenses.total


@dataclass
class ScheduleEData:
    """Schedule E Part I - Rental Real Estate aggregated data.

    Holds all rental properties and taxpayer participation status for
    determining passive activity loss limitations.

    Example:
        >>> sch_e = ScheduleEData(
        ...     properties=[prop1, prop2],
        ...     actively_participates=True,
        ... )
        >>> sch_e.net_before_limitations
        Decimal('15000')
    """

    properties: list[RentalProperty] = field(default_factory=list)
    actively_participates: bool = True  # For $25k loss allowance
    is_real_estate_professional: bool = False  # No passive limits if True
    prior_year_suspended_loss: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def total_rental_income(self) -> Decimal:
        """Sum of all rental income across properties."""
        return sum(p.rental_income for p in self.properties)

    @property
    def total_expenses(self) -> Decimal:
        """Sum of all expenses across properties."""
        return sum(p.expenses.total for p in self.properties)

    @property
    def net_before_limitations(self) -> Decimal:
        """Net rental income/loss before passive activity limitations."""
        return sum(p.net_income_loss for p in self.properties)


@dataclass
class ScheduleEResult:
    """Result of Schedule E calculation with passive loss limitations.

    Attributes:
        total_rental_income: Sum of all rental income.
        total_expenses: Sum of all expenses.
        net_before_limitations: Net before passive activity rules.
        loss_limited: Whether loss was limited by passive rules.
        allowed_loss: Amount of loss allowed this year.
        suspended_loss: Loss suspended for future years.
        net_rental_income_loss: Final amount included in AGI.
        qbi_rental_income: Rental income eligible for QBI deduction.
        property_results: Per-property breakdown.
    """

    total_rental_income: Decimal
    total_expenses: Decimal
    net_before_limitations: Decimal
    loss_limited: bool
    allowed_loss: Decimal
    suspended_loss: Decimal
    net_rental_income_loss: Decimal
    qbi_rental_income: Decimal
    property_results: list[dict]


@dataclass
class CapitalTransaction:
    """Single capital gain/loss transaction from 1099-B or other source.

    Represents a single sale of stock, mutual fund, or other capital asset.
    Tracks holding period, basis, and special tax treatments.

    Attributes:
        description: Security description (e.g., "100 sh AAPL").
        date_acquired: Acquisition date or "Various" for multiple lots.
        date_sold: Sale date.
        proceeds: Sale proceeds (Box 1d of 1099-B).
        cost_basis: Cost or other basis (None if not reported to IRS).
        is_short_term: Held 1 year or less (ordinary rates).
        is_long_term: Held more than 1 year (preferential rates).
        basis_reported_to_irs: Whether broker reported basis to IRS.
        wash_sale_disallowed: Wash sale loss adjustment (Box 1g).
        is_collectibles: Subject to 28% max rate.
        is_section_1202: QSBS exclusion eligible.
        is_section_1250: Unrecaptured depreciation gain.
    """

    description: str
    date_acquired: str | None  # May be "Various"
    date_sold: str
    proceeds: Decimal
    cost_basis: Decimal | None  # None if not reported to IRS

    # Classification
    is_short_term: bool = False  # Held ≤1 year
    is_long_term: bool = False  # Held >1 year
    basis_reported_to_irs: bool = True  # Box 12 from 1099-B

    # Adjustments
    wash_sale_disallowed: Decimal = field(default_factory=lambda: Decimal("0"))

    # Special types
    is_collectibles: bool = False  # 28% max rate
    is_section_1202: bool = False  # QSBS exclusion
    is_section_1250: bool = False  # Unrecaptured depreciation

    @property
    def requires_basis_escalation(self) -> bool:
        """Transaction requires escalation due to missing basis."""
        return self.cost_basis is None

    @property
    def gain_loss(self) -> Decimal | None:
        """Calculate gain or loss. Returns None if basis unknown."""
        if self.cost_basis is None:
            return None  # Cannot calculate - needs escalation
        return self.proceeds - self.cost_basis + self.wash_sale_disallowed

    @property
    def adjusted_gain_loss(self) -> Decimal | None:
        """Gain/loss after wash sale adjustment."""
        return self.gain_loss


@dataclass
class ScheduleDData:
    """Schedule D - Capital Gains and Losses.

    Aggregates all capital transactions for the tax year and tracks
    prior year carryovers.

    Attributes:
        transactions: List of all capital transactions.
        prior_year_loss_carryover: Capital loss carryforward from prior year.
    """

    transactions: list[CapitalTransaction] = field(default_factory=list)

    # Prior year carryover
    prior_year_loss_carryover: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def short_term_transactions(self) -> list[CapitalTransaction]:
        """Filter short-term transactions."""
        return [t for t in self.transactions if t.is_short_term]

    @property
    def long_term_transactions(self) -> list[CapitalTransaction]:
        """Filter long-term transactions."""
        return [t for t in self.transactions if t.is_long_term]

    @property
    def net_short_term(self) -> Decimal:
        """Net short-term capital gain/loss (excluding missing basis)."""
        return sum(
            t.adjusted_gain_loss
            for t in self.short_term_transactions
            if t.adjusted_gain_loss is not None
        )

    @property
    def net_long_term(self) -> Decimal:
        """Net long-term capital gain/loss (excluding missing basis)."""
        return sum(
            t.adjusted_gain_loss
            for t in self.long_term_transactions
            if t.adjusted_gain_loss is not None
        )

    @property
    def transactions_with_missing_basis(self) -> list[CapitalTransaction]:
        """Transactions that require basis escalation."""
        return [t for t in self.transactions if t.requires_basis_escalation]

    @property
    def collectibles_gain(self) -> Decimal:
        """Total collectibles gain (28% rate)."""
        return sum(
            t.adjusted_gain_loss
            for t in self.long_term_transactions
            if t.is_collectibles
            and t.adjusted_gain_loss is not None
            and t.adjusted_gain_loss > Decimal("0")
        )

    @property
    def net_capital_gain_loss(self) -> Decimal:
        """Combined net capital gain/loss before carryover."""
        return self.net_short_term + self.net_long_term


@dataclass
class ScheduleDResult:
    """Result of Schedule D calculation.

    Contains final figures after applying loss limitations and carryovers.

    Attributes:
        net_short_term_gain_loss: Post-carryover short-term net.
        net_long_term_gain_loss: Post-carryover long-term net.
        collectibles_gain: Total gain from collectibles (28% rate).
        unrecaptured_1250_gain: Unrecaptured Section 1250 gain.
        gross_short_term: Pre-carryover short-term net.
        gross_long_term: Pre-carryover long-term net.
        net_capital_gain_loss: Combined net after carryover.
        capital_loss_carryover_used: Amount of prior carryover applied.
        capital_loss_limitation_applied: Whether $3k limit was applied.
        allowed_capital_loss: Allowed loss this year (max $3k/$1.5k).
        net_included_in_income: Amount included in AGI.
        new_loss_carryforward: Loss to carry to next year.
        qualified_dividends_and_ltcg: For preferential rate calculation.
        transactions_missing_basis: Count needing escalation.
    """

    # Part I: Short-term (after carryover)
    net_short_term_gain_loss: Decimal

    # Part II: Long-term (after carryover)
    net_long_term_gain_loss: Decimal
    collectibles_gain: Decimal
    unrecaptured_1250_gain: Decimal

    # Pre-carryover values for audit trail
    gross_short_term: Decimal
    gross_long_term: Decimal

    # Part III: Summary
    net_capital_gain_loss: Decimal
    capital_loss_carryover_used: Decimal
    capital_loss_limitation_applied: bool

    # Final figures
    allowed_capital_loss: Decimal
    net_included_in_income: Decimal
    new_loss_carryforward: Decimal

    # For tax calculation
    qualified_dividends_and_ltcg: Decimal

    # Escalation tracking
    transactions_missing_basis: int = 0


@dataclass
class QBIComponent:
    """QBI component from a single qualified trade or business.

    Tracks qualified business income and W-2 wage/property limitations
    for Section 199A deduction calculation.

    Attributes:
        business_name: Name of the trade or business.
        qualified_business_income: Net income from business (QBI).
        w2_wages: W-2 wages paid by the business (for limitation).
        unadjusted_basis_qualified_property: UBIA of qualified property.
        is_sstb: Whether business is a Specified Service Trade or Business.
        sstb_reason: Reason for SSTB classification (from auto-detect).
        source: Source of income (schedule_c, k1_partnership, k1_s_corp, rental).
    """

    business_name: str
    qualified_business_income: Decimal

    # W-2 wages (for limitation above threshold)
    w2_wages: Decimal = field(default_factory=lambda: Decimal("0"))

    # Qualified property (for limitation)
    unadjusted_basis_qualified_property: Decimal = field(
        default_factory=lambda: Decimal("0")
    )

    # SSTB status
    is_sstb: bool = False
    sstb_reason: str | None = None

    # Source
    source: str = "schedule_c"  # schedule_c, k1_partnership, k1_s_corp, rental

    @property
    def tentative_qbi_deduction(self) -> Decimal:
        """20% of QBI before limitations."""
        return max(Decimal("0"), self.qualified_business_income * Decimal("0.20"))

    @property
    def w2_wage_limit(self) -> Decimal:
        """50% of W-2 wages limitation."""
        return self.w2_wages * Decimal("0.50")

    @property
    def wage_plus_property_limit(self) -> Decimal:
        """25% of W-2 wages + 2.5% of UBIA limitation."""
        return (
            self.w2_wages * Decimal("0.25")
            + self.unadjusted_basis_qualified_property * Decimal("0.025")
        )

    @property
    def wage_limit(self) -> Decimal:
        """Greater of the two wage-based limits."""
        return max(self.w2_wage_limit, self.wage_plus_property_limit)


@dataclass
class QBIDeduction:
    """Final QBI deduction calculation result.

    Attributes:
        components: List of QBI components from each business.
        total_qbi: Sum of qualified business income.
        total_tentative_deduction: Sum of tentative deductions before limits.
        filing_status: Filing status for threshold determination.
        taxable_income: Taxable income before QBI deduction.
        threshold: Income threshold for this filing status.
        phaseout_range: Range over which limitations phase in.
        is_above_threshold: Whether in or above phaseout range.
        is_fully_phased_out: Whether fully above threshold + phaseout.
        wage_limit_applied: Whether W-2 wage limitation reduced deduction.
        sstb_exclusion_applied: Whether any SSTB was excluded/reduced.
        taxable_income_limit_applied: Whether 20% TI limit applied.
        qbi_deduction_before_limit: Deduction before TI limitation.
        taxable_income_limit: 20% of (TI - net capital gains).
        final_qbi_deduction: Final allowed deduction.
    """

    # Components
    components: list[QBIComponent]

    # Total QBI amounts
    total_qbi: Decimal
    total_tentative_deduction: Decimal

    # Threshold info
    filing_status: FilingStatus
    taxable_income: Decimal
    threshold: Decimal
    phaseout_range: Decimal
    is_above_threshold: bool
    is_fully_phased_out: bool

    # Limitations applied
    wage_limit_applied: bool
    sstb_exclusion_applied: bool
    taxable_income_limit_applied: bool

    # Final deduction
    qbi_deduction_before_limit: Decimal
    taxable_income_limit: Decimal
    final_qbi_deduction: Decimal


@dataclass
class PremiumTaxCredit:
    """Premium Tax Credit calculation result (Form 8962).

    Contains all components for ACA marketplace premium credit reconciliation.

    Attributes:
        household_size: Number of people in tax household.
        household_income: Modified AGI for household.
        federal_poverty_level: FPL for household size.
        income_as_fpl_percent: Income as percentage of FPL.
        annual_enrollment_premium: Total enrolled premiums from 1095-A.
        annual_slcsp_premium: Total SLCSP premiums from 1095-A.
        applicable_percentage: Contribution % based on income.
        annual_contribution: Income × applicable %.
        calculated_ptc: SLCSP premium - contribution.
        advance_ptc_received: Advance payments from 1095-A.
        net_ptc: Additional credit (+) or repayment (-).
        repayment_required: Whether repayment is due.
        repayment_amount: Amount to repay (may be limited).
        repayment_limitation: Cap based on income, or None if unlimited.
        additional_credit: Extra credit to claim.
        is_eligible: Whether eligible for PTC.
        ineligibility_reason: Why ineligible, if applicable.
        is_partial_year: Whether coverage was < 12 months.
        coverage_months: Number of months with coverage.
    """

    # Household data
    household_size: int
    household_income: Decimal
    federal_poverty_level: Decimal
    income_as_fpl_percent: Decimal

    # Premium data
    annual_enrollment_premium: Decimal
    annual_slcsp_premium: Decimal

    # Credit calculation
    applicable_percentage: Decimal
    annual_contribution: Decimal
    calculated_ptc: Decimal

    # Reconciliation
    advance_ptc_received: Decimal

    # Final result
    net_ptc: Decimal
    repayment_required: bool
    repayment_amount: Decimal
    repayment_limitation: Decimal | None
    additional_credit: Decimal

    # Eligibility
    is_eligible: bool
    ineligibility_reason: str | None = None

    # Partial year tracking
    is_partial_year: bool = False
    coverage_months: int = 12


@dataclass
class ItemizedDeductionBreakdown:
    """Itemized deduction components and totals.

    Attributes:
        mortgage_interest: Sum of mortgage interest from Form 1098.
        points_paid: Sum of points paid from Form 1098.
        mortgage_insurance_premiums: Sum of PMI from Form 1098.
        property_taxes_paid: Sum of property taxes from Form 1098.
        state_income_taxes_paid: Sum of state tax withholding (W-2, 1099-R, 1099-G).
        salt_total: Combined state and local taxes before cap.
        salt_deduction: SALT deduction after applying cap.
        total: Total itemized deductions (mortgage + points + PMI + SALT).
    """

    mortgage_interest: Decimal
    points_paid: Decimal
    mortgage_insurance_premiums: Decimal
    property_taxes_paid: Decimal
    state_income_taxes_paid: Decimal
    salt_total: Decimal
    salt_deduction: Decimal
    total: Decimal


@dataclass
class CreditInputs:
    """Aggregated inputs for credit evaluation.

    Attributes:
        education_expenses: Qualified education expenses for AOC/LLC.
        education_credit_type: Preferred credit type ("aoc" or "llc").
        retirement_contributions: Eligible retirement contributions for Saver's Credit.
    """

    education_expenses: Decimal
    education_credit_type: str
    retirement_contributions: Decimal


@dataclass
class DeductionResult:
    """Result of deduction calculation.

    Attributes:
        method: Either "standard" or "itemized".
        amount: The deduction amount to use.
        standard_amount: The standard deduction for this filing status.
        itemized_amount: The total itemized deductions provided.
    """

    method: str
    amount: Decimal
    standard_amount: Decimal
    itemized_amount: Decimal


@dataclass
class TaxSituation:
    """Tax situation for credits evaluation.

    Attributes:
        agi: Adjusted Gross Income.
        filing_status: One of "single", "mfj", "mfs", "hoh".
        tax_year: Tax year (e.g., 2024).
        num_qualifying_children: Number of children under 17.
        education_expenses: Qualified education expenses.
        education_credit_type: Education credit type ("aoc" or "llc").
        retirement_contributions: Eligible retirement contributions.
        earned_income: Earned income for EITC calculation.
        tax_liability: Pre-credit tax liability for ACTC calculation.
    """

    agi: Decimal
    filing_status: str
    tax_year: int
    num_qualifying_children: int = 0
    education_expenses: Decimal = field(default_factory=lambda: Decimal("0"))
    education_credit_type: str = "aoc"
    retirement_contributions: Decimal = field(default_factory=lambda: Decimal("0"))
    earned_income: Decimal = field(default_factory=lambda: Decimal("0"))
    tax_liability: Decimal | None = None


@dataclass
class CreditItem:
    """Individual tax credit.

    Attributes:
        name: Name of the credit (e.g., "Child Tax Credit").
        amount: Credit amount in dollars.
        refundable: Whether the credit is refundable (can exceed tax liability).
        form: IRS form for claiming this credit.
    """

    name: str
    amount: Decimal
    refundable: bool
    form: str


@dataclass
class CreditsResult:
    """Result of credits evaluation.

    Attributes:
        credits: List of applicable credit items.
        total_nonrefundable: Sum of non-refundable credits.
        total_refundable: Sum of refundable credits.
        total_credits: Grand total of all credits.
    """

    credits: list[CreditItem]
    total_nonrefundable: Decimal
    total_refundable: Decimal
    total_credits: Decimal


@dataclass
class TaxResult:
    """Result of tax calculation.

    Attributes:
        gross_tax: Tax before credits.
        bracket_breakdown: List of dicts with bracket, rate, and tax_in_bracket.
        effective_rate: Gross tax divided by taxable income.
        credits_applied: Total credits applied against tax.
        final_liability: Tax after credits (minimum 0).
        refundable_credits: Refundable credits that can result in refund.
    """

    gross_tax: Decimal
    bracket_breakdown: list[dict]
    effective_rate: Decimal
    credits_applied: Decimal = field(default_factory=lambda: Decimal("0"))
    final_liability: Decimal = field(default_factory=lambda: Decimal("0"))
    refundable_credits: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class VarianceItem:
    """Variance item for prior year comparison.

    Attributes:
        field: Name of the field with variance.
        current_value: Current year value.
        prior_value: Prior year value.
        variance_pct: Percentage change (absolute value).
        direction: Either "increase" or "decrease".
    """

    field: str
    current_value: Decimal
    prior_value: Decimal
    variance_pct: Decimal
    direction: str


# =============================================================================
# Constants
# =============================================================================

# Standard deductions by (year, filing_status)
STANDARD_DEDUCTIONS: dict[tuple[int, str], Decimal] = {
    # 2024 values
    (2024, "single"): Decimal("14600"),
    (2024, "mfj"): Decimal("29200"),
    (2024, "mfs"): Decimal("14600"),
    (2024, "hoh"): Decimal("21900"),
    # 2023 values
    (2023, "single"): Decimal("13850"),
    (2023, "mfj"): Decimal("27700"),
    (2023, "mfs"): Decimal("13850"),
    (2023, "hoh"): Decimal("20800"),
}

# SALT caps (state and local taxes) by filing status.
SALT_CAPS: dict[str, Decimal] = {
    "single": Decimal("10000"),
    "mfj": Decimal("10000"),
    "hoh": Decimal("10000"),
    "mfs": Decimal("5000"),
}

# Tax brackets by (year, filing_status) - list of (upper_bound, rate)
# None for upper_bound means no limit
TAX_BRACKETS: dict[tuple[int, str], list[tuple[Decimal | None, Decimal]]] = {
    (2024, "single"): [
        (Decimal("11600"), Decimal("0.10")),
        (Decimal("47150"), Decimal("0.12")),
        (Decimal("100525"), Decimal("0.22")),
        (Decimal("191950"), Decimal("0.24")),
        (Decimal("243725"), Decimal("0.32")),
        (Decimal("609350"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2024, "mfj"): [
        (Decimal("23200"), Decimal("0.10")),
        (Decimal("94300"), Decimal("0.12")),
        (Decimal("201050"), Decimal("0.22")),
        (Decimal("383900"), Decimal("0.24")),
        (Decimal("487450"), Decimal("0.32")),
        (Decimal("731200"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2024, "mfs"): [
        (Decimal("11600"), Decimal("0.10")),
        (Decimal("47150"), Decimal("0.12")),
        (Decimal("100525"), Decimal("0.22")),
        (Decimal("191950"), Decimal("0.24")),
        (Decimal("243725"), Decimal("0.32")),
        (Decimal("365600"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2024, "hoh"): [
        (Decimal("16550"), Decimal("0.10")),
        (Decimal("63100"), Decimal("0.12")),
        (Decimal("100500"), Decimal("0.22")),
        (Decimal("191950"), Decimal("0.24")),
        (Decimal("243700"), Decimal("0.32")),
        (Decimal("609350"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2023, "single"): [
        (Decimal("11000"), Decimal("0.10")),
        (Decimal("44725"), Decimal("0.12")),
        (Decimal("95375"), Decimal("0.22")),
        (Decimal("182100"), Decimal("0.24")),
        (Decimal("231250"), Decimal("0.32")),
        (Decimal("578125"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2023, "mfj"): [
        (Decimal("22000"), Decimal("0.10")),
        (Decimal("89450"), Decimal("0.12")),
        (Decimal("190750"), Decimal("0.22")),
        (Decimal("364200"), Decimal("0.24")),
        (Decimal("462500"), Decimal("0.32")),
        (Decimal("693750"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2023, "mfs"): [
        (Decimal("11000"), Decimal("0.10")),
        (Decimal("44725"), Decimal("0.12")),
        (Decimal("95375"), Decimal("0.22")),
        (Decimal("182100"), Decimal("0.24")),
        (Decimal("231250"), Decimal("0.32")),
        (Decimal("346875"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
    (2023, "hoh"): [
        (Decimal("15700"), Decimal("0.10")),
        (Decimal("59850"), Decimal("0.12")),
        (Decimal("95350"), Decimal("0.22")),
        (Decimal("182100"), Decimal("0.24")),
        (Decimal("231250"), Decimal("0.32")),
        (Decimal("578100"), Decimal("0.35")),
        (None, Decimal("0.37")),
    ],
}

# Child Tax Credit constants (2024)
CTC_AMOUNT = Decimal("2000")
CTC_PHASEOUT_SINGLE = Decimal("200000")
CTC_PHASEOUT_MFJ = Decimal("400000")
CTC_PHASEOUT_RATE = Decimal("50")  # $50 reduction per $1000 over threshold
ACTC_MAX_PER_CHILD = Decimal("1700")

# Education credit constants
AOC_REFUNDABLE_RATE = Decimal("0.40")
AOC_REFUNDABLE_CAP = Decimal("1000")
LLC_RATE = Decimal("0.20")
LLC_MAX_EXPENSES = Decimal("10000")
LLC_MAX_CREDIT = Decimal("2000")

# Saver's Credit rates by (year, filing_status) - list of (agi_limit, rate)
SAVERS_CREDIT_RATES: dict[tuple[int, str], list[tuple[Decimal, Decimal]]] = {
    (2024, "single"): [
        (Decimal("23000"), Decimal("0.50")),
        (Decimal("25000"), Decimal("0.20")),
        (Decimal("38250"), Decimal("0.10")),
    ],
    (2024, "mfj"): [
        (Decimal("46000"), Decimal("0.50")),
        (Decimal("50000"), Decimal("0.20")),
        (Decimal("76500"), Decimal("0.10")),
    ],
    (2024, "mfs"): [
        (Decimal("23000"), Decimal("0.50")),
        (Decimal("25000"), Decimal("0.20")),
        (Decimal("38250"), Decimal("0.10")),
    ],
    (2024, "hoh"): [
        (Decimal("34500"), Decimal("0.50")),
        (Decimal("37500"), Decimal("0.20")),
        (Decimal("57375"), Decimal("0.10")),
    ],
}
SAVERS_CREDIT_MAX_CONTRIBUTION = Decimal("2000")

# EITC simplified thresholds (2024, no children)
EITC_MAX_NO_CHILDREN = Decimal("632")
EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN = Decimal("18591")
EITC_INCOME_LIMITS_NO_CHILDREN = {
    "single": EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN,
    "mfj": EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN,
    "mfs": EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN,
    "hoh": EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN,
}


# Type alias for document union
TaxDocument = Union[
    W2Data,
    Form1099INT,
    Form1099DIV,
    Form1099NEC,
    Form1098,
    Form1099R,
    Form1099G,
    Form1098T,
    Form5498,
    Form1099S,
    FormK1,
]


# =============================================================================
# Schedule C Calculation (PTAX-04-03)
# =============================================================================


def calculate_schedule_c(data: ScheduleCData) -> dict[str, Decimal]:
    """Calculate Schedule C net profit and key figures.

    Computes line-by-line values from Schedule C (Profit or Loss from Business)
    following IRS form structure.

    Args:
        data: ScheduleCData with business income and expenses.

    Returns:
        Dict with calculation results:
        - gross_income: Line 3 (gross receipts - returns)
        - gross_profit: Line 5 (gross income - COGS)
        - total_income: Line 7 (gross profit + other income)
        - total_expenses: Line 28 (sum of all deductions)
        - net_profit_or_loss: Line 31 (total income - expenses)
        - qualified_business_income: QBI for Section 199A deduction

    Example:
        >>> sch_c = ScheduleCData(
        ...     business_name="Consulting",
        ...     business_activity="IT",
        ...     principal_business_code="541511",
        ...     gross_receipts=Decimal("100000"),
        ...     expenses=ScheduleCExpenses(office_expense=Decimal("5000")),
        ... )
        >>> result = calculate_schedule_c(sch_c)
        >>> result["net_profit_or_loss"]
        Decimal('95000')
    """
    result = {
        "gross_income": data.gross_income,
        "gross_profit": data.gross_profit,
        "total_income": data.total_income,
        "total_expenses": data.total_expenses,
        "net_profit_or_loss": data.net_profit_or_loss,
    }

    # QBI is generally net profit minus SE tax deduction (calculated later)
    # For now, return net profit as qualified business income (QBI can't be negative)
    result["qualified_business_income"] = max(Decimal("0"), data.net_profit_or_loss)

    return result


def calculate_self_employment_tax(
    net_self_employment_earnings: Decimal,
    filing_status: FilingStatus,
    tax_year: int = 2024,
) -> SelfEmploymentTax:
    """Calculate self-employment tax (Schedule SE).

    Self-employment tax consists of Social Security and Medicare taxes for
    self-employed individuals. Unlike W-2 employees who split these taxes
    with employers, self-employed pay both portions.

    2024 Rates:
    - 12.4% Social Security on net earnings up to $168,600 (wage base)
    - 2.9% Medicare on all net earnings
    - Additional 0.9% Medicare on earnings above threshold ($200k single/$250k MFJ)

    Args:
        net_self_employment_earnings: Net earnings from Schedule C or K-1 Box 14.
        filing_status: Filing status for Additional Medicare threshold.
        tax_year: Tax year for rates and limits (default 2024).

    Returns:
        SelfEmploymentTax with breakdown of all components.

    Example:
        >>> result = calculate_self_employment_tax(
        ...     Decimal("100000"),
        ...     FilingStatus.SINGLE,
        ... )
        >>> result.net_earnings
        Decimal('92350.00')
        >>> result.total_se_tax
        Decimal('14129.55')
    """
    config = get_tax_year_config(tax_year)

    # Additional Medicare threshold varies by filing status
    threshold_map = {
        FilingStatus.SINGLE: config.additional_medicare_threshold_single,
        FilingStatus.MARRIED_FILING_JOINTLY: config.additional_medicare_threshold_mfj,
        FilingStatus.MARRIED_FILING_SEPARATELY: config.additional_medicare_threshold_mfs,
        FilingStatus.HEAD_OF_HOUSEHOLD: config.additional_medicare_threshold_single,
        FilingStatus.QUALIFYING_WIDOW: config.additional_medicare_threshold_mfj,
    }

    # Net earnings = 92.35% of net self-employment income
    # This matches the employer portion adjustment for W-2 workers
    net_earnings = net_self_employment_earnings * config.se_net_earnings_factor
    net_earnings = max(Decimal("0"), net_earnings)

    # Social Security (12.4% up to wage base)
    ss_taxable = min(net_earnings, config.ss_wage_base)
    social_security_tax = ss_taxable * config.se_ss_rate

    # Medicare (2.9% on all earnings)
    medicare_tax = net_earnings * config.se_medicare_rate

    # Additional Medicare (0.9% over threshold)
    threshold = threshold_map.get(
        filing_status, config.additional_medicare_threshold_single
    )
    additional_earnings = max(Decimal("0"), net_earnings - threshold)
    additional_medicare_tax = additional_earnings * config.additional_medicare_rate

    # Total and deductible portion (50% is above-the-line deduction)
    total_se_tax = social_security_tax + medicare_tax + additional_medicare_tax
    deductible_portion = total_se_tax * config.se_tax_deduction_rate

    return SelfEmploymentTax(
        net_earnings=net_earnings.quantize(Decimal("0.01")),
        social_security_tax=social_security_tax.quantize(Decimal("0.01")),
        medicare_tax=medicare_tax.quantize(Decimal("0.01")),
        additional_medicare_tax=additional_medicare_tax.quantize(Decimal("0.01")),
        total_se_tax=total_se_tax.quantize(Decimal("0.01")),
        deductible_portion=deductible_portion.quantize(Decimal("0.01")),
        social_security_wage_base=config.ss_wage_base,
        additional_medicare_threshold=threshold,
    )


# =============================================================================
# Schedule E Calculation (PTAX-04-04)
# =============================================================================


def calculate_schedule_e(
    data: ScheduleEData,
    modified_agi: Decimal,
    filing_status: FilingStatus,
) -> ScheduleEResult:
    """Calculate Schedule E rental income with passive activity loss limitations.

    Passive Activity Loss Rules (simplified):
    - Rental activities are generally passive (can't offset other income)
    - Active participation: $25,000 loss allowance
    - Allowance phases out from $100k to $150k MAGI
    - Real estate professionals: No passive limitations

    Args:
        data: ScheduleEData with all rental properties.
        modified_agi: MAGI for phaseout calculation.
        filing_status: For determining phaseout thresholds.

    Returns:
        ScheduleEResult with final figures and limitation details.

    Example:
        >>> sch_e = ScheduleEData(properties=[prop], actively_participates=True)
        >>> result = calculate_schedule_e(sch_e, Decimal("90000"), FilingStatus.SINGLE)
        >>> result.net_rental_income_loss
        Decimal('-10000')  # Full loss allowed under $100k MAGI
    """
    config = get_tax_year_config(2024)

    # Calculate per-property results
    property_results = []
    for prop in data.properties:
        property_results.append(
            {
                "address": prop.property_address,
                "income": prop.rental_income,
                "expenses": prop.expenses.total,
                "net": prop.net_income_loss,
                "qbi_eligible": prop.qbi_eligible and not prop.is_personal_use_property,
            }
        )

    net_before = data.net_before_limitations

    # QBI-eligible rental income (only profitable, eligible properties)
    qbi_eligible_income = sum(
        p["net"]
        for p in property_results
        if p["qbi_eligible"] and p["net"] > Decimal("0")
    )

    # If net income (not loss), no limitations apply
    if net_before >= Decimal("0"):
        return ScheduleEResult(
            total_rental_income=data.total_rental_income,
            total_expenses=data.total_expenses,
            net_before_limitations=net_before,
            loss_limited=False,
            allowed_loss=Decimal("0"),
            suspended_loss=Decimal("0"),
            net_rental_income_loss=net_before,
            qbi_rental_income=qbi_eligible_income,
            property_results=property_results,
        )

    # Handle rental loss
    rental_loss = abs(net_before)

    # Real estate professional: No limitation
    if data.is_real_estate_professional:
        allowed_loss = rental_loss
        suspended_loss = Decimal("0")
    # Active participation: $25k allowance with phaseout
    elif data.actively_participates:
        phaseout_start = config.pal_phaseout_start
        phaseout_end = config.pal_phaseout_end
        max_allowance = config.pal_allowance

        if modified_agi <= phaseout_start:
            allowance = max_allowance
        elif modified_agi >= phaseout_end:
            allowance = Decimal("0")
        else:
            # Reduce by $1 for every $2 over $100k
            reduction = (modified_agi - phaseout_start) * Decimal("0.5")
            allowance = max(Decimal("0"), max_allowance - reduction)

        allowed_loss = min(rental_loss, allowance)
        suspended_loss = rental_loss - allowed_loss
    else:
        # No active participation: No current year loss allowed
        allowed_loss = Decimal("0")
        suspended_loss = rental_loss

    return ScheduleEResult(
        total_rental_income=data.total_rental_income,
        total_expenses=data.total_expenses,
        net_before_limitations=net_before,
        loss_limited=suspended_loss > Decimal("0"),
        allowed_loss=allowed_loss,
        suspended_loss=suspended_loss,
        net_rental_income_loss=-allowed_loss,  # Negative = loss
        qbi_rental_income=Decimal("0"),  # No QBI for loss
        property_results=property_results,
    )


# =============================================================================
# Schedule D Calculation (PTAX-04-05)
# =============================================================================


def get_capital_gains_rate(
    taxable_income: Decimal,
    filing_status: FilingStatus,
    tax_year: int = 2024,
) -> Decimal:
    """Determine the applicable long-term capital gains tax rate.

    2024 Rates:
    - 0%: Below threshold (depends on filing status)
    - 15%: Middle income
    - 20%: High income

    Args:
        taxable_income: Total taxable income (not just capital gains).
        filing_status: Filing status for threshold determination.
        tax_year: Tax year for thresholds (default 2024).

    Returns:
        Rate as decimal (e.g., Decimal("0.15") for 15%).

    Example:
        >>> rate = get_capital_gains_rate(Decimal("40000"), FilingStatus.SINGLE)
        >>> rate
        Decimal('0')  # 0% rate
    """
    config = get_tax_year_config(tax_year)

    # Get thresholds from TaxYearConfig
    if filing_status in (
        FilingStatus.MARRIED_FILING_JOINTLY,
        FilingStatus.QUALIFYING_WIDOW,
    ):
        low_threshold = config.ltcg_0_threshold_mfj
        high_threshold = config.ltcg_15_threshold_mfj
    elif filing_status == FilingStatus.MARRIED_FILING_SEPARATELY:
        # MFS has half of MFJ thresholds
        low_threshold = config.ltcg_0_threshold_mfj / 2
        high_threshold = config.ltcg_15_threshold_mfj / 2
    elif filing_status == FilingStatus.HEAD_OF_HOUSEHOLD:
        # HOH has specific thresholds (between single and MFJ)
        low_threshold = Decimal("63000")  # 2024 HOH 0% threshold
        high_threshold = Decimal("551350")  # 2024 HOH 15% threshold
    else:
        # Single
        low_threshold = config.ltcg_0_threshold_single
        high_threshold = config.ltcg_15_threshold_single

    if taxable_income <= low_threshold:
        return Decimal("0")
    elif taxable_income <= high_threshold:
        return Decimal("0.15")
    else:
        return Decimal("0.20")


def calculate_schedule_d(
    data: ScheduleDData,
    filing_status: FilingStatus,
) -> ScheduleDResult:
    """Calculate Schedule D capital gains/losses with limitations.

    Capital Loss Rules:
    - Net capital loss limited to $3,000/year ($1,500 MFS)
    - Excess loss carries forward to future years
    - Short-term losses offset short-term gains first
    - Long-term losses offset long-term gains first
    - Then net against each other
    - Prior year carryover applies to short-term gains first

    Args:
        data: ScheduleDData with all transactions.
        filing_status: For loss limitation amount.

    Returns:
        ScheduleDResult with final figures.

    Example:
        >>> sch_d = ScheduleDData(transactions=[txn1, txn2])
        >>> result = calculate_schedule_d(sch_d, FilingStatus.SINGLE)
        >>> result.net_included_in_income
        Decimal('2000')
    """
    config = get_tax_year_config(2024)

    # Get gross short-term and long-term before carryover
    gross_st = data.net_short_term
    gross_lt = data.net_long_term

    # Start with gross values for post-carryover calculation
    net_st = gross_st
    net_lt = gross_lt

    # Special long-term categories
    collectibles_gain = data.collectibles_gain
    unrecaptured_1250 = Decimal("0")  # Would need depreciation data

    # Apply prior year carryover to short-term first, then long-term
    carryover_used = Decimal("0")
    remaining_carryover = data.prior_year_loss_carryover

    if remaining_carryover > Decimal("0") and net_st > Decimal("0"):
        st_offset = min(net_st, remaining_carryover)
        net_st -= st_offset
        remaining_carryover -= st_offset
        carryover_used += st_offset

    if remaining_carryover > Decimal("0") and net_lt > Decimal("0"):
        lt_offset = min(net_lt, remaining_carryover)
        net_lt -= lt_offset
        remaining_carryover -= lt_offset
        carryover_used += lt_offset

    # Combined net gain/loss
    net_combined = net_st + net_lt

    # Apply loss limitation
    loss_limit = config.capital_loss_limit
    if filing_status == FilingStatus.MARRIED_FILING_SEPARATELY:
        loss_limit = config.capital_loss_limit_mfs

    if net_combined < Decimal("0"):
        # Net loss - apply limitation
        total_loss = abs(net_combined)
        allowed_loss = min(total_loss, loss_limit)
        new_carryforward = total_loss - allowed_loss
        net_included = -allowed_loss
        loss_limited = total_loss > loss_limit
    else:
        # Net gain - no limitation
        allowed_loss = Decimal("0")
        new_carryforward = Decimal("0")
        net_included = net_combined
        loss_limited = False

    # Qualified dividends and LTCG for preferential rates
    qualified_ltcg = max(Decimal("0"), net_lt)

    # Count transactions missing basis for escalation
    missing_basis_count = len(data.transactions_with_missing_basis)

    return ScheduleDResult(
        net_short_term_gain_loss=net_st,
        net_long_term_gain_loss=net_lt,
        collectibles_gain=collectibles_gain,
        unrecaptured_1250_gain=unrecaptured_1250,
        gross_short_term=gross_st,
        gross_long_term=gross_lt,
        net_capital_gain_loss=net_combined,
        capital_loss_carryover_used=carryover_used,
        capital_loss_limitation_applied=loss_limited,
        allowed_capital_loss=allowed_loss,
        net_included_in_income=net_included,
        new_loss_carryforward=new_carryforward,
        qualified_dividends_and_ltcg=qualified_ltcg,
        transactions_missing_basis=missing_basis_count,
    )


def convert_1099b_to_transactions(
    forms_1099b: list[Form1099B],
) -> tuple[list[CapitalTransaction], list[Form1099B]]:
    """Convert Form 1099-B documents to CapitalTransaction objects.

    Transforms broker-reported 1099-B data into standardized CapitalTransaction
    objects for Schedule D processing. Tracks forms with missing cost basis
    for escalation/client follow-up.

    Args:
        forms_1099b: List of Form1099B from document extraction.

    Returns:
        Tuple of:
        - List of CapitalTransaction objects ready for Schedule D
        - List of Form1099B with missing basis (needs escalation)

    Example:
        >>> form = Form1099B(
        ...     payer_name="Broker Inc",
        ...     payer_tin="12-3456789",
        ...     recipient_tin="123-45-6789",
        ...     description="100 sh AAPL",
        ...     date_sold="2024-06-15",
        ...     proceeds=Decimal("15000"),
        ...     cost_basis=Decimal("10000"),
        ...     is_long_term=True,
        ...     basis_reported_to_irs=True,
        ... )
        >>> transactions, missing = convert_1099b_to_transactions([form])
        >>> len(transactions)
        1
        >>> transactions[0].gain_loss
        Decimal('5000')
    """
    transactions: list[CapitalTransaction] = []
    missing_basis: list[Form1099B] = []

    for form in forms_1099b:
        txn = CapitalTransaction(
            description=form.description,
            date_acquired=form.date_acquired,
            date_sold=form.date_sold,
            proceeds=form.proceeds,
            cost_basis=form.cost_basis,
            is_short_term=form.is_short_term,
            is_long_term=form.is_long_term,
            basis_reported_to_irs=form.basis_reported_to_irs,
            wash_sale_disallowed=form.wash_sale_loss_disallowed,
            is_collectibles=form.is_collectibles,
        )
        transactions.append(txn)

        # Track forms needing basis lookup from client
        if form.cost_basis is None and not form.basis_reported_to_irs:
            missing_basis.append(form)

    return transactions, missing_basis


# =============================================================================
# QBI Deduction - Section 199A (PTAX-04-06)
# =============================================================================

# QBI Section 199A thresholds (2024)
# Format: (threshold, phaseout_range)
QBI_THRESHOLDS: dict[FilingStatus, tuple[Decimal, Decimal]] = {
    FilingStatus.SINGLE: (Decimal("191950"), Decimal("50000")),
    FilingStatus.MARRIED_FILING_JOINTLY: (Decimal("383900"), Decimal("100000")),
    FilingStatus.MARRIED_FILING_SEPARATELY: (Decimal("191950"), Decimal("50000")),
    FilingStatus.HEAD_OF_HOUSEHOLD: (Decimal("191950"), Decimal("50000")),
    FilingStatus.QUALIFYING_WIDOW: (Decimal("383900"), Decimal("100000")),
}


def calculate_qbi_deduction(
    components: list[QBIComponent],
    taxable_income: Decimal,
    net_capital_gains: Decimal,
    filing_status: FilingStatus,
) -> QBIDeduction:
    """Calculate QBI deduction under Section 199A.

    Implements the simplified QBI rules:
    1. Below threshold: 20% of QBI, no W-2 wage limitation
    2. In phaseout range: Phased limitation on SSTB and wage limit
    3. Above phaseout: Full W-2 wage limitation, no SSTB deduction

    Final deduction is lesser of:
    - Combined QBI deduction from all businesses
    - 20% of (taxable income - net capital gains)

    Args:
        components: List of QBI components from each business.
        taxable_income: Taxable income before QBI deduction.
        net_capital_gains: Net capital gains (for final limitation).
        filing_status: For threshold determination.

    Returns:
        QBIDeduction with complete breakdown.

    Example:
        >>> comp = QBIComponent(
        ...     business_name="Consulting",
        ...     qualified_business_income=Decimal("100000"),
        ... )
        >>> result = calculate_qbi_deduction(
        ...     [comp],
        ...     taxable_income=Decimal("150000"),
        ...     net_capital_gains=Decimal("0"),
        ...     filing_status=FilingStatus.SINGLE,
        ... )
        >>> result.final_qbi_deduction
        Decimal('20000.00')
    """
    threshold, phaseout = QBI_THRESHOLDS.get(
        filing_status,
        (Decimal("191950"), Decimal("50000")),
    )

    phaseout_end = threshold + phaseout

    is_above_threshold = taxable_income > threshold
    is_fully_phased_out = taxable_income >= phaseout_end

    # Calculate deduction for each component
    total_deduction = Decimal("0")
    wage_limit_applied = False
    sstb_exclusion_applied = False

    for comp in components:
        if comp.qualified_business_income <= Decimal("0"):
            continue

        tentative = comp.tentative_qbi_deduction

        # Handle SSTB
        if comp.is_sstb:
            if is_fully_phased_out:
                # No deduction for SSTB above threshold
                sstb_exclusion_applied = True
                continue
            elif is_above_threshold:
                # Partial SSTB in phaseout
                sstb_exclusion_applied = True
                phaseout_pct = (taxable_income - threshold) / phaseout
                tentative = tentative * (Decimal("1") - phaseout_pct)

        # Apply W-2 wage limitation if above threshold
        if is_above_threshold and not is_fully_phased_out:
            # Phased-in limitation
            phaseout_pct = (taxable_income - threshold) / phaseout
            limit = comp.wage_limit
            reduction = (tentative - limit) * phaseout_pct
            if reduction > Decimal("0"):
                tentative = max(tentative - reduction, limit)
                wage_limit_applied = True
        elif is_fully_phased_out:
            # Full limitation
            if tentative > comp.wage_limit:
                tentative = comp.wage_limit
                wage_limit_applied = True

        total_deduction += tentative

    # Final limitation: 20% of (taxable income - net capital gains)
    taxable_income_limit = (taxable_income - net_capital_gains) * Decimal("0.20")
    taxable_income_limit = max(Decimal("0"), taxable_income_limit)

    final_deduction = min(total_deduction, taxable_income_limit)
    taxable_income_limit_applied = total_deduction > taxable_income_limit

    return QBIDeduction(
        components=components,
        total_qbi=sum(c.qualified_business_income for c in components),
        total_tentative_deduction=sum(c.tentative_qbi_deduction for c in components),
        filing_status=filing_status,
        taxable_income=taxable_income,
        threshold=threshold,
        phaseout_range=phaseout,
        is_above_threshold=is_above_threshold,
        is_fully_phased_out=is_fully_phased_out,
        wage_limit_applied=wage_limit_applied,
        sstb_exclusion_applied=sstb_exclusion_applied,
        taxable_income_limit_applied=taxable_income_limit_applied,
        qbi_deduction_before_limit=total_deduction.quantize(Decimal("0.01")),
        taxable_income_limit=taxable_income_limit.quantize(Decimal("0.01")),
        final_qbi_deduction=final_deduction.quantize(Decimal("0.01")),
    )


def build_qbi_from_schedule_c(
    schedule_c: ScheduleCData,
    se_tax_deduction: Decimal,
    is_sstb: bool | None = None,
) -> QBIComponent:
    """Build QBI component from Schedule C data.

    QBI = Net profit - 50% SE tax - SE health insurance - retirement contributions
    Simplified: QBI = Net profit - 50% SE tax

    If is_sstb is None, automatically classifies based on NAICS code
    and business description using classify_sstb().

    Args:
        schedule_c: Schedule C data for the business.
        se_tax_deduction: Deductible portion of SE tax (50%).
        is_sstb: Override SSTB classification (None = auto-detect).

    Returns:
        QBIComponent for the Schedule C business.

    Example:
        >>> sch_c = ScheduleCData(
        ...     business_name="Tech Consulting",
        ...     business_activity="Consulting",
        ...     principal_business_code="541611",
        ...     gross_receipts=Decimal("150000"),
        ...     expenses=ScheduleCExpenses(),
        ... )
        >>> qbi = build_qbi_from_schedule_c(sch_c, Decimal("7000"))
        >>> qbi.is_sstb  # Auto-detected as consulting SSTB
        True
    """
    from src.agents.personal_tax.sstb import classify_sstb

    # Auto-classify SSTB if not explicitly provided
    sstb_reason = None
    if is_sstb is None:
        is_sstb, sstb_reason = classify_sstb(
            schedule_c.principal_business_code,
            schedule_c.business_activity,
            schedule_c.business_name,
        )
    elif is_sstb:
        sstb_reason = "Manually specified"

    qbi = schedule_c.net_profit_or_loss - se_tax_deduction

    return QBIComponent(
        business_name=schedule_c.business_name,
        qualified_business_income=max(Decimal("0"), qbi),
        w2_wages=Decimal("0"),  # Sole prop has no W-2 wages
        is_sstb=is_sstb,
        sstb_reason=sstb_reason,
        source="schedule_c",
    )


def build_qbi_from_k1(
    k1: FormK1,
    is_sstb: bool = False,
) -> QBIComponent:
    """Build QBI component from K-1 data.

    IMPORTANT: Guaranteed payments (Box 4) are NOT QBI.
    - Guaranteed payments are treated like wages for partners
    - QBI = Box 1 (ordinary income) EXCLUDING guaranteed payments
    - In reality, K-1 QBI statement would provide exact amount

    For K-1: QBI = Box 1 (ordinary income) only
    W-2 wages and UBIA may be reported on K-1 supplemental.

    Args:
        k1: K-1 data from partnership or S-corp.
        is_sstb: Whether business is SSTB (from K-1 supplemental).

    Returns:
        QBIComponent for the K-1 entity.

    Example:
        >>> k1 = FormK1(
        ...     entity_name="ABC Partners",
        ...     entity_ein="12-3456789",
        ...     entity_type="partnership",
        ...     ordinary_business_income=Decimal("50000"),
        ...     guaranteed_payments=Decimal("20000"),  # NOT included in QBI
        ... )
        >>> qbi = build_qbi_from_k1(k1)
        >>> qbi.qualified_business_income
        Decimal('50000')
    """
    # Use ordinary income only - guaranteed payments are NOT QBI
    # Note: K-1s often include a QBI statement with exact amounts
    qbi = k1.ordinary_business_income or Decimal("0")

    # Guaranteed payments are subject to SE tax but NOT QBI
    # They are reported separately and handled in aggregate_income()

    return QBIComponent(
        business_name=k1.entity_name,
        qualified_business_income=max(Decimal("0"), qbi),
        w2_wages=Decimal("0"),  # Would come from K-1 supplemental
        unadjusted_basis_qualified_property=Decimal("0"),
        is_sstb=is_sstb,
        source="k1_partnership" if k1.entity_type == "partnership" else "k1_s_corp",
    )


def build_qbi_from_rental(
    rental_net_income: Decimal,
    property_name: str,
    qualifies_safe_harbor: bool = True,
) -> QBIComponent | None:
    """Build QBI component from rental income (if qualifying).

    Rental qualifies for QBI under safe harbor if:
    - 250+ hours of rental services per year
    - Separate books and records
    - Not triple net lease

    Args:
        rental_net_income: Net rental income from Schedule E.
        property_name: Name/address of the property.
        qualifies_safe_harbor: Whether rental meets safe harbor requirements.

    Returns:
        QBIComponent if qualifying rental income, None otherwise.

    Example:
        >>> qbi = build_qbi_from_rental(Decimal("15000"), "123 Main St")
        >>> qbi.qualified_business_income
        Decimal('15000')
    """
    if not qualifies_safe_harbor or rental_net_income <= Decimal("0"):
        return None

    return QBIComponent(
        business_name=f"Rental: {property_name}",
        qualified_business_income=rental_net_income,
        w2_wages=Decimal("0"),
        is_sstb=False,  # Rentals are never SSTB
        source="rental",
    )


# =============================================================================
# Premium Tax Credit - Form 8962 (PTAX-04-07)
# =============================================================================

# Federal Poverty Level (2024) - 48 contiguous states
# Used for Premium Tax Credit calculation
FPL_2024: dict[int, Decimal] = {
    1: Decimal("14580"),
    2: Decimal("19720"),
    3: Decimal("24860"),
    4: Decimal("30000"),
    5: Decimal("35140"),
    6: Decimal("40280"),
    7: Decimal("45420"),
    8: Decimal("50560"),
}

# Additional person above 8
FPL_2024_ADDITIONAL = Decimal("5140")


def get_fpl(household_size: int, tax_year: int = 2024) -> Decimal:
    """Get Federal Poverty Level for household size.

    Args:
        household_size: Number of people in tax household.
        tax_year: Tax year (currently only 2024 supported).

    Returns:
        Federal Poverty Level amount.

    Example:
        >>> get_fpl(4)
        Decimal('30000')
    """
    if household_size <= 8:
        return FPL_2024.get(household_size, FPL_2024[1])
    else:
        # For each additional person above 8
        return FPL_2024[8] + FPL_2024_ADDITIONAL * (household_size - 8)


def get_applicable_percentage(
    income_as_fpl_percent: Decimal,
) -> Decimal:
    """Get applicable percentage for PTC calculation.

    2024 rates (ARP extended):
    - <150% FPL: 0%
    - 150-200% FPL: 0-2%
    - 200-250% FPL: 2-4%
    - 250-300% FPL: 4-6%
    - 300-400% FPL: 6-8.5%
    - >400% FPL: 8.5%

    Args:
        income_as_fpl_percent: Household income as % of FPL (e.g., 250 for 250%).

    Returns:
        Contribution as decimal (e.g., 0.04 for 4%).

    Example:
        >>> get_applicable_percentage(Decimal("200"))
        Decimal('0.02')
    """
    if income_as_fpl_percent < Decimal("150"):
        return Decimal("0")
    elif income_as_fpl_percent < Decimal("200"):
        # Linear from 0% to 2%
        pct = (income_as_fpl_percent - Decimal("150")) / Decimal("50")
        return pct * Decimal("0.02")
    elif income_as_fpl_percent < Decimal("250"):
        # Linear from 2% to 4%
        pct = (income_as_fpl_percent - Decimal("200")) / Decimal("50")
        return Decimal("0.02") + pct * Decimal("0.02")
    elif income_as_fpl_percent < Decimal("300"):
        # Linear from 4% to 6%
        pct = (income_as_fpl_percent - Decimal("250")) / Decimal("50")
        return Decimal("0.04") + pct * Decimal("0.02")
    elif income_as_fpl_percent < Decimal("400"):
        # Linear from 6% to 8.5%
        pct = (income_as_fpl_percent - Decimal("300")) / Decimal("100")
        return Decimal("0.06") + pct * Decimal("0.025")
    else:
        return Decimal("0.085")


def get_ptc_repayment_limit(
    income_as_fpl_percent: Decimal,
    filing_status: FilingStatus,
) -> Decimal | None:
    """Get repayment limitation for excess advance PTC.

    2024 limits:
    | FPL %     | Single/HOH | MFJ/QW  |
    |-----------|------------|---------|
    | <200%     | $375       | $750    |
    | 200-300%  | $975       | $1,950  |
    | 300-400%  | $1,625     | $3,250  |
    | >400%     | No limit   | No limit|

    Args:
        income_as_fpl_percent: Income as % of FPL.
        filing_status: Filing status for limit determination.

    Returns:
        Repayment limit or None if no limit applies.

    Example:
        >>> get_ptc_repayment_limit(Decimal("250"), FilingStatus.SINGLE)
        Decimal('975')
    """
    is_joint = filing_status in (
        FilingStatus.MARRIED_FILING_JOINTLY,
        FilingStatus.QUALIFYING_WIDOW,
    )

    if income_as_fpl_percent >= Decimal("400"):
        return None  # No limit - full repayment required
    elif income_as_fpl_percent >= Decimal("300"):
        return Decimal("3250") if is_joint else Decimal("1625")
    elif income_as_fpl_percent >= Decimal("200"):
        return Decimal("1950") if is_joint else Decimal("975")
    else:
        return Decimal("750") if is_joint else Decimal("375")


def calculate_premium_tax_credit(
    household_income: Decimal,
    household_size: int,
    form_1095a: Form1095A,
    filing_status: FilingStatus,
) -> PremiumTaxCredit:
    """Calculate Premium Tax Credit and reconcile advance payments.

    Form 8962 logic:
    1. Calculate household income as % of FPL
    2. Determine applicable percentage (contribution %)
    3. Calculate annual contribution (income × applicable %)
    4. Calculate PTC = SLCSP premium - contribution
    5. Compare to advance payments received
    6. Determine additional credit or repayment (with limitations)

    Args:
        household_income: Modified AGI for household.
        household_size: Number of people in tax household.
        form_1095a: Form 1095-A with marketplace data.
        filing_status: For repayment limitation.

    Returns:
        PremiumTaxCredit with complete reconciliation.

    Example:
        >>> from src.documents.models import Form1095A
        >>> form = Form1095A(
        ...     recipient_name="John Smith",
        ...     recipient_tin="123-45-6789",
        ...     marketplace_id="FFM123",
        ...     policy_number="POL123",
        ...     policy_start_date="2024-01-01",
        ...     annual_enrollment_premium=Decimal("7800"),
        ...     annual_slcsp_premium=Decimal("9600"),
        ...     annual_advance_ptc=Decimal("4800"),
        ... )
        >>> result = calculate_premium_tax_credit(
        ...     Decimal("40000"), 2, form, FilingStatus.SINGLE
        ... )
        >>> result.is_eligible
        True
    """
    # Calculate FPL percentage
    fpl = get_fpl(household_size)
    income_as_fpl_percent = (household_income / fpl) * Decimal("100")

    # Check eligibility (100-400% FPL for 2024 under ARP extension)
    # Below 100% generally eligible for Medicaid, above 400% no longer excluded
    is_eligible = income_as_fpl_percent >= Decimal("100")
    ineligibility_reason = None
    if not is_eligible:
        ineligibility_reason = "Income below 100% FPL (may qualify for Medicaid)"

    # Get applicable percentage
    applicable_pct = get_applicable_percentage(income_as_fpl_percent)

    # Calculate annual contribution (what taxpayer should pay)
    annual_contribution = household_income * applicable_pct

    # Get premium data from 1095-A
    annual_slcsp = form_1095a.annual_slcsp_premium
    annual_enrolled = form_1095a.annual_enrollment_premium
    advance_ptc = form_1095a.annual_advance_ptc

    # Calculate PTC = SLCSP - contribution (but not more than enrolled premium)
    calculated_ptc = max(Decimal("0"), annual_slcsp - annual_contribution)
    calculated_ptc = min(calculated_ptc, annual_enrolled)

    # Reconciliation: compare calculated PTC to advance received
    net_ptc = calculated_ptc - advance_ptc

    # Determine repayment or additional credit
    repayment_required = net_ptc < Decimal("0")
    additional_credit = max(Decimal("0"), net_ptc)

    # Apply repayment limitation if needed
    repayment_limitation = None
    if repayment_required:
        repayment_limitation = get_ptc_repayment_limit(
            income_as_fpl_percent, filing_status
        )

    if repayment_required:
        raw_repayment = abs(net_ptc)
        if repayment_limitation is not None:
            repayment_amount = min(raw_repayment, repayment_limitation)
        else:
            repayment_amount = raw_repayment
    else:
        repayment_amount = Decimal("0")

    # Determine coverage months from monthly data
    coverage_months = sum(
        1 for premium in form_1095a.monthly_enrollment_premium if premium > Decimal("0")
    )
    is_partial_year = coverage_months < 12 and coverage_months > 0

    return PremiumTaxCredit(
        household_size=household_size,
        household_income=household_income,
        federal_poverty_level=fpl,
        income_as_fpl_percent=income_as_fpl_percent.quantize(Decimal("0.01")),
        annual_enrollment_premium=annual_enrolled,
        annual_slcsp_premium=annual_slcsp,
        applicable_percentage=applicable_pct.quantize(Decimal("0.0001")),
        annual_contribution=annual_contribution.quantize(Decimal("0.01")),
        calculated_ptc=calculated_ptc.quantize(Decimal("0.01")),
        advance_ptc_received=advance_ptc,
        net_ptc=net_ptc.quantize(Decimal("0.01")),
        repayment_required=repayment_required,
        repayment_amount=repayment_amount.quantize(Decimal("0.01")),
        repayment_limitation=repayment_limitation,
        additional_credit=additional_credit.quantize(Decimal("0.01")),
        is_eligible=is_eligible,
        ineligibility_reason=ineligibility_reason,
        is_partial_year=is_partial_year,
        coverage_months=coverage_months,
    )


# =============================================================================
# Income Aggregation (PTAX-03)
# =============================================================================


def aggregate_income(
    documents: list[TaxDocument],
    schedule_c_data: list[ScheduleCData] | None = None,
    schedule_e_data: ScheduleEData | None = None,
    schedule_d_data: ScheduleDData | None = None,
    filing_status: FilingStatus = FilingStatus.SINGLE,
    modified_agi_for_pal: Decimal | None = None,
) -> IncomeSummary:
    """Aggregate income from all tax documents.

    Args:
        documents: List of supported tax document models (W-2, 1099s, K-1).
        schedule_c_data: Optional list of Schedule C business data.
        schedule_e_data: Optional Schedule E rental property data.
        schedule_d_data: Optional Schedule D capital gains/losses data.
        filing_status: Filing status for SE tax and capital loss limits.
        modified_agi_for_pal: MAGI for passive activity loss calculation.

    Returns:
        IncomeSummary with totals by income type including business and capital gains.

    Note:
        - Some forms (1098, 1098-T, 5498, 1099-S) do not directly contribute to
          income but are tracked for deduction/credit calculation.
        - K-1 SE income comes from Box 14 (self_employment_earnings), NOT Box 1.
        - S-corp K-1s do NOT generate SE tax (shareholders receive W-2 wages).
        - Guaranteed payments (Box 4) are included in Box 14 when subject to SE.
        - Schedule E losses may be limited by passive activity rules.
        - Capital losses limited to $3,000/year ($1,500 MFS); excess carries forward.

    Example:
        >>> w2 = W2Data(wages_tips_compensation=Decimal("50000"), ...)
        >>> result = aggregate_income([w2])
        >>> result.total_wages
        Decimal('50000')
    """
    total_wages = Decimal("0")
    total_interest = Decimal("0")
    total_dividends = Decimal("0")
    total_qualified_dividends = Decimal("0")
    total_nec = Decimal("0")
    total_retirement_distributions = Decimal("0")
    total_unemployment = Decimal("0")
    total_state_tax_refund = Decimal("0")
    total_other = Decimal("0")
    federal_withholding = Decimal("0")

    # K-1 income tracking
    k1_ordinary_income = Decimal("0")
    k1_guaranteed_payments = Decimal("0")
    k1_se_earnings = Decimal("0")  # Box 14 only - NOT Box 1 + Box 4
    k1_interest_income = Decimal("0")
    k1_dividend_income = Decimal("0")
    k1_rental_income = Decimal("0")
    k1_capital_gains = Decimal("0")
    k1_other_income = Decimal("0")

    for doc in documents:
        if isinstance(doc, W2Data):
            total_wages += doc.wages_tips_compensation
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, Form1099INT):
            total_interest += doc.interest_income
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, Form1099DIV):
            total_dividends += doc.total_ordinary_dividends
            total_qualified_dividends += doc.qualified_dividends
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, Form1099NEC):
            total_nec += doc.nonemployee_compensation
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, Form1099R):
            # Add taxable amount to retirement distributions
            # If taxable_amount is not determined, use gross_distribution
            if doc.taxable_amount is not None:
                total_retirement_distributions += doc.taxable_amount
            else:
                # Taxable amount not determined - use gross distribution
                # This should trigger an escalation in the agent
                total_retirement_distributions += doc.gross_distribution
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, Form1099G):
            total_unemployment += doc.unemployment_compensation
            total_state_tax_refund += doc.state_local_tax_refund
            federal_withholding += doc.federal_tax_withheld
        elif isinstance(doc, FormK1):
            # K-1 ordinary income (Box 1) goes to total_other for income tax
            k1_ordinary_income += doc.ordinary_business_income or Decimal("0")
            k1_guaranteed_payments += doc.guaranteed_payments or Decimal("0")
            k1_interest_income += doc.interest_income or Decimal("0")
            k1_dividend_income += doc.dividend_income or Decimal("0")
            k1_rental_income += (
                (doc.net_rental_real_estate or Decimal("0"))
                + (doc.other_rental_income or Decimal("0"))
            )
            k1_capital_gains += (
                (doc.net_short_term_capital_gain or Decimal("0"))
                + (doc.net_long_term_capital_gain or Decimal("0"))
                + (doc.net_section_1231_gain or Decimal("0"))
            )
            k1_other_income += (
                (doc.royalties or Decimal("0"))
                + (doc.other_income or Decimal("0"))
            )

            # IMPORTANT: SE income uses Box 14 (self_employment_earnings), NOT Box 1 + Box 4
            # S-corp K-1s do NOT have SE tax - shareholders receive W-2 wages instead
            if doc.entity_type == "partnership":
                k1_se_earnings += doc.self_employment_earnings or Decimal("0")
        # Form1098, Form1098T, Form5498, Form1099S are informational for
        # deductions/credits and don't directly add to income totals

    # Aggregate Schedule C net profit
    schedule_c_profit = Decimal("0")
    if schedule_c_data:
        for sch_c in schedule_c_data:
            schedule_c_profit += sch_c.net_profit_or_loss

    # Total self-employment income = Schedule C profit + K-1 Box 14 (partnerships only)
    # NOTE: Guaranteed payments are INCLUDED in Box 14 when subject to SE tax
    self_employment_income = schedule_c_profit + k1_se_earnings

    # Calculate self-employment tax if applicable
    se_tax = Decimal("0")
    se_tax_deduction = Decimal("0")
    if self_employment_income > Decimal("0"):
        se_result = calculate_self_employment_tax(
            self_employment_income,
            filing_status,
        )
        se_tax = se_result.total_se_tax
        se_tax_deduction = se_result.deductible_portion

    # K-1 ordinary income is added to total_other for tax calculation
    total_interest += k1_interest_income
    total_dividends += k1_dividend_income
    total_other += k1_ordinary_income + k1_guaranteed_payments + k1_other_income

    # K-1 rental income only flows into totals if Schedule E not supplied
    if schedule_e_data is None:
        total_other += k1_rental_income

    # K-1 capital gains only flow into totals if Schedule D not supplied
    if schedule_d_data is None:
        total_other += k1_capital_gains

    # Schedule E rental income (with passive activity loss limitations)
    schedule_e_rental_income = Decimal("0")
    schedule_e_expenses = Decimal("0")
    schedule_e_net = Decimal("0")
    schedule_e_suspended_loss = Decimal("0")
    if schedule_e_data:
        # Use provided MAGI or estimate from known income for PAL calculation
        # Note: In practice, MAGI may need iterative calculation
        magi = modified_agi_for_pal or (
            total_wages
            + total_interest
            + total_dividends
            + total_nec
            + total_retirement_distributions
            + total_unemployment
            + total_other
            + schedule_c_profit
        )
        sch_e_result = calculate_schedule_e(schedule_e_data, magi, filing_status)
        schedule_e_rental_income = sch_e_result.total_rental_income
        schedule_e_expenses = sch_e_result.total_expenses
        schedule_e_net = sch_e_result.net_rental_income_loss
        schedule_e_suspended_loss = sch_e_result.suspended_loss

    # Schedule D capital gains/losses (with $3k/$1.5k loss limitation)
    capital_gains_short_term = Decimal("0")
    capital_gains_long_term = Decimal("0")
    capital_gains_net = Decimal("0")
    capital_loss_carryforward = Decimal("0")
    if schedule_d_data:
        sch_d_result = calculate_schedule_d(schedule_d_data, filing_status)
        capital_gains_short_term = sch_d_result.net_short_term_gain_loss
        capital_gains_long_term = sch_d_result.net_long_term_gain_loss
        capital_gains_net = sch_d_result.net_included_in_income  # After loss limit
        capital_loss_carryforward = sch_d_result.new_loss_carryforward

    nec_income = Decimal("0") if schedule_c_data else total_nec
    total_income = (
        total_wages
        + total_interest
        + total_dividends
        + nec_income
        + total_retirement_distributions
        + total_unemployment
        + total_other
        + schedule_c_profit  # Schedule C net profit is part of total income
        + schedule_e_net  # Schedule E net rental income/loss (after PAL limits)
        + capital_gains_net  # Schedule D capital gains/losses (after loss limit)
    )
    # Note: state_tax_refund may be taxable if itemized in prior year,
    # but this requires additional context - handle in escalation

    return IncomeSummary(
        total_wages=total_wages,
        total_interest=total_interest,
        total_dividends=total_dividends,
        total_qualified_dividends=total_qualified_dividends,
        total_nec=total_nec,
        total_retirement_distributions=total_retirement_distributions,
        total_unemployment=total_unemployment,
        total_state_tax_refund=total_state_tax_refund,
        total_other=total_other,
        total_income=total_income,
        federal_withholding=federal_withholding,
        schedule_c_profit=schedule_c_profit,
        k1_ordinary_income=k1_ordinary_income,
        k1_guaranteed_payments=k1_guaranteed_payments,
        self_employment_income=self_employment_income,
        se_tax=se_tax,
        se_tax_deduction=se_tax_deduction,
        schedule_e_rental_income=schedule_e_rental_income,
        schedule_e_expenses=schedule_e_expenses,
        schedule_e_net=schedule_e_net,
        schedule_e_suspended_loss=schedule_e_suspended_loss,
        capital_gains_short_term=capital_gains_short_term,
        capital_gains_long_term=capital_gains_long_term,
        capital_gains_net=capital_gains_net,
        capital_loss_carryforward=capital_loss_carryforward,
    )


# =============================================================================
# Deduction Calculation (PTAX-04)
# =============================================================================


def get_standard_deduction(filing_status: str, tax_year: int) -> Decimal:
    """Get the standard deduction for a filing status and year.

    Args:
        filing_status: One of "single", "mfj", "mfs", "hoh".
        tax_year: Tax year (e.g., 2024).

    Returns:
        Standard deduction amount.

    Raises:
        ValueError: If filing status or year not found.

    Example:
        >>> get_standard_deduction("single", 2024)
        Decimal('14600')
    """
    key = (tax_year, filing_status.lower())
    if key not in STANDARD_DEDUCTIONS:
        raise ValueError(f"Unknown filing status/year: {filing_status}/{tax_year}")
    return STANDARD_DEDUCTIONS[key]


def compute_itemized_deductions(
    documents: list[TaxDocument],
    filing_status: str,
) -> ItemizedDeductionBreakdown:
    """Compute itemized deductions from supported documents.

    Args:
        documents: List of tax document models.
        filing_status: Filing status for SALT cap selection.

    Returns:
        ItemizedDeductionBreakdown with component totals and final amount.
    """
    mortgage_interest = Decimal("0")
    points_paid = Decimal("0")
    mortgage_insurance_premiums = Decimal("0")
    property_taxes_paid = Decimal("0")
    state_income_taxes_paid = Decimal("0")

    for doc in documents:
        if isinstance(doc, Form1098):
            mortgage_interest += doc.mortgage_interest
            points_paid += doc.points_paid
            mortgage_insurance_premiums += doc.mortgage_insurance_premiums
            property_taxes_paid += doc.property_taxes_paid
        elif isinstance(doc, W2Data):
            state_income_taxes_paid += doc.state_tax_withheld
        elif isinstance(doc, Form1099R):
            state_income_taxes_paid += doc.state_tax_withheld
        elif isinstance(doc, Form1099G):
            state_income_taxes_paid += doc.state_tax_withheld

    salt_total = property_taxes_paid + state_income_taxes_paid
    cap = SALT_CAPS.get(filing_status.lower(), SALT_CAPS["single"])
    salt_deduction = min(salt_total, cap)

    total = (
        mortgage_interest + points_paid + mortgage_insurance_premiums + salt_deduction
    )

    return ItemizedDeductionBreakdown(
        mortgage_interest=mortgage_interest,
        points_paid=points_paid,
        mortgage_insurance_premiums=mortgage_insurance_premiums,
        property_taxes_paid=property_taxes_paid,
        state_income_taxes_paid=state_income_taxes_paid,
        salt_total=salt_total,
        salt_deduction=salt_deduction,
        total=total,
    )


def calculate_deductions(
    income: IncomeSummary,
    filing_status: str,
    tax_year: int,
    itemized_total: Decimal = Decimal("0"),
) -> DeductionResult:
    """Calculate deductions, selecting standard or itemized.

    Compares standard deduction to itemized total and selects the higher value.

    Args:
        income: IncomeSummary from aggregate_income.
        filing_status: One of "single", "mfj", "mfs", "hoh".
        tax_year: Tax year (e.g., 2024).
        itemized_total: Total itemized deductions (default 0).

    Returns:
        DeductionResult with method and amount.

    Example:
        >>> result = calculate_deductions(income, "single", 2024, Decimal("10000"))
        >>> result.method
        'standard'  # because $14,600 > $10,000
    """
    standard_amount = get_standard_deduction(filing_status, tax_year)

    if itemized_total > standard_amount:
        return DeductionResult(
            method="itemized",
            amount=itemized_total,
            standard_amount=standard_amount,
            itemized_amount=itemized_total,
        )
    else:
        return DeductionResult(
            method="standard",
            amount=standard_amount,
            standard_amount=standard_amount,
            itemized_amount=itemized_total,
        )


# =============================================================================
# Credits Evaluation (PTAX-05)
# =============================================================================


def _calculate_child_tax_credit(situation: TaxSituation) -> Decimal:
    """Calculate Child Tax Credit with phaseout.

    Args:
        situation: TaxSituation with AGI and filing status.

    Returns:
        CTC amount after phaseout.
    """
    if situation.num_qualifying_children <= 0:
        return Decimal("0")

    # Base credit: $2,000 per child
    base_credit = CTC_AMOUNT * situation.num_qualifying_children

    # Determine phaseout threshold
    if situation.filing_status.lower() == "mfj":
        threshold = CTC_PHASEOUT_MFJ
    else:
        threshold = CTC_PHASEOUT_SINGLE

    # Calculate phaseout reduction
    if situation.agi > threshold:
        # Reduce by $50 for each $1,000 (or part thereof) over threshold
        excess = situation.agi - threshold
        # Round up to nearest $1,000
        excess_thousands = (excess + Decimal("999")) // Decimal("1000")
        reduction = CTC_PHASEOUT_RATE * excess_thousands
        credit = max(Decimal("0"), base_credit - reduction)
    else:
        credit = base_credit

    return credit


def _calculate_education_credits(situation: TaxSituation) -> list[CreditItem]:
    """Calculate education credits (AOC or LLC).

    AOC: 100% of first $2,000 + 25% of next $2,000 = max $2,500.
    40% is refundable (up to $1,000). LLC: 20% of up to $10,000 (max $2,000).

    Args:
        situation: TaxSituation with education expenses and credit type.

    Returns:
        List of CreditItem entries for education credits.
    """
    expenses = situation.education_expenses
    if expenses <= Decimal("0"):
        return []

    credit_type = situation.education_credit_type.lower().strip()
    if credit_type == "llc":
        qualified_expenses = min(expenses, LLC_MAX_EXPENSES)
        credit_amount = min(qualified_expenses * LLC_RATE, LLC_MAX_CREDIT)
        if credit_amount <= Decimal("0"):
            return []
        return [
            CreditItem(
                name="Lifetime Learning Credit",
                amount=credit_amount,
                refundable=False,
                form="Form 8863",
            )
        ]

    # Default to American Opportunity Credit
    first_portion = min(expenses, Decimal("2000"))
    second_portion = min(max(expenses - Decimal("2000"), Decimal("0")), Decimal("2000"))
    total_credit = first_portion + (second_portion * Decimal("0.25"))

    refundable = min(total_credit * AOC_REFUNDABLE_RATE, AOC_REFUNDABLE_CAP)
    nonrefundable = total_credit - refundable

    credits: list[CreditItem] = []
    if nonrefundable > Decimal("0"):
        credits.append(
            CreditItem(
                name="American Opportunity Credit",
                amount=nonrefundable,
                refundable=False,
                form="Form 8863",
            )
        )
    if refundable > Decimal("0"):
        credits.append(
            CreditItem(
                name="American Opportunity Credit (Refundable)",
                amount=refundable,
                refundable=True,
                form="Form 8863",
            )
        )
    return credits


def _calculate_savers_credit(situation: TaxSituation) -> Decimal:
    """Calculate Retirement Savings Contribution Credit.

    Args:
        situation: TaxSituation with retirement contributions and AGI.

    Returns:
        Saver's Credit amount.
    """
    if situation.retirement_contributions <= Decimal("0"):
        return Decimal("0")

    key = (situation.tax_year, situation.filing_status.lower())
    if key not in SAVERS_CREDIT_RATES:
        return Decimal("0")

    rates = SAVERS_CREDIT_RATES[key]
    agi = situation.agi

    # Find applicable rate based on AGI
    rate = Decimal("0")
    for limit, tier_rate in rates:
        if agi <= limit:
            rate = tier_rate
            break

    if rate == Decimal("0"):
        return Decimal("0")

    # Apply rate to contributions (max $2,000)
    eligible_contributions = min(
        situation.retirement_contributions, SAVERS_CREDIT_MAX_CONTRIBUTION
    )
    return eligible_contributions * rate


def _calculate_eitc(situation: TaxSituation) -> Decimal:
    """Calculate simplified Earned Income Tax Credit.

    Simplified implementation for no-child filers only.

    Args:
        situation: TaxSituation with earned income.

    Returns:
        EITC amount.
    """
    if situation.earned_income <= Decimal("0"):
        return Decimal("0")

    # Simplified: only handle no-child case
    if situation.num_qualifying_children > 0:
        # Would need full EITC tables - return simplified estimate
        return Decimal("0")

    # Check income limit by filing status
    status = situation.filing_status.lower()
    limit = EITC_INCOME_LIMITS_NO_CHILDREN.get(
        status, EITC_INCOME_LIMIT_SINGLE_NO_CHILDREN
    )
    if situation.agi > limit:
        return Decimal("0")

    # Simplified credit calculation - phase in and phase out
    # Max credit for no children in 2024 is $632
    earned = situation.earned_income

    # Phase-in: credit increases with income up to about $7,840
    phase_in_end = Decimal("7840")
    phase_in_rate = Decimal("0.0765")

    # Phase-out: credit decreases from about $9,800
    phase_out_start = Decimal("9800")
    phase_out_rate = Decimal("0.0765")

    if earned <= phase_in_end:
        credit = earned * phase_in_rate
    elif earned <= phase_out_start:
        credit = EITC_MAX_NO_CHILDREN
    else:
        reduction = (earned - phase_out_start) * phase_out_rate
        credit = max(Decimal("0"), EITC_MAX_NO_CHILDREN - reduction)

    return min(credit, EITC_MAX_NO_CHILDREN)


def build_credit_inputs(documents: list[TaxDocument]) -> CreditInputs:
    """Build credit inputs from extracted documents.

    Args:
        documents: List of tax document models.

    Returns:
        CreditInputs with aggregated education expenses and retirement contributions.
    """
    education_expenses = Decimal("0")
    education_credit_type = "aoc"
    retirement_contributions = Decimal("0")

    for doc in documents:
        if isinstance(doc, Form1098T):
            net_expenses = (
                doc.payments_received
                - doc.scholarships_grants
                - doc.adjustments_prior_year
                - doc.scholarships_adjustments_prior_year
            )
            if net_expenses > Decimal("0"):
                education_expenses += net_expenses
            if not doc.at_least_half_time:
                education_credit_type = "llc"
        elif isinstance(doc, Form5498):
            retirement_contributions += (
                doc.ira_contributions
                + doc.sep_contributions
                + doc.simple_contributions
                + doc.roth_ira_contributions
            )

    return CreditInputs(
        education_expenses=education_expenses,
        education_credit_type=education_credit_type,
        retirement_contributions=retirement_contributions,
    )


def evaluate_credits(situation: TaxSituation) -> CreditsResult:
    """Evaluate all applicable tax credits.

    Evaluates Child Tax Credit (and ACTC when liability is provided),
    Education Credits (AOC/LLC), Saver's Credit, and EITC.

    Args:
        situation: TaxSituation with all relevant data.

    Returns:
        CreditsResult with list of applicable credits and totals.

    Example:
        >>> situation = TaxSituation(agi=Decimal("80000"), filing_status="single",
        ...                          tax_year=2024, num_qualifying_children=2)
        >>> result = evaluate_credits(situation)
        >>> result.total_credits
        Decimal('4000')
    """
    credits: list[CreditItem] = []

    # Child Tax Credit
    ctc_amount = _calculate_child_tax_credit(situation)
    if ctc_amount > Decimal("0"):
        ctc_nonrefundable = ctc_amount
        actc_amount = Decimal("0")
        if situation.tax_liability is not None:
            tax_liability = max(Decimal("0"), situation.tax_liability)
            ctc_nonrefundable = min(ctc_amount, tax_liability)
            unused_ctc = ctc_amount - ctc_nonrefundable
            actc_cap = ACTC_MAX_PER_CHILD * situation.num_qualifying_children
            actc_amount = min(unused_ctc, actc_cap)

        if ctc_nonrefundable > Decimal("0"):
            credits.append(
                CreditItem(
                    name="Child Tax Credit",
                    amount=ctc_nonrefundable,
                    refundable=False,
                    form="Schedule 8812",
                )
            )

        if actc_amount > Decimal("0"):
            credits.append(
                CreditItem(
                    name="Additional Child Tax Credit",
                    amount=actc_amount,
                    refundable=True,
                    form="Schedule 8812",
                )
            )

    # Education Credit (AOC)
    if situation.education_expenses > Decimal("0"):
        credits.extend(_calculate_education_credits(situation))

    # Saver's Credit
    savers_amount = _calculate_savers_credit(situation)
    if savers_amount > Decimal("0"):
        credits.append(
            CreditItem(
                name="Saver's Credit",
                amount=savers_amount,
                refundable=False,
                form="Form 8880",
            )
        )

    # EITC
    eitc_amount = _calculate_eitc(situation)
    if eitc_amount > Decimal("0"):
        credits.append(
            CreditItem(
                name="Earned Income Credit",
                amount=eitc_amount,
                refundable=True,
                form="Schedule EIC",
            )
        )

    total_nonrefundable = sum(c.amount for c in credits if not c.refundable)
    total_refundable = sum(c.amount for c in credits if c.refundable)
    total_credits = total_nonrefundable + total_refundable

    return CreditsResult(
        credits=credits,
        total_nonrefundable=total_nonrefundable,
        total_refundable=total_refundable,
        total_credits=total_credits,
    )


# =============================================================================
# Tax Calculation (PTAX-06)
# =============================================================================


def calculate_tax(
    taxable_income: Decimal, filing_status: str, tax_year: int
) -> TaxResult:
    """Calculate federal income tax using marginal brackets.

    Args:
        taxable_income: Income after deductions.
        filing_status: One of "single", "mfj", "mfs", "hoh".
        tax_year: Tax year (e.g., 2024).

    Returns:
        TaxResult with gross tax, bracket breakdown, and effective rate.

    Raises:
        ValueError: If filing status or year not found.

    Example:
        >>> result = calculate_tax(Decimal("50000"), "single", 2024)
        >>> result.gross_tax
        Decimal('6053')
    """
    key = (tax_year, filing_status.lower())
    if key not in TAX_BRACKETS:
        raise ValueError(f"Unknown filing status/year: {filing_status}/{tax_year}")

    brackets = TAX_BRACKETS[key]
    remaining_income = taxable_income
    gross_tax = Decimal("0")
    bracket_breakdown: list[dict] = []
    prev_bracket = Decimal("0")

    for upper_bound, rate in brackets:
        if remaining_income <= Decimal("0"):
            break

        if upper_bound is None:
            # Top bracket - no limit
            bracket_size = remaining_income
        else:
            bracket_size = min(remaining_income, upper_bound - prev_bracket)

        tax_in_bracket = bracket_size * rate
        gross_tax += tax_in_bracket

        if bracket_size > Decimal("0"):
            bracket_breakdown.append(
                {
                    "bracket": upper_bound,
                    "rate": rate,
                    "tax_in_bracket": tax_in_bracket,
                }
            )

        remaining_income -= bracket_size
        if upper_bound is not None:
            prev_bracket = upper_bound

    # Calculate effective rate
    if taxable_income > Decimal("0"):
        effective_rate = gross_tax / taxable_income
    else:
        effective_rate = Decimal("0")

    return TaxResult(
        gross_tax=gross_tax,
        bracket_breakdown=bracket_breakdown,
        effective_rate=effective_rate,
    )


# =============================================================================
# Prior Year Comparison (PTAX-12)
# =============================================================================


def compare_years(
    current: dict[str, Decimal],
    prior: dict[str, Decimal],
    threshold: Decimal = Decimal("10"),
) -> list[VarianceItem]:
    """Compare current and prior year values, flagging significant variances.

    Flags fields where the variance exceeds the threshold percentage.

    Args:
        current: Current year values by field name.
        prior: Prior year values by field name.
        threshold: Percentage threshold for flagging (default 10%).

    Returns:
        List of VarianceItem for fields exceeding threshold.

    Example:
        >>> variances = compare_years(
        ...     {"wages": Decimal("80000")},
        ...     {"wages": Decimal("70000")},
        ... )
        >>> len(variances)
        1
    """
    variances: list[VarianceItem] = []

    for field_name, current_value in current.items():
        prior_value = prior.get(field_name, Decimal("0"))

        # Handle new income source (prior = 0)
        if prior_value == Decimal("0"):
            if current_value > Decimal("0"):
                variances.append(
                    VarianceItem(
                        field=field_name,
                        current_value=current_value,
                        prior_value=prior_value,
                        variance_pct=Decimal("100"),
                        direction="increase",
                    )
                )
            continue

        # Calculate percentage change
        difference = current_value - prior_value
        variance_pct = abs(difference) / prior_value * Decimal("100")

        # Flag if exceeds threshold (must be greater than, not equal to)
        if variance_pct > threshold:
            direction = "increase" if difference > Decimal("0") else "decrease"
            variances.append(
                VarianceItem(
                    field=field_name,
                    current_value=current_value,
                    prior_value=prior_value,
                    variance_pct=variance_pct,
                    direction=direction,
                )
            )

    return variances
