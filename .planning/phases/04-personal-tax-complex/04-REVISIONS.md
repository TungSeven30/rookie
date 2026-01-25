# Phase 4 Plan Review: Proposed Revisions

**Created:** 2026-01-25
**Reviewer:** Claude Opus 4.5
**Phase:** 4 - Personal Tax Complex Returns

## Executive Summary

The Phase 4 plan is well-structured with clear wave dependencies and comprehensive coverage of complex tax scenarios. This document identifies architectural improvements, missing features, and reliability enhancements that would significantly strengthen the implementation.

---

## Revision Summary

| # | Revision | Impact | Effort | Priority |
|---|----------|--------|--------|----------|
| 1 | K-1 Basis Management | High | Medium | P1 |
| 2 | 1099-B Transaction Aggregation | High | Medium | P1 |
| 3 | Iterative QBI Calculation | Medium | Low | P2 |
| 4 | Prior Year Carryover Integration | High | Medium | P1 |
| 5 | Form 8949 Generation | Medium | Low | P2 |
| 6 | SSTB Auto-Classification | Medium | Low | P2 |
| 7 | Estimated Tax Payment Tracking | High | Medium | P1 |
| 8 | Validation Layer | High | Medium | P1 |
| 9 | Tax Year Parameterization | Medium | Low | P3 |
| 10 | Property-Based Testing | Medium | Low | P3 |

**Priority Legend:**
- P1: Critical for accurate tax calculations
- P2: Important for CPA workflow efficiency
- P3: Maintainability and quality improvements

---

## Revision 1: Add Multi-Entity K-1 Tracking and Basis Management

### Problem

The current K-1 model captures income flows but **lacks crucial basis tracking** that CPAs need. Without basis, you can't determine:
- If distributions are taxable
- Whether losses are deductible
- If at-risk rules apply

### Impact

A CPA reviewing a K-1 return needs to know: "Can this partner actually deduct this loss?" Without basis tracking, the agent can't answer this, forcing every K-1 with losses to escalate unnecessarily.

### Proposed Changes

**File: `src/documents/models.py` (04-01-PLAN.md)**

```diff
 class FormK1(BaseModel):
     """Schedule K-1 data from Partnership (1065) or S-Corp (1120-S)."""

     # Entity information (Part I)
     entity_name: str
     entity_ein: str
     entity_type: str  # "partnership" or "s_corp"
     tax_year: int
+    form_type: str = "1065"  # "1065" for partnerships, "1120-S" for S-corps

     # Partner/Shareholder information (Part II)
     recipient_name: str
     recipient_tin: str
     ownership_percentage: Decimal
+    capital_account_beginning: Decimal | None = None  # Beginning capital
+    capital_account_ending: Decimal | None = None     # Ending capital
+    current_year_increase: Decimal | None = None
+    current_year_decrease: Decimal | None = None

     # Income items (Part III)
     # ... existing fields ...

+    # Debt basis (partnerships) - from K-1 supplemental
+    share_of_recourse_liabilities: Decimal | None = None
+    share_of_nonrecourse_liabilities: Decimal | None = None
+    share_of_qualified_nonrecourse: Decimal | None = None
+
+    # Loan repayments (S-corps)
+    loan_repayments: Decimal = Decimal("0")
+
+    @property
+    def requires_basis_escalation(self) -> bool:
+        """
+        Check if basis limitation may affect loss deductibility.
+
+        Escalate if:
+        - Net K-1 loss > $10k AND no capital account info
+        - This prevents silent disallowance of legitimate losses
+        """
+        net_loss = self.ordinary_business_income + self.net_rental_real_estate
+        has_significant_loss = net_loss < Decimal("-10000")
+        missing_basis_info = self.capital_account_ending is None
+        return has_significant_loss and missing_basis_info
```

**New File: `src/agents/personal_tax/basis_tracker.py`**

```python
"""Partner/Shareholder basis tracking for loss limitation rules."""

from dataclasses import dataclass
from decimal import Decimal

from src.documents.models import FormK1


@dataclass
class PartnerBasis:
    """Track partner/shareholder basis for loss limitation."""

    entity_ein: str
    tax_year: int

    # Stock basis (S-corp) or Capital account (Partnership)
    beginning_basis: Decimal = Decimal("0")

    # Increases
    capital_contributions: Decimal = Decimal("0")
    ordinary_income: Decimal = Decimal("0")
    separately_stated_income: Decimal = Decimal("0")
    tax_exempt_income: Decimal = Decimal("0")
    debt_increases: Decimal = Decimal("0")  # Partnerships only

    # Decreases (order matters per IRC)
    distributions: Decimal = Decimal("0")
    nondeductible_expenses: Decimal = Decimal("0")
    losses_and_deductions: Decimal = Decimal("0")
    debt_decreases: Decimal = Decimal("0")  # Partnerships only

    @property
    def ending_basis(self) -> Decimal:
        """Calculate ending basis (minimum $0)."""
        basis = self.beginning_basis
        basis += self.capital_contributions + self.ordinary_income
        basis += self.separately_stated_income + self.tax_exempt_income
        basis += self.debt_increases
        basis -= self.distributions + self.nondeductible_expenses
        basis -= self.losses_and_deductions + self.debt_decreases
        return max(Decimal("0"), basis)

    @property
    def deductible_loss(self) -> Decimal:
        """Loss deductible this year (limited by basis)."""
        requested_loss = abs(min(Decimal("0"),
            self.ordinary_income + self.separately_stated_income))
        available_basis = self.beginning_basis + self.capital_contributions
        available_basis += self.tax_exempt_income + self.debt_increases
        available_basis -= self.distributions + self.nondeductible_expenses
        return min(requested_loss, max(Decimal("0"), available_basis))

    @property
    def suspended_loss(self) -> Decimal:
        """Loss suspended due to basis limitation."""
        total_loss = abs(min(Decimal("0"),
            self.ordinary_income + self.separately_stated_income))
        return total_loss - self.deductible_loss


def check_basis_limitation(
    k1: FormK1,
    prior_year_basis: Decimal | None = None,
) -> tuple[Decimal, Decimal, list[str]]:
    """
    Check if K-1 loss is limited by basis.

    Returns:
        (deductible_loss, suspended_loss, escalation_messages)
    """
    escalations = []

    # If we have capital account info, use it
    if k1.capital_account_beginning is not None:
        basis = PartnerBasis(
            entity_ein=k1.entity_ein,
            tax_year=k1.tax_year,
            beginning_basis=k1.capital_account_beginning,
            ordinary_income=k1.ordinary_business_income,
            distributions=k1.distributions,
        )
        return basis.deductible_loss, basis.suspended_loss, escalations

    # Without basis info, we can't compute - escalate
    if k1.requires_basis_escalation:
        escalations.append(
            f"K-1 from {k1.entity_name} shows loss but no basis info - "
            "verify partner has sufficient basis to deduct loss"
        )
        # Assume deductible for worksheet, but flag heavily
        return abs(k1.ordinary_business_income), Decimal("0"), escalations

    # No loss, no basis check needed
    return Decimal("0"), Decimal("0"), escalations
```

