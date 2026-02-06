"""Pydantic models for S-Corporation (Form 1120-S) business tax processing.

This module defines validated data models for:
- ShareholderInfo: Shareholder data for K-1 generation
- TrialBalanceEntry / TrialBalance: General ledger structures
- ScheduleKLine / ScheduleK: Pro-rata share items (Boxes 1-17)
- ScheduleLLine / ScheduleL: Balance sheet per books
- Form1120SResult: Complete 1120-S computation result

All monetary fields use Decimal for precision.
EIN and TIN fields are validated via src.documents.models utilities.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.documents.models import ConfidenceLevel, TIN, validate_ein, validate_tin


# =============================================================================
# Shareholder Information
# =============================================================================


class ShareholderInfo(BaseModel):
    """Shareholder data for K-1 generation.

    Captures ownership percentage, TIN, and basis data needed for
    shareholder-level allocation and K-1 output.
    """

    name: str = Field(description="Shareholder name")
    tin: TIN = Field(description="Shareholder TIN (SSN or EIN)")
    ownership_pct: Decimal = Field(description="Ownership percentage (0-100)")
    is_officer: bool = Field(description="Whether shareholder is a corporate officer")
    beginning_stock_basis: Decimal = Field(description="Beginning stock basis")
    beginning_debt_basis: Decimal = Field(description="Beginning debt basis")
    suspended_losses: Decimal = Field(
        default=Decimal("0"), description="Suspended losses from prior years"
    )
    officer_compensation: Decimal = Field(
        default=Decimal("0"), description="Reasonable compensation if officer"
    )

    @field_validator("tin", mode="before")
    @classmethod
    def validate_shareholder_tin(cls, v: str) -> str:
        """Validate shareholder TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ssn")

    @field_validator("ownership_pct")
    @classmethod
    def validate_ownership_pct(cls, v: Decimal) -> Decimal:
        """Validate ownership percentage is between 0 (exclusive) and 100 (inclusive)."""
        if v <= Decimal("0") or v > Decimal("100"):
            raise ValueError(
                f"Ownership percentage must be 0 < pct <= 100, got {v}"
            )
        return v


# =============================================================================
# Trial Balance
# =============================================================================

ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "cogs", "expense")


class TrialBalanceEntry(BaseModel):
    """Single general ledger account line in a trial balance.

    For asset/expense accounts, debit is normal balance.
    For liability/equity/revenue accounts, credit is normal balance.
    """

    account_number: str | None = Field(
        default=None, description="GL account number"
    )
    account_name: str = Field(description="Account name")
    account_type: Literal[
        "asset", "liability", "equity", "revenue", "cogs", "expense"
    ] = Field(description="Account classification")
    debit: Decimal = Field(default=Decimal("0"), description="Debit amount")
    credit: Decimal = Field(default=Decimal("0"), description="Credit amount")

    @property
    def net_balance(self) -> Decimal:
        """Net balance (debit - credit)."""
        return self.debit - self.credit


class TrialBalance(BaseModel):
    """Complete trial balance from a general ledger.

    Contains all GL entries with period info and balance validation.
    """

    entries: list[TrialBalanceEntry] = Field(description="Trial balance entries")
    period_start: str = Field(description="Period start date (YYYY-MM-DD)")
    period_end: str = Field(description="Period end date (YYYY-MM-DD)")
    entity_name: str = Field(description="Entity name")
    source_format: Literal["excel", "pdf", "csv"] = Field(
        description="Source file format"
    )

    @property
    def total_debits(self) -> Decimal:
        """Sum of all debit balances."""
        return sum((e.debit for e in self.entries), Decimal("0"))

    @property
    def total_credits(self) -> Decimal:
        """Sum of all credit balances."""
        return sum((e.credit for e in self.entries), Decimal("0"))

    @property
    def is_balanced(self) -> bool:
        """Check if total debits equal total credits."""
        return self.total_debits == self.total_credits

    def entries_by_type(self, account_type: str) -> list[TrialBalanceEntry]:
        """Filter entries by account type.

        Args:
            account_type: One of asset, liability, equity, revenue, cogs, expense.

        Returns:
            List of entries matching the given account type.
        """
        return [e for e in self.entries if e.account_type == account_type]


