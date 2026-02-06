"""K-1 pro-rata allocation and handoff protocol for S-Corporation shareholders.

This module bridges the Business Tax Agent output to the Personal Tax Agent
input by:
1. Allocating Schedule K line items to shareholders pro-rata by ownership_pct
2. Generating validated FormK1 Pydantic models for each shareholder
3. Serializing/deserializing K-1 artifacts for inter-agent handoff

Rounding strategy: All shareholders except the last get a quantized amount.
The last shareholder receives the residual (total minus sum of others),
guaranteeing allocations sum exactly to the Schedule K total. This is
standard accounting practice for eliminating rounding discrepancies.

All arithmetic uses Decimal. No floating point.
"""

from __future__ import annotations

from decimal import Decimal

import orjson

from src.agents.business_tax.basis import BasisResult
from src.agents.business_tax.models import ScheduleK, ShareholderInfo
from src.documents.models import ConfidenceLevel, FormK1

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

# ScheduleK field -> FormK1 field name mapping.
# Keys are ScheduleK attribute names; values are FormK1 attribute names.
_SCHEDULE_K_TO_K1_MAP: dict[str, str] = {
    "ordinary_income": "ordinary_business_income",
    "net_rental_real_estate": "net_rental_real_estate",
    "other_rental_income": "other_rental_income",
    "interest_income": "interest_income",
    "dividends": "dividend_income",
    "royalties": "royalties",
    "net_short_term_capital_gain": "net_short_term_capital_gain",
    "net_long_term_capital_gain": "net_long_term_capital_gain",
    "net_section_1231_gain": "net_section_1231_gain",
    "other_income_loss": "other_income",
    "section_179_deduction": "section_179_deduction",
    "charitable_contributions": "other_deductions",
    "credits": "credits",
    "foreign_transactions": "foreign_transactions",
    "distributions": "distributions",
}

# Income-side K-1 fields (used for current_year_increase heuristic)
_INCOME_FIELDS = {
    "ordinary_business_income",
    "net_rental_real_estate",
    "other_rental_income",
    "interest_income",
    "dividend_income",
    "royalties",
    "net_short_term_capital_gain",
    "net_long_term_capital_gain",
    "net_section_1231_gain",
    "other_income",
}

# Deduction/distribution-side K-1 fields (used for current_year_decrease)
_DECREASE_FIELDS = {
    "section_179_deduction",
    "other_deductions",
    "distributions",
}


def allocate_k1_item(
    schedule_k_total: Decimal,
    shareholders: list[ShareholderInfo],
) -> list[Decimal]:
    """Allocate a single Schedule K line item pro-rata by ownership percentage.

    For all shareholders except the last, the amount is computed as:
        (total * ownership_pct / 100).quantize(Decimal("0.01"))

    The last shareholder receives the residual (total - sum of others),
    which eliminates rounding discrepancies.

    Args:
        schedule_k_total: The total amount for this Schedule K line.
        shareholders: List of shareholders with ownership_pct fields.

    Returns:
        List of Decimal amounts in the same order as shareholders.

    Raises:
        ValueError: If ownership percentages do not sum to 100.
    """
    pct_sum = sum(sh.ownership_pct for sh in shareholders)
    if pct_sum != Decimal("100"):
        raise ValueError(
            f"Ownership percentages must sum to 100, got {pct_sum}"
        )

    amounts: list[Decimal] = []
    running_total = ZERO

    for i, sh in enumerate(shareholders):
        if i < len(shareholders) - 1:
            amount = (schedule_k_total * sh.ownership_pct / Decimal("100")).quantize(
                TWO_PLACES
            )
            amounts.append(amount)
            running_total += amount
        else:
            # Last shareholder gets the residual
            amounts.append(schedule_k_total - running_total)

    return amounts


