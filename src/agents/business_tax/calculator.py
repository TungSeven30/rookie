"""1120-S tax computation functions for S-Corporation returns.

Pure functions that transform mapped trial balance data into complete
Form 1120-S schedules:
- compute_page1: Page 1 income/deductions -> ordinary business income
- compute_schedule_k: Shareholder pro-rata share items (Boxes 1-17)
- compute_schedule_l: Balance sheet per books (beginning/ending)
- compute_schedule_m1: Book-to-tax income reconciliation
- compute_schedule_m2: Accumulated Adjustments Account (AAA) analysis

All functions use Decimal arithmetic with no side effects or LLM calls.
Follows the pattern from src/agents/personal_tax/calculator.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.agents.business_tax.models import ScheduleK, ScheduleL, ScheduleLLine


# =============================================================================
# Page 1 Result
# =============================================================================


@dataclass
class Page1Result:
    """Form 1120-S Page 1 computation result.

    Line references correspond to IRS Form 1120-S, Page 1.

    Attributes:
        gross_receipts: Line 1a gross receipts or sales.
        returns_and_allowances: Line 1b returns and allowances.
        cost_of_goods_sold: Line 2 cost of goods sold.
        gross_profit: Line 3 = 1a - 1b - 2.
        net_gain_loss_form_4797: Line 4 net gain/loss from Form 4797.
        other_income: Line 5 other income (loss).
        total_income: Line 6 = 3 + 4 + 5.
        officer_compensation: Line 7 compensation of officers.
        salaries_wages: Line 8 salaries and wages.
        repairs: Line 9 repairs and maintenance.
        bad_debts: Line 10 bad debts.
        taxes_licenses: Line 12 taxes and licenses.
        rents: Line 13 rents.
        interest: Line 14 interest.
        depreciation: Line 15 depreciation.
        advertising: Line 17 advertising.
        pension_profit_sharing: Line 18 pension/profit-sharing plans.
        employee_benefits: Line 19 employee benefit programs.
        other_deductions: Line 20 other deductions.
        total_deductions: Line 21 = sum of lines 7-20.
        ordinary_business_income: Line 22 = line 6 - line 21.
    """

    gross_receipts: Decimal
    returns_and_allowances: Decimal
    cost_of_goods_sold: Decimal
    gross_profit: Decimal
    net_gain_loss_form_4797: Decimal
    other_income: Decimal
    total_income: Decimal
    officer_compensation: Decimal
    salaries_wages: Decimal
    repairs: Decimal
    bad_debts: Decimal
    taxes_licenses: Decimal
    rents: Decimal
    interest: Decimal
    depreciation: Decimal
    advertising: Decimal
    pension_profit_sharing: Decimal
    employee_benefits: Decimal
    other_deductions: Decimal
    total_deductions: Decimal
    ordinary_business_income: Decimal


# =============================================================================
# Schedule M-1 Result
# =============================================================================


@dataclass
class ScheduleM1Result:
    """Schedule M-1 book-to-tax income reconciliation.

    Reconciles net income per books (Line 1) to income per return (Line 8).
    Line 8 should equal Page 1, Line 22 (ordinary business income).

    Attributes:
        book_income: Line 1 net income per books.
        income_on_books_not_on_return: Line 2 income on books not on return.
        expenses_on_return_not_on_books: Line 3 expenses on return not on books.
        total_lines_1_3: Sum of lines 1 through 3.
        income_on_return_not_on_books: Line 5 income on return not on books.
        expenses_on_books_not_on_return: Line 6 expenses on books not on return.
        total_lines_5_6: Sum of lines 5 and 6.
        income_per_return: Line 8 = total_1_3 - total_5_6.
    """

    book_income: Decimal
    income_on_books_not_on_return: Decimal
    expenses_on_return_not_on_books: Decimal
    total_lines_1_3: Decimal
    income_on_return_not_on_books: Decimal
    expenses_on_books_not_on_return: Decimal
    total_lines_5_6: Decimal
    income_per_return: Decimal


# =============================================================================
# Schedule M-2 Result
# =============================================================================


@dataclass
class ScheduleM2Result:
    """Schedule M-2 Accumulated Adjustments Account (AAA) analysis.

    AAA tracks S-Corp earnings that have been taxed at shareholder level.
    AAA can go negative from losses but not from distributions.

    Attributes:
        aaa_beginning: Beginning AAA balance.
        ordinary_income: Ordinary income from Schedule K Box 1.
        other_additions: Other additions (separately stated income items).
        losses_deductions: Losses and deductions reducing AAA.
        other_reductions: Nondeductible expenses.
        distributions: Distributions to shareholders.
        aaa_ending: Ending AAA balance.
    """

    aaa_beginning: Decimal
    ordinary_income: Decimal
    other_additions: Decimal
    losses_deductions: Decimal
    other_reductions: Decimal
    distributions: Decimal
    aaa_ending: Decimal


# =============================================================================
# compute_page1
# =============================================================================

_ZERO = Decimal("0")


def compute_page1(mapped_amounts: dict[str, Decimal]) -> Page1Result:
    """Compute Form 1120-S Page 1 from mapped trial balance amounts.

    Takes the output of aggregate_mapped_amounts (dict of form_line -> Decimal)
    and computes gross profit, total income, total deductions, and ordinary
    business income. Missing keys default to zero.

    Args:
        mapped_amounts: Dict keyed by form line identifiers (e.g. 'page1_line1a').

    Returns:
        Page1Result with all Page 1 line values computed.
    """
    gross_receipts = mapped_amounts.get("page1_line1a", _ZERO)
    returns_and_allowances = mapped_amounts.get("page1_line1b", _ZERO)
    cost_of_goods_sold = mapped_amounts.get("page1_line2", _ZERO)
    net_gain_loss_form_4797 = mapped_amounts.get("page1_line4", _ZERO)
    other_income = mapped_amounts.get("page1_line5", _ZERO)

    gross_profit = gross_receipts - returns_and_allowances - cost_of_goods_sold
    total_income = gross_profit + net_gain_loss_form_4797 + other_income

    # Deduction lines
    officer_compensation = mapped_amounts.get("page1_line7", _ZERO)
    salaries_wages = mapped_amounts.get("page1_line8", _ZERO)
    repairs = mapped_amounts.get("page1_line9", _ZERO)
    bad_debts = mapped_amounts.get("page1_line10", _ZERO)
    taxes_licenses = mapped_amounts.get("page1_line12", _ZERO)
    rents = mapped_amounts.get("page1_line13", _ZERO)
    interest = mapped_amounts.get("page1_line14", _ZERO)
    depreciation = mapped_amounts.get("page1_line15", _ZERO)
    advertising = mapped_amounts.get("page1_line17", _ZERO)
    pension_profit_sharing = mapped_amounts.get("page1_line18", _ZERO)
    employee_benefits = mapped_amounts.get("page1_line19", _ZERO)
    other_deductions = mapped_amounts.get("page1_line20", _ZERO)

    total_deductions = (
        officer_compensation
        + salaries_wages
        + repairs
        + bad_debts
        + taxes_licenses
        + rents
        + interest
        + depreciation
        + advertising
        + pension_profit_sharing
        + employee_benefits
        + other_deductions
    )

    ordinary_business_income = total_income - total_deductions

    return Page1Result(
        gross_receipts=gross_receipts,
        returns_and_allowances=returns_and_allowances,
        cost_of_goods_sold=cost_of_goods_sold,
        gross_profit=gross_profit,
        net_gain_loss_form_4797=net_gain_loss_form_4797,
        other_income=other_income,
        total_income=total_income,
        officer_compensation=officer_compensation,
        salaries_wages=salaries_wages,
        repairs=repairs,
        bad_debts=bad_debts,
        taxes_licenses=taxes_licenses,
        rents=rents,
        interest=interest,
        depreciation=depreciation,
        advertising=advertising,
        pension_profit_sharing=pension_profit_sharing,
        employee_benefits=employee_benefits,
        other_deductions=other_deductions,
        total_deductions=total_deductions,
        ordinary_business_income=ordinary_business_income,
    )


# =============================================================================
# compute_schedule_k
# =============================================================================

# Fields on ScheduleK that can be populated from separately_stated dict
_SCHEDULE_K_FIELDS: set[str] = {
    "net_rental_real_estate",
    "other_rental_income",
    "interest_income",
    "dividends",
    "royalties",
    "net_short_term_capital_gain",
    "net_long_term_capital_gain",
    "net_section_1231_gain",
    "other_income_loss",
    "section_179_deduction",
    "charitable_contributions",
    "credits",
    "foreign_transactions",
    "amt_items",
    "tax_exempt_interest",
    "other_tax_exempt_income",
    "nondeductible_expenses",
    "distributions",
    "other_information",
}


def compute_schedule_k(
    page1: Page1Result,
    separately_stated: dict[str, Decimal] | None = None,
) -> ScheduleK:
    """Compute Schedule K from Page 1 result and separately stated items.

    Box 1 = page1.ordinary_business_income. Boxes 2-17 come from the
    separately_stated dict. Unknown keys are ignored. All boxes default
    to Decimal('0') when not provided.

    Args:
        page1: Computed Page 1 result.
        separately_stated: Dict of Schedule K field names to Decimal amounts.

    Returns:
        Populated ScheduleK Pydantic model.
    """
    kwargs: dict[str, Decimal] = {
        "ordinary_income": page1.ordinary_business_income,
    }

    if separately_stated:
        for key, value in separately_stated.items():
            if key in _SCHEDULE_K_FIELDS:
                kwargs[key] = value

    return ScheduleK(**kwargs)


# =============================================================================
# compute_schedule_l
# =============================================================================

# Mapping of ScheduleL field names to their form line keys and line numbers
_SCHEDULE_L_LINE_MAP: list[tuple[str, str, int, str]] = [
    # (field_name, mapped_amounts_key, line_number, description)
    # Assets
    ("cash", "schedule_l_line1", 1, "Cash"),
    ("trade_receivables", "schedule_l_line2", 2, "Trade notes and accounts receivable"),
    ("inventories", "schedule_l_line3", 3, "Inventories"),
    ("us_government_obligations", "schedule_l_line4", 4, "U.S. government obligations"),
    ("tax_exempt_securities", "schedule_l_line5", 5, "Tax-exempt securities"),
    ("other_current_assets", "schedule_l_line6", 6, "Other current assets"),
    ("loans_to_shareholders", "schedule_l_line7", 7, "Loans to shareholders"),
    ("mortgage_real_estate", "schedule_l_line8", 8, "Mortgage and real estate loans"),
    ("other_investments", "schedule_l_line9", 9, "Other investments"),
    ("buildings_other_depreciable", "schedule_l_line10a", 10, "Buildings and other depreciable assets"),
    ("depreciable_accumulated_depreciation", "schedule_l_line10b", 11, "Less accumulated depreciation"),
    ("depletable_assets", "schedule_l_line12", 12, "Depletable assets"),
    ("land", "schedule_l_line13", 13, "Land"),
    ("intangible_assets", "schedule_l_line14", 14, "Intangible assets"),
    ("other_assets", "schedule_l_line15", 15, "Other assets"),
    # Liabilities
    ("accounts_payable", "schedule_l_line16", 16, "Accounts payable"),
    ("mortgages_bonds_payable_less_1yr", "schedule_l_line17", 17, "Short-term debt"),
    ("other_current_liabilities", "schedule_l_line18", 18, "Other current liabilities"),
    ("loans_from_shareholders", "schedule_l_line19", 19, "Loans from shareholders"),
    ("mortgages_bonds_payable_1yr_plus", "schedule_l_line20", 20, "Long-term debt"),
    ("other_liabilities", "schedule_l_line21", 21, "Other liabilities"),
    # Equity
    ("capital_stock", "schedule_l_line22", 22, "Capital stock"),
    ("additional_paid_in_capital", "schedule_l_line23", 23, "Additional paid-in capital"),
    ("retained_earnings", "schedule_l_line24", 24, "Retained earnings"),
    ("adjustments_to_shareholders_equity", "schedule_l_line25", 25, "Adjustments to shareholders' equity"),
    ("less_cost_treasury_stock", "schedule_l_line26", 26, "Less cost of treasury stock"),
]


def compute_schedule_l(
    mapped_amounts: dict[str, Decimal],
    prior_year_schedule_l: ScheduleL | None,
    current_year_net_income: Decimal,
    current_year_distributions: Decimal,
) -> ScheduleL:
    """Compute Schedule L balance sheet from mapped amounts and prior year.

    Beginning amounts come from prior_year_schedule_l (or zeros if first year).
    Ending amounts come from mapped trial balance. Retained earnings ending is
    computed as: beginning + current_year_net_income - current_year_distributions.

    Does NOT raise on imbalance -- caller should check is_balanced_ending.

    Args:
        mapped_amounts: Dict of schedule_l_lineN -> Decimal ending amounts.
        prior_year_schedule_l: Prior year ScheduleL (None for first year).
        current_year_net_income: Net income for retained earnings update.
        current_year_distributions: Distributions for retained earnings update.

    Returns:
        Populated ScheduleL with beginning and ending columns.
    """
    lines: dict[str, ScheduleLLine] = {}

    for field_name, line_key, line_number, description in _SCHEDULE_L_LINE_MAP:
        # Beginning amount from prior year ending (or zero)
        if prior_year_schedule_l is not None:
            prior_line: ScheduleLLine = getattr(prior_year_schedule_l, field_name)
            beginning = prior_line.ending_amount
        else:
            beginning = _ZERO

        # Ending amount from mapped amounts (or zero)
        ending = mapped_amounts.get(line_key, _ZERO)

        # Override retained earnings with computed value
        if field_name == "retained_earnings":
            ending = beginning + current_year_net_income - current_year_distributions

        lines[field_name] = ScheduleLLine(
            line_number=line_number,
            description=description,
            beginning_amount=beginning,
            ending_amount=ending,
        )

    return ScheduleL(**lines)


# =============================================================================
# compute_schedule_m1
# =============================================================================


def compute_schedule_m1(
    book_income: Decimal,
    tax_income: Decimal,
    tax_exempt_income: Decimal = _ZERO,
    nondeductible_expenses: Decimal = _ZERO,
) -> ScheduleM1Result:
    """Compute Schedule M-1 book-to-tax income reconciliation.

    Reconciles net income per books to income per return.
    Line 8 (income_per_return) should equal Page 1 Line 22.

    The reconciliation works as follows:
    - Line 1: Book income
    - Line 2: Income on books not on return (e.g., tax-exempt interest)
    - Line 3: Expenses on return not on books (e.g., tax depreciation > book)
    - Lines 1+2+3 = total_lines_1_3
    - Line 5: Income on return not on books
    - Line 6: Expenses on books not on return (e.g., nondeductible expenses)
    - Lines 5+6 = total_lines_5_6
    - Line 8: income_per_return = total_1_3 - total_5_6

    Args:
        book_income: Net income per books.
        tax_income: Income per return (Page 1 Line 22).
        tax_exempt_income: Tax-exempt income included in book income.
        nondeductible_expenses: Expenses on books not deductible on return.

    Returns:
        ScheduleM1Result with all reconciliation lines.
    """
    # Schedule M-1 reconciliation (IRS Form 1120-S):
    #   Line 1: Net income per books
    #   Line 2: Income on Schedule K not recorded on books (addition)
    #   Line 3: Expenses on books not included on Schedule K (addition)
    #   total_lines_1_3 = Line 1 + Line 2 + Line 3
    #   Line 5: Income on books not included on Schedule K (subtraction)
    #           e.g., tax-exempt interest
    #   Line 6: Deductions on Schedule K not charged against books (subtraction)
    #           e.g., nondeductible expenses
    #   total_lines_5_6 = Line 5 + Line 6
    #   Line 8 = total_lines_1_3 - total_lines_5_6

    # Line 5: Tax-exempt income is on books but NOT on the tax return
    income_on_books_not_on_return = _ZERO  # Line 2 (placeholder for future items)

    # Line 6: Nondeductible expenses reduce book income, not on Sch K
    expenses_on_books_not_on_return = nondeductible_expenses

    # Tax-exempt income goes on the subtraction side (Line 5 per IRS)
    income_on_return_not_on_books_known = tax_exempt_income

    # Compute residual for remaining reconciliation items
    # target: book + L2 + L3 - L5 - L6 = tax_income
    # L3 = tax_income - book - L2 + L5 + L6
    residual = (
        tax_income
        - book_income
        - income_on_books_not_on_return
        + income_on_return_not_on_books_known
        + expenses_on_books_not_on_return
    )

    if residual >= _ZERO:
        expenses_on_return_not_on_books = residual
        income_on_return_not_on_books = income_on_return_not_on_books_known
    else:
        expenses_on_return_not_on_books = _ZERO
        income_on_return_not_on_books = income_on_return_not_on_books_known + (-residual)

    total_lines_1_3 = (
        book_income + income_on_books_not_on_return + expenses_on_return_not_on_books
    )
    total_lines_5_6 = income_on_return_not_on_books + expenses_on_books_not_on_return

    income_per_return = total_lines_1_3 - total_lines_5_6

    return ScheduleM1Result(
        book_income=book_income,
        income_on_books_not_on_return=income_on_books_not_on_return,
        expenses_on_return_not_on_books=expenses_on_return_not_on_books,
        total_lines_1_3=total_lines_1_3,
        income_on_return_not_on_books=income_on_return_not_on_books,
        expenses_on_books_not_on_return=expenses_on_books_not_on_return,
        total_lines_5_6=total_lines_5_6,
        income_per_return=income_per_return,
    )


# =============================================================================
# compute_schedule_m2
# =============================================================================


def compute_schedule_m2(
    aaa_beginning: Decimal,
    ordinary_income: Decimal,
    separately_stated_net: Decimal,
    nondeductible_expenses: Decimal,
    distributions: Decimal,
) -> ScheduleM2Result:
    """Compute Schedule M-2 AAA (Accumulated Adjustments Account) analysis.

    AAA tracks undistributed S-Corp income that has been taxed to shareholders.
    AAA can go negative from losses but not from distributions (per IRC 1368).

    Computation:
        ending = beginning + income + other_additions - losses - nondeductible - distributions

    For losses: if ordinary_income is negative, it becomes a loss that reduces AAA.
    separately_stated_net captures net of other Schedule K income/loss items.

    Args:
        aaa_beginning: Beginning AAA balance.
        ordinary_income: Schedule K Box 1 ordinary income (can be negative for loss).
        separately_stated_net: Net of Schedule K Boxes 2-10.
        nondeductible_expenses: Schedule K Box 16c nondeductible expenses.
        distributions: Schedule K Box 16d distributions.

    Returns:
        ScheduleM2Result with AAA beginning, adjustments, and ending balance.
    """
    # Separate income from losses
    if ordinary_income >= _ZERO:
        income_addition = ordinary_income
        income_loss = _ZERO
    else:
        income_addition = _ZERO
        income_loss = -ordinary_income  # Make positive for the loss bucket

    # Separately stated: positive = addition, negative = loss
    if separately_stated_net >= _ZERO:
        other_additions = separately_stated_net
        other_losses = _ZERO
    else:
        other_additions = _ZERO
        other_losses = -separately_stated_net

    total_losses_deductions = income_loss + other_losses

    aaa_ending = (
        aaa_beginning
        + income_addition
        + other_additions
        - total_losses_deductions
        - nondeductible_expenses
        - distributions
    )

    return ScheduleM2Result(
        aaa_beginning=aaa_beginning,
        ordinary_income=income_addition,
        other_additions=other_additions,
        losses_deductions=total_losses_deductions,
        other_reductions=nondeductible_expenses,
        distributions=distributions,
        aaa_ending=aaa_ending,
    )