---

## Revision 2: Add Transaction Aggregation for 1099-B Composite Statements

### Problem

The current plan handles 1099-B as individual transactions, but **real-world broker statements often have thousands of transactions**. Missing:
- Transaction aggregation by category
- Summary-level extraction for IRS-reported totals
- Memory/performance handling for large transaction counts

### Impact

Fidelity/Schwab statements can have 500+ transactions. Extracting each individually is:
- Expensive (API costs)
- Error-prone (LLM may miss some)
- Unnecessary (IRS accepts summary reporting for covered transactions)

### Proposed Changes

**File: `src/documents/models.py` (04-01-PLAN.md)**

```python
class Form1099BSummary(BaseModel):
    """
    Aggregated 1099-B summary for high-volume broker statements.

    When a broker statement has >50 transactions, extract category totals
    instead of individual transactions. This matches IRS Form 8949 categories.
    """

    # Payer info (same for all transactions)
    payer_name: str
    payer_tin: str
    recipient_tin: str

    # Category A: Short-term, basis reported to IRS
    cat_a_proceeds: Decimal = Decimal("0")
    cat_a_cost_basis: Decimal = Decimal("0")
    cat_a_adjustments: Decimal = Decimal("0")
    cat_a_gain_loss: Decimal = Decimal("0")
    cat_a_transaction_count: int = 0

    # Category B: Short-term, basis NOT reported to IRS
    cat_b_proceeds: Decimal = Decimal("0")
    cat_b_cost_basis: Decimal | None = None  # May need client input
    cat_b_transaction_count: int = 0

    # Category D: Long-term, basis reported to IRS
    cat_d_proceeds: Decimal = Decimal("0")
    cat_d_cost_basis: Decimal = Decimal("0")
    cat_d_adjustments: Decimal = Decimal("0")
    cat_d_gain_loss: Decimal = Decimal("0")
    cat_d_transaction_count: int = 0

    # Category E: Long-term, basis NOT reported to IRS
    cat_e_proceeds: Decimal = Decimal("0")
    cat_e_cost_basis: Decimal | None = None
    cat_e_transaction_count: int = 0

    # Wash sale totals (summed across all categories)
    total_wash_sale_disallowed: Decimal = Decimal("0")

    # Collectibles and other special categories
    collectibles_gain: Decimal = Decimal("0")
    section_1202_gain: Decimal = Decimal("0")

    # Metadata
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH

    @property
    def has_missing_basis(self) -> bool:
        """Check if any non-reported categories need basis input."""
        return (
            (self.cat_b_transaction_count > 0 and self.cat_b_cost_basis is None) or
            (self.cat_e_transaction_count > 0 and self.cat_e_cost_basis is None)
        )

    @property
    def total_net_gain_loss(self) -> Decimal:
        """Total gain/loss from all reported categories."""
        return self.cat_a_gain_loss + self.cat_d_gain_loss
```

**File: `src/documents/extractor.py` (04-02-PLAN.md)**

```python
async def extract_1099_b_smart(
    client: anthropic.AsyncAnthropic,
    image_data: bytes,
    mock: bool = False,
) -> Form1099BSummary | list[Form1099B]:
    """
    Smart 1099-B extraction that uses summary mode for large statements.

    Strategy:
    1. First pass: Ask LLM how many transactions are on the form
    2. If <50 transactions: Extract individually (original behavior)
    3. If >=50 transactions: Extract summary totals by category

    This prevents API cost explosion and reduces extraction errors
    on high-volume broker statements.
    """
    if mock:
        return _mock_1099_b()

    # First: Quick count check
    count_response = await client.messages.create(
        model="claude-sonnet-4-20250514",  # Fast model for simple check
        max_tokens=50,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.b64encode(image_data).decode()
                    }
                },
                {
                    "type": "text",
                    "text": "How many individual transactions are listed on this 1099-B? "
                            "Just respond with a number."
                }
            ]
        }]
    )

    try:
        transaction_count = int(count_response.content[0].text.strip())
    except (ValueError, IndexError):
        transaction_count = 1  # Assume small if unclear

    if transaction_count >= 50:
        # Use summary extraction
        return await _extract_1099_b_summary(client, image_data)
    else:
        # Use detailed extraction
        return await extract_1099_b(client, image_data, mock=False)
```

