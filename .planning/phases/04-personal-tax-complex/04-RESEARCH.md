# Phase 4 Research: Personal Tax Agent - Complex Returns

**Created:** 2026-01-25
**Phase:** 4 of 8
**Goal:** Handle Schedule C, E, D, Form 8962, and common complexities

## Requirements Analysis

### DOC-05: K-1 Extraction (>90% accuracy)

**Schedule K-1 Overview:**
- Form 1065 K-1: Partnership income
- Form 1120-S K-1: S-Corporation income
- Form 1041 K-1: Estate/Trust income (deferred to v2)

**Key K-1 Fields:**
- Part I: Entity information (name, EIN, entity type)
- Part II: Partner/Shareholder information (name, TIN, ownership %)
- Part III: Partner/Shareholder share of income, deductions, credits
  - Box 1: Ordinary business income/loss
  - Box 2: Net rental real estate income/loss
  - Box 3: Other net rental income/loss
  - Box 4: Guaranteed payments (partnerships)
  - Box 5: Interest income
  - Box 6: Dividends
  - Box 7: Royalties
  - Box 8-9: Capital gains/losses
  - Box 10: Net section 1231 gain/loss
  - Box 11: Other income/loss
  - Box 12: Section 179 deduction
  - Box 13: Other deductions
  - Box 14: Self-employment earnings
  - Box 15: Credits
  - Box 16: Foreign transactions
  - Box 17: Alternative minimum tax items
  - Box 18: Tax-exempt income
  - Box 19: Distributions
  - Box 20: Other information

**Extraction Challenges:**
- Multiple box types with codes (e.g., Box 13 Code A, B, C...)
- Variable layouts between 1065 and 1120-S versions
- Footnotes and supplemental statements

### PTAX-07: Schedule C (Self-Employment)

**Schedule C Structure:**
- Part I: Income (Line 1-7)
  - Gross receipts
  - Returns and allowances
  - Cost of goods sold
  - Gross profit
  - Other income
- Part II: Expenses (Lines 8-27)
  - Advertising
  - Car and truck expenses
  - Commissions and fees
  - Contract labor
  - Depletion
  - Depreciation
  - Employee benefit programs
  - Insurance
  - Interest (mortgage, other)
  - Legal and professional services
  - Office expense
  - Pension and profit-sharing
  - Rent/lease (vehicles, machinery, other)
  - Repairs and maintenance
  - Supplies
  - Taxes and licenses
  - Travel
  - Deductible meals
  - Utilities
  - Wages
  - Other expenses
- Part III: Cost of Goods Sold
- Part IV: Information on Vehicle
- Part V: Other Expenses

**Schedule SE (Self-Employment Tax):**
- 15.3% on net self-employment earnings
- 12.4% Social Security (up to wage base: $168,600 for 2024)
- 2.9% Medicare (no limit)
- Additional 0.9% Medicare on earnings over $200k single / $250k MFJ
- Deductible: 50% of SE tax as above-the-line deduction

### PTAX-08: Schedule E (Rental Income)

**Schedule E Structure:**
- Part I: Income or Loss from Rental Real Estate
  - Property address
  - Type of property
  - Fair rental days
  - Personal use days
  - Rental income
  - Expenses:
    - Advertising
    - Auto and travel
    - Cleaning and maintenance
    - Commissions
    - Insurance
    - Legal and professional
    - Management fees
    - Mortgage interest
    - Other interest
    - Repairs
    - Supplies
    - Taxes
    - Utilities
    - Depreciation
    - Other
  - Total expenses
  - Net income/loss per property

**Passive Activity Rules:**
- Rental activities generally passive
- $25,000 loss allowance for active participation
- Phaseout: $100k-$150k MAGI
- Real estate professional exception

### PTAX-09: Schedule D (Capital Gains)

**Schedule D Structure:**
- Part I: Short-Term Capital Gains/Losses (held ≤1 year)
- Part II: Long-Term Capital Gains/Losses (held >1 year)
- Part III: Summary

**Form 1099-B Fields:**
- Description of property
- Date acquired
- Date sold
- Proceeds (sales price)
- Cost or other basis
- Gain or loss
- Wash sale loss disallowed
- Type of gain: collectibles, Section 1202

**Capital Gains Tax Rates (2024):**
| Filing Status | 0% Rate | 15% Rate | 20% Rate |
|---------------|---------|----------|----------|
| Single | $0-$47,025 | $47,026-$518,900 | >$518,900 |
| MFJ | $0-$94,050 | $94,051-$583,750 | >$583,750 |
| MFS | $0-$47,025 | $47,026-$291,850 | >$291,850 |
| HOH | $0-$63,000 | $63,001-$551,350 | >$551,350 |

