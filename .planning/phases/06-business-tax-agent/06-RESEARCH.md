# Phase 6: Business Tax Agent - Research

**Researched:** 2026-02-06
**Domain:** IRS Form 1120-S (S-Corporation), K-1 generation, shareholder basis, trial balance extraction
**Confidence:** MEDIUM (domain knowledge is strong via IRS sources; architecture patterns are HIGH from existing codebase; trial balance extraction specifics are LOW due to variability in source document formats)

## Summary

Phase 6 introduces a Business Tax Agent that processes S-Corporation (Form 1120-S) returns, generates Schedule K-1 worksheets for shareholders, tracks shareholder basis, extracts trial balances from source documents, and reconciles Schedule L (balance sheet) to the trial balance. The generated K-1 data must flow back to the existing Personal Tax Agent for individual return preparation.

The core challenge is that this phase shifts from *consuming* tax data (as the Personal Tax Agent does with K-1 extraction) to *producing* tax data: transforming a trial balance + entity information into a complete 1120-S return with generated K-1s. This is a fundamentally different workflow. The Personal Tax Agent reads finished documents and extracts numbers; the Business Tax Agent reads raw accounting data and computes the return.

**Primary recommendation:** Mirror the Personal Tax Agent's architecture (agent class, calculator module, output generators) but with a distinct `BusinessTaxAgent` in `src/agents/business_tax/`. Reuse the existing document extraction infrastructure for trial balance and source documents. The K-1 handoff should serialize generated K-1s as `FormK1` Pydantic models (already defined in `src/documents/models.py`), persisted as task artifacts for the Personal Tax Agent to consume.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.x (already in project) | Data models for 1120-S, K-1, shareholder basis, trial balance | Validation, serialization, existing pattern |
| openpyxl | 3.x (already in project) | Drake worksheet generation for 1120-S and K-1 outputs | Already used by Personal Tax Agent output.py |
| Decimal (stdlib) | N/A | All monetary calculations | Existing project convention, eliminates float precision issues |
| instructor | (already in project) | Structured extraction from Claude for trial balance parsing | Already used by document extractor |
| anthropic | (already in project) | Claude Vision API for trial balance document extraction | Already used throughout |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| orjson | (already in project) | K-1 handoff serialization | Serializing FormK1 models for inter-agent data flow |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| openpyxl for Drake worksheets | Direct Drake XML | Not viable - reverse-engineering GruntWorx schema explicitly out of scope per REQUIREMENTS.md |
| Claude Vision for trial balance | QuickBooks API direct import | Phase 7 (Bookkeeping) handles QBO integration; Phase 6 should handle document-based trial balance as primary input |
| Custom basis tracker | Third-party tax calculation library | No Python library exists for S-Corp basis tracking; must be hand-built with careful IRS rule implementation |

**Installation:** No new dependencies needed. All libraries already in the project.

## Architecture Patterns

### Recommended Project Structure

```
src/
  agents/
    business_tax/
      __init__.py         # Public API exports
      agent.py            # BusinessTaxAgent orchestrator (mirrors personal_tax/agent.py)
      calculator.py       # 1120-S computations: income/deductions aggregation, K-1 allocation, basis tracking
      basis.py            # Shareholder basis tracker (stock + debt basis per shareholder per year)
      trial_balance.py    # Trial balance model + GL-to-1120S line mapping
      output.py           # Drake worksheet generators (1120-S worksheet, K-1 worksheets, basis worksheets)
      models.py           # Business tax specific Pydantic models (Form1120S, ScheduleK, ScheduleL, ShareholderBasis, TrialBalance)
      handoff.py          # K-1 handoff protocol: serialize generated K-1s for Personal Tax Agent
tests/
  agents/
    business_tax/
      __init__.py
      test_agent.py       # Agent orchestration tests
      test_calculator.py  # 1120-S calculation tests
      test_basis.py       # Basis tracking tests (critical - most common error source)
      test_trial_balance.py  # Trial balance extraction + mapping tests
      test_output.py      # Drake worksheet output tests
      test_handoff.py     # K-1 handoff protocol tests
      test_schedule_l.py  # Balance sheet reconciliation tests
```

### Pattern 1: Agent Orchestrator (from Personal Tax Agent)

**What:** Single entry-point agent class with a `process()` method that coordinates the full workflow.
**When to use:** Always. This is the established pattern.
**How it works in existing code:**

The `PersonalTaxAgent.process()` method follows this flow:
1. Load context (client profile, prior year)
2. Scan for documents
3. Classify and extract each document
4. Check for missing/conflicting data
5. Calculate (aggregate income, deductions, tax)
6. Compare prior year
7. Generate outputs (Drake worksheet, preparer notes)
8. Handle escalations