def allocate_k1s(
    schedule_k: ScheduleK,
    shareholders: list[ShareholderInfo],
) -> list[dict[str, Decimal]]:
    """Allocate every Schedule K field to each shareholder.

    Iterates over all mapped Schedule K fields, allocates each to
    shareholders using allocate_k1_item, and returns a list of dicts
    (one per shareholder) mapping FormK1 field names to allocated amounts.

    Args:
        schedule_k: The Schedule K with entity-level totals.
        shareholders: Shareholders to allocate to.

    Returns:
        List of dicts (one per shareholder), each mapping K-1 field names
        to allocated Decimal amounts.
    """
    n = len(shareholders)
    result: list[dict[str, Decimal]] = [{} for _ in range(n)]

    for sk_field, k1_field in _SCHEDULE_K_TO_K1_MAP.items():
        total = getattr(schedule_k, sk_field)
        amounts = allocate_k1_item(total, shareholders)
        for i, amount in enumerate(amounts):
            result[i][k1_field] = amount

    return result


def generate_k1_for_handoff(
    entity_name: str,
    entity_ein: str,
    tax_year: int,
    shareholder: ShareholderInfo,
    allocated_amounts: dict[str, Decimal],
    basis_result: BasisResult | None = None,
) -> FormK1:
    """Create a FormK1 instance from computed K-1 data.

    Builds a fully validated FormK1 Pydantic model with entity info,
    shareholder info, and all allocated amounts. If a BasisResult is
    provided, capital account fields are populated.

    Args:
        entity_name: S-Corporation name.
        entity_ein: Entity EIN (XX-XXXXXXX or 9 digits).
        tax_year: Tax year for the K-1.
        shareholder: Shareholder receiving this K-1.
        allocated_amounts: Dict mapping FormK1 field names to Decimal amounts.
        basis_result: Optional basis computation result for capital account.

    Returns:
        Validated FormK1 model.
    """
    fields: dict[str, object] = {
        "entity_name": entity_name,
        "entity_ein": entity_ein,
        "entity_type": "s_corp",
        "tax_year": tax_year,
        "recipient_name": shareholder.name,
        "recipient_tin": shareholder.tin,
        "ownership_percentage": shareholder.ownership_pct,
        "confidence": ConfidenceLevel.HIGH,
    }

    # Set allocated amounts
    for field_name, amount in allocated_amounts.items():
        fields[field_name] = amount

    # Map BasisResult to capital account fields
    if basis_result is not None:
        fields["capital_account_beginning"] = basis_result.beginning_stock_basis
        fields["capital_account_ending"] = basis_result.ending_stock_basis

        # Compute current_year_increase: sum of positive income allocations
        increase = ZERO
        for field_name in _INCOME_FIELDS:
            val = allocated_amounts.get(field_name, ZERO)
            if val > ZERO:
                increase += val
        fields["current_year_increase"] = increase

        # Compute current_year_decrease: sum of loss allocations + distributions
        decrease = ZERO
        for field_name in _INCOME_FIELDS:
            val = allocated_amounts.get(field_name, ZERO)
            if val < ZERO:
                decrease += abs(val)
        for field_name in _DECREASE_FIELDS:
            val = allocated_amounts.get(field_name, ZERO)
            if val > ZERO:
                decrease += val
        fields["current_year_decrease"] = decrease

    return FormK1(**fields)


def serialize_k1_artifact(form_k1: FormK1) -> str:
    """Serialize a FormK1 to a JSON string using orjson.

    Uses model_dump(mode="json") for proper Decimal serialization.

    Args:
        form_k1: The FormK1 model to serialize.

    Returns:
        JSON string representation.
    """
    data = form_k1.model_dump(mode="json")
    return orjson.dumps(data).decode("utf-8")


def deserialize_k1_artifact(json_str: str) -> FormK1:
    """Deserialize a JSON string back to a FormK1.

    Validates all fields through Pydantic model construction.

    Args:
        json_str: JSON string to deserialize.

    Returns:
        Validated FormK1 model.

    Raises:
        ValidationError: If JSON data fails FormK1 validation.
    """
    data = orjson.loads(json_str)
    return FormK1(**data)