---

## Revision 3: Add Iterative QBI Calculation for AGI Dependency

### Problem

The QBI deduction has a **circular dependency**: QBI deduction affects taxable income, but taxable income determines QBI limitations. The current plan calculates QBI once, but this can produce incorrect results when:
- Taxpayer is near the threshold ($191,950 single)
- QBI deduction itself pushes them below threshold
- Different limitation applies than initially calculated

### Impact

Consider: Taxable income = $195,000 (above threshold), QBI = $50,000.
- Initial calc applies wage limitation → deduction = $8,000
- New TI = $187,000 (below threshold!)
- No wage limitation should apply → deduction = $10,000

This requires iteration.

### Proposed Changes

**File: `src/agents/personal_tax/calculator.py` (04-06-PLAN.md)**

```python
def calculate_qbi_deduction(
    components: list[QBIComponent],
    taxable_income: Decimal,
    net_capital_gains: Decimal,
    filing_status: FilingStatus,
) -> QBIDeduction:
    """
    Calculate QBI deduction with iterative refinement.

    The QBI deduction has a circular dependency:
    - QBI deduction reduces taxable income
    - Taxable income determines if wage limitations apply

    For taxpayers near the threshold, the QBI deduction itself may
    push them below the threshold, changing which rules apply.

    This function iterates until the deduction stabilizes (max 3 iterations).
    """
    MAX_ITERATIONS = 3
    CONVERGENCE_THRESHOLD = Decimal("1.00")  # $1 tolerance

    current_ti = taxable_income
    previous_deduction = Decimal("0")

    for iteration in range(MAX_ITERATIONS):
        # Calculate QBI with current taxable income estimate
        result = _calculate_qbi_single_pass(
            components=components,
            taxable_income=current_ti,
            net_capital_gains=net_capital_gains,
            filing_status=filing_status,
        )

        # Check for convergence
        if abs(result.final_qbi_deduction - previous_deduction) < CONVERGENCE_THRESHOLD:
            result.iterations_required = iteration + 1
            return result

        # Update for next iteration
        previous_deduction = result.final_qbi_deduction
        # Recalculate taxable income with this deduction
        current_ti = taxable_income - result.final_qbi_deduction

    # Didn't converge - use conservative (lower) deduction
    result.convergence_warning = True
    result.iterations_required = MAX_ITERATIONS
    return result


def _calculate_qbi_single_pass(
    components: list[QBIComponent],
    taxable_income: Decimal,
    net_capital_gains: Decimal,
    filing_status: FilingStatus,
) -> QBIDeduction:
    """
    Single-pass QBI calculation (internal helper).

    Called iteratively by calculate_qbi_deduction() to handle
    the circular dependency between QBI deduction and taxable income.
    """
    # ... existing single-pass logic from 04-06-PLAN.md ...
```

**Update QBIDeduction dataclass:**

```diff
 @dataclass
 class QBIDeduction:
     """Final QBI deduction calculation result."""

     # ... existing fields ...

     # Final deduction
     qbi_deduction_before_limit: Decimal
     taxable_income_limit: Decimal
     final_qbi_deduction: Decimal
+
+    # Iteration tracking
+    iterations_required: int = 1
+    convergence_warning: bool = False  # True if didn't converge
```

---

## Revision 4: Add Prior Year Data Integration for Carryovers

### Problem

The plan mentions prior year carryover fields (capital loss, passive loss) but **doesn't specify how they're sourced**. Phase 4 needs explicit:
- Prior year data model for carryovers
- Integration with client profile system from Phase 2
- Validation that carryovers match prior year return

### Impact

Without this, the agent will either:
- Ignore carryovers (understates refund/overstates tax)
- Require manual input every time (defeats automation)

### Proposed Changes

**File: `src/agents/personal_tax/carryovers.py` (new)**

```python
"""Tax year carryover tracking and loading."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class TaxYearCarryovers:
    """Carryover amounts from prior year return."""

    tax_year: int  # Year these carryovers are FROM (prior year)

    # Capital losses (Schedule D)
    capital_loss_carryforward: Decimal = Decimal("0")
    capital_loss_carryforward_short_term: Decimal = Decimal("0")
    capital_loss_carryforward_long_term: Decimal = Decimal("0")

    # Passive activity losses (Schedule E / Form 8582)
    passive_loss_carryforward: Decimal = Decimal("0")
    passive_loss_by_activity: dict[str, Decimal] = field(default_factory=dict)

    # Net Operating Loss (if applicable)
    nol_carryforward: Decimal = Decimal("0")

    # Charitable contribution carryovers
    charitable_carryforward: Decimal = Decimal("0")

    # Investment interest expense carryover
    investment_interest_carryforward: Decimal = Decimal("0")

    # AMT credit carryforward
    amt_credit_carryforward: Decimal = Decimal("0")

    # Foreign tax credit carryforward
    foreign_tax_credit_carryforward: Decimal = Decimal("0")

    # K-1 suspended losses by entity
    k1_suspended_losses: dict[str, Decimal] = field(default_factory=dict)

    # Source tracking
    source: str = "prior_year_return"  # or "client_input", "estimated"
    verified: bool = False
```

**File: `src/agents/personal_tax/agent.py` (04-08-PLAN.md)**