The `BusinessTaxAgent.process()` should follow an analogous flow:
1. Load context (entity profile, prior year return, shareholder info)
2. Extract trial balance from source document(s)
3. Map trial balance GL accounts to 1120-S line items
4. Compute 1120-S pages 1-5 (income, deductions, tax)
5. Compute Schedule K (shareholder pro-rata items)
6. Allocate Schedule K items to individual K-1s per shareholder
7. Track shareholder basis (stock + debt) for each shareholder
8. Compute Schedule L (balance sheet) and verify reconciliation to trial balance
9. Compute Schedule M-1 (book vs tax reconciliation) and M-2 (AAA analysis)
10. Generate outputs (1120-S Drake worksheet, K-1 worksheets, basis worksheets, preparer notes)
11. Execute K-1 handoff (persist FormK1 models as task artifacts)
12. Handle escalations

### Pattern 2: Pure Calculator Functions (from calculator.py)

**What:** Tax computation as pure functions with typed inputs/outputs. No side effects, no LLM calls.
**When to use:** All tax math, allocation logic, basis calculations.
**Why:** Testable, deterministic, auditable. Existing pattern in `src/agents/personal_tax/calculator.py`.

### Pattern 3: Task Dispatcher Integration

**What:** Register `business_tax_handler` with the `TaskDispatcher` for routing.
**When to use:** At application startup.
**Existing pattern:** `personal_tax_handler` is registered in `src/agents/personal_tax/agent.py`.

### Pattern 4: K-1 Handoff via FormK1 Model

**What:** Generated K-1 data serialized as `FormK1` Pydantic models and stored as task artifacts.
**When to use:** After K-1 generation is complete.
**Why:** The `FormK1` model already exists in `src/documents/models.py` with all the fields needed. The Personal Tax Agent already consumes K-1 data through this model. The handoff simply writes the generated K-1 as a `FormK1` instance.

### Anti-Patterns to Avoid

- **Shared mutable state for basis tracking:** Basis calculations must be pure functions. Do not store running basis in a class attribute that mutates across calls. Instead, compute basis as a transformation: `(prior_basis, k1_items, distributions) -> new_basis`.
- **Hardcoded GL-to-1120S mapping:** Trial balance account names vary wildly between clients. The mapping must be flexible (configurable or LLM-assisted), not a fixed dictionary.
- **Monolithic calculator:** The 1120-S calculation is complex enough to warrant splitting into sub-modules (basis.py, trial_balance.py) rather than a single massive calculator.py.
- **Treating K-1 generation as output-only:** K-1 data must be structured data (FormK1 model) for handoff, not just a formatted Excel sheet.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tax form field validation | Custom SSN/EIN validators | `validate_ssn()`, `validate_ein()`, `validate_tin()` from `src/documents/models.py` | Already battle-tested with masked SSN support |
| Document extraction | Custom parsing | `extract_document()` via Claude Vision + Instructor (existing `src/documents/extractor.py`) | Proven pattern across 13+ document types |
| Document classification | Manual file type detection | `classify_document()` from `src/documents/classifier.py` | Already handles all supported types |
| Excel generation | Raw openpyxl cell-by-cell | Adapt helper functions from `src/agents/personal_tax/output.py` (`_create_currency_style`, `_create_header_style`, `_auto_fit_columns`) | Consistent formatting, less boilerplate |
| Task state management | Manual status tracking | `TaskStateMachine` from `src/orchestration/state_machine.py` | Already handles all transitions including escalation |
| Confidence scoring | Ad-hoc confidence logic | `ConfidenceLevel` enum from `src/documents/models.py` | Consistent HIGH/MEDIUM/LOW across the system |

**Key insight:** The trial balance GL-to-1120S mapping is the one area where hand-rolling is unavoidable. There is no standard library for this because chart of accounts structures vary enormously. Use Claude (LLM-assisted mapping) with a configurable default mapping as fallback.

## Common Pitfalls

### Pitfall 1: Basis Ordering Rule Violations

**What goes wrong:** Computing shareholder basis in the wrong order causes incorrect loss limitation and distribution taxation.
**Why it happens:** The IRS requires a specific ordering: (1) increase for income, (2) decrease for distributions, (3) decrease for nondeductible expenses, (4) decrease for losses. Developers naturally process items in K-1 box order, which is wrong.
**How to avoid:** Implement basis calculation as a single function that takes all items at once and applies the ordering rule internally. Never allow incremental/piecemeal basis updates.
**Warning signs:** Tests showing distributions taxed as capital gains when they shouldn't be, or losses allowed when basis is insufficient.

### Pitfall 2: Pro-Rata Allocation with Mid-Year Ownership Changes