**Special Rules:**
- Net capital loss limit: $3,000/year ($1,500 MFS)
- Carryforward of unused losses
- Netting: short-term vs long-term

### PTAX-10: QBI Deduction (Section 199A)

**QBI Deduction Overview:**
- 20% deduction on qualified business income
- Applies to: sole proprietors, partnerships, S-corps, some rentals
- Does NOT apply to: C-corps, wages, guaranteed payments

**Calculation:**
1. Determine QBI from each qualified trade/business
2. Calculate 20% of QBI
3. Apply limitations if above threshold

**Thresholds (2024):**
| Filing Status | Threshold | Phaseout Range |
|---------------|-----------|----------------|
| Single/HOH | $191,950 | $50,000 |
| MFJ | $383,900 | $100,000 |
| MFS | $191,950 | $50,000 |

**Limitations (above threshold):**
- 50% of W-2 wages, OR
- 25% of W-2 wages + 2.5% of unadjusted basis of qualified property

**SSTB (Specified Service Trade or Business):**
- Health, law, accounting, actuarial, performing arts, consulting, athletics, financial services, brokerage
- No QBI deduction above phaseout for SSTB

**Final Limitation:**
- QBI deduction cannot exceed 20% of (taxable income - net capital gains)

### PTAX-11: Form 8962 (ACA Reconciliation)

**Form 1095-A Fields:**
- Covered individuals
- Monthly enrollment premiums
- Monthly SLCSP premium
- Monthly advance payments

**Premium Tax Credit Calculation:**
1. Determine household income as % of FPL
2. Determine applicable percentage (contribution %)
3. Calculate annual contribution (income × applicable %)
4. Calculate annual credit = SLCSP premium - contribution
5. Compare to advance payments received
6. Reconcile: additional credit or repayment

**Federal Poverty Level (2024):**
- 1 person: $14,580
- 2 persons: $19,720
- 3 persons: $24,860
- 4 persons: $30,000
- Each additional: +$5,140

**Applicable Percentage (2024 ARP extended):**
| FPL % | Contribution % |
|-------|----------------|
| <150% | 0% |
| 150-200% | 0-2% |
| 200-250% | 2-4% |
| 250-300% | 4-6% |
| 300-400% | 6-8.5% |
| >400% | 8.5% |

**Repayment Limits:**
| FPL % | Single | Family |
|-------|--------|--------|
| <200% | $375 | $750 |
| 200-300% | $975 | $1,950 |
| 300-400% | $1,625 | $3,250 |
| >400% | No limit | No limit |

## Existing Code Analysis

### Document Models (src/documents/models.py)
- Pattern: Pydantic BaseModel with Decimal fields
- TIN validation helpers available
- ConfidenceLevel enum for extraction quality
- CRITICAL_FIELDS dict for confidence scoring

### Extractors (src/documents/extractor.py)
- Pattern: `extract_<form_type>()` function per document
- Uses `_extract_with_vision()` helper
- Mock functions for testing: `_mock_<form_type>()`
- Router dict in `extract_document()`

### Calculator (src/agents/personal_tax/calculator.py)
- IncomeSummary: needs extension for business/rental/capital gains
- TaxSituation: needs QBI fields
- Credits implemented: CTC, AOC, Saver's, EITC
- Pure functions, easy to extend

### Output (src/agents/personal_tax/output.py)
- generate_drake_worksheet(): needs Schedule C/E/D sheets
- generate_preparer_notes(): needs business/rental sections

## Implementation Strategy

### Wave 1: Document Foundation (04-01, 04-02)
Build K-1 and 1099-B models and extractors first. These are the input documents for Schedule C/E/D.

### Wave 2: Schedule C + SE Tax (04-03)
Self-employment is the most common complex scenario. Build this first.

### Wave 3: Schedule E and D (04-04, 04-05)
Rental and capital gains can be done in parallel - no dependencies between them.

### Wave 4: QBI and PTC (04-06, 04-07)
QBI depends on Schedule C/E being complete. PTC is independent but medium priority.

### Wave 5: Integration (04-08)
Update PersonalTaxAgent to orchestrate complex returns with all new schedules.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| K-1 extraction accuracy | Start with clean scanned documents, escalate handwritten |
| QBI complexity | Simplified SSTB handling (defer complex cases) |
| Passive loss rules | Basic $25k allowance only, escalate complex cases |
| Capital gains netting | Focus on simple cases first |
| ACA reconciliation | Handle common scenarios, escalate complex |

## Dependencies

- Phase 3 complete: PersonalTaxAgent, document extraction, tax calculator
- No new Python packages required
- Uses existing anthropic, instructor, openpyxl, fsspec

---

*Research completed: 2026-01-25*
