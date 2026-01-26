"""Personal tax agent module.

This module provides the PersonalTaxAgent for processing personal tax returns,
along with tax calculation functions and output generators.

Components:
- PersonalTaxAgent: Main agent orchestrating the complete workflow
- personal_tax_handler: Task handler for dispatcher integration
- Calculator functions: Income aggregation, deductions, credits, tax computation
- Output generators: Drake worksheet and preparer notes generation
"""

from src.agents.personal_tax.agent import (
    EscalationRequired,
    PersonalTaxAgent,
    PersonalTaxResult,
    personal_tax_handler,
)
from src.agents.personal_tax.calculator import (
    CreditItem,
    CreditInputs,
    CreditsResult,
    DeductionResult,
    IncomeSummary,
    ItemizedDeductionBreakdown,
    TaxResult,
    TaxSituation,
    VarianceItem,
    aggregate_income,
    build_credit_inputs,
    calculate_deductions,
    calculate_tax,
    compare_years,
    compute_itemized_deductions,
    evaluate_credits,
    get_standard_deduction,
)
from src.agents.personal_tax.output import (
    generate_drake_worksheet,
    generate_preparer_notes,
)

__all__ = [
    # Agent
    "PersonalTaxAgent",
    "PersonalTaxResult",
    "EscalationRequired",
    "personal_tax_handler",
    # Data structures
    "IncomeSummary",
    "DeductionResult",
    "ItemizedDeductionBreakdown",
    "TaxSituation",
    "CreditInputs",
    "CreditItem",
    "CreditsResult",
    "TaxResult",
    "VarianceItem",
    # Calculator functions
    "aggregate_income",
    "get_standard_deduction",
    "calculate_deductions",
    "compute_itemized_deductions",
    "build_credit_inputs",
    "evaluate_credits",
    "calculate_tax",
    "compare_years",
    # Output generators
    "generate_drake_worksheet",
    "generate_preparer_notes",
]
