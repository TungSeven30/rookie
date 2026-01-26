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
    Form1098,
    Form1098T,
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
# Income Aggregation (PTAX-03)
# =============================================================================


def aggregate_income(
    documents: list[TaxDocument],
    schedule_c_data: list[ScheduleCData] | None = None,
    filing_status: FilingStatus = FilingStatus.SINGLE,
) -> IncomeSummary:
    """Aggregate income from all tax documents.

    Args:
        documents: List of supported tax document models (W-2, 1099s, K-1).
        schedule_c_data: Optional list of Schedule C business data.
        filing_status: Filing status for SE tax calculation.

    Returns:
        IncomeSummary with totals by income type including business income.

    Note:
        - Some forms (1098, 1098-T, 5498, 1099-S) do not directly contribute to
          income but are tracked for deduction/credit calculation.
        - K-1 SE income comes from Box 14 (self_employment_earnings), NOT Box 1.
        - S-corp K-1s do NOT generate SE tax (shareholders receive W-2 wages).
        - Guaranteed payments (Box 4) are included in Box 14 when subject to SE.

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
    total_other += k1_ordinary_income

    total_income = (
        total_wages
        + total_interest
        + total_dividends
        + total_nec
        + total_retirement_distributions
        + total_unemployment
        + total_other
        + schedule_c_profit  # Schedule C net profit is part of total income
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
