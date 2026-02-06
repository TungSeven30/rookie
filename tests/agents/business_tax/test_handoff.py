"""Tests for K-1 allocation and handoff protocol.

TDD test suite covering:
- allocate_k1_item: Pro-rata allocation with residual rounding
- allocate_k1s: Full Schedule K allocation to shareholders
- generate_k1_for_handoff: FormK1 creation with validation
- serialize_k1_artifact / deserialize_k1_artifact: JSON roundtrip
- Reconciliation: K-1 totals match Schedule K
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from src.agents.business_tax.basis import BasisResult
from src.agents.business_tax.handoff import (
    allocate_k1_item,
    allocate_k1s,
    deserialize_k1_artifact,
    generate_k1_for_handoff,
    serialize_k1_artifact,
)
from src.agents.business_tax.models import ScheduleK, ShareholderInfo
from src.documents.models import ConfidenceLevel, FormK1

D = Decimal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_shareholder(
    name: str,
    tin: str,
    pct: Decimal,
    stock_basis: Decimal = D("10000"),
    debt_basis: Decimal = D("0"),
) -> ShareholderInfo:
    """Create a ShareholderInfo for testing."""
    return ShareholderInfo(
        name=name,
        tin=tin,
        ownership_pct=pct,
        is_officer=False,
        beginning_stock_basis=stock_basis,
        beginning_debt_basis=debt_basis,
    )


def _shareholders_50_50() -> list[ShareholderInfo]:
    return [
        _make_shareholder("Alice", "123-45-6789", D("50")),
        _make_shareholder("Bob", "987-65-4321", D("50")),
    ]


def _shareholders_75_25() -> list[ShareholderInfo]:
    return [
        _make_shareholder("Alice", "123-45-6789", D("75")),
        _make_shareholder("Bob", "987-65-4321", D("25")),
    ]


def _shareholders_thirds() -> list[ShareholderInfo]:
    return [
        _make_shareholder("Alice", "123-45-6789", D("33.33")),
        _make_shareholder("Bob", "987-65-4321", D("33.33")),
        _make_shareholder("Carol", "111-22-3333", D("33.34")),
    ]


def _schedule_k_simple(ordinary: Decimal = D("100000")) -> ScheduleK:
    return ScheduleK(ordinary_income=ordinary)


def _schedule_k_multi() -> ScheduleK:
    return ScheduleK(
        ordinary_income=D("100000"),
        interest_income=D("5000"),
        dividends=D("3000"),
        net_long_term_capital_gain=D("10000"),
        charitable_contributions=D("2000"),
        distributions=D("20000"),
    )


# ===========================================================================
# allocate_k1_item tests
# ===========================================================================


class TestAllocateK1Item:
    """Tests for single-item pro-rata allocation."""

    def test_50_50_split(self) -> None:
        result = allocate_k1_item(D("100"), _shareholders_50_50())
        assert result == [D("50"), D("50")]

    def test_75_25_split(self) -> None:
        result = allocate_k1_item(D("100"), _shareholders_75_25())
        assert result == [D("75"), D("25")]

    def test_thirds_sum_exact(self) -> None:
        """Three-way split sums to exactly the original amount."""
        result = allocate_k1_item(D("100"), _shareholders_thirds())
        assert sum(result) == D("100")
        assert len(result) == 3

    def test_uneven_rounding_101_cents(self) -> None:
        """$1.01 split 50/50 -- last shareholder gets residual."""
        result = allocate_k1_item(D("1.01"), _shareholders_50_50())
        assert sum(result) == D("1.01")
        # First gets floor: 1.01 * 50/100 = 0.505 -> 0.51 (rounded)
        # or 0.50, last gets residual
        assert result[0] + result[1] == D("1.01")

    def test_zero_amount(self) -> None:
        result = allocate_k1_item(D("0"), _shareholders_50_50())
        assert result == [D("0"), D("0")]

    def test_negative_amount_loss(self) -> None:
        result = allocate_k1_item(D("-100"), _shareholders_50_50())
        assert result == [D("-50"), D("-50")]

    def test_negative_thirds_sum_exact(self) -> None:
        """Negative amount three-way split sums exactly."""
        result = allocate_k1_item(D("-100"), _shareholders_thirds())
        assert sum(result) == D("-100")

    def test_ownership_not_100_raises(self) -> None:
        bad = [
            _make_shareholder("A", "123-45-6789", D("40")),
            _make_shareholder("B", "987-65-4321", D("40")),
        ]
        with pytest.raises(ValueError, match="100"):
            allocate_k1_item(D("100"), bad)

    def test_single_shareholder_100pct(self) -> None:
        sh = [_make_shareholder("Solo", "123-45-6789", D("100"))]
        result = allocate_k1_item(D("12345.67"), sh)
        assert result == [D("12345.67")]

    def test_large_amount_rounding(self) -> None:
        """Large amount with thirds -- rounding residual correct."""
        result = allocate_k1_item(D("999999.99"), _shareholders_thirds())
        assert sum(result) == D("999999.99")

    def test_tiny_amount_rounding(self) -> None:
        """Very small amount split across 3 shareholders."""
        result = allocate_k1_item(D("0.01"), _shareholders_thirds())
        assert sum(result) == D("0.01")


# ===========================================================================
# allocate_k1s tests
# ===========================================================================


class TestAllocateK1s:
    """Tests for full Schedule K allocation."""

    def test_two_shareholders_50_50_ordinary_only(self) -> None:
        sk = _schedule_k_simple(D("100000"))
        result = allocate_k1s(sk, _shareholders_50_50())
        assert len(result) == 2
        assert result[0]["ordinary_business_income"] == D("50000")
        assert result[1]["ordinary_business_income"] == D("50000")

    def test_two_shareholders_70_30_multi(self) -> None:
        sk = _schedule_k_multi()
        shareholders = [
            _make_shareholder("Alice", "123-45-6789", D("70")),
            _make_shareholder("Bob", "987-65-4321", D("30")),
        ]
        result = allocate_k1s(sk, shareholders)
        assert len(result) == 2
        # Ordinary: 70000 / 30000
        assert result[0]["ordinary_business_income"] == D("70000")
        assert result[1]["ordinary_business_income"] == D("30000")
        # Interest: 3500 / 1500
        assert result[0]["interest_income"] == D("3500")
        assert result[1]["interest_income"] == D("1500")

    def test_all_amounts_sum_to_schedule_k(self) -> None:
        """Every allocated field sums across shareholders to Schedule K total."""
        sk = _schedule_k_multi()
        result = allocate_k1s(sk, _shareholders_thirds())
        # Check every key
        for key in result[0]:
            total = sum(r[key] for r in result)
            # Map back to ScheduleK field name to find expected total
            k_field = _k1_to_schedule_k_field(key)
            if k_field is not None:
                expected = getattr(sk, k_field)
                assert total == expected, f"{key}: {total} != {expected}"

    def test_zero_schedule_k_produces_zeros(self) -> None:
        sk = ScheduleK()
        result = allocate_k1s(sk, _shareholders_50_50())
        for r in result:
            for v in r.values():
                assert v == D("0")

    def test_field_name_mapping_dividends(self) -> None:
        """ScheduleK.dividends maps to FormK1 key 'dividend_income'."""
        sk = ScheduleK(dividends=D("1000"))
        result = allocate_k1s(sk, _shareholders_50_50())
        assert "dividend_income" in result[0]
        assert result[0]["dividend_income"] == D("500")

    def test_field_name_mapping_other_income(self) -> None:
        """ScheduleK.other_income_loss maps to FormK1 key 'other_income'."""
        sk = ScheduleK(other_income_loss=D("800"))
        result = allocate_k1s(sk, _shareholders_50_50())
        assert "other_income" in result[0]
        assert result[0]["other_income"] == D("400")

    def test_charitable_contributions_maps_to_other_deductions(self) -> None:
        """ScheduleK.charitable_contributions maps to 'other_deductions'."""
        sk = ScheduleK(charitable_contributions=D("5000"))
        result = allocate_k1s(sk, _shareholders_50_50())
        assert result[0]["other_deductions"] == D("2500")


# ===========================================================================
# generate_k1_for_handoff tests
# ===========================================================================


class TestGenerateK1ForHandoff:
    """Tests for FormK1 creation."""

    def test_creates_valid_form_k1(self) -> None:
        sh = _shareholders_50_50()[0]
        amounts = {"ordinary_business_income": D("50000"), "interest_income": D("2500")}
        k1 = generate_k1_for_handoff(
            entity_name="Test Corp",
            entity_ein="12-3456789",
            tax_year=2024,
            shareholder=sh,
            allocated_amounts=amounts,
        )
        assert isinstance(k1, FormK1)
        assert k1.entity_name == "Test Corp"
        assert k1.entity_ein == "12-3456789"
        assert k1.tax_year == 2024

    def test_entity_type_is_s_corp(self) -> None:
        sh = _shareholders_50_50()[0]
        k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, {})
        assert k1.entity_type == "s_corp"

    def test_confidence_is_high(self) -> None:
        sh = _shareholders_50_50()[0]
        k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, {})
        assert k1.confidence == ConfidenceLevel.HIGH

    def test_allocated_amounts_set(self) -> None:
        sh = _shareholders_50_50()[0]
        amounts = {
            "ordinary_business_income": D("75000"),
            "dividend_income": D("3000"),
            "distributions": D("10000"),
        }
        k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, amounts)
        assert k1.ordinary_business_income == D("75000")
        assert k1.dividend_income == D("3000")
        assert k1.distributions == D("10000")

    def test_recipient_info_from_shareholder(self) -> None:
        sh = _shareholders_50_50()[0]
        k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, {})
        assert k1.recipient_name == sh.name
        assert k1.recipient_tin == sh.tin
        assert k1.ownership_percentage == sh.ownership_pct

    def test_ein_validated(self) -> None:
        sh = _shareholders_50_50()[0]
        # EIN without dash should be reformatted
        k1 = generate_k1_for_handoff("Corp", "123456789", 2024, sh, {})
        assert k1.entity_ein == "12-3456789"

    def test_with_basis_result_capital_account(self) -> None:
        sh = _shareholders_50_50()[0]
        basis = BasisResult(
            beginning_stock_basis=D("10000"),
            ending_stock_basis=D("15000"),
            beginning_debt_basis=D("0"),
            ending_debt_basis=D("0"),
            suspended_losses=D("0"),
            distributions_taxable=D("0"),
            distributions_nontaxable=D("5000"),
            losses_allowed=D("0"),
            losses_limited_by_basis=D("0"),
        )
        amounts = {"ordinary_business_income": D("50000"), "distributions": D("5000")}
        k1 = generate_k1_for_handoff(
            "Corp", "12-3456789", 2024, sh, amounts, basis_result=basis
        )
        assert k1.capital_account_beginning == D("10000")
        assert k1.capital_account_ending == D("15000")
        assert k1.current_year_increase is not None
        assert k1.current_year_decrease is not None

    def test_without_basis_result_capital_account_none(self) -> None:
        sh = _shareholders_50_50()[0]
        k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, {})
        assert k1.capital_account_beginning is None
        assert k1.capital_account_ending is None
        assert k1.current_year_increase is None
        assert k1.current_year_decrease is None


# ===========================================================================
# Serialization roundtrip tests
# ===========================================================================


class TestSerialization:
    """Tests for serialize/deserialize roundtrip."""

    def _make_k1(self) -> FormK1:
        return FormK1(
            entity_name="Test Corp",
            entity_ein="12-3456789",
            entity_type="s_corp",
            tax_year=2024,
            recipient_name="Alice",
            recipient_tin="123-45-6789",
            ownership_percentage=D("50"),
            ordinary_business_income=D("50000.50"),
            interest_income=D("2500.25"),
            dividend_income=D("1500"),
            distributions=D("10000"),
            confidence=ConfidenceLevel.HIGH,
        )

    def test_roundtrip_identical(self) -> None:
        k1 = self._make_k1()
        json_str = serialize_k1_artifact(k1)
        restored = deserialize_k1_artifact(json_str)
        assert restored == k1

    def test_decimal_precision_preserved(self) -> None:
        k1 = self._make_k1()
        json_str = serialize_k1_artifact(k1)
        restored = deserialize_k1_artifact(json_str)
        assert restored.ordinary_business_income == D("50000.50")
        assert restored.interest_income == D("2500.25")

    def test_all_fields_survive(self) -> None:
        """No data loss through serialization."""
        k1 = FormK1(
            entity_name="Full Corp",
            entity_ein="98-7654321",
            entity_type="s_corp",
            tax_year=2024,
            recipient_name="Bob",
            recipient_tin="987-65-4321",
            ownership_percentage=D("100"),
            capital_account_beginning=D("10000"),
            capital_account_ending=D("15000"),
            current_year_increase=D("7000"),
            current_year_decrease=D("2000"),
            ordinary_business_income=D("50000"),
            net_rental_real_estate=D("1000"),
            other_rental_income=D("500"),
            interest_income=D("200"),
            dividend_income=D("300"),
            royalties=D("100"),
            net_short_term_capital_gain=D("400"),
            net_long_term_capital_gain=D("600"),
            net_section_1231_gain=D("150"),
            other_income=D("75"),
            section_179_deduction=D("3000"),
            other_deductions=D("1500"),
            self_employment_earnings=D("0"),
            credits=D("250"),
            foreign_transactions=D("0"),
            distributions=D("5000"),
            confidence=ConfidenceLevel.HIGH,
            uncertain_fields=["net_section_1231_gain"],
        )
        json_str = serialize_k1_artifact(k1)
        restored = deserialize_k1_artifact(json_str)
        assert restored == k1

    def test_serialize_returns_string(self) -> None:
        k1 = self._make_k1()
        result = serialize_k1_artifact(k1)
        assert isinstance(result, str)

    def test_deserialize_validates(self) -> None:
        """Invalid JSON raises an error."""
        with pytest.raises(Exception):
            deserialize_k1_artifact('{"entity_name": "bad"}')


# ===========================================================================
# Reconciliation (critical integration test)
# ===========================================================================


class TestReconciliation:
    """K-1 allocations must sum to Schedule K totals."""

    def test_two_shareholders_all_fields_reconcile(self) -> None:
        """Generate K-1s and verify every field sums to Schedule K."""
        sk = _schedule_k_multi()
        shareholders = _shareholders_50_50()
        allocated = allocate_k1s(sk, shareholders)

        k1s = []
        for sh, amounts in zip(shareholders, allocated):
            k1 = generate_k1_for_handoff(
                "Test Corp", "12-3456789", 2024, sh, amounts
            )
            k1s.append(k1)

        # Check that K-1 fields sum to Schedule K
        assert k1s[0].ordinary_business_income + k1s[1].ordinary_business_income == sk.ordinary_income
        assert k1s[0].interest_income + k1s[1].interest_income == sk.interest_income
        assert k1s[0].dividend_income + k1s[1].dividend_income == sk.dividends
        assert k1s[0].net_long_term_capital_gain + k1s[1].net_long_term_capital_gain == sk.net_long_term_capital_gain
        assert k1s[0].other_deductions + k1s[1].other_deductions == sk.charitable_contributions
        assert k1s[0].distributions + k1s[1].distributions == sk.distributions

    def test_three_shareholders_unequal_reconcile(self) -> None:
        """Three shareholders with unequal splits must reconcile."""
        sk = ScheduleK(
            ordinary_income=D("123456.78"),
            interest_income=D("9876.54"),
            dividends=D("5432.10"),
            net_short_term_capital_gain=D("-2345.67"),
            distributions=D("50000"),
        )
        shareholders = _shareholders_thirds()
        allocated = allocate_k1s(sk, shareholders)

        k1s = []
        for sh, amounts in zip(shareholders, allocated):
            k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, amounts)
            k1s.append(k1)

        # Every field must reconcile
        fields_to_check = [
            ("ordinary_business_income", "ordinary_income"),
            ("interest_income", "interest_income"),
            ("dividend_income", "dividends"),
            ("net_short_term_capital_gain", "net_short_term_capital_gain"),
            ("distributions", "distributions"),
        ]
        for k1_field, sk_field in fields_to_check:
            total = sum(getattr(k1, k1_field) for k1 in k1s)
            expected = getattr(sk, sk_field)
            assert total == expected, f"{k1_field}: {total} != {expected}"

    def test_full_end_to_end_roundtrip(self) -> None:
        """Allocate -> generate -> serialize -> deserialize -> reconcile."""
        sk = _schedule_k_multi()
        shareholders = _shareholders_50_50()
        allocated = allocate_k1s(sk, shareholders)

        for sh, amounts in zip(shareholders, allocated):
            k1 = generate_k1_for_handoff("Corp", "12-3456789", 2024, sh, amounts)
            json_str = serialize_k1_artifact(k1)
            restored = deserialize_k1_artifact(json_str)
            assert restored == k1


# ---------------------------------------------------------------------------
# Helper: map K-1 field name back to Schedule K field name for reconciliation
# ---------------------------------------------------------------------------

_K1_TO_SK_MAP = {
    "ordinary_business_income": "ordinary_income",
    "net_rental_real_estate": "net_rental_real_estate",
    "other_rental_income": "other_rental_income",
    "interest_income": "interest_income",
    "dividend_income": "dividends",
    "royalties": "royalties",
    "net_short_term_capital_gain": "net_short_term_capital_gain",
    "net_long_term_capital_gain": "net_long_term_capital_gain",
    "net_section_1231_gain": "net_section_1231_gain",
    "other_income": "other_income_loss",
    "section_179_deduction": "section_179_deduction",
    "other_deductions": "charitable_contributions",
    "credits": "credits",
    "foreign_transactions": "foreign_transactions",
    "distributions": "distributions",
}


def _k1_to_schedule_k_field(k1_field: str) -> str | None:
    """Map a K-1 field name to the corresponding Schedule K field name."""
    return _K1_TO_SK_MAP.get(k1_field)