**What goes wrong:** K-1 allocations are incorrect when shareholders buy/sell shares during the year.
**Why it happens:** S-Corp income must be allocated based on per-share, per-day ownership. A simple percentage-based allocation only works if ownership is constant for the full year.
**How to avoid:** For v1, support only full-year shareholders (no mid-year changes). Add an escalation check: if shareholder ownership changed during the year, escalate to CPA. This matches the 85% accuracy rollback threshold.
**Warning signs:** Shareholder K-1 amounts don't sum to Schedule K totals.

### Pitfall 3: Schedule L Not Balancing

**What goes wrong:** Total assets (Line 15) does not equal total liabilities + equity (Line 27).
**Why it happens:** Common causes: (a) retained earnings not updated for current year income/loss, (b) distributions not reflected in equity section, (c) book-tax differences not reconciled via M-1, (d) shareholder loans misclassified as equity.
**How to avoid:** Build a reconciliation check that runs after Schedule L computation and produces a specific error with the difference amount. Automatically update retained earnings from the M-2 analysis.
**Warning signs:** `assert schedule_l.total_assets == schedule_l.total_liabilities_equity` fails.

### Pitfall 4: Debt Basis vs Stock Basis Confusion

**What goes wrong:** Losses are incorrectly allowed against guarantees instead of direct loans, or debt basis is used before stock basis is exhausted.
**Why it happens:** Only personal loans from shareholder to corporation create debt basis. Loan guarantees do not. Stock basis must be exhausted before debt basis can absorb losses.
**How to avoid:** Track stock basis and debt basis as separate fields. Apply losses to stock basis first, then debt basis only if stock basis is zero. Validate that debt basis entries have source documentation (loan agreements, not guarantees).
**Warning signs:** Shareholder claiming more losses than their stock + debt basis supports.

### Pitfall 5: Trial Balance Account Mapping Ambiguity

**What goes wrong:** GL accounts from the trial balance map to the wrong 1120-S lines, causing income/deduction misclassification.
**Why it happens:** Chart of accounts naming varies wildly between QuickBooks, Xero, and custom accounting systems. "Professional fees" could be legal expenses (deductible) or officer compensation (different line).
**How to avoid:** Use a two-pass approach: (1) automatic mapping using account type + name heuristics, (2) LLM-assisted disambiguation for ambiguous accounts. Always flag low-confidence mappings for CPA review.
**Warning signs:** 1120-S line totals don't match trial balance totals after mapping.

### Pitfall 6: Reasonable Compensation Requirement

**What goes wrong:** S-Corp return shows zero officer compensation but significant distributions.
**Why it happens:** This is an IRS audit trigger -- S-Corp shareholders who perform services must receive "reasonable compensation" (W-2 wages) before taking distributions.
**How to avoid:** Check if trial balance shows officer salary/wages. If officer compensation is zero or very low relative to distributions, add an escalation flag for CPA review. This is not something the agent should fix -- it's an advisory flag.
**Warning signs:** Distributions >> Officer compensation in the return data.

## Code Examples

### Example 1: Shareholder Basis Calculation (Pure Function)

```python
# Source: IRS Publication - S Corporation Stock and Debt Basis rules
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class BasisAdjustmentInputs:
    """All items affecting shareholder basis for the year."""
    # K-1 income items (increase basis)
    ordinary_income: Decimal  # Box 1 (if positive)
    separately_stated_income: Decimal  # Boxes 2-10 positive items
    tax_exempt_income: Decimal  # Box 16A/B
    excess_depletion: Decimal  # Box 15C

    # Distributions (decrease basis, step 2)
    non_dividend_distributions: Decimal  # Box 16D

    # Nondeductible expenses (decrease basis, step 3)
    nondeductible_expenses: Decimal  # Box 16C

    # Loss/deduction items (decrease basis, step 4)
    ordinary_loss: Decimal  # Box 1 (if negative, use absolute value)
    separately_stated_losses: Decimal  # Boxes 2-12 negative items
    oil_gas_depletion: Decimal  # Box 17R


@dataclass
class BasisResult:
    """Result of annual basis calculation."""
    beginning_stock_basis: Decimal
    ending_stock_basis: Decimal
    beginning_debt_basis: Decimal
    ending_debt_basis: Decimal
    suspended_losses: Decimal  # Losses exceeding total basis
    distributions_taxable: Decimal  # Distributions exceeding basis


def calculate_shareholder_basis(
    beginning_stock_basis: Decimal,
    beginning_debt_basis: Decimal,
    adjustments: BasisAdjustmentInputs,
) -> BasisResult:
    """Calculate ending shareholder basis applying IRS ordering rules."""
    # Step 1: Increase stock basis for income items
    stock = beginning_stock_basis
    stock += adjustments.ordinary_income
    stock += adjustments.separately_stated_income
    stock += adjustments.tax_exempt_income
    stock += adjustments.excess_depletion

    # Step 2: Decrease for distributions (not below zero)
    distributions_taxable = Decimal("0")
    if adjustments.non_dividend_distributions > stock:
        distributions_taxable = adjustments.non_dividend_distributions - stock
        stock = Decimal("0")
    else:
        stock -= adjustments.non_dividend_distributions

    # Step 3: Decrease for nondeductible expenses (not below zero)
    stock = max(Decimal("0"), stock - adjustments.nondeductible_expenses)

    # Step 4: Decrease for losses (stock basis first, then debt basis)
    total_losses = (
        adjustments.ordinary_loss
        + adjustments.separately_stated_losses
        + adjustments.oil_gas_depletion
    )
    suspended = Decimal("0")
    debt = beginning_debt_basis

    if total_losses <= stock:
        stock -= total_losses
    else:
        remainder = total_losses - stock
        stock = Decimal("0")
        if remainder <= debt:
            debt -= remainder
        else:
            suspended = remainder - debt
            debt = Decimal("0")

    return BasisResult(
        beginning_stock_basis=beginning_stock_basis,
        ending_stock_basis=stock,
        beginning_debt_basis=beginning_debt_basis,
        ending_debt_basis=debt,
        suspended_losses=suspended,
        distributions_taxable=distributions_taxable,
    )
```

