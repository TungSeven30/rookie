---
phase: 6
plan: 4
subsystem: business-tax-calculator
tags: [1120-s, page1, schedule-k, schedule-l, m1, m2, aaa, decimal, tdd]
dependency-graph:
  requires: [06-01, 06-02]
  provides: [1120s-calculator, page1-computation, schedule-k, schedule-l, m1-reconciliation, m2-aaa]
  affects: [06-05, 06-06, 06-07]
tech-stack:
  added: []
  patterns: [pure-function-calculator, dataclass-result, dict-keyed-input]
key-files:
  created:
    - src/agents/business_tax/calculator.py
  modified:
    - src/agents/business_tax/__init__.py
    - tests/agents/business_tax/test_calculator.py
    - tests/agents/business_tax/test_schedule_l.py
decisions:
  - "Retained earnings always computed (beginning + net_income - distributions), never read from mapped_amounts"
  - "M-1 Line 5 holds tax-exempt income (IRS semantics: income on books not on return), subtraction side"
  - "M-2 separates income from losses into distinct buckets for clarity"
  - "Unknown separately_stated keys silently ignored in compute_schedule_k"
metrics:
  duration: "6 min"
  completed: "2026-02-06"
  tests: 41
  lines-of-code: 537
---

# Phase 6 Plan 4: 1120-S Calculator Summary

**One-liner:** Pure Decimal computation for 1120-S Page 1 income/deductions, Schedule K pro-rata items, Schedule L balance sheet, M-1 book-tax reconciliation, and M-2 AAA tracking.

## What Was Built

Five pure computation functions that transform mapped trial balance data into complete Form 1120-S schedules:

### compute_page1(mapped_amounts) -> Page1Result
Reads `page1_lineN` keys from the dict output of `aggregate_mapped_amounts`. Computes:
- Gross profit = receipts - returns - COGS
- Total income = gross profit + Form 4797 gain + other income
- Total deductions = sum of Lines 7-20
- Ordinary business income = total income - total deductions

### compute_schedule_k(page1, separately_stated) -> ScheduleK
- Box 1 = `page1.ordinary_business_income` (linkage verified by test)
- Boxes 2-17 from `separately_stated` dict (unknown keys ignored)
- All boxes default to `Decimal("0")`

### compute_schedule_l(mapped_amounts, prior_year, net_income, distributions) -> ScheduleL
- Beginning amounts from prior year ending (or zeros for first year)
- Ending amounts from mapped trial balance
- Retained earnings computed: `beginning + net_income - distributions`
- Does NOT raise on imbalance -- caller checks `is_balanced_ending`

### compute_schedule_m1(book_income, tax_income, tax_exempt, nondeductible) -> ScheduleM1Result
- IRS Line 5 semantics: tax-exempt income goes on subtraction side
- Residual differences allocated to Line 3 or Line 5 as appropriate
- `income_per_return` always reconciles to `tax_income`

### compute_schedule_m2(aaa_beginning, ordinary_income, separately_stated_net, nondeductible, distributions) -> ScheduleM2Result
- AAA can go negative from losses (not from distributions per IRC 1368)
- Income and losses separated into distinct buckets
- Nondeductible expenses reduce AAA

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Retained earnings always computed, never from mapped_amounts | RE is a derived quantity; prevents stale/inconsistent data |
| M-1 Line 5 = tax-exempt income (subtraction side) | Matches IRS Schedule M-1 semantics: income on books not included on Sch K |
| Income/loss separation in M-2 | Clearer AAA tracking; losses can go negative but distributions cannot |
| Unknown separately_stated keys ignored | Resilient to upstream changes; no need to fail on extra data |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed Schedule L balanced_ending test**
- **Found during:** GREEN phase
- **Issue:** Test passed `schedule_l_line24` as mapped amount for retained earnings, but `compute_schedule_l` always computes RE from beginning + net_income - distributions. With net_income=0, RE ended up as 0 instead of 50000.
- **Fix:** Changed test to pass `current_year_net_income=50000` so RE computes to the correct balance.
- **Commit:** e7a7b1f

**2. [Rule 1 - Bug] Fixed M-1 tax-exempt income placement**
- **Found during:** GREEN phase
- **Issue:** Initial implementation placed tax-exempt income on the addition side (Line 2), but IRS M-1 Line 5 requires it on the subtraction side (income on books NOT on return).
- **Fix:** Rewrote reconciliation logic to place tax-exempt income in `income_on_return_not_on_books` (subtraction), matching IRS semantics. Updated test assertion accordingly.
- **Commit:** e7a7b1f

**3. [Rule 1 - Bug] Fixed M-2 test field name mismatch**
- **Found during:** GREEN phase
- **Issue:** Test accessed `result.nondeductible_expenses` but the ScheduleM2Result field is named `other_reductions`.
- **Fix:** Changed test to use `result.other_reductions`.
- **Commit:** e7a7b1f

## Test Results

```
41 passed in 0.04s
```

### Test Coverage by Function

| Function | Tests | Key Scenarios |
|----------|-------|---------------|
| compute_page1 | 16 | Basic computation, zero/empty, missing defaults, startup loss |
| compute_schedule_k | 8 | Box 1 linkage, separately stated, defaults, unknown keys |
| compute_schedule_l | 6 | Balanced, RE update, prior year, first year, imbalance, depreciation |
| compute_schedule_m1 | 5 | Book=tax, tax-exempt, nondeductible, combined, line totals |
| compute_schedule_m2 | 6 | Income increase, distributions, negative losses, first year, fields |

## Artifacts

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/business_tax/calculator.py` | 537 | 5 pure computation functions + 3 dataclasses |
| `tests/agents/business_tax/test_calculator.py` | 286 | Page 1 + Schedule K tests |
| `tests/agents/business_tax/test_schedule_l.py` | 359 | Schedule L + M-1 + M-2 tests |

## Next Phase Readiness

Calculator is ready for agent integration (06-06/06-07). The data flow is:
1. `parse_excel_trial_balance` -> TrialBalance
2. `map_gl_to_1120s` -> GLMapping list
3. `aggregate_mapped_amounts` -> dict[str, Decimal]
4. `compute_page1` -> Page1Result
5. `compute_schedule_k` -> ScheduleK
6. `compute_schedule_l` -> ScheduleL
7. `compute_schedule_m1` -> ScheduleM1Result
8. `compute_schedule_m2` -> ScheduleM2Result

No blockers. No new dependencies added.
