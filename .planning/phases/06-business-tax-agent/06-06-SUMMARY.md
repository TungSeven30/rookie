# Phase 6 Plan 6: Output Generators Summary

**One-liner:** Drake 1120-S worksheet, per-shareholder K-1 and basis worksheets (Form 7203), and Markdown preparer notes with compensation/balance checks

## What Was Built

Four CPA-facing output generators for the Business Tax Agent:

1. **generate_1120s_drake_worksheet** -- Excel workbook with 5-7 sheets (Summary, Page 1 Income, Page 1 Deductions, Schedule K, Schedule L, optional M-1/M-2) for manual entry into Drake Tax Software
2. **generate_k1_worksheets** -- Excel workbook with one sheet per shareholder containing entity info, allocated K-1 boxes matching IRS layout, and income/deduction/distribution summary
3. **generate_basis_worksheets** -- Excel workbook with one sheet per shareholder following Form 7203 structure (Section A: Stock Basis, Section B: Debt Basis, Summary with suspended losses/taxable distributions)
4. **generate_business_preparer_notes** -- Markdown with 8 sections: entity summary, income summary, shareholder summary table, flags/escalations, Schedule L balance check, reasonable compensation check, review focus areas, v1 assumptions

## Key Files

### Created
- `src/agents/business_tax/output.py` (567 lines) -- All four output generators with shared helpers
- `tests/agents/business_tax/test_output.py` (529 lines) -- 38 tests across 4 test classes

### Modified
- `src/agents/business_tax/__init__.py` -- Added output generator exports

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Optional schedule_m1/schedule_m2 params on Drake generator | Form1120SResult lacks these fields; simplest approach without model changes |
| Shared _write_header_row/_write_line_item helpers | DRY pattern for consistent Excel formatting across all sheets |
| Compensation/distribution ratio < 0.5 triggers warning | Common IRS audit trigger; conservative threshold for CPA attention |
| K-1 box descriptions hardcoded (not derived from model) | IRS form layout is stable; descriptions need "Box N:" prefix for CPA readability |
| _truncate_sheet_name for 31-char Excel limit | Excel hard limit; prefix + name pattern matches personal_tax output approach |

## Test Results

- **38 tests passing** (target: 20+)
  - 13 Drake worksheet tests (sheets, content, formatting, M-1/M-2)
  - 6 K-1 worksheet tests (per-shareholder, TIN, allocations, truncation)
  - 6 basis worksheet tests (Form 7203 sections, stock/debt, suspended losses)
  - 13 preparer notes tests (all 8 sections, compensation warning, suspended losses)

## Deviations from Plan

None -- plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 5570bff | feat(business-tax): add 1120-S output generators for Drake worksheet, K-1, basis, and preparer notes |
| ef747e2 | test(business-tax): add output generators test suite with 38 tests |

## Duration

~5 minutes

## Next Phase Readiness

Phase 6 Plan 07 (Agent Integration) can proceed. All output generators are exported from `src.agents.business_tax` and ready for orchestration by the agent class.