```python
async def _load_carryovers(
    self,
    client_id: str,
    from_tax_year: int,
) -> TaxYearCarryovers:
    """
    Load carryover amounts from client profile.

    Strategy:
    1. Check if we prepared prior year return (profile has data)
    2. If yes, use calculated carryovers from that return
    3. If no, check if client provided carryover amounts
    4. If neither, return zeros with escalation flag
    """
    # Try to load from client profile
    profile = await self.profile_service.get_client_profile(client_id)

    prior_year_return = profile.get_tax_return(from_tax_year)
    if prior_year_return and prior_year_return.carryovers:
        return prior_year_return.carryovers

    # Check for manually entered carryovers
    manual_carryovers = profile.get_manual_carryovers(from_tax_year)
    if manual_carryovers:
        return manual_carryovers

    # No carryover data - flag for review
    self.escalations.append(Escalation(
        severity=EscalationSeverity.LOW,
        message=f"No carryover data available from {from_tax_year}. "
                "Verify if client has capital loss or passive loss carryforwards.",
    ))
    return TaxYearCarryovers(tax_year=from_tax_year, source="estimated")
```

---

## Revision 5: Add Form 8949 Generation for Schedule D

### Problem

Schedule D requires Form 8949 for transaction details. The current plan generates a Schedule D sheet but **doesn't mention Form 8949**, which is required when:
- Any transaction has wash sale adjustments
- Basis was not reported to IRS
- Any adjustment codes apply

### Impact

Without Form 8949 generation, the Drake worksheet is incomplete - CPA still needs to manually create 8949 from the transaction data.

### Proposed Changes

**File: `src/agents/personal_tax/output.py` (04-08-PLAN.md)**

```python
def _generate_form_8949_sheets(
    wb: Workbook,
    transactions: list[CapitalTransaction],
    schedule_d_result: ScheduleDResult,
) -> None:
    """
    Generate Form 8949 sheets for Schedule D transactions.

    Creates separate sheets for each 8949 category:
    - Part I (Short-Term): Box A (basis reported), Box B (basis not reported)
    - Part II (Long-Term): Box D (basis reported), Box E (basis not reported)
    """
    # Categorize transactions
    categories = {
        "8949_Part_I_A": [],  # Short-term, basis reported
        "8949_Part_I_B": [],  # Short-term, basis NOT reported
        "8949_Part_II_D": [],  # Long-term, basis reported
        "8949_Part_II_E": [],  # Long-term, basis NOT reported
    }

    for txn in transactions:
        if txn.is_short_term:
            if txn.basis_reported_to_irs:
                categories["8949_Part_I_A"].append(txn)
            else:
                categories["8949_Part_I_B"].append(txn)
        elif txn.is_long_term:
            if txn.basis_reported_to_irs:
                categories["8949_Part_II_D"].append(txn)
            else:
                categories["8949_Part_II_E"].append(txn)

    # Create sheets only for non-empty categories
    for category_name, txns in categories.items():
        if not txns:
            continue

        ws = wb.create_sheet(category_name)
        _populate_8949_sheet(ws, txns, category_name)


def _populate_8949_sheet(
    ws: Worksheet,
    transactions: list[CapitalTransaction],
    category: str,
) -> None:
    """Populate a single Form 8949 sheet."""
    # Header row matching IRS Form 8949
    headers = [
        "(a) Description",
        "(b) Date acquired",
        "(c) Date sold",
        "(d) Proceeds",
        "(e) Cost basis",
        "(f) Code(s)",  # W for wash sale, B for basis adjustment, etc.
        "(g) Adjustment",
        "(h) Gain or loss",
    ]

    for col, header in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=header)

    # Transaction rows
    for row_num, txn in enumerate(transactions, 2):
        ws.cell(row=row_num, column=1, value=txn.description)
        ws.cell(row=row_num, column=2, value=txn.date_acquired or "Various")
        ws.cell(row=row_num, column=3, value=txn.date_sold)
        ws.cell(row=row_num, column=4, value=float(txn.proceeds))
        ws.cell(row=row_num, column=5, value=float(txn.cost_basis) if txn.cost_basis else "")

        # Adjustment codes
        codes = []
        if txn.wash_sale_disallowed > 0:
            codes.append("W")
        ws.cell(row=row_num, column=6, value=",".join(codes))

        # Adjustment amount
        adjustment = txn.wash_sale_disallowed
        ws.cell(row=row_num, column=7, value=float(adjustment) if adjustment else "")

        # Gain/loss
        if txn.gain_loss is not None:
            ws.cell(row=row_num, column=8, value=float(txn.gain_loss))

    # Category totals row
    total_row = len(transactions) + 2
    ws.cell(row=total_row, column=1, value="TOTALS")
    ws.cell(row=total_row, column=4, value=f"=SUM(D2:D{total_row-1})")
    ws.cell(row=total_row, column=5, value=f"=SUM(E2:E{total_row-1})")
    ws.cell(row=total_row, column=7, value=f"=SUM(G2:G{total_row-1})")
    ws.cell(row=total_row, column=8, value=f"=SUM(H2:H{total_row-1})")
```

---

## Revision 6: Add SSTB Classification Helper

### Problem

The QBI plan mentions SSTB (Specified Service Trade or Business) but **leaves classification to the caller**. This is problematic because:
- SSTB classification requires knowledge of business codes
- Common businesses (law, medicine, accounting) should auto-classify
- Misclassification has significant tax impact

### Impact

A law firm shouldn't get QBI deduction at high income. The system should recognize this from the NAICS code or business description without CPA intervention.

### Proposed Changes

**File: `src/agents/personal_tax/sstb.py` (new)**

