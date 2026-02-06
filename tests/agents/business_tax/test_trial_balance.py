"""Tests for trial balance parsing and GL-to-1120S mapping.

TDD test suite covering:
- Excel trial balance parsing (2-column, single-column, edge cases)
- GL account mapping to 1120-S line items with confidence scoring
- Amount aggregation by form line
"""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from src.agents.business_tax.models import TrialBalance, TrialBalanceEntry
from src.agents.business_tax.trial_balance import (
    DEFAULT_GL_MAPPING,
    GLMapping,
    aggregate_mapped_amounts,
    map_gl_to_1120s,
    parse_excel_trial_balance,
)
from src.documents.models import ConfidenceLevel


# =============================================================================
# Helpers: Build in-memory Excel bytes for test fixtures
# =============================================================================


def _make_excel_bytes(
    rows: list[list],
    sheet_name: str = "Trial Balance",
) -> bytes:
    """Create an in-memory Excel file from rows and return as bytes.

    Args:
        rows: List of row lists (first row is header).
        sheet_name: Name for the worksheet.

    Returns:
        Excel file bytes.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _standard_two_column_excel() -> bytes:
    """Fixture: Standard QuickBooks-style 2-column (debit/credit) trial balance."""
    rows = [
        ["Account", "Account Type", "Debit", "Credit"],
        ["1000 - Cash in Bank", "asset", 50000.00, 0],
        ["1200 - Accounts Receivable", "asset", 25000.00, 0],
        ["1500 - Inventory", "asset", 15000.00, 0],
        ["1700 - Equipment", "asset", 100000.00, 0],
        ["1750 - Accumulated Depreciation", "asset", 0, 20000.00],
        ["2000 - Accounts Payable", "liability", 0, 18000.00],
        ["2100 - Shareholder Loan", "liability", 0, 50000.00],
        ["3000 - Capital Stock", "equity", 0, 10000.00],
        ["3100 - Retained Earnings", "equity", 0, 42000.00],
        ["4000 - Revenue", "revenue", 0, 500000.00],
        ["5000 - Cost of Goods Sold", "cogs", 300000.00, 0],
        ["6000 - Officer Salary", "expense", 120000.00, 0],
        ["6100 - Salaries and Wages", "expense", 15000.00, 0],
        ["6200 - Rent Expense", "expense", 12000.00, 0],
        ["6300 - Advertising", "expense", 3000.00, 0],
    ]
    return _make_excel_bytes(rows)


def _standard_two_column_with_metadata_excel() -> bytes:
    """Fixture: Trial balance with entity name, period info, then data."""
    rows = [
        ["Acme Corp"],
        ["Trial Balance"],
        ["Period: 01/01/2024 to 12/31/2024"],
        [],  # blank row
        ["Account", "Account Type", "Debit", "Credit"],
        ["1000 - Cash", "asset", 10000.00, 0],
        ["4000 - Sales Revenue", "revenue", 0, 10000.00],
    ]
    return _make_excel_bytes(rows)


def _single_net_balance_excel() -> bytes:
    """Fixture: Single net balance column format (positive = debit normal)."""
    rows = [
        ["Account", "Account Type", "Balance"],
        ["Cash", "asset", 50000.00],
        ["Accounts Receivable", "asset", 25000.00],
        ["Accounts Payable", "liability", -18000.00],
        ["Revenue", "revenue", -500000.00],
        ["Cost of Goods Sold", "cogs", 300000.00],
        ["Officer Compensation", "expense", 120000.00],
    ]
    return _make_excel_bytes(rows)


def _with_totals_excel() -> bytes:
    """Fixture: Trial balance with header and total rows that should be skipped."""
    rows = [
        ["Trial Balance Report"],
        ["Account", "Account Type", "Debit", "Credit"],
        ["Cash", "asset", 10000.00, 0],
        ["Revenue", "revenue", 0, 10000.00],
        ["Total", "", 10000.00, 10000.00],
        ["", "", "", ""],
    ]
    return _make_excel_bytes(rows)


def _empty_excel() -> bytes:
    """Fixture: Empty spreadsheet with only headers."""
    rows = [
        ["Account", "Account Type", "Debit", "Credit"],
    ]
    return _make_excel_bytes(rows)


def _completely_empty_excel() -> bytes:
    """Fixture: Completely empty spreadsheet."""
    wb = Workbook()
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _whitespace_names_excel() -> bytes:
    """Fixture: Account names with extra whitespace."""
    rows = [
        ["Account", "Account Type", "Debit", "Credit"],
        ["  Cash in Bank  ", "asset", 10000.00, 0],
        [" Revenue ", "revenue", 0, 10000.00],
    ]
    return _make_excel_bytes(rows)


def _string_amounts_excel() -> bytes:
    """Fixture: Amounts stored as strings instead of numbers."""
    rows = [
        ["Account", "Account Type", "Debit", "Credit"],
        ["Cash", "asset", "10,000.00", "0.00"],
        ["Revenue", "revenue", "0.00", "10,000.00"],
    ]
    return _make_excel_bytes(rows)


def _with_account_numbers_excel() -> bytes:
    """Fixture: Account numbers in a separate column."""
    rows = [
        ["Account Number", "Account Name", "Account Type", "Debit", "Credit"],
        ["1000", "Cash", "asset", 10000.00, 0],
        ["4000", "Sales Revenue", "revenue", 0, 10000.00],
    ]
    return _make_excel_bytes(rows)


# =============================================================================
# Tests: parse_excel_trial_balance
# =============================================================================


class TestParseExcelTrialBalance:
    """Tests for Excel trial balance parsing."""

    def test_standard_two_column_debit_credit(self) -> None:
        """Standard 2-column (debit/credit) Excel parses to correct TrialBalance."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)

        assert isinstance(tb, TrialBalance)
        assert tb.source_format == "excel"
        assert len(tb.entries) == 16

        # Verify first entry
        cash = tb.entries[0]
        assert cash.account_name == "1000 - Cash in Bank"
        assert cash.account_type == "asset"
        assert cash.debit == Decimal("50000")
        assert cash.credit == Decimal("0")

        # Verify revenue entry
        revenue = [e for e in tb.entries if "Revenue" in e.account_name][0]
        assert revenue.account_type == "revenue"
        assert revenue.credit == Decimal("500000")

    def test_single_net_balance_column(self) -> None:
        """Single net balance column parses correctly."""
        data = _single_net_balance_excel()
        tb = parse_excel_trial_balance(data)

        assert isinstance(tb, TrialBalance)
        assert len(tb.entries) == 6

        # Positive balance -> debit for asset
        cash = [e for e in tb.entries if "Cash" in e.account_name][0]
        assert cash.debit == Decimal("50000")
        assert cash.credit == Decimal("0")

        # Negative balance -> credit for liability
        ap = [e for e in tb.entries if "Payable" in e.account_name][0]
        assert ap.debit == Decimal("0")
        assert ap.credit == Decimal("18000")

    def test_skips_header_and_total_rows(self) -> None:
        """Header rows and total/summary rows are skipped during parsing."""
        data = _with_totals_excel()
        tb = parse_excel_trial_balance(data)

        # Should only have the two data entries (Cash and Revenue), not header or total
        assert len(tb.entries) == 2
        names = [e.account_name for e in tb.entries]
        assert "Total" not in names
        assert "Trial Balance Report" not in names

    def test_empty_spreadsheet_raises_value_error(self) -> None:
        """Empty spreadsheet (no data rows) raises ValueError."""
        data = _empty_excel()
        with pytest.raises(ValueError, match="[Nn]o.*entries|[Ee]mpty"):
            parse_excel_trial_balance(data)

    def test_completely_empty_raises_value_error(self) -> None:
        """Completely empty spreadsheet raises ValueError."""
        data = _completely_empty_excel()
        with pytest.raises(ValueError):
            parse_excel_trial_balance(data)

    def test_strips_whitespace_from_account_names(self) -> None:
        """Whitespace is stripped from account names."""
        data = _whitespace_names_excel()
        tb = parse_excel_trial_balance(data)

        for entry in tb.entries:
            assert entry.account_name == entry.account_name.strip()
        cash = tb.entries[0]
        assert cash.account_name == "Cash in Bank"

    def test_converts_string_amounts_to_decimal(self) -> None:
        """String amounts (e.g., '10,000.00') are correctly converted to Decimal."""
        data = _string_amounts_excel()
        tb = parse_excel_trial_balance(data)

        cash = tb.entries[0]
        assert cash.debit == Decimal("10000")
        assert cash.credit == Decimal("0")

    def test_trial_balance_is_balanced(self) -> None:
        """Parsed trial balance has debits == credits."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)

        assert tb.is_balanced, (
            f"Trial balance not balanced: debits={tb.total_debits}, "
            f"credits={tb.total_credits}"
        )

    def test_entity_name_and_period_detected(self) -> None:
        """Entity name and period are populated."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)

        # At minimum, entity_name and period_end should be non-empty strings
        assert tb.entity_name
        assert tb.period_end

    def test_with_metadata_rows(self) -> None:
        """Trial balance with metadata header rows (entity name, period) parses correctly."""
        data = _standard_two_column_with_metadata_excel()
        tb = parse_excel_trial_balance(data)

        assert len(tb.entries) == 2
        assert tb.entity_name == "Acme Corp"

    def test_account_numbers_parsed(self) -> None:
        """Account numbers in separate column are captured."""
        data = _with_account_numbers_excel()
        tb = parse_excel_trial_balance(data)

        assert len(tb.entries) == 2
        assert tb.entries[0].account_number == "1000"


