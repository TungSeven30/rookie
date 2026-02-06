"""Tests for business tax Pydantic models.

Covers validation, computed properties, balance checks, and edge cases
for all 8 models: ShareholderInfo, TrialBalanceEntry, TrialBalance,
ScheduleKLine, ScheduleK, ScheduleLLine, ScheduleL, Form1120SResult.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.agents.business_tax.models import (
    Form1120SResult,
    ScheduleK,
    ScheduleKLine,
    ScheduleL,
    ScheduleLLine,
    ShareholderInfo,
    TrialBalance,
    TrialBalanceEntry,
)
from src.documents.models import ConfidenceLevel


# =============================================================================
# Helpers
# =============================================================================


def _zero_line(line_number: int, description: str) -> ScheduleLLine:
    """Create a zero-balance ScheduleLLine."""
    return ScheduleLLine(
        line_number=line_number,
        description=description,
        beginning_amount=Decimal("0"),
        ending_amount=Decimal("0"),
    )


def _make_schedule_l(
    cash_begin: Decimal = Decimal("1000"),
    cash_end: Decimal = Decimal("1000"),
    re_begin: Decimal = Decimal("1000"),
    re_end: Decimal = Decimal("1000"),
) -> ScheduleL:
    """Create a ScheduleL with cash and retained earnings, rest zeroed."""
    return ScheduleL(
        cash=ScheduleLLine(
            line_number=1,
            description="Cash",
            beginning_amount=cash_begin,
            ending_amount=cash_end,
        ),
        trade_receivables=_zero_line(2, "Trade receivables"),
        inventories=_zero_line(3, "Inventories"),
        us_government_obligations=_zero_line(4, "US gov obligations"),
        tax_exempt_securities=_zero_line(5, "Tax-exempt securities"),
        other_current_assets=_zero_line(6, "Other current assets"),
        loans_to_shareholders=_zero_line(7, "Loans to shareholders"),
        mortgage_real_estate=_zero_line(8, "Mortgage RE"),
        other_investments=_zero_line(9, "Other investments"),
        buildings_other_depreciable=_zero_line(10, "Buildings"),
        depreciable_accumulated_depreciation=_zero_line(11, "Accum depreciation"),
        depletable_assets=_zero_line(12, "Depletable assets"),
        land=_zero_line(13, "Land"),
        intangible_assets=_zero_line(14, "Intangible assets"),
        other_assets=_zero_line(15, "Other assets"),
        accounts_payable=_zero_line(16, "Accounts payable"),
        mortgages_bonds_payable_less_1yr=_zero_line(17, "Mortgages <1yr"),
        other_current_liabilities=_zero_line(18, "Other current liabilities"),
        loans_from_shareholders=_zero_line(19, "Loans from shareholders"),
        mortgages_bonds_payable_1yr_plus=_zero_line(20, "Mortgages >1yr"),
        other_liabilities=_zero_line(21, "Other liabilities"),
        capital_stock=_zero_line(22, "Capital stock"),
        additional_paid_in_capital=_zero_line(23, "APIC"),
        retained_earnings=ScheduleLLine(
            line_number=24,
            description="Retained earnings",
            beginning_amount=re_begin,
            ending_amount=re_end,
        ),
        adjustments_to_shareholders_equity=_zero_line(25, "Adj SH equity"),
        less_cost_treasury_stock=_zero_line(26, "Treasury stock"),
    )


# =============================================================================
# ShareholderInfo Tests
# =============================================================================


class TestShareholderInfo:
    """Tests for ShareholderInfo model."""

    def test_valid_construction(self) -> None:
        """Valid shareholder with all fields."""
        sh = ShareholderInfo(
            name="John Smith",
            tin="123-45-6789",
            ownership_pct=Decimal("50"),
            is_officer=True,
            beginning_stock_basis=Decimal("10000"),
            beginning_debt_basis=Decimal("5000"),
            suspended_losses=Decimal("2000"),
            officer_compensation=Decimal("80000"),
        )
        assert sh.name == "John Smith"
        assert sh.tin == "123-45-6789"
        assert sh.ownership_pct == Decimal("50")
        assert sh.is_officer is True
        assert sh.beginning_stock_basis == Decimal("10000")
        assert sh.beginning_debt_basis == Decimal("5000")
        assert sh.suspended_losses == Decimal("2000")
        assert sh.officer_compensation == Decimal("80000")

    def test_tin_validation_ssn_format(self) -> None:
        """SSN formatted TIN is accepted."""
        sh = ShareholderInfo(
            name="A",
            tin="123-45-6789",
            ownership_pct=Decimal("100"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.tin == "123-45-6789"

    def test_tin_validation_ein_format(self) -> None:
        """EIN formatted TIN is accepted."""
        sh = ShareholderInfo(
            name="Corp Trust",
            tin="12-3456789",
            ownership_pct=Decimal("100"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.tin == "12-3456789"

    def test_tin_validation_no_dashes(self) -> None:
        """Digits-only TIN gets formatted as SSN (default)."""
        sh = ShareholderInfo(
            name="A",
            tin="123456789",
            ownership_pct=Decimal("100"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.tin == "123-45-6789"

    def test_ownership_pct_rejects_zero(self) -> None:
        """Ownership percentage of 0 is rejected."""
        with pytest.raises(ValidationError, match="Ownership percentage"):
            ShareholderInfo(
                name="A",
                tin="123-45-6789",
                ownership_pct=Decimal("0"),
                is_officer=False,
                beginning_stock_basis=Decimal("0"),
                beginning_debt_basis=Decimal("0"),
            )

    def test_ownership_pct_rejects_over_100(self) -> None:
        """Ownership percentage over 100 is rejected."""
        with pytest.raises(ValidationError, match="Ownership percentage"):
            ShareholderInfo(
                name="A",
                tin="123-45-6789",
                ownership_pct=Decimal("100.01"),
                is_officer=False,
                beginning_stock_basis=Decimal("0"),
                beginning_debt_basis=Decimal("0"),
            )

    def test_ownership_pct_accepts_fractional(self) -> None:
        """Fractional ownership like 50.5% is accepted."""
        sh = ShareholderInfo(
            name="A",
            tin="123-45-6789",
            ownership_pct=Decimal("50.5"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.ownership_pct == Decimal("50.5")

    def test_ownership_pct_accepts_100(self) -> None:
        """Ownership percentage of exactly 100 is accepted."""
        sh = ShareholderInfo(
            name="A",
            tin="123-45-6789",
            ownership_pct=Decimal("100"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.ownership_pct == Decimal("100")

    def test_default_values(self) -> None:
        """Optional fields default correctly."""
        sh = ShareholderInfo(
            name="A",
            tin="123-45-6789",
            ownership_pct=Decimal("50"),
            is_officer=False,
            beginning_stock_basis=Decimal("0"),
            beginning_debt_basis=Decimal("0"),
        )
        assert sh.suspended_losses == Decimal("0")
        assert sh.officer_compensation == Decimal("0")


# =============================================================================
# TrialBalanceEntry Tests
# =============================================================================


class TestTrialBalanceEntry:
    """Tests for TrialBalanceEntry model."""

    def test_net_balance_debit(self) -> None:
        """Asset account with debit balance."""
        entry = TrialBalanceEntry(
            account_name="Cash",
            account_type="asset",
            debit=Decimal("10000"),
        )
        assert entry.net_balance == Decimal("10000")

    def test_net_balance_credit(self) -> None:
        """Liability account with credit balance."""
        entry = TrialBalanceEntry(
            account_name="Accounts Payable",
            account_type="liability",
            credit=Decimal("5000"),
        )
        assert entry.net_balance == Decimal("-5000")

    def test_net_balance_zero(self) -> None:
        """Entry with equal debit and credit."""
        entry = TrialBalanceEntry(
            account_name="Clearing",
            account_type="asset",
            debit=Decimal("100"),
            credit=Decimal("100"),
        )
        assert entry.net_balance == Decimal("0")

    def test_default_amounts(self) -> None:
        """Debit and credit default to zero."""
        entry = TrialBalanceEntry(
            account_name="Empty", account_type="expense"
        )
        assert entry.debit == Decimal("0")
        assert entry.credit == Decimal("0")
        assert entry.net_balance == Decimal("0")

    def test_optional_account_number(self) -> None:
        """Account number is optional."""
        entry = TrialBalanceEntry(
            account_number="1010",
            account_name="Cash",
            account_type="asset",
            debit=Decimal("500"),
        )
        assert entry.account_number == "1010"

    def test_invalid_account_type(self) -> None:
        """Invalid account type is rejected."""
        with pytest.raises(ValidationError):
            TrialBalanceEntry(
                account_name="Bad",
                account_type="invalid",  # type: ignore[arg-type]
            )

    def test_all_valid_account_types(self) -> None:
        """All six account types are accepted."""
        for acct_type in ("asset", "liability", "equity", "revenue", "cogs", "expense"):
            entry = TrialBalanceEntry(
                account_name="Test", account_type=acct_type  # type: ignore[arg-type]
            )
            assert entry.account_type == acct_type


# =============================================================================
# TrialBalance Tests
# =============================================================================


class TestTrialBalance:
    """Tests for TrialBalance model."""

    def test_balanced_trial_balance(self) -> None:
        """Balanced TB: total debits == total credits."""
        tb = TrialBalance(
            entries=[
                TrialBalanceEntry(
                    account_name="Cash",
                    account_type="asset",
                    debit=Decimal("10000"),
                ),
                TrialBalanceEntry(
                    account_name="Revenue",
                    account_type="revenue",
                    credit=Decimal("10000"),
                ),
            ],
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Test Corp",
            source_format="excel",
        )
        assert tb.total_debits == Decimal("10000")
        assert tb.total_credits == Decimal("10000")
        assert tb.is_balanced is True

    def test_unbalanced_trial_balance(self) -> None:
        """Unbalanced TB is detected."""
        tb = TrialBalance(
            entries=[
                TrialBalanceEntry(
                    account_name="Cash",
                    account_type="asset",
                    debit=Decimal("10000"),
                ),
                TrialBalanceEntry(
                    account_name="Revenue",
                    account_type="revenue",
                    credit=Decimal("9000"),
                ),
            ],
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Test Corp",
            source_format="pdf",
        )
        assert tb.is_balanced is False

    def test_entries_by_type(self) -> None:
        """Filter entries by account type."""
        tb = TrialBalance(
            entries=[
                TrialBalanceEntry(
                    account_name="Cash", account_type="asset", debit=Decimal("5000")
                ),
                TrialBalanceEntry(
                    account_name="AR", account_type="asset", debit=Decimal("3000")
                ),
                TrialBalanceEntry(
                    account_name="AP", account_type="liability", credit=Decimal("8000")
                ),
            ],
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Test Corp",
            source_format="csv",
        )
        assets = tb.entries_by_type("asset")
        assert len(assets) == 2
        liabilities = tb.entries_by_type("liability")
        assert len(liabilities) == 1
        expenses = tb.entries_by_type("expense")
        assert len(expenses) == 0

    def test_empty_trial_balance(self) -> None:
        """Empty TB has zero totals and is balanced."""
        tb = TrialBalance(
            entries=[],
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Empty Corp",
            source_format="excel",
        )
        assert tb.total_debits == Decimal("0")
        assert tb.total_credits == Decimal("0")
        assert tb.is_balanced is True

    def test_invalid_source_format(self) -> None:
        """Invalid source format is rejected."""
        with pytest.raises(ValidationError):
            TrialBalance(
                entries=[],
                period_start="2024-01-01",
                period_end="2024-12-31",
                entity_name="Test",
                source_format="json",  # type: ignore[arg-type]
            )


# =============================================================================
# ScheduleKLine Tests
# =============================================================================


class TestScheduleKLine:
    """Tests for ScheduleKLine model."""

    def test_construction(self) -> None:
        """Basic line item construction."""
        line = ScheduleKLine(
            line_number="1",
            description="Ordinary income",
            amount=Decimal("50000"),
        )
        assert line.line_number == "1"
        assert line.description == "Ordinary income"
        assert line.amount == Decimal("50000")

    def test_negative_amount(self) -> None:
        """Negative amounts (losses) are allowed."""
        line = ScheduleKLine(
            line_number="2",
            description="Net rental loss",
            amount=Decimal("-12000"),
        )
        assert line.amount == Decimal("-12000")


# =============================================================================
# ScheduleK Tests
# =============================================================================


class TestScheduleK:
    """Tests for ScheduleK model."""

    def test_default_zero_values(self) -> None:
        """All boxes default to zero."""
        sk = ScheduleK()
        assert sk.ordinary_income == Decimal("0")
        assert sk.net_rental_real_estate == Decimal("0")
        assert sk.other_rental_income == Decimal("0")
        assert sk.interest_income == Decimal("0")
        assert sk.dividends == Decimal("0")
        assert sk.royalties == Decimal("0")
        assert sk.net_short_term_capital_gain == Decimal("0")
        assert sk.net_long_term_capital_gain == Decimal("0")
        assert sk.net_section_1231_gain == Decimal("0")
        assert sk.other_income_loss == Decimal("0")
        assert sk.section_179_deduction == Decimal("0")
        assert sk.charitable_contributions == Decimal("0")
        assert sk.credits == Decimal("0")
        assert sk.foreign_transactions == Decimal("0")
        assert sk.amt_items == Decimal("0")
        assert sk.tax_exempt_interest == Decimal("0")
        assert sk.other_tax_exempt_income == Decimal("0")
        assert sk.nondeductible_expenses == Decimal("0")
        assert sk.distributions == Decimal("0")
        assert sk.other_information == Decimal("0")

    def test_setting_income_items(self) -> None:
        """Set various income and deduction boxes."""
        sk = ScheduleK(
            ordinary_income=Decimal("100000"),
            interest_income=Decimal("5000"),
            dividends=Decimal("3000"),
            section_179_deduction=Decimal("25000"),
            distributions=Decimal("50000"),
        )
        assert sk.ordinary_income == Decimal("100000")
        assert sk.interest_income == Decimal("5000")
        assert sk.dividends == Decimal("3000")
        assert sk.section_179_deduction == Decimal("25000")
        assert sk.distributions == Decimal("50000")

    def test_all_fields_are_decimal(self) -> None:
        """Verify all numeric fields are Decimal type."""
        sk = ScheduleK(ordinary_income=Decimal("1"))
        for field_name in ScheduleK.model_fields:
            val = getattr(sk, field_name)
            assert isinstance(val, Decimal), f"{field_name} is not Decimal: {type(val)}"


# =============================================================================
# ScheduleLLine Tests
# =============================================================================


class TestScheduleLLine:
    """Tests for ScheduleLLine model."""

    def test_construction(self) -> None:
        """Basic line item construction."""
        line = ScheduleLLine(
            line_number=1,
            description="Cash",
            beginning_amount=Decimal("5000"),
            ending_amount=Decimal("8000"),
        )
        assert line.line_number == 1
        assert line.beginning_amount == Decimal("5000")
        assert line.ending_amount == Decimal("8000")

    def test_negative_amounts(self) -> None:
        """Negative amounts (e.g., accumulated depreciation) are allowed."""
        line = ScheduleLLine(
            line_number=11,
            description="Accumulated depreciation",
            beginning_amount=Decimal("-50000"),
            ending_amount=Decimal("-60000"),
        )
        assert line.beginning_amount == Decimal("-50000")


# =============================================================================
# ScheduleL Tests
# =============================================================================


class TestScheduleL:
    """Tests for ScheduleL model."""

    def test_balanced_balance_sheet(self) -> None:
        """Balance sheet that balances: assets == liabilities + equity."""
        sl = _make_schedule_l()
        assert sl.total_assets_beginning == Decimal("1000")
        assert sl.total_assets_ending == Decimal("1000")
        assert sl.total_liabilities_equity_beginning == Decimal("1000")
        assert sl.total_liabilities_equity_ending == Decimal("1000")
        assert sl.is_balanced_beginning is True
        assert sl.is_balanced_ending is True

    def test_unbalanced_balance_sheet(self) -> None:
        """Balance sheet that does NOT balance is detected."""
        sl = _make_schedule_l(
            cash_begin=Decimal("5000"),
            cash_end=Decimal("5000"),
            re_begin=Decimal("1000"),
            re_end=Decimal("1000"),
        )
        # Assets = 5000, Equity = 1000 => not balanced
        assert sl.is_balanced_beginning is False
        assert sl.is_balanced_ending is False

    def test_beginning_ending_separation(self) -> None:
        """Beginning and ending periods are independent."""
        sl = _make_schedule_l(
            cash_begin=Decimal("1000"),
            cash_end=Decimal("2000"),
            re_begin=Decimal("1000"),
            re_end=Decimal("2000"),
        )
        assert sl.total_assets_beginning == Decimal("1000")
        assert sl.total_assets_ending == Decimal("2000")
        assert sl.is_balanced_beginning is True
        assert sl.is_balanced_ending is True

    def test_total_computation_multiple_items(self) -> None:
        """Total computation with multiple non-zero asset and equity lines."""
        sl = _make_schedule_l()
        # Override some fields via a fresh construction
        sl = ScheduleL(
            cash=ScheduleLLine(
                line_number=1,
                description="Cash",
                beginning_amount=Decimal("5000"),
                ending_amount=Decimal("5000"),
            ),
            trade_receivables=ScheduleLLine(
                line_number=2,
                description="AR",
                beginning_amount=Decimal("3000"),
                ending_amount=Decimal("3000"),
            ),
            inventories=_zero_line(3, "Inventories"),
            us_government_obligations=_zero_line(4, "US gov"),
            tax_exempt_securities=_zero_line(5, "Tax exempt"),
            other_current_assets=_zero_line(6, "Other current"),
            loans_to_shareholders=_zero_line(7, "Loans to SH"),
            mortgage_real_estate=_zero_line(8, "Mortgage RE"),
            other_investments=_zero_line(9, "Other inv"),
            buildings_other_depreciable=_zero_line(10, "Buildings"),
            depreciable_accumulated_depreciation=_zero_line(11, "Accum depr"),
            depletable_assets=_zero_line(12, "Depletable"),
            land=_zero_line(13, "Land"),
            intangible_assets=_zero_line(14, "Intangible"),
            other_assets=_zero_line(15, "Other assets"),
            accounts_payable=ScheduleLLine(
                line_number=16,
                description="AP",
                beginning_amount=Decimal("2000"),
                ending_amount=Decimal("2000"),
            ),
            mortgages_bonds_payable_less_1yr=_zero_line(17, "Mortgages <1yr"),
            other_current_liabilities=_zero_line(18, "Other current liab"),
            loans_from_shareholders=_zero_line(19, "Loans from SH"),
            mortgages_bonds_payable_1yr_plus=_zero_line(20, "Mortgages >1yr"),
            other_liabilities=_zero_line(21, "Other liab"),
            capital_stock=ScheduleLLine(
                line_number=22,
                description="Capital stock",
                beginning_amount=Decimal("1000"),
                ending_amount=Decimal("1000"),
            ),
            additional_paid_in_capital=_zero_line(23, "APIC"),
            retained_earnings=ScheduleLLine(
                line_number=24,
                description="RE",
                beginning_amount=Decimal("5000"),
                ending_amount=Decimal("5000"),
            ),
            adjustments_to_shareholders_equity=_zero_line(25, "Adj SH equity"),
            less_cost_treasury_stock=_zero_line(26, "Treasury stock"),
        )
        # Assets: 5000 + 3000 = 8000
        assert sl.total_assets_beginning == Decimal("8000")
        # Liabilities: 2000, Equity: 1000 + 5000 = 6000, Total: 8000
        assert sl.total_liabilities_equity_beginning == Decimal("8000")
        assert sl.is_balanced_beginning is True


# =============================================================================
# Form1120SResult Tests
# =============================================================================


class TestForm1120SResult:
    """Tests for Form1120SResult model."""

    def _build_result(self, **overrides: object) -> Form1120SResult:
        """Build a valid Form1120SResult with optional overrides."""
        defaults: dict[str, object] = {
            "entity_name": "Test Corp",
            "entity_ein": "12-3456789",
            "tax_year": 2024,
            "gross_receipts": Decimal("500000"),
            "cost_of_goods_sold": Decimal("200000"),
            "gross_profit": Decimal("300000"),
            "total_income": Decimal("300000"),
            "total_deductions": Decimal("150000"),
            "ordinary_business_income": Decimal("150000"),
            "schedule_k": ScheduleK(ordinary_income=Decimal("150000")),
            "schedule_l": _make_schedule_l(),
            "shareholders": [
                ShareholderInfo(
                    name="Owner",
                    tin="123-45-6789",
                    ownership_pct=Decimal("100"),
                    is_officer=True,
                    beginning_stock_basis=Decimal("50000"),
                    beginning_debt_basis=Decimal("0"),
                ),
            ],
        }
        defaults.update(overrides)
        return Form1120SResult(**defaults)  # type: ignore[arg-type]

    def test_valid_construction(self) -> None:
        """Valid result with all components."""
        result = self._build_result()
        assert result.entity_name == "Test Corp"
        assert result.entity_ein == "12-3456789"
        assert result.tax_year == 2024
        assert result.ordinary_business_income == Decimal("150000")

    def test_confidence_defaults_to_high(self) -> None:
        """Confidence defaults to HIGH."""
        result = self._build_result()
        assert result.confidence == ConfidenceLevel.HIGH

    def test_escalations_default_empty(self) -> None:
        """Escalations list is empty by default."""
        result = self._build_result()
        assert result.escalations == []

    def test_escalations_can_be_set(self) -> None:
        """Escalations can contain items."""
        result = self._build_result(
            escalations=["Foreign transactions detected", "AMT items present"]
        )
        assert len(result.escalations) == 2
        assert "Foreign transactions detected" in result.escalations

    def test_ein_validation(self) -> None:
        """EIN is validated and formatted."""
        result = self._build_result(entity_ein="123456789")
        assert result.entity_ein == "12-3456789"

    def test_ein_invalid_digits(self) -> None:
        """Invalid EIN is rejected."""
        with pytest.raises(ValidationError, match="EIN must be exactly 9 digits"):
            self._build_result(entity_ein="12345")

    def test_fiscal_year_end_optional(self) -> None:
        """Fiscal year end is None by default."""
        result = self._build_result()
        assert result.fiscal_year_end is None

    def test_fiscal_year_end_set(self) -> None:
        """Fiscal year end can be set."""
        result = self._build_result(fiscal_year_end="06-30")
        assert result.fiscal_year_end == "06-30"

    def test_multiple_shareholders(self) -> None:
        """Result with multiple shareholders."""
        shareholders = [
            ShareholderInfo(
                name="Owner A",
                tin="123-45-6789",
                ownership_pct=Decimal("60"),
                is_officer=True,
                beginning_stock_basis=Decimal("30000"),
                beginning_debt_basis=Decimal("0"),
            ),
            ShareholderInfo(
                name="Owner B",
                tin="987-65-4321",
                ownership_pct=Decimal("40"),
                is_officer=False,
                beginning_stock_basis=Decimal("20000"),
                beginning_debt_basis=Decimal("0"),
            ),
        ]
        result = self._build_result(shareholders=shareholders)
        assert len(result.shareholders) == 2

    def test_confidence_can_be_overridden(self) -> None:
        """Confidence can be set to MEDIUM or LOW."""
        result = self._build_result(confidence=ConfidenceLevel.MEDIUM)
        assert result.confidence == ConfidenceLevel.MEDIUM