### Example 2: K-1 Pro-Rata Allocation

```python
from decimal import Decimal


def allocate_k1_pro_rata(
    schedule_k_total: Decimal,
    shareholder_ownership_pct: Decimal,
) -> Decimal:
    """Allocate Schedule K item to shareholder by ownership percentage.

    For full-year shareholders with constant ownership, allocation is simple
    pro-rata multiplication.

    Args:
        schedule_k_total: Total amount from Schedule K line item.
        shareholder_ownership_pct: Shareholder's ownership as decimal (e.g., 0.50 for 50%).

    Returns:
        Shareholder's allocated share, rounded to 2 decimal places.
    """
    return (schedule_k_total * shareholder_ownership_pct).quantize(Decimal("0.01"))
```

### Example 3: Schedule L Balance Sheet Reconciliation Check

```python
from decimal import Decimal


def check_schedule_l_balance(
    total_assets: Decimal,
    total_liabilities_equity: Decimal,
) -> tuple[bool, Decimal]:
    """Verify Schedule L balances.

    Returns:
        Tuple of (balances, difference). If balances is False, difference
        shows the imbalance amount for debugging.
    """
    diff = total_assets - total_liabilities_equity
    return diff == Decimal("0"), diff
```

### Example 4: K-1 Handoff to Personal Tax Agent