```python
"""SSTB (Specified Service Trade or Business) classification."""

from decimal import Decimal

# SSTB classification by NAICS code prefix
# Reference: IRS Reg. 1.199A-5
SSTB_NAICS_PREFIXES = {
    # Health
    "621": "Health care services",
    "6211": "Offices of physicians",
    "6212": "Offices of dentists",
    "6213": "Offices of other health practitioners",
    "622": "Hospitals",

    # Law
    "5411": "Legal services",

    # Accounting
    "5412": "Accounting, tax prep, bookkeeping",

    # Actuarial science
    "524292": "Third party administration of insurance",

    # Performing arts
    "7111": "Performing arts companies",
    "7112": "Spectator sports",
    "711": "Performing arts, sports",

    # Consulting
    "5416": "Management, scientific, technical consulting",

    # Athletics
    "611620": "Sports and recreation instruction",
    "713940": "Fitness and recreational sports centers",

    # Financial services
    "523": "Securities, commodity contracts, investments",
    "5231": "Securities and commodity exchanges",
    "5239": "Other financial investment activities",

    # Brokerage services
    "5312": "Offices of real estate agents and brokers",
    "52312": "Securities brokerage",
}

# Keywords that suggest SSTB regardless of code
SSTB_KEYWORDS = [
    "law firm", "attorney", "lawyer", "legal",
    "physician", "doctor", "medical", "dental", "dentist",
    "cpa", "accountant", "accounting", "tax prep",
    "consulting", "consultant",
    "financial advisor", "investment advisor", "wealth management",
    "broker", "brokerage",
    "actor", "actress", "musician", "athlete", "sports",
]


def classify_sstb(
    naics_code: str,
    business_activity: str,
    business_name: str,
) -> tuple[bool, str | None]:
    """
    Classify whether a business is an SSTB (Specified Service Trade or Business).

    Args:
        naics_code: 6-digit NAICS business code
        business_activity: Description of business activity
        business_name: Name of the business

    Returns:
        (is_sstb, reason) - reason is None if not SSTB
    """
    # Check NAICS code first (most reliable)
    for prefix, description in SSTB_NAICS_PREFIXES.items():
        if naics_code.startswith(prefix):
            return True, f"NAICS {naics_code} is {description}"

    # Check keywords in activity/name
    combined_text = f"{business_activity} {business_name}".lower()
    for keyword in SSTB_KEYWORDS:
        if keyword in combined_text:
            return True, f"Business description contains '{keyword}'"

    return False, None
```

**Update 04-06-PLAN.md `build_qbi_from_schedule_c()`:**

```diff
 def build_qbi_from_schedule_c(
     schedule_c: ScheduleCData,
     se_tax_deduction: Decimal,
-    is_sstb: bool = False,
+    is_sstb: bool | None = None,  # None = auto-detect
 ) -> QBIComponent:
+    """
+    Build QBI component from Schedule C data.
+
+    If is_sstb is None, automatically classifies based on NAICS code
+    and business description.
+    """
+    # Auto-classify SSTB if not explicitly provided
+    if is_sstb is None:
+        is_sstb, sstb_reason = classify_sstb(
+            schedule_c.principal_business_code,
+            schedule_c.business_activity,
+            schedule_c.business_name,
+        )
+    else:
+        sstb_reason = "Manually specified" if is_sstb else None
+
     qbi = schedule_c.net_profit_or_loss - se_tax_deduction

     return QBIComponent(
         business_name=schedule_c.business_name,
         qualified_business_income=max(Decimal("0"), qbi),
         w2_wages=Decimal("0"),
         is_sstb=is_sstb,
+        sstb_reason=sstb_reason,
         source="schedule_c",
     )
```

---

## Revision 7: Add Estimated Tax Payment Tracking

### Problem

The Phase 4 plan calculates tax liability but **doesn't account for estimated tax payments** (Form 1040-ES). Complex returns typically have:
- Self-employment → estimated payments required
- Capital gains → possible estimated payments
- K-1 income → often has state estimated payments too

Without this, the agent can't compute balance due or refund accurately.

### Impact

A self-employed person with $100k Schedule C income likely made quarterly payments. Without tracking these, the worksheet shows a huge balance due instead of showing payments made and actual balance.

### Proposed Changes

**File: `src/agents/personal_tax/payments.py` (new)**

```python
"""Estimated tax payment tracking."""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class EstimatedPayments:
    """Estimated tax payments made during the year."""

    tax_year: int

    # Federal estimated payments (Form 1040-ES)
    q1_federal: Decimal = Decimal("0")  # Due April 15
    q2_federal: Decimal = Decimal("0")  # Due June 15
    q3_federal: Decimal = Decimal("0")  # Due September 15
    q4_federal: Decimal = Decimal("0")  # Due January 15 (next year)

    # Extension payment
    extension_payment: Decimal = Decimal("0")

    # Prior year overpayment applied
    prior_year_refund_applied: Decimal = Decimal("0")

    # Additional payments
    additional_payments: list[tuple[str, Decimal]] = field(default_factory=list)

    @property
    def total_federal_estimated(self) -> Decimal:
        """Total federal estimated payments."""
        base = self.q1_federal + self.q2_federal + self.q3_federal + self.q4_federal
        additional = sum(amt for _, amt in self.additional_payments)
        return base + self.extension_payment + self.prior_year_refund_applied + additional

    # State estimated payments (for state return support)
    state_payments: dict[str, Decimal] = field(default_factory=dict)


@dataclass
class TaxSummary:
    """Final tax summary with payments and balance due."""

    # Computed amounts
    total_tax_liability: Decimal
    total_credits: Decimal

    # Withholding
    federal_withholding: Decimal  # From W-2s

    # Estimated payments
    estimated_payments: EstimatedPayments

    # Premium Tax Credit impact
    ptc_adjustment: Decimal = Decimal("0")  # + = additional credit, - = repayment

    @property
    def total_payments(self) -> Decimal:
        """Total payments and credits toward tax liability."""
        return (
            self.federal_withholding +
            self.estimated_payments.total_federal_estimated +
            self.total_credits +
            max(Decimal("0"), self.ptc_adjustment)
        )

    @property
    def balance_due_or_refund(self) -> Decimal:
        """
        Positive = refund due to taxpayer
        Negative = balance due from taxpayer
        """
        ptc_repayment = abs(min(Decimal("0"), self.ptc_adjustment))
        return self.total_payments - self.total_tax_liability - ptc_repayment
```