# =============================================================================
# Tests: GLMapping and DEFAULT_GL_MAPPING
# =============================================================================


class TestGLMapping:
    """Tests for GLMapping dataclass and DEFAULT_GL_MAPPING."""

    def test_gl_mapping_has_required_fields(self) -> None:
        """GLMapping has account_name, form_line, confidence, reasoning."""
        mapping = GLMapping(
            account_name="Cash",
            form_line="schedule_l_line1",
            confidence=ConfidenceLevel.HIGH,
            reasoning="Exact match on 'Cash'",
        )
        assert mapping.account_name == "Cash"
        assert mapping.form_line == "schedule_l_line1"
        assert mapping.confidence == ConfidenceLevel.HIGH
        assert mapping.reasoning == "Exact match on 'Cash'"

    def test_default_gl_mapping_has_revenue_entry(self) -> None:
        """DEFAULT_GL_MAPPING contains a revenue/sales pattern."""
        # Should have at least one pattern that maps to page1_line1a
        targets = set(DEFAULT_GL_MAPPING.values())
        assert "page1_line1a" in targets

    def test_default_gl_mapping_has_cogs_entry(self) -> None:
        """DEFAULT_GL_MAPPING contains a COGS pattern."""
        targets = set(DEFAULT_GL_MAPPING.values())
        assert "page1_line2" in targets

    def test_default_gl_mapping_has_officer_comp(self) -> None:
        """DEFAULT_GL_MAPPING contains officer compensation pattern."""
        targets = set(DEFAULT_GL_MAPPING.values())
        assert "page1_line7" in targets

    def test_default_gl_mapping_has_balance_sheet_lines(self) -> None:
        """DEFAULT_GL_MAPPING includes Schedule L balance sheet lines."""
        targets = set(DEFAULT_GL_MAPPING.values())
        assert "schedule_l_line1" in targets  # Cash
        assert "schedule_l_line2" in targets  # AR
        assert "schedule_l_line16" in targets  # AP
        assert "schedule_l_line22" in targets  # Capital Stock


