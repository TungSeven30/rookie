---
phase: 6
plan: 2
subsystem: business-tax
tags: [trial-balance, excel-parsing, gl-mapping, 1120-s, confidence-scoring]
dependency-graph:
  requires: [06-01]
  provides: [trial-balance-parsing, gl-to-1120s-mapping, amount-aggregation]
  affects: [06-04, 06-05, 06-06]
tech-stack:
  added: []
  patterns: [tdd-red-green, regex-pattern-matching, confidence-tiering, dataclass-mapping]
key-files:
  created:
    - src/agents/business_tax/trial_balance.py
  modified:
    - src/agents/business_tax/__init__.py
    - tests/agents/business_tax/test_trial_balance.py
decisions:
  - id: BTAX-02-01
    description: "3-tier confidence scoring: HIGH for pattern match, MEDIUM for type-hinted names, LOW for completely ambiguous"
  - id: BTAX-02-02
    description: "Name-based type hint check distinguishes MEDIUM from LOW (account names containing type keywords like 'expense' get MEDIUM)"
  - id: BTAX-02-03
    description: "Pure regex heuristic mapping with no LLM calls in v1"
  - id: BTAX-02-04
    description: "Credit-positive lines (revenue) negate net_balance for positive income; debit-positive lines preserve sign"
metrics:
  duration: "5 min"
  completed: "2026-02-06"
  tests: 44
  lines-impl: 530
  lines-test: 737
---

# Phase 6 Plan 2: Trial Balance Parsing and GL-to-1120S Mapping Summary

Pure heuristic Excel trial balance parser with 23-pattern GL-to-1120S regex mapping and 3-tier confidence scoring (HIGH/MEDIUM/LOW).

## What Was Built

### parse_excel_trial_balance(file_bytes) -> TrialBalance
- Reads Excel bytes via openpyxl with automatic column layout detection
- Supports 2-column (debit/credit) and single net balance column formats
- Auto-detects entity name and period from metadata rows above the header
- Handles QuickBooks exports: strips whitespace, converts string amounts, skips header/total rows
- Separate account number column detection

### GLMapping (frozen dataclass)
- account_name, form_line, confidence (ConfidenceLevel), reasoning
- Immutable record of each mapping decision for audit trail

### DEFAULT_GL_MAPPING (23 patterns)
- Revenue/Sales -> page1_line1a, COGS -> page1_line2
- Officer Comp -> page1_line7, Salaries -> page1_line8
- Repairs, Bad Debts, Taxes/Licenses, Rent, Interest, Depreciation, Advertising, Pension, Employee Benefits
- Schedule L: Cash, AR, Inventory, Fixed Assets, Accum Depreciation, AP, Shareholder Loans, Capital Stock, Retained Earnings

### map_gl_to_1120s(trial_balance) -> list[GLMapping]
- First pass: case-insensitive regex against DEFAULT_GL_MAPPING -> HIGH confidence
- Second pass: type-based fallback with name hint check -> MEDIUM (name has type keywords) or LOW (completely ambiguous)
- One mapping per entry, preserves entry order

### aggregate_mapped_amounts(trial_balance, mappings) -> dict[str, Decimal]
- Groups by form_line, sums amounts with correct sign handling
- Revenue credit balances become positive income
- Expense/asset debit balances stay positive

## Test Coverage

44 tests across 5 test classes:
- TestParseExcelTrialBalance (11): 2-column, single-column, metadata, whitespace, string amounts, totals, empty, balanced
- TestGLMapping (5): dataclass fields, DEFAULT_GL_MAPPING coverage
- TestMapGlTo1120s (18): specific account mappings, confidence levels, case insensitivity
- TestAggregateMappedAmounts (6): sign handling, multi-account summation, edge cases
- TestEndToEnd (4): full parse -> map -> aggregate pipeline

## Decisions Made

1. **3-tier confidence scoring** (BTAX-02-01): HIGH = regex pattern match, MEDIUM = no pattern but name contains type keywords (e.g., "Miscellaneous Expense"), LOW = completely ambiguous name with no recognizable keywords
2. **Name-based type hint check** (BTAX-02-02): Differentiates MEDIUM from LOW by checking if account name contains words like expense/income/receivable/payable/cost/salary/rent/tax/insurance/utility
3. **Pure heuristic v1** (BTAX-02-03): No LLM calls for mapping. Confidence scoring flags ambiguous accounts for CPA review
4. **Sign convention** (BTAX-02-04): Credit-positive lines (revenue) negate net_balance; debit-positive lines (expenses) preserve net_balance as-is

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test fixture count mismatch**
- **Found during:** GREEN phase
- **Issue:** Test expected 16 entries but fixture only had 15 data rows
- **Fix:** Corrected assertion from 16 to 15
- **Files modified:** tests/agents/business_tax/test_trial_balance.py

No other deviations. Plan executed as written.

## Commits

| Hash | Message |
|------|---------|
| 8becc2a | test(06-02): add failing tests for trial balance parsing and GL mapping |
| ffd10c2 | feat(06-02): implement trial balance parsing and GL-to-1120S mapping |

## Next Phase Readiness

No blockers. The trial balance parser and GL mapping are ready for:
- 06-04: 1120-S calculation engine (consumes aggregate_mapped_amounts output)
- 06-05: K-1 generation (uses mapped amounts for shareholder allocation)
- 06-06: Agent integration (parse -> map -> calculate pipeline)
