---
phase: 6
plan: 3
subsystem: business-tax
tags: [basis-tracking, form-7203, irs-ordering, decimal-arithmetic, tdd]
dependency-graph:
  requires: [06-01]
  provides: [shareholder-basis-tracker, basis-adjustment-inputs, basis-result]
  affects: [06-04, 06-05]
tech-stack:
  added: []
  patterns: [frozen-dataclass, pure-function, decimal-arithmetic, tdd-red-green]
key-files:
  created:
    - src/agents/business_tax/basis.py
    - tests/agents/business_tax/test_basis.py
  modified:
    - src/agents/business_tax/__init__.py
decisions:
  - id: frozen-dataclass-inputs
    description: BasisAdjustmentInputs is a frozen dataclass to prevent mutation
    rationale: Tax inputs must be immutable once constructed to prevent accidental modification during multi-step calculation
  - id: losses-limited-equals-suspended
    description: losses_limited_by_basis equals suspended_losses in BasisResult
    rationale: Both represent the same quantity (losses that could not be applied due to insufficient basis) from different perspectives
  - id: negative-basis-guard
    description: ValueError raised for negative beginning stock or debt basis
    rationale: Negative beginning basis is an upstream data error and should fail fast
metrics:
  duration: 3m
  completed: 2026-02-06
---

# Phase 6 Plan 3: Shareholder Basis Tracker Summary

**One-liner:** IRS Form 7203 basis tracking with frozen inputs, 4-step ordering enforcement, stock-then-debt loss absorption, and suspended loss carry-forward -- 47 TDD tests, all Decimal.

## What Was Built

Implemented `calculate_shareholder_basis()` -- a pure function that applies the IRS 4-step ordering rules for annual shareholder basis adjustments in S-Corporations:

1. **Step 1 -- Income increases:** Ordinary income, separately stated income, tax-exempt income, and excess depletion increase stock basis.
2. **Step 2 -- Distributions:** Non-dividend distributions reduce stock basis (not below zero). Excess distributions are flagged as taxable capital gain.
3. **Step 3 -- Nondeductible expenses:** Nondeductible expenses and oil/gas depletion reduce stock basis (not below zero).
4. **Step 4 -- Losses:** Ordinary losses + separately stated losses + prior suspended losses reduce stock basis first (to zero), then debt basis (to zero). Any remaining losses are suspended for carry-forward.

### Data Structures

- **BasisAdjustmentInputs** (frozen dataclass): All 9 adjustment fields with Decimal defaults of zero. Immutable after construction.
- **BasisResult** (dataclass): 9 computed fields covering beginning/ending stock and debt basis, taxable/nontaxable distributions, allowed/suspended losses.

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Frozen dataclass for inputs | Prevents accidental mutation during multi-step calculation |
| Regular dataclass for result | Computed output, no need for immutability enforcement |
| ValueError on negative beginning basis | Fail fast on upstream data errors |
| All Decimal arithmetic | No floating point precision issues with monetary values |

## TDD Execution

### RED Phase (commit b3a305c)
- 47 failing tests covering all IRS ordering permutations
- 745 lines of test code across 10 test classes

### GREEN Phase (commit af29b26)
- 193-line implementation making all 47 tests pass
- Zero deviations -- plan executed exactly as specified

## Test Coverage

| Test Class | Count | Covers |
|-----------|-------|--------|
| TestBasisAdjustmentInputsImmutability | 2 | Frozen dataclass, default values |
| TestIncomeIncreasesBasis | 5 | All income types, summing |
| TestDistributions | 5 | Within/exceeding basis, zero basis, ordering |
| TestNondeductibleExpenses | 5 | Reduce basis, not below zero, ordering |
| TestLosses | 8 | Stock/debt absorption, suspension, carry-forward |
| TestMultiYear | 3 | Year-to-year continuity, debt restoration |
| TestEdgeCases | 6 | Zeros, large numbers, negative guards |
| TestOrderingRuleCompliance | 4 | Proving correct vs incorrect ordering |
| TestBasisResultFields | 2 | Field presence, Decimal types |
| TestAdditionalEdgeCases | 7 | Distributions vs debt, cents precision |
| **Total** | **47** | |

## Deviations from Plan

None -- plan executed exactly as written.

## Verification

```
uv run pytest tests/agents/business_tax/test_basis.py -v --tb=short
47 passed in 0.02s
```

## Files

| File | Lines | Purpose |
|------|-------|---------|
| src/agents/business_tax/basis.py | 193 | BasisAdjustmentInputs, BasisResult, calculate_shareholder_basis |
| tests/agents/business_tax/test_basis.py | 745 | 47 comprehensive tests |
| src/agents/business_tax/__init__.py | 50 | Updated exports |

## Next Phase Readiness

The basis tracker is ready for consumption by:
- **06-04 (K-1 Generation):** Will call `calculate_shareholder_basis()` per shareholder to compute K-1 basis disclosures
- **06-05 (Business Tax Agent):** Will integrate basis tracking into the full 1120-S workflow