# =============================================================================
# Tests: map_gl_to_1120s
# =============================================================================


class TestMapGlTo1120s:
    """Tests for GL account mapping to 1120-S lines."""

    def _make_tb(self, entries: list[TrialBalanceEntry]) -> TrialBalance:
        """Helper to create a TrialBalance from entries."""
        return TrialBalance(
            entries=entries,
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Test Corp",
            source_format="excel",
        )

    def test_officer_salary_maps_to_page1_line7_high_confidence(self) -> None:
        """'Officer Salary' maps to page1_line7 with HIGH confidence."""
        entry = TrialBalanceEntry(
            account_name="Officer Salary",
            account_type="expense",
            debit=Decimal("120000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert len(mappings) == 1
        assert mappings[0].form_line == "page1_line7"
        assert mappings[0].confidence == ConfidenceLevel.HIGH

    def test_cash_in_bank_maps_to_schedule_l_line1_high(self) -> None:
        """'Cash in Bank' maps to schedule_l_line1 with HIGH confidence."""
        entry = TrialBalanceEntry(
            account_name="Cash in Bank",
            account_type="asset",
            debit=Decimal("50000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert len(mappings) == 1
        assert mappings[0].form_line == "schedule_l_line1"
        assert mappings[0].confidence == ConfidenceLevel.HIGH

    def test_revenue_maps_to_page1_line1a(self) -> None:
        """'Sales Revenue' maps to page1_line1a."""
        entry = TrialBalanceEntry(
            account_name="Sales Revenue",
            account_type="revenue",
            credit=Decimal("500000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line1a"
        assert mappings[0].confidence == ConfidenceLevel.HIGH

    def test_cogs_maps_to_page1_line2(self) -> None:
        """'Cost of Goods Sold' maps to page1_line2."""
        entry = TrialBalanceEntry(
            account_name="Cost of Goods Sold",
            account_type="cogs",
            debit=Decimal("300000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line2"
        assert mappings[0].confidence == ConfidenceLevel.HIGH

    def test_rent_maps_to_page1_line13(self) -> None:
        """'Rent Expense' maps to page1_line13."""
        entry = TrialBalanceEntry(
            account_name="Rent Expense",
            account_type="expense",
            debit=Decimal("12000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line13"

    def test_depreciation_maps_to_page1_line15(self) -> None:
        """'Depreciation Expense' maps to page1_line15."""
        entry = TrialBalanceEntry(
            account_name="Depreciation Expense",
            account_type="expense",
            debit=Decimal("20000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line15"

    def test_interest_expense_maps_to_page1_line14(self) -> None:
        """'Interest Expense' maps to page1_line14."""
        entry = TrialBalanceEntry(
            account_name="Interest Expense",
            account_type="expense",
            debit=Decimal("5000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line14"

    def test_taxes_and_licenses_maps_to_page1_line12(self) -> None:
        """'Taxes and Licenses' maps to page1_line12."""
        entry = TrialBalanceEntry(
            account_name="Taxes and Licenses",
            account_type="expense",
            debit=Decimal("3000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line12"

    def test_miscellaneous_expense_medium_confidence(self) -> None:
        """'Miscellaneous Expense' maps to page1_line20 with MEDIUM confidence."""
        entry = TrialBalanceEntry(
            account_name="Miscellaneous Expense",
            account_type="expense",
            debit=Decimal("1000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line20"
        assert mappings[0].confidence == ConfidenceLevel.MEDIUM

    def test_unknown_account_low_confidence(self) -> None:
        """Completely unknown account gets LOW confidence."""
        entry = TrialBalanceEntry(
            account_name="ZZZ Widget Counter",
            account_type="expense",
            debit=Decimal("500"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].confidence == ConfidenceLevel.LOW

    def test_one_mapping_per_entry(self) -> None:
        """Each TrialBalanceEntry gets exactly one GLMapping."""
        entries = [
            TrialBalanceEntry(
                account_name="Cash", account_type="asset", debit=Decimal("10000")
            ),
            TrialBalanceEntry(
                account_name="Revenue", account_type="revenue", credit=Decimal("10000")
            ),
        ]
        tb = self._make_tb(entries)
        mappings = map_gl_to_1120s(tb)

        assert len(mappings) == len(entries)

    def test_case_insensitive_matching(self) -> None:
        """Mapping is case-insensitive ('OFFICER SALARY' still matches)."""
        entry = TrialBalanceEntry(
            account_name="OFFICER SALARY",
            account_type="expense",
            debit=Decimal("120000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "page1_line7"
        assert mappings[0].confidence == ConfidenceLevel.HIGH

    def test_accounts_receivable_maps_to_schedule_l_line2(self) -> None:
        """'Accounts Receivable' maps to schedule_l_line2."""
        entry = TrialBalanceEntry(
            account_name="Accounts Receivable",
            account_type="asset",
            debit=Decimal("25000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line2"

    def test_inventory_maps_to_schedule_l_line3(self) -> None:
        """'Inventory' maps to schedule_l_line3."""
        entry = TrialBalanceEntry(
            account_name="Inventory",
            account_type="asset",
            debit=Decimal("15000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line3"

    def test_accounts_payable_maps_to_schedule_l_line16(self) -> None:
        """'Accounts Payable' maps to schedule_l_line16."""
        entry = TrialBalanceEntry(
            account_name="Accounts Payable",
            account_type="liability",
            credit=Decimal("18000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line16"

    def test_retained_earnings_maps_to_schedule_l_line24(self) -> None:
        """'Retained Earnings' maps to schedule_l_line24."""
        entry = TrialBalanceEntry(
            account_name="Retained Earnings",
            account_type="equity",
            credit=Decimal("42000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line24"

    def test_accumulated_depreciation_maps_to_schedule_l_line10b(self) -> None:
        """'Accumulated Depreciation' maps to schedule_l_line10b (contra asset)."""
        entry = TrialBalanceEntry(
            account_name="Accumulated Depreciation",
            account_type="asset",
            credit=Decimal("20000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line10b"

    def test_fixed_assets_maps_to_schedule_l_line10a(self) -> None:
        """'Equipment' / 'Fixed Assets' maps to schedule_l_line10a."""
        entry = TrialBalanceEntry(
            account_name="Equipment",
            account_type="asset",
            debit=Decimal("100000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)

        assert mappings[0].form_line == "schedule_l_line10a"


# =============================================================================
# Tests: aggregate_mapped_amounts
# =============================================================================


class TestAggregateMappedAmounts:
    """Tests for aggregation of mapped amounts by form line."""

    def _make_tb(self, entries: list[TrialBalanceEntry]) -> TrialBalance:
        """Helper to create a TrialBalance from entries."""
        return TrialBalance(
            entries=entries,
            period_start="2024-01-01",
            period_end="2024-12-31",
            entity_name="Test Corp",
            source_format="excel",
        )

    def test_revenue_credit_balance_becomes_positive_income(self) -> None:
        """Revenue with credit balance aggregates to positive income amount."""
        entry = TrialBalanceEntry(
            account_name="Sales Revenue",
            account_type="revenue",
            credit=Decimal("500000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        # Revenue credit balance (net_balance = -500000) -> positive income
        assert result["page1_line1a"] == Decimal("500000")

    def test_expense_debit_balance_stays_positive(self) -> None:
        """Expense with debit balance aggregates to positive deduction amount."""
        entry = TrialBalanceEntry(
            account_name="Officer Salary",
            account_type="expense",
            debit=Decimal("120000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        assert result["page1_line7"] == Decimal("120000")

    def test_multiple_accounts_on_same_line_are_summed(self) -> None:
        """Multiple accounts mapping to the same line are aggregated."""
        entries = [
            TrialBalanceEntry(
                account_name="Salaries and Wages",
                account_type="expense",
                debit=Decimal("15000"),
            ),
            TrialBalanceEntry(
                account_name="Employee Wages",
                account_type="expense",
                debit=Decimal("10000"),
            ),
        ]
        tb = self._make_tb(entries)
        mappings = map_gl_to_1120s(tb)

        # Both should map to page1_line8 (salaries/wages)
        result = aggregate_mapped_amounts(tb, mappings)
        assert result.get("page1_line8", Decimal("0")) == Decimal("25000")

    def test_aggregation_returns_dict_of_decimals(self) -> None:
        """Result is dict[str, Decimal]."""
        entries = [
            TrialBalanceEntry(
                account_name="Cash", account_type="asset", debit=Decimal("10000")
            ),
            TrialBalanceEntry(
                account_name="Revenue",
                account_type="revenue",
                credit=Decimal("10000"),
            ),
        ]
        tb = self._make_tb(entries)
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        assert isinstance(result, dict)
        for key, val in result.items():
            assert isinstance(key, str)
            assert isinstance(val, Decimal)

    def test_cogs_debit_balance_positive(self) -> None:
        """COGS with debit balance aggregates to positive amount."""
        entry = TrialBalanceEntry(
            account_name="Cost of Goods Sold",
            account_type="cogs",
            debit=Decimal("300000"),
        )
        tb = self._make_tb([entry])
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        assert result["page1_line2"] == Decimal("300000")

    def test_empty_trial_balance_returns_empty_dict(self) -> None:
        """Empty trial balance returns empty aggregation dict."""
        tb = self._make_tb([])
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        assert result == {}


# =============================================================================
# Tests: Integration / End-to-end
# =============================================================================


class TestEndToEnd:
    """End-to-end tests: parse -> map -> aggregate."""

    def test_full_pipeline(self) -> None:
        """Parse Excel, map accounts, aggregate amounts -- full pipeline."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)
        mappings = map_gl_to_1120s(tb)
        result = aggregate_mapped_amounts(tb, mappings)

        # Verify key amounts
        assert result.get("page1_line1a") == Decimal("500000")  # Revenue
        assert result.get("page1_line2") == Decimal("300000")  # COGS
        assert result.get("page1_line7") == Decimal("120000")  # Officer comp
        assert result.get("schedule_l_line1") == Decimal("50000")  # Cash

    def test_debits_equal_credits_after_parsing(self) -> None:
        """Trial balance debits == credits after parsing standard Excel."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)

        assert tb.total_debits == tb.total_credits
        assert tb.is_balanced

    def test_all_entries_get_mappings(self) -> None:
        """Every entry from parsed trial balance gets a mapping."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)
        mappings = map_gl_to_1120s(tb)

        assert len(mappings) == len(tb.entries)

    def test_high_confidence_for_common_accounts(self) -> None:
        """Common account names get HIGH confidence mapping."""
        data = _standard_two_column_excel()
        tb = parse_excel_trial_balance(data)
        mappings = map_gl_to_1120s(tb)

        high_confidence = [m for m in mappings if m.confidence == ConfidenceLevel.HIGH]
        # Most of the standard accounts should be HIGH confidence
        assert len(high_confidence) >= 10