---

## Revision 8: Add Validation Layer for Extracted Data

### Problem

The current plan extracts data and passes it directly to calculators. There's **no validation layer** to catch:
- Impossible values (negative wages, percentages > 100%)
- Cross-document inconsistencies (W-2 SSN ≠ 1099 SSN)
- Math errors (K-1 boxes that should sum correctly)

### Impact

Vision extraction can produce invalid data. Without validation, garbage-in-garbage-out occurs silently. A validation layer catches errors before they propagate.

### Proposed Changes

**File: `src/documents/validation.py` (new)**

```python
"""Document validation for extracted data."""

from dataclasses import dataclass
from decimal import Decimal

from src.documents.models import FormW2, FormK1, Form1099B


@dataclass
class ValidationResult:
    """Result of document validation."""
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    corrections_applied: list[str]


class DocumentValidator:
    """Validate extracted document data for consistency and accuracy."""

    def validate_w2(self, w2: FormW2) -> ValidationResult:
        """Validate W-2 data."""
        errors = []
        warnings = []
        corrections = []

        # Federal withholding shouldn't exceed wages
        if w2.federal_withholding > w2.wages_tips_compensation:
            errors.append(
                f"Federal withholding ({w2.federal_withholding}) "
                f"exceeds wages ({w2.wages_tips_compensation})"
            )

        # Social Security wages have a cap
        ss_cap = Decimal("168600")  # 2024
        if w2.social_security_wages > ss_cap:
            warnings.append(
                f"Social Security wages ({w2.social_security_wages}) "
                f"exceed cap ({ss_cap})"
            )

        # SS tax should be ~6.2% of SS wages
        expected_ss_tax = min(w2.social_security_wages, ss_cap) * Decimal("0.062")
        if abs(w2.social_security_tax - expected_ss_tax) > Decimal("10"):
            warnings.append(
                f"Social Security tax ({w2.social_security_tax}) "
                f"doesn't match expected ({expected_ss_tax})"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrections_applied=corrections,
        )

    def validate_k1(self, k1: FormK1) -> ValidationResult:
        """Validate K-1 data."""
        errors = []
        warnings = []

        # Ownership percentage should be 0-100
        if not (Decimal("0") <= k1.ownership_percentage <= Decimal("100")):
            errors.append(f"Invalid ownership percentage: {k1.ownership_percentage}%")

        # Entity type validation
        if k1.entity_type not in ("partnership", "s_corp"):
            errors.append(f"Invalid entity type: {k1.entity_type}")

        # S-corps shouldn't have guaranteed payments (Box 4)
        if k1.entity_type == "s_corp" and k1.guaranteed_payments != Decimal("0"):
            warnings.append(
                f"S-corp K-1 has guaranteed payments ({k1.guaranteed_payments}) - verify"
            )

        # K-1 with huge losses relative to income is suspicious
        total_income = (k1.ordinary_business_income + k1.interest_income +
                       k1.dividend_income + k1.net_long_term_capital_gain)
        if total_income < Decimal("-100000"):
            warnings.append(f"Large K-1 loss ({total_income}) - verify basis and at-risk")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrections_applied=[],
        )

    def validate_1099b(self, form: Form1099B) -> ValidationResult:
        """Validate 1099-B transaction data."""
        errors = []
        warnings = []

        # Proceeds must be positive
        if form.proceeds <= Decimal("0"):
            errors.append(f"Invalid proceeds: {form.proceeds}")

        # If cost basis reported to IRS, it should exist
        if form.basis_reported_to_irs and form.cost_basis is None:
            warnings.append("Basis reported to IRS but not extracted - verify document")

        # Can't be both short-term and long-term
        if form.is_short_term and form.is_long_term:
            errors.append("Transaction marked as both short-term and long-term")

        # Wash sale shouldn't exceed loss
        if form.cost_basis and form.proceeds < form.cost_basis:
            loss = form.cost_basis - form.proceeds
            if form.wash_sale_loss_disallowed > loss:
                errors.append(
                    f"Wash sale disallowed ({form.wash_sale_loss_disallowed}) "
                    f"exceeds loss ({loss})"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrections_applied=[],
        )

    def validate_cross_document(
        self,
        w2s: list[FormW2],
        k1s: list[FormK1],
        forms_1099: list,
    ) -> ValidationResult:
        """Cross-document consistency validation."""
        errors = []
        warnings = []

        # All documents should have same recipient TIN
        tins = set()
        for w2 in w2s:
            tins.add(w2.employee_tin[-4:])  # Last 4 digits
        for k1 in k1s:
            tins.add(k1.recipient_tin[-4:])
        for f in forms_1099:
            if hasattr(f, 'recipient_tin'):
                tins.add(f.recipient_tin[-4:])

        if len(tins) > 1:
            warnings.append(
                f"Multiple TIN last-4 found across documents: {tins}. "
                "Verify all documents are for the same taxpayer."
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            corrections_applied=[],
        )
```

---