# =============================================================================
# Schedule K (Pro-Rata Share Items)
# =============================================================================


class ScheduleKLine(BaseModel):
    """Single Schedule K line item."""

    line_number: str = Field(description="Line number on Schedule K")
    description: str = Field(description="Line description")
    amount: Decimal = Field(description="Line amount")


class ScheduleK(BaseModel):
    """Schedule K - Shareholders' Pro Rata Share Items (Pages 2-3 of 1120-S).

    Boxes 1-17 capturing all items that flow through to shareholders' K-1s.
    """

    # Income/Loss (Boxes 1-11)
    ordinary_income: Decimal = Field(
        default=Decimal("0"), description="Box 1: Ordinary business income (loss)"
    )
    net_rental_real_estate: Decimal = Field(
        default=Decimal("0"),
        description="Box 2: Net rental real estate income (loss)",
    )
    other_rental_income: Decimal = Field(
        default=Decimal("0"), description="Box 3: Other net rental income (loss)"
    )
    interest_income: Decimal = Field(
        default=Decimal("0"), description="Box 4: Interest income"
    )
    dividends: Decimal = Field(
        default=Decimal("0"), description="Box 5: Dividends"
    )
    royalties: Decimal = Field(
        default=Decimal("0"), description="Box 6: Royalties"
    )
    net_short_term_capital_gain: Decimal = Field(
        default=Decimal("0"),
        description="Box 7: Net short-term capital gain (loss)",
    )
    net_long_term_capital_gain: Decimal = Field(
        default=Decimal("0"),
        description="Box 8: Net long-term capital gain (loss)",
    )
    net_section_1231_gain: Decimal = Field(
        default=Decimal("0"), description="Box 9: Net section 1231 gain (loss)"
    )
    other_income_loss: Decimal = Field(
        default=Decimal("0"), description="Box 10: Other income (loss)"
    )
    section_179_deduction: Decimal = Field(
        default=Decimal("0"), description="Box 11: Section 179 deduction"
    )

    # Deductions, Credits, Foreign, AMT (Boxes 12-15)
    charitable_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 12: Charitable contributions"
    )
    credits: Decimal = Field(
        default=Decimal("0"), description="Box 13: Credits"
    )
    foreign_transactions: Decimal = Field(
        default=Decimal("0"),
        description="Box 14: Foreign transactions (escalation trigger)",
    )
    amt_items: Decimal = Field(
        default=Decimal("0"),
        description="Box 15: AMT items (escalation trigger)",
    )

    # Other Information (Boxes 16-17)
    tax_exempt_interest: Decimal = Field(
        default=Decimal("0"), description="Box 16a: Tax-exempt interest income"
    )
    other_tax_exempt_income: Decimal = Field(
        default=Decimal("0"), description="Box 16b: Other tax-exempt income"
    )
    nondeductible_expenses: Decimal = Field(
        default=Decimal("0"), description="Box 16c: Nondeductible expenses"
    )
    distributions: Decimal = Field(
        default=Decimal("0"), description="Box 16d: Distributions"
    )
    other_information: Decimal = Field(
        default=Decimal("0"), description="Box 17: Other information"
    )


# =============================================================================
# Schedule L (Balance Sheet Per Books)
# =============================================================================


class ScheduleLLine(BaseModel):
    """Balance sheet line item with beginning and ending amounts."""

    line_number: int = Field(description="Line number on Schedule L")
    description: str = Field(description="Line description")
    beginning_amount: Decimal = Field(description="Beginning of year amount")
    ending_amount: Decimal = Field(description="End of year amount")