```python
from src.documents.models import FormK1, ConfidenceLevel


def generate_k1_for_handoff(
    entity_name: str,
    entity_ein: str,
    tax_year: int,
    shareholder_name: str,
    shareholder_tin: str,
    ownership_pct: Decimal,
    schedule_k_items: dict,  # Schedule K line items
) -> FormK1:
    """Generate a FormK1 model from computed K-1 data for Personal Tax Agent.

    The output FormK1 is identical in structure to what the Personal Tax
    Agent extracts from received K-1 documents. This enables seamless handoff.
    """
    return FormK1(
        entity_name=entity_name,
        entity_ein=entity_ein,
        entity_type="s_corp",
        tax_year=tax_year,
        recipient_name=shareholder_name,
        recipient_tin=shareholder_tin,
        ownership_percentage=ownership_pct,
        ordinary_business_income=allocate_k1_pro_rata(
            schedule_k_items.get("ordinary_income", Decimal("0")),
            ownership_pct / Decimal("100"),
        ),
        # ... map all Schedule K items to K-1 boxes ...
        confidence=ConfidenceLevel.HIGH,  # Generated, not extracted
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual K-1 preparation | Tax software (Drake, ProSeries) generates K-1s from 1120-S data entry | Standard practice | This agent automates the data entry step, not the generation logic |
| Paper trial balance | QuickBooks/Xero export to Excel/PDF | Ongoing | Source documents will be Excel or PDF; need both extraction paths |
| Shareholder basis tracked informally | IRS Form 7203 required since 2021 | Tax year 2021 | Basis tracking is now mandatory filing for many shareholders; our worksheet should match Form 7203 structure |

**Deprecated/outdated:**
- Pre-2021 basis tracking was optional. Since 2021, Form 7203 is required when shareholders claim losses, receive non-dividend distributions, dispose of stock, or receive loan repayments. Our basis worksheet should align with Form 7203 structure.

## 1120-S Form Structure (Detailed)

### Form 1120-S Main Pages (5 pages)

**Page 1: Income and Deductions**
- Lines 1a-1b: Gross receipts/sales, returns/allowances
- Line 2: Cost of goods sold
- Line 4: Net gain/loss from Form 4797
- Line 5: Other income
- Lines 7-20: Deductions (officer compensation, salaries/wages, repairs, bad debts, rent, taxes, interest, depreciation, depletion, advertising, pension/profit-sharing, employee benefits, other deductions)
- Line 21: Ordinary business income (loss)

**Pages 2-3: Schedule K (Shareholders' Pro Rata Share Items)**
- Lines 1-10: Income/loss items (ordinary income, rental, interest, dividends, royalties, capital gains, Section 1231)
- Lines 11-12: Deductions (Section 179, charitable, other)
- Line 13: Credits
- Lines 14-15: Foreign transactions, AMT items
- Lines 16-17: Items affecting shareholder basis (tax-exempt income, nondeductible expenses, distributions)

**Page 4: Schedule L (Balance Sheet per Books)**
- Lines 1-15: Assets (cash, receivables, inventory, investments, fixed assets, intangibles)
- Lines 16-22: Liabilities (payables, short-term debt, shareholder loans, long-term debt)
- Lines 23-27: Equity (capital stock, paid-in capital, retained earnings, adjustments, treasury stock)

**Page 4-5: Schedules M-1 and M-2**
- M-1: Reconciliation of book income to tax return income
- M-2: Analysis of Accumulated Adjustments Account (AAA), Previously Taxed Income, Accumulated E&P, and Other Adjustments Account

### Schedule K-1 (Form 1120-S) Boxes

| Box | Description | Personal Return Destination |
|-----|-------------|---------------------------|
| 1 | Ordinary business income/loss | Schedule E, Part II |
| 2 | Net rental real estate income/loss | Schedule E, Part II |
| 3 | Other net rental income/loss | Schedule E, Part II |
| 4 | Interest income | Schedule B |
| 5a | Ordinary dividends | Schedule B |
| 5b | Qualified dividends | Qualified dividends worksheet |
| 6 | Royalties | Schedule E |
| 7 | Net short-term capital gain/loss | Schedule D |
| 8a | Net long-term capital gain/loss | Schedule D |
| 9 | Net section 1231 gain/loss | Form 4797 |
| 10 | Other income/loss | Various |
| 11 | Section 179 deduction | Form 4562 |
| 12 | Other deductions | Schedule A or other |
| 13 | Credits | Various credit forms |
| 14 | Foreign transactions | Form 1116 |
| 15 | AMT items | Form 6251 |
| 16 | Items affecting basis | Basis worksheet |
| 17 | Other information | Various |

## Shareholder Basis Tracking (Detailed)

### Stock Basis Ordering Rule (IRS Required Sequence)

Applied annually as of the last day of the tax year:

1. **Increase** for income items (K-1 Box 1 positive, Boxes 2-10 positive, Box 16A/B tax-exempt)
2. **Decrease** for non-dividend distributions (Box 16D) -- not below zero; excess is capital gain
3. **Decrease** for nondeductible expenses (Box 16C) and oil/gas depletion (Box 17R) -- not below zero
4. **Decrease** for losses and deductions (Box 1 negative, Boxes 2-12 losses) -- not below zero; excess goes to debt basis

### Debt Basis Rules

- Only direct shareholder-to-corporation loans create debt basis (NOT loan guarantees)
- Stock basis must be fully exhausted before debt basis absorbs losses
- Debt basis restoration happens before stock basis restoration in subsequent years
- Debt basis has its own separate ordering

### Suspended Losses

- When losses exceed stock + debt basis, excess is suspended
- Suspended losses retain their character (ordinary, capital, etc.)
- Carry forward indefinitely
- Treated as newly incurred in the following year
- Lost permanently if shareholder disposes of all stock

## Trial Balance Extraction

### What a Trial Balance Looks Like

A trial balance typically arrives as:
1. **Excel export from QuickBooks/Xero** -- most common, structured columnar data
2. **PDF printout** -- requires Vision API extraction
3. **CSV export** -- structured but varies in format

Standard columns: Account Number, Account Name, Account Type, Debit Balance, Credit Balance (or single Net Balance column).

### GL Account to 1120-S Line Mapping Strategy

**Challenge:** Chart of accounts varies enormously between businesses. "Professional Services Expense" might be legal fees (Line 18 other deductions) or consulting fees (Line 20 other deductions) depending on the business.

**Recommended approach:**

1. **Account type classification:** Map by QuickBooks/Xero account type (Revenue, COGS, Operating Expense, Fixed Asset, etc.) to broad 1120-S categories
2. **Name-based heuristics:** Common account names map to specific lines (e.g., "Officer Salary" -> Line 7, "Rent" -> Line 13)
3. **LLM-assisted disambiguation:** For ambiguous accounts, use Claude to classify based on account name + description + context
4. **Confidence scoring:** Each mapping gets HIGH/MEDIUM/LOW confidence; LOW confidence mappings are flagged for CPA review

### Default Mapping Table (Common Accounts)

| Account Type / Name Pattern | 1120-S Line |
|----------------------------|-------------|
| Revenue / Sales / Income | Line 1a (Gross receipts) |
| COGS / Cost of Goods Sold | Line 2 |
| Officer Compensation / Officer Salary | Line 7 |
| Salaries and Wages (non-officer) | Line 8 |
| Repairs and Maintenance | Line 9 |
| Bad Debts | Line 10 |
| Rent / Lease | Lines 13a/b |
| Taxes and Licenses | Line 12 |
| Interest Expense | Line 14 |
| Depreciation | Line 15 |
| Advertising | Line 17 |
| Pension / Profit Sharing | Line 18 |
| Employee Benefits | Line 19 |
| Other Operating Expenses | Line 20 |
| Cash / Bank | Schedule L Line 1 |
| Accounts Receivable | Schedule L Line 2 |
| Inventory | Schedule L Line 3 |
| Fixed Assets | Schedule L Line 10 |
| Accumulated Depreciation | Schedule L Line 10b |
| Accounts Payable | Schedule L Line 16 |
| Shareholder Loans Payable | Schedule L Line 19 |
| Capital Stock | Schedule L Line 22 |
| Retained Earnings | Schedule L Line 24 |

## K-1 to Personal Tax Handoff Protocol

### Design Decision: Use FormK1 Pydantic Model

The existing `FormK1` model in `src/documents/models.py` has all fields needed:
- Entity information (name, EIN, type, tax year)
- Recipient information (name, TIN, ownership percentage)
- Capital account information (beginning, ending, increases, decreases)
- All income/deduction boxes (1-17)
- Distributions (Box 19)
- Confidence level and uncertain fields

### Handoff Flow

1. **Business Tax Agent** generates K-1 data during 1120-S processing
2. Agent creates `FormK1` instances for each shareholder
3. K-1 data is serialized (via `orjson`) and stored as `TaskArtifact` with `artifact_type="generated_k1"`
4. **Personal Tax Agent** loads generated K-1s during context building (query artifacts by client + entity)
5. Personal Tax Agent processes the `FormK1` through its existing K-1 consumption path (already built in Phase 4)

### Handoff Data Format

```python
# Stored as TaskArtifact
artifact = TaskArtifact(
    task_id=business_tax_task.id,
    artifact_type="generated_k1",
    content=orjson.dumps(form_k1.model_dump(mode="json")).decode(),
)
```

### Retrieval by Personal Tax Agent

The Personal Tax Agent's context builder (`src/context/builder.py`) should be extended to query for `generated_k1` artifacts related to the client. This is an enhancement to the existing `get_client_documents()` stub.

## Existing Codebase Patterns to Reuse

### From `src/agents/personal_tax/agent.py`

- **Agent class structure:** `__init__` with storage_url/output_dir, async `process()` method, escalation accumulator
- **Result dataclass:** `PersonalTaxResult` pattern -> create `BusinessTaxResult`
- **EscalationRequired exception:** Reuse directly from personal_tax
- **Document extraction flow:** `_extract_documents()` with concurrency control via semaphore
- **Handler function:** `personal_tax_handler` pattern for dispatcher registration

### From `src/agents/personal_tax/calculator.py`

- **Pure function pattern:** All calculations as standalone functions with typed inputs/outputs
- **Dataclass inputs/outputs:** `IncomeSummary`, `DeductionResult`, `TaxResult` -> create analogous `Form1120SResult`, `ScheduleKResult`
- **Filing status enum:** May need a `BusinessEntityType` enum for future expansion (1120-S, 1065, 1120)
- **Tax year config usage:** `get_tax_year_config()` for year-specific thresholds

### From `src/agents/personal_tax/output.py`

- **Drake worksheet generator pattern:** `generate_drake_worksheet()` with openpyxl
- **Helper functions:** `_create_currency_style()`, `_create_header_style()`, `_auto_fit_columns()`, `_format_decimal()`
- **Preparer notes generator:** `generate_preparer_notes()` as Markdown

### From `src/documents/models.py`

- **FormK1 model:** Direct reuse for K-1 generation output
- **Validation functions:** `validate_ssn()`, `validate_ein()`, `validate_tin()`
- **ConfidenceLevel enum:** Standard confidence tracking

### From `src/orchestration/`

- **TaskDispatcher:** Register "business_tax" handler
- **TaskStateMachine:** Use for state transitions
- **CircuitBreaker:** Protect LLM calls during trial balance extraction

### Patterns to Adapt (Not Direct Reuse)

- **Calculator structure:** Personal Tax calculator is a single large file. Business Tax should split into `calculator.py` (main computations), `basis.py` (basis tracking), and `trial_balance.py` (GL mapping) to avoid a monolithic file.
- **Context builder:** Needs extension for business entities (entity profile vs client profile), shareholder roster, prior year basis data.
- **Document types:** Trial balance is a new document type not in the existing classifier/extractor. May need a new `DocumentType.TRIAL_BALANCE` or handle as a structured extraction (Excel parsing + LLM-assisted mapping).

## Testing Strategy

### Essential Test Cases

**1. Basis Tracking Tests (HIGHEST PRIORITY -- most common error source)**
- Stock basis increase from income (all income types)
- Stock basis decrease from distributions (not below zero)
- Stock basis decrease from losses (not below zero, excess to debt basis)
- Ordering rule compliance (income before distributions before losses)
- Debt basis: only direct loans count, not guarantees
- Debt basis: stock basis exhausted before debt basis used
- Suspended losses: character retention, carry forward, loss on disposition
- Multi-year basis tracking: beginning basis = prior year ending basis
- Edge case: zero basis shareholder receiving income + distribution
- Edge case: distributions exceeding basis = capital gain

**2. K-1 Allocation Tests**
- Pro-rata allocation for 2 shareholders (50/50)
- Pro-rata allocation for unequal ownership (70/30)
- All Schedule K line items flow correctly to K-1 boxes
- K-1 amounts sum exactly to Schedule K totals (reconciliation)
- Rounding: K-1 amounts sum to Schedule K total (handle rounding residual)

**3. Schedule L Balance Sheet Tests**
- Assets = Liabilities + Equity (fundamental balance check)
- Trial balance maps correctly to Schedule L lines
- Beginning balance = prior year ending balance
- Retained earnings updated for current year income/loss
- Distributions reflected in equity

**4. Trial Balance Extraction Tests**
- Excel trial balance parsing (standard QuickBooks format)
- GL account mapping to 1120-S lines (common accounts)
- Ambiguous account flagging (LOW confidence)
- Trial balance totals: debits = credits
- Missing required accounts escalation

**5. K-1 Handoff Tests**
- Generated FormK1 model validates (all required fields present)
- Serialization/deserialization roundtrip
- Personal Tax Agent can consume generated K-1 through existing path
- Generated K-1 fields match what Personal Tax Agent expects

**6. 1120-S Computation Tests**
- Ordinary business income from trial balance income/deduction lines
- Schedule K computation from 1120-S page 1 items
- Schedule M-1 reconciliation (book income vs tax income)
- Schedule M-2 AAA tracking

**7. End-to-End Integration Tests**
- Process test 1120-S with 2 equal shareholders (50/50)
- Process test 1120-S with 2 unequal shareholders (75/25)
- K-1 data flows to Personal Tax Agent and is consumed correctly
- Escalation fires when expected data is missing

### Mock Data Needed

1. **Sample trial balance (Excel):** 30-40 GL accounts typical of a small S-Corp (revenue, COGS, operating expenses, officer comp, balance sheet accounts). Two versions: clean and ambiguous.
2. **Sample shareholder roster:** 2 shareholders with SSNs, ownership percentages, beginning basis amounts, and loan balances.
3. **Expected 1120-S output:** Manually computed reference 1120-S for the sample trial balance to verify against.
4. **Expected K-1 outputs:** One K-1 per shareholder with manually computed allocations.
5. **Expected basis worksheets:** Beginning basis, adjustments, ending basis for each shareholder.
6. **Prior year data:** Prior year 1120-S return and basis worksheets for carry-forward testing.

## Risks and Pitfalls

### Risk 1: Trial Balance Format Variability (HIGH)

**Risk:** Trial balances from different accounting software (QuickBooks, Xero, Wave, custom) have wildly different formats, column orders, and account naming conventions.
**Impact:** Extraction accuracy could fall below the 85% rollback threshold.
**Mitigation:** Start with Excel-based extraction (openpyxl) for structured data; add PDF/Vision extraction as a second path. Use LLM-assisted mapping for account classification. Always flag ambiguous mappings.

### Risk 2: Basis Calculation Errors (HIGH)

**Risk:** Getting the ordering rule or debt basis logic wrong silently produces incorrect K-1s.
**Impact:** Incorrect K-1s flow to shareholders' personal returns, causing IRS notices.
**Mitigation:** Extensive unit tests for every basis scenario. Compare against manually computed basis worksheets. Add a reconciliation check: sum of all shareholders' ending basis should relate predictably to entity equity.

### Risk 3: K-1 Amounts Not Summing to Schedule K (MEDIUM)

**Risk:** Rounding errors in pro-rata allocation cause K-1 totals to differ from Schedule K totals.
**Impact:** IRS matching program flags the discrepancy.
**Mitigation:** Allocate all but one shareholder's share by percentage; compute the last shareholder's share as Schedule K total minus sum of all others. This is the standard accounting approach.

### Risk 4: Mid-Year Ownership Changes (MEDIUM)

**Risk:** The simplified pro-rata model breaks if shareholders bought/sold stock during the year.
**Impact:** Incorrect allocations for affected shareholders.
**Mitigation:** v1 supports only full-year constant-ownership shareholders. Detect mid-year changes and escalate. This matches the 85% rollback threshold strategy.

### Risk 5: Reasonable Compensation (LOW for agent, HIGH for client)

**Risk:** Agent produces technically correct return but officer compensation is unreasonably low relative to distributions.
**Impact:** IRS audit risk for the client.
**Mitigation:** Add advisory flag (not escalation) when distributions significantly exceed officer compensation. This is CPA judgment, not agent decision.

### Risk 6: Multi-State Considerations (OUT OF SCOPE)

**Risk:** S-Corp operating in multiple states requires apportionment.
**Impact:** State returns are incomplete.
**Mitigation:** v1 handles federal 1120-S only. Multi-state is explicitly listed as v2 requirement (ADV-01).

## Open Questions

1. **Trial balance source format priority**
   - What we know: Clients use QuickBooks, Xero, or custom systems
   - What's unclear: Should v1 support only Excel trial balances, or also PDF extraction via Vision API?
   - Recommendation: Start with Excel (openpyxl parsing) as primary; add PDF as stretch goal. Excel covers ~80% of real-world trial balance submissions.

2. **Chart of Accounts Mapping Configuration**
   - What we know: GL account names vary wildly
   - What's unclear: Should the mapping be per-client configurable (stored in profile), or should the LLM classify each time?
   - Recommendation: LLM-assisted mapping each time with a default heuristic table as fallback. Store successful mappings as client profile data for future returns (learning).

3. **Prior Year Basis Data Source**
   - What we know: Basis tracking requires prior year ending basis as starting point
   - What's unclear: Where does prior year basis data come from for new clients?
   - Recommendation: Accept manual input (CPA enters prior year basis) for year 1. For returning clients, carry forward from prior year's BusinessTaxAgent result.

4. **Tax-Exempt Interest and Other Schedule K Items**
   - What we know: Schedule K has many specialized items (foreign transactions, AMT, etc.)
   - What's unclear: How many of these should v1 support?
   - Recommendation: v1 handles the core items (Boxes 1-12, 16 distributions, 16A/B tax-exempt). Foreign transactions (Box 14), AMT (Box 15), and specialized credits (Box 13 beyond basic) should escalate.

5. **Schedule M-1 Automation Level**
   - What we know: M-1 reconciles book income to tax income
   - What's unclear: Can we reliably compute book-tax differences without detailed knowledge of the client's accounting methods?
   - Recommendation: For v1, compute M-1 only from known differences (depreciation differences if provided). Flag M-1 for CPA review if book and tax income differ significantly without explained adjustments.

## Sources

### Primary (HIGH confidence)
- IRS Instructions for Form 1120-S (2025): https://www.irs.gov/instructions/i1120s
- IRS Shareholder's Instructions for Schedule K-1 (Form 1120-S) (2025): https://www.irs.gov/instructions/i1120ssk
- IRS S Corporation Stock and Debt Basis: https://www.irs.gov/businesses/small-businesses-self-employed/s-corporation-stock-and-debt-basis
- IRS About Form 7203 (Shareholder Stock and Debt Basis Limitations): https://www.irs.gov/forms-pubs/about-form-7203
- Existing codebase: `src/agents/personal_tax/`, `src/documents/models.py`, `src/orchestration/`

### Secondary (MEDIUM confidence)
- Drake Tax KB - Shareholder's Adjusted Basis Worksheet: https://kb.drakesoftware.com/kb/Drake-Tax/10919.htm
- White Coat Investor - Schedule L for Form 1120-S: https://www.whitecoatinvestor.com/schedule-l-balance-sheets-per-books-for-form-1120-s/
- Intuit Tax Pro Center - Basics of Shareholder Basis: https://accountants.intuit.com/taxprocenter/tax-law-and-news/basics-of-shareholder-basis-in-an-s-corporation/

### Tertiary (LOW confidence)
- General web search results on trial balance formats and common 1120-S errors (various sources, not individually authoritative)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in the project; no new dependencies
- Architecture: HIGH - Direct mirror of established Personal Tax Agent patterns
- 1120-S domain knowledge: HIGH - IRS official instructions fetched and verified
- Shareholder basis rules: HIGH - IRS official documentation confirmed ordering rules
- Trial balance extraction: LOW - Source document format variability is high; no authoritative standard for mapping
- K-1 handoff protocol: HIGH - FormK1 model already exists and is consumed by Personal Tax Agent
- Testing strategy: MEDIUM - Test scenarios identified but mock data creation complexity is uncertain
- Pitfalls: MEDIUM - Common errors identified from IRS documentation and practitioner forums

**Research date:** 2026-02-06
**Valid until:** 2026-03-08 (30 days - stable domain, IRS rules change annually but 2025 forms are finalized)
