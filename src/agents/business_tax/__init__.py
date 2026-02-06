"""Business tax agent module for S-Corporation (Form 1120-S) returns.

This module provides Pydantic data models for the Business Tax Agent:
- Form1120SResult: Complete 1120-S computation result
- ScheduleK: Pro-rata share items (Boxes 1-17)
- ScheduleL: Balance sheet per books with beginning/ending columns
- ShareholderInfo: Shareholder data for K-1 generation
- TrialBalance / TrialBalanceEntry: General ledger account structures
- ScheduleKLine / ScheduleLLine: Individual line items

Shareholder basis tracking (Form 7203):
- BasisAdjustmentInputs: Frozen dataclass for year's adjustment items
- BasisResult: Computed basis result with allowed/suspended losses
- calculate_shareholder_basis: IRS ordering rule engine

Trial balance parsing and GL-to-1120S mapping:
- parse_excel_trial_balance: Parse Excel bytes into TrialBalance
- map_gl_to_1120s: Map GL accounts to 1120-S lines with confidence
- aggregate_mapped_amounts: Sum mapped amounts by form line
- GLMapping: Single account-to-line mapping with confidence
- DEFAULT_GL_MAPPING: Pattern-to-line mapping dictionary

1120-S tax computation:
- compute_page1: Page 1 income/deductions -> ordinary business income
- compute_schedule_k: Shareholder pro-rata share items (Boxes 1-17)
- compute_schedule_l: Balance sheet per books (beginning/ending)
- compute_schedule_m1: Book-to-tax income reconciliation
- compute_schedule_m2: AAA (Accumulated Adjustments Account) analysis
- Page1Result / ScheduleM1Result / ScheduleM2Result: Computation result dataclasses

K-1 allocation and handoff protocol:
- allocate_k1_item: Pro-rata allocation of single Schedule K line item
- allocate_k1s: Full Schedule K allocation to all shareholders
- generate_k1_for_handoff: Create validated FormK1 from allocated amounts
- serialize_k1_artifact: Serialize FormK1 to JSON for inter-agent handoff
- deserialize_k1_artifact: Deserialize JSON back to FormK1
"""

from src.agents.business_tax.calculator import (
    Page1Result,
    ScheduleM1Result,
    ScheduleM2Result,
    compute_page1,
    compute_schedule_k,
    compute_schedule_l,
    compute_schedule_m1,
    compute_schedule_m2,
)
from src.agents.business_tax.basis import (
    BasisAdjustmentInputs,
    BasisResult,
    calculate_shareholder_basis,
)
from src.agents.business_tax.handoff import (
    allocate_k1_item,
    allocate_k1s,
    deserialize_k1_artifact,
    generate_k1_for_handoff,
    serialize_k1_artifact,
)
from src.agents.business_tax.models import (
    Form1120SResult,
    ScheduleK,
    ScheduleKLine,
    ScheduleL,
    ScheduleLLine,
    ShareholderInfo,
    TrialBalance,
    TrialBalanceEntry,
)
from src.agents.business_tax.trial_balance import (
    DEFAULT_GL_MAPPING,
    GLMapping,
    aggregate_mapped_amounts,
    map_gl_to_1120s,
    parse_excel_trial_balance,
)

__all__ = [
    # Core result
    "Form1120SResult",
    # Schedules
    "ScheduleK",
    "ScheduleKLine",
    "ScheduleL",
    "ScheduleLLine",
    # Shareholder
    "ShareholderInfo",
    # Trial balance
    "TrialBalance",
    "TrialBalanceEntry",
    # Basis tracking
    "BasisAdjustmentInputs",
    "BasisResult",
    "calculate_shareholder_basis",
    # Trial balance parsing & mapping
    "DEFAULT_GL_MAPPING",
    "GLMapping",
    "aggregate_mapped_amounts",
    "map_gl_to_1120s",
    "parse_excel_trial_balance",
    # 1120-S calculator
    "Page1Result",
    "ScheduleM1Result",
    "ScheduleM2Result",
    "compute_page1",
    "compute_schedule_k",
    "compute_schedule_l",
    "compute_schedule_m1",
    "compute_schedule_m2",
    # K-1 allocation & handoff
    "allocate_k1_item",
    "allocate_k1s",
    "generate_k1_for_handoff",
    "serialize_k1_artifact",
    "deserialize_k1_artifact",
]
