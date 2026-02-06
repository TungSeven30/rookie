---
phase: 6
plan: 5
subsystem: business-tax-handoff
tags: [k1, allocation, pro-rata, handoff, serialization, pydantic]
dependency-graph:
  requires: [06-01, 06-03]
  provides: [k1-allocation, k1-handoff-protocol, k1-serialization]
  affects: [06-06, 06-07, personal-tax-agent-k1-intake]
tech-stack:
  added: []
  patterns: [residual-rounding, field-name-mapping, orjson-roundtrip]
key-files:
  created:
    - src/agents/business_tax/handoff.py
    - tests/agents/business_tax/test_handoff.py
  modified:
    - src/agents/business_tax/__init__.py
decisions:
  - Last-shareholder-residual rounding eliminates all cent discrepancies
  - ScheduleK->FormK1 field name mapping as dict constant (15 fields)
  - current_year_increase from positive income allocations, current_year_decrease from losses + distributions
metrics:
  duration: 3 min
  completed: 2026-02-06
  tests: 34
  lines-impl: 245
  lines-test: 499
---

# Phase 6 Plan 5: K-1 Allocation and Handoff Protocol Summary

Pro-rata K-1 allocation with residual rounding and orjson serialization handoff for inter-agent communication.

## What Was Built

### allocate_k1_item
- Allocates a single Schedule K line item to shareholders by ownership_pct
- All shareholders except last get `(total * pct / 100).quantize(Decimal("0.01"))`
- Last shareholder gets `total - sum(others)` -- eliminates all rounding discrepancies
- Validates ownership percentages sum to exactly 100

### allocate_k1s
- Iterates all 15 mapped Schedule K fields, allocates each via allocate_k1_item
- Returns list of dicts (one per shareholder) mapping FormK1 field names to amounts
- Handles field name mapping: `dividends` -> `dividend_income`, `ordinary_income` -> `ordinary_business_income`, etc.

### generate_k1_for_handoff
- Creates validated FormK1 Pydantic model from entity info + shareholder + allocated amounts
- Sets entity_type = "s_corp", confidence = HIGH (generated, not extracted)
- With BasisResult: populates capital_account_beginning/ending, current_year_increase/decrease
- Without BasisResult: leaves capital account fields as None

### serialize_k1_artifact / deserialize_k1_artifact
- orjson-based JSON serialization via model_dump(mode="json")
- Decimal precision preserved through roundtrip
- Full Pydantic validation on deserialization

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| Last-shareholder-residual rounding | Standard accounting practice; guarantees allocations sum exactly to K totals |
| 15-field ScheduleK-to-FormK1 mapping dict | Single source of truth for field name translation |
| current_year_increase = sum of positive income allocations | BasisResult lacks intermediate step values; heuristic matches allocated income |
| current_year_decrease = abs(losses) + deductions + distributions | Covers all basis-reducing items from the allocated amounts |

## Test Coverage

34 tests across 5 test classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| TestAllocateK1Item | 11 | 50/50, 75/25, thirds, rounding, zeros, negatives, validation |
| TestAllocateK1s | 7 | Multi-field allocation, field name mapping, zero schedule K |
| TestGenerateK1ForHandoff | 8 | FormK1 creation, entity type, confidence, EIN validation, basis result |
| TestSerialization | 5 | Roundtrip, Decimal precision, all fields, validation errors |
| TestReconciliation | 3 | 2-shareholder, 3-shareholder unequal, end-to-end roundtrip |

## Deviations from Plan

None -- plan executed exactly as written.

## Next Phase Readiness

K-1 handoff protocol is ready to:
- Be consumed by the 1120-S calculation engine (06-06) to generate K-1s after Schedule K computation
- Feed FormK1 models to the Personal Tax Agent via serialized JSON artifacts
- Support basis tracking integration when BasisResult is available from 06-03