## Revision 9: Add Tax Year Parameterization

### Problem

The plan hardcodes 2024 tax year values throughout. This creates **technical debt** because:
- Tax brackets change annually
- Standard deductions change
- QBI thresholds are inflation-adjusted
- SS wage base increases yearly

### Impact

When 2025 values are needed, changes are scattered across many files. A centralized tax year config makes updates easier and enables testing with prior year data.

### Proposed Changes

**File: `src/tax/year_config.py` (new)**

```python
"""Tax year-specific constants and thresholds."""

from decimal import Decimal
from dataclasses import dataclass


@dataclass(frozen=True)
class TaxYearConfig:
    """Tax year-specific constants and thresholds."""

    tax_year: int

    # Social Security
    ss_wage_base: Decimal
    ss_rate_employee: Decimal = Decimal("0.062")
    ss_rate_employer: Decimal = Decimal("0.062")
    medicare_rate: Decimal = Decimal("0.0145")
    additional_medicare_threshold_single: Decimal = Decimal("200000")
    additional_medicare_threshold_mfj: Decimal = Decimal("250000")
    additional_medicare_rate: Decimal = Decimal("0.009")

    # Standard deductions
    standard_deduction_single: Decimal
    standard_deduction_mfj: Decimal
    standard_deduction_mfs: Decimal
    standard_deduction_hoh: Decimal
    standard_deduction_qw: Decimal
    additional_deduction_65_blind: Decimal

    # QBI thresholds
    qbi_threshold_single: Decimal
    qbi_threshold_mfj: Decimal
    qbi_phaseout: Decimal

    # Capital gains brackets
    ltcg_0_threshold_single: Decimal
    ltcg_0_threshold_mfj: Decimal
    ltcg_15_threshold_single: Decimal
    ltcg_15_threshold_mfj: Decimal

    # Capital loss limit
    capital_loss_limit: Decimal = Decimal("3000")
    capital_loss_limit_mfs: Decimal = Decimal("1500")

    # PTC (ACA)
    fpl_1_person: Decimal
    fpl_per_additional: Decimal


# 2024 Configuration
TAX_YEAR_2024 = TaxYearConfig(
    tax_year=2024,
    ss_wage_base=Decimal("168600"),
    standard_deduction_single=Decimal("14600"),
    standard_deduction_mfj=Decimal("29200"),
    standard_deduction_mfs=Decimal("14600"),
    standard_deduction_hoh=Decimal("21900"),
    standard_deduction_qw=Decimal("29200"),
    additional_deduction_65_blind=Decimal("1550"),
    qbi_threshold_single=Decimal("191950"),
    qbi_threshold_mfj=Decimal("383900"),
    qbi_phaseout=Decimal("50000"),
    ltcg_0_threshold_single=Decimal("47025"),
    ltcg_0_threshold_mfj=Decimal("94050"),
    ltcg_15_threshold_single=Decimal("518900"),
    ltcg_15_threshold_mfj=Decimal("583750"),
    fpl_1_person=Decimal("14580"),
    fpl_per_additional=Decimal("5140"),
)

# 2025 Configuration (projected - update when IRS releases)
TAX_YEAR_2025 = TaxYearConfig(
    tax_year=2025,
    ss_wage_base=Decimal("176100"),  # Projected
    standard_deduction_single=Decimal("15000"),  # Projected
    standard_deduction_mfj=Decimal("30000"),
    standard_deduction_mfs=Decimal("15000"),
    standard_deduction_hoh=Decimal("22500"),
    standard_deduction_qw=Decimal("30000"),
    additional_deduction_65_blind=Decimal("1600"),
    qbi_threshold_single=Decimal("197300"),  # Projected
    qbi_threshold_mfj=Decimal("394600"),
    qbi_phaseout=Decimal("50000"),
    ltcg_0_threshold_single=Decimal("48350"),
    ltcg_0_threshold_mfj=Decimal("96700"),
    ltcg_15_threshold_single=Decimal("533400"),
    ltcg_15_threshold_mfj=Decimal("600050"),
    fpl_1_person=Decimal("15060"),  # Projected
    fpl_per_additional=Decimal("5380"),
)

TAX_YEAR_CONFIGS = {
    2024: TAX_YEAR_2024,
    2025: TAX_YEAR_2025,
}


def get_tax_year_config(year: int) -> TaxYearConfig:
    """Get configuration for a specific tax year."""
    if year not in TAX_YEAR_CONFIGS:
        raise ValueError(f"No tax configuration for year {year}")
    return TAX_YEAR_CONFIGS[year]
```

---

## Revision 10: Enhance Testing Strategy with Property-Based Tests

### Problem