class ScheduleL(BaseModel):
    """Schedule L - Balance Sheets per Books.

    Assets (lines 1-15), Liabilities (lines 16-21), and Equity (lines 22-27)
    with beginning and ending period columns.
    """

    # Asset lines (1-15)
    cash: ScheduleLLine = Field(description="Line 1: Cash")
    trade_receivables: ScheduleLLine = Field(
        description="Line 2: Trade notes and accounts receivable"
    )
    inventories: ScheduleLLine = Field(description="Line 3: Inventories")
    us_government_obligations: ScheduleLLine = Field(
        description="Line 4: U.S. government obligations"
    )
    tax_exempt_securities: ScheduleLLine = Field(
        description="Line 5: Tax-exempt securities"
    )
    other_current_assets: ScheduleLLine = Field(
        description="Line 6: Other current assets"
    )
    loans_to_shareholders: ScheduleLLine = Field(
        description="Line 7: Loans to shareholders"
    )
    mortgage_real_estate: ScheduleLLine = Field(
        description="Line 8: Mortgage and real estate loans"
    )
    other_investments: ScheduleLLine = Field(
        description="Line 9: Other investments"
    )
    buildings_other_depreciable: ScheduleLLine = Field(
        description="Line 10: Buildings and other depreciable assets"
    )
    depreciable_accumulated_depreciation: ScheduleLLine = Field(
        description="Line 11: Less accumulated depreciation (negative)"
    )
    depletable_assets: ScheduleLLine = Field(
        description="Line 12: Depletable assets"
    )
    land: ScheduleLLine = Field(description="Line 13: Land (net of any amortization)")
    intangible_assets: ScheduleLLine = Field(
        description="Line 14: Intangible assets (amortizable only)"
    )
    other_assets: ScheduleLLine = Field(description="Line 15: Other assets")

    # Liability lines (16-21)
    accounts_payable: ScheduleLLine = Field(
        description="Line 16: Accounts payable"
    )
    mortgages_bonds_payable_less_1yr: ScheduleLLine = Field(
        description="Line 17: Mortgages, notes, bonds payable in less than 1 year"
    )
    other_current_liabilities: ScheduleLLine = Field(
        description="Line 18: Other current liabilities"
    )
    loans_from_shareholders: ScheduleLLine = Field(
        description="Line 19: Loans from shareholders"
    )
    mortgages_bonds_payable_1yr_plus: ScheduleLLine = Field(
        description="Line 20: Mortgages, notes, bonds payable in 1 year or more"
    )
    other_liabilities: ScheduleLLine = Field(
        description="Line 21: Other liabilities"
    )

    # Equity lines (22-27)
    capital_stock: ScheduleLLine = Field(
        description="Line 22: Capital stock"
    )
    additional_paid_in_capital: ScheduleLLine = Field(
        description="Line 23: Additional paid-in capital"
    )
    retained_earnings: ScheduleLLine = Field(
        description="Line 24: Retained earnings"
    )
    adjustments_to_shareholders_equity: ScheduleLLine = Field(
        description="Line 25: Adjustments to shareholders' equity"
    )
    less_cost_treasury_stock: ScheduleLLine = Field(
        description="Line 26: Less cost of treasury stock"
    )

    # -------------------------------------------------------------------------
    # Computed properties
    # -------------------------------------------------------------------------

    @property
    def _asset_lines(self) -> list[ScheduleLLine]:
        """All asset line items."""
        return [
            self.cash,
            self.trade_receivables,
            self.inventories,
            self.us_government_obligations,
            self.tax_exempt_securities,
            self.other_current_assets,
            self.loans_to_shareholders,
            self.mortgage_real_estate,
            self.other_investments,
            self.buildings_other_depreciable,
            self.depreciable_accumulated_depreciation,
            self.depletable_assets,
            self.land,
            self.intangible_assets,
            self.other_assets,
        ]

    @property
    def _liability_lines(self) -> list[ScheduleLLine]:
        """All liability line items."""
        return [
            self.accounts_payable,
            self.mortgages_bonds_payable_less_1yr,
            self.other_current_liabilities,
            self.loans_from_shareholders,
            self.mortgages_bonds_payable_1yr_plus,
            self.other_liabilities,
        ]

    @property
    def _equity_lines(self) -> list[ScheduleLLine]:
        """All equity line items."""
        return [
            self.capital_stock,
            self.additional_paid_in_capital,
            self.retained_earnings,
            self.adjustments_to_shareholders_equity,
            self.less_cost_treasury_stock,
        ]

    @property
    def total_assets_beginning(self) -> Decimal:
        """Total assets at beginning of year."""
        return sum(
            (line.beginning_amount for line in self._asset_lines), Decimal("0")
        )

    @property
    def total_assets_ending(self) -> Decimal:
        """Total assets at end of year."""
        return sum(
            (line.ending_amount for line in self._asset_lines), Decimal("0")
        )

    @property
    def total_liabilities_equity_beginning(self) -> Decimal:
        """Total liabilities + equity at beginning of year."""
        liabilities = sum(
            (line.beginning_amount for line in self._liability_lines), Decimal("0")
        )
        equity = sum(
            (line.beginning_amount for line in self._equity_lines), Decimal("0")
        )
        return liabilities + equity

    @property
    def total_liabilities_equity_ending(self) -> Decimal:
        """Total liabilities + equity at end of year."""
        liabilities = sum(
            (line.ending_amount for line in self._liability_lines), Decimal("0")
        )
        equity = sum(
            (line.ending_amount for line in self._equity_lines), Decimal("0")
        )
        return liabilities + equity

    @property
    def is_balanced_beginning(self) -> bool:
        """Check if balance sheet balances at beginning of year."""
        return self.total_assets_beginning == self.total_liabilities_equity_beginning

    @property
    def is_balanced_ending(self) -> bool:
        """Check if balance sheet balances at end of year."""
        return self.total_assets_ending == self.total_liabilities_equity_ending


