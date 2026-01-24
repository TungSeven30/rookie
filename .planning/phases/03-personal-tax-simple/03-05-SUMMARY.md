# Plan 03-05 Summary: Tax Calculator with Credits

**Status:** Complete
**Duration:** ~10 minutes
**TDD Phases:** RED → GREEN → REFACTOR

## What Was Built

### Tax Calculator Module (`src/agents/personal_tax/calculator.py`)

Pure functions for personal tax calculations:

| Function | Purpose |
|----------|---------|
| `aggregate_income()` | Sums W-2 wages, 1099-INT interest, 1099-DIV dividends, 1099-NEC income |
| `get_standard_deduction()` | Lookup by filing status and year (2023, 2024) |
| `calculate_deductions()` | Standard vs itemized comparison, selects higher |
| `evaluate_credits()` | CTC, AOC, Saver's Credit, EITC evaluation with phaseouts |
| `calculate_tax()` | Marginal bracket calculation for all filing statuses |
| `compare_years()` | Variance detection with configurable threshold |

### Data Structures

| Structure | Purpose |
|-----------|---------|
| `IncomeSummary` | Aggregated income by type with federal withholding |
| `DeductionResult` | Selected deduction method and amounts |
| `TaxSituation` | Input for credits evaluation (AGI, children, expenses) |
| `CreditItem` | Individual credit with name, amount, refundable flag |
| `CreditsResult` | All credits with refundable/nonrefundable totals |
| `TaxResult` | Gross tax, bracket breakdown, effective rate |
| `VarianceItem` | Prior year variance with percentage and direction |

### Tax Constants (2024)

| Constant | Single | MFJ | MFS | HOH |
|----------|--------|-----|-----|-----|
| Standard Deduction | $14,600 | $29,200 | $14,600 | $21,900 |
| 10% Bracket | $0-$11,600 | $0-$23,200 | $0-$11,600 | $0-$16,550 |
| 12% Bracket | $11,601-$47,150 | $23,201-$94,300 | $11,601-$47,150 | $16,551-$63,100 |
| CTC Phaseout | $200,000 | $400,000 | - | - |

### Credits Implemented (PTAX-05)

1. **Child Tax Credit (CTC):** $2,000/child, phases out $50/$1,000 above threshold
2. **American Opportunity Credit (AOC):** 100% of first $2k + 25% of next $2k = max $2,500
3. **Saver's Credit:** 10-50% of retirement contributions based on AGI tier
4. **Earned Income Credit (EITC):** Simplified for no-child filers, fully refundable

## Test Coverage

**Total: 72 tests passing**

| Category | Tests |
|----------|-------|
| Income Aggregation | 7 |
| Standard Deduction | 5 |
| Calculate Deductions | 3 |
| Child Tax Credit | 5 |
| Education Credit | 3 |
| Saver's Credit | 3 |
| EITC | 3 |
| Credits Result | 3 |
| Tax Calculation | 6 |
| Prior Year Variance | 8 |
| Data Structures | 7 |
| Edge Cases | 19 |

## Requirements Delivered

| Requirement | Description | Status |
|-------------|-------------|--------|
| PTAX-03 | Income aggregation from W-2, 1099s | ✅ Complete |
| PTAX-04 | Standard vs itemized deduction selection | ✅ Complete |
| PTAX-05 | Credits evaluation (CTC, AOC, Saver's, EITC) | ✅ Complete |
| PTAX-06 | Tax bracket calculation with marginal rates | ✅ Complete |
| PTAX-12 | Prior year variance detection (>10%) | ✅ Complete |

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| Decimal for all monetary values | Float precision issues with currency |
| Dataclasses for structures | Simple, immutable data containers |
| Constants indexed by (year, status) | Easy to add new tax years |
| CTC phaseout rounding up | IRS rounds up to nearest $1,000 |
| EITC simplified (no children only) | Full EITC tables complex, defer to v2 |

## TDD Commits

1. `test(03-05): add failing tests for tax calculator with credits` - RED phase
2. `feat(03-05): implement tax calculator with credits evaluation` - GREEN phase
3. `refactor(03-05): add edge case tests for tax calculator` - REFACTOR phase

## Files Modified

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/__init__.py` | 4 | Package marker |
| `src/agents/personal_tax/__init__.py` | 35 | Module exports |
| `src/agents/personal_tax/calculator.py` | 762 | Implementation |
| `tests/agents/__init__.py` | 1 | Package marker |
| `tests/agents/personal_tax/__init__.py` | 1 | Package marker |
| `tests/agents/personal_tax/test_calculator.py` | 1076 | Test suite |

## Dependencies

- Uses existing `src/documents/models.py` (W2Data, Form1099INT, Form1099DIV, Form1099NEC)
- Pure Python with only `decimal` and `dataclasses` from stdlib

## Next Steps

- 03-06: Form routing based on document type
- 03-07: End-to-end integration testing