The current plan uses example-based tests, which miss edge cases. For tax calculations, **property-based testing** would catch:
- Boundary conditions at thresholds
- Monotonicity (more income → more tax)
- Commutativity (order of income sources shouldn't matter)

### Impact

A bug at exactly $191,950 (QBI threshold) would be missed by testing $150k and $250k but caught by property tests that explore the full range.

### Proposed Changes

**File: `tests/agents/personal_tax/test_calculator_properties.py` (new)**

```python
"""Property-based tests for tax calculator invariants."""

import pytest
from decimal import Decimal
from hypothesis import given, assume
from hypothesis import strategies as st

from src.agents.personal_tax.calculator import (
    calculate_qbi_deduction,
    calculate_self_employment_tax,
    QBIComponent,
    FilingStatus,
)


class TestQBIPropertyBased:
    """Property-based tests for QBI calculation invariants."""

    @given(
        qbi=st.decimals(min_value=0, max_value=1000000, places=2),
        taxable_income=st.decimals(min_value=0, max_value=2000000, places=2),
    )
    def test_qbi_deduction_never_exceeds_20_percent(self, qbi, taxable_income):
        """QBI deduction never exceeds 20% of QBI."""
        components = [
            QBIComponent(
                business_name="Test",
                qualified_business_income=qbi,
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=taxable_income,
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        assert result.final_qbi_deduction <= qbi * Decimal("0.20") + Decimal("0.01")

    @given(
        qbi=st.decimals(min_value=1000, max_value=500000, places=2),
        taxable_income=st.decimals(min_value=1000, max_value=500000, places=2),
    )
    def test_qbi_deduction_never_exceeds_taxable_income_limit(self, qbi, taxable_income):
        """QBI deduction never exceeds 20% of taxable income."""
        components = [
            QBIComponent(
                business_name="Test",
                qualified_business_income=qbi,
            ),
        ]
        result = calculate_qbi_deduction(
            components,
            taxable_income=taxable_income,
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )
        limit = taxable_income * Decimal("0.20") + Decimal("0.01")
        assert result.final_qbi_deduction <= limit

    @given(
        income1=st.decimals(min_value=0, max_value=200000, places=2),
        income2=st.decimals(min_value=0, max_value=200000, places=2),
        taxable_income=st.decimals(min_value=100000, max_value=180000, places=2),
    )
    def test_qbi_aggregation_is_additive_below_threshold(self, income1, income2, taxable_income):
        """QBI from multiple sources aggregates correctly below threshold."""
        # Two businesses
        components_separate = [
            QBIComponent(business_name="A", qualified_business_income=income1),
            QBIComponent(business_name="B", qualified_business_income=income2),
        ]
        result_separate = calculate_qbi_deduction(
            components_separate,
            taxable_income=taxable_income,
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )

        # Single business with combined income (below threshold)
        assume(taxable_income < Decimal("191950"))  # Below threshold
        components_combined = [
            QBIComponent(
                business_name="Combined",
                qualified_business_income=income1 + income2
            ),
        ]
        result_combined = calculate_qbi_deduction(
            components_combined,
            taxable_income=taxable_income,
            net_capital_gains=Decimal("0"),
            filing_status=FilingStatus.SINGLE,
        )

        # Below threshold, deductions should match
        diff = abs(result_separate.final_qbi_deduction - result_combined.final_qbi_deduction)
        assert diff < Decimal("1")


class TestSEPropertyBased:
    """Property-based tests for self-employment tax."""

    @given(
        income=st.decimals(min_value=0, max_value=500000, places=2),
    )
    def test_se_tax_always_positive_or_zero(self, income):
        """SE tax is never negative."""
        result = calculate_self_employment_tax(income, FilingStatus.SINGLE)
        assert result.total_se_tax >= Decimal("0")

    @given(
        income=st.decimals(min_value=0, max_value=500000, places=2),
    )
    def test_se_deduction_is_half_of_tax(self, income):
        """SE tax deduction is always 50% of total SE tax."""
        result = calculate_self_employment_tax(income, FilingStatus.SINGLE)
        expected = result.total_se_tax * Decimal("0.5")
        assert abs(result.deductible_portion - expected) < Decimal("0.01")

    @given(
        income1=st.decimals(min_value=1000, max_value=100000, places=2),
        income2=st.decimals(min_value=1000, max_value=100000, places=2),
    )
    def test_se_tax_is_monotonic(self, income1, income2):
        """Higher income always results in equal or higher SE tax."""
        assume(income2 > income1)
        result1 = calculate_self_employment_tax(income1, FilingStatus.SINGLE)
        result2 = calculate_self_employment_tax(income2, FilingStatus.SINGLE)
        assert result2.total_se_tax >= result1.total_se_tax
```

---

## Implementation Order

Given the dependencies and priorities, implement in this order:

### Wave 1 (Critical - Add to existing plans)
1. **Revision 8**: Validation Layer → Add to 04-02-PLAN.md after extraction
2. **Revision 9**: Tax Year Config → Create before 04-03-PLAN.md, reference throughout
3. **Revision 1**: K-1 Basis Management → Add to 04-01-PLAN.md and 04-08-PLAN.md

### Wave 2 (Important - Add to existing plans)
4. **Revision 4**: Prior Year Carryovers → Add to 04-05-PLAN.md and 04-08-PLAN.md
5. **Revision 7**: Estimated Payments → Add to 04-08-PLAN.md
6. **Revision 2**: 1099-B Aggregation → Add to 04-01-PLAN.md and 04-02-PLAN.md

### Wave 3 (Enhancements - Add to relevant plans)
7. **Revision 3**: Iterative QBI → Update 04-06-PLAN.md
8. **Revision 6**: SSTB Classification → Add to 04-06-PLAN.md
9. **Revision 5**: Form 8949 → Add to 04-08-PLAN.md

### Wave 4 (Quality - Add to test plans)
10. **Revision 10**: Property-Based Testing → Add to all calculator test files

---

## Key Architectural Principles

These revisions embody the following principles:

1. **Fail-safe defaults**: When data is missing (basis, carryovers), the system should escalate rather than silently produce incorrect results.

2. **Real-world data handling**: Broker statements have thousands of transactions. Handle this efficiently instead of naively processing each one.

3. **Circular dependency resolution**: The iterative QBI calculation handles the mathematical reality that deductions affect their own inputs.

4. **Centralized configuration**: Tax year parameters change annually. Scattering magic numbers creates maintenance nightmares.

5. **Defense in depth**: Validation at extraction prevents garbage-in-garbage-out at calculation time.

---

*Revisions document created: 2026-01-25*
