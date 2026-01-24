"""Personal tax agent module.

This module provides tax calculation functions for personal (individual) tax returns.
Supports W-2 and 1099 income aggregation, deduction calculation, credits evaluation,
tax bracket computation, and prior year comparison.
"""

from src.agents.personal_tax.calculator import (
    CreditItem,
    CreditsResult,
    DeductionResult,
    IncomeSummary,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    calculate_deductions,
    calculate_tax,
    compare_years,
    evaluate_credits,
    get_standard_deduction,
)

__all__ = [
    "IncomeSummary",
    "DeductionResult",
    "TaxSituation",
    "CreditItem",
    "CreditsResult",
    "TaxResult",
    "VarianceItem",
    "aggregate_income",
    "get_standard_deduction",
    "calculate_deductions",
    "evaluate_credits",
    "calculate_tax",
    "compare_years",
]