# =============================================================================
# Form 1120-S Result
# =============================================================================


class Form1120SResult(BaseModel):
    """Complete Form 1120-S computation result.

    Aggregates all schedules, page 1 computations, shareholder info,
    and escalation flags into a single result object.
    """

    # Entity identification
    entity_name: str = Field(description="S-Corporation name")
    entity_ein: str = Field(description="Entity EIN (XX-XXXXXXX)")
    tax_year: int = Field(description="Tax year")
    fiscal_year_end: str | None = Field(
        default=None, description="Fiscal year end (if not calendar year)"
    )

    # Page 1 results
    gross_receipts: Decimal = Field(description="Line 1a: Gross receipts or sales")
    cost_of_goods_sold: Decimal = Field(description="Line 2: Cost of goods sold")
    gross_profit: Decimal = Field(description="Line 3: Gross profit")
    total_income: Decimal = Field(description="Line 6: Total income (loss)")
    total_deductions: Decimal = Field(description="Line 20: Total deductions")
    ordinary_business_income: Decimal = Field(
        description="Line 21: Ordinary business income (loss)"
    )

    # Schedules
    schedule_k: ScheduleK = Field(description="Schedule K pro-rata share items")
    schedule_l: ScheduleL = Field(description="Schedule L balance sheet per books")

    # Shareholders
    shareholders: list[ShareholderInfo] = Field(
        description="Shareholder information for K-1 generation"
    )

    # Escalations and confidence
    escalations: list[str] = Field(
        default_factory=list, description="Items requiring human review"
    )
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Overall confidence level"
    )

    @field_validator("entity_ein", mode="before")
    @classmethod
    def validate_entity_ein(cls, v: str) -> str:
        """Validate and format entity EIN."""
        return validate_ein(v)
