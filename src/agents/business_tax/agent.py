"""Business Tax Agent for orchestrating S-Corporation (Form 1120-S) workflow.

This module provides the main agent entry point that coordinates:
- Trial balance parsing from Excel bytes
- GL-to-1120S line mapping with confidence scoring
- Page 1 income/deductions computation
- Schedule K shareholder pro-rata share items
- K-1 allocation to shareholders
- Shareholder basis tracking (Form 7203)
- Schedule L balance sheet, M-1, M-2
- Output generation (Drake worksheet, K-1/basis worksheets, preparer notes)
- K-1 handoff data for Personal Tax Agent consumption

Example:
    >>> from src.agents.business_tax.agent import BusinessTaxAgent
    >>> agent = BusinessTaxAgent(output_dir=Path("/output"))
    >>> result = await agent.process(
    ...     entity_name="Acme Corp",
    ...     entity_ein="12-3456789",
    ...     tax_year=2024,
    ...     trial_balance_bytes=tb_bytes,
    ...     shareholders=shareholders,
    ...     session=session,
    ... )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

from src.agents.business_tax.basis import (
    BasisAdjustmentInputs,
    BasisResult,
    calculate_shareholder_basis,
)
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
from src.agents.business_tax.handoff import (
    allocate_k1s,
    generate_k1_for_handoff,
)
from src.agents.business_tax.models import (
    Form1120SResult,
    ScheduleK,
    ScheduleL,
    ShareholderInfo,
    TrialBalance,
)
from src.agents.business_tax.output import (
    generate_1120s_drake_worksheet,
    generate_basis_worksheets,
    generate_business_preparer_notes,
    generate_k1_worksheets,
)
from src.agents.business_tax.trial_balance import (
    GLMapping,
    aggregate_mapped_amounts,
    map_gl_to_1120s,
    parse_excel_trial_balance,
)
from src.core.logging import get_logger
from src.documents.models import ConfidenceLevel, FormK1

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.models.task import Task

logger = get_logger(__name__)

ZERO = Decimal("0")


class EscalationRequired(Exception):
    """Raised when agent needs human intervention.

    Attributes:
        reasons: List of reasons requiring escalation.
        result: Optional partial result for CPA review.
    """

    def __init__(
        self,
        reasons: list[str],
        result: "BusinessTaxResult | None" = None,
    ) -> None:
        """Initialize with escalation reasons.

        Args:
            reasons: List of reasons requiring human attention.
            result: Optional partial result payload for CPA review.
        """
        self.reasons = reasons
        self.result = result
        super().__init__(f"Escalation required: {', '.join(reasons)}")


@dataclass
class BusinessTaxResult:
    """Result of business tax agent execution.

    Attributes:
        drake_worksheet_path: Path to 1120-S Drake worksheet Excel file.
        k1_worksheet_path: Path to K-1 worksheets Excel file.
        basis_worksheet_path: Path to basis worksheets Excel file.
        preparer_notes_path: Path to preparer notes Markdown file.
        form_result: Computed Form 1120-S data.
        k1_handoff_data: Generated K-1s for Personal Tax Agent handoff.
        basis_results: Per-shareholder basis computation results.
        escalations: List of escalation reasons.
        overall_confidence: Aggregate confidence level (HIGH/MEDIUM/LOW).
    """

    drake_worksheet_path: Path
    k1_worksheet_path: Path
    basis_worksheet_path: Path
    preparer_notes_path: Path
    form_result: Form1120SResult
    k1_handoff_data: list[FormK1]
    basis_results: list[BasisResult]
    escalations: list[str]
    overall_confidence: str


class BusinessTaxAgent:
    """Business Tax Agent for S-Corporation (Form 1120-S) returns.

    Orchestrates the complete 1120-S preparation workflow:
    1. Parse trial balance from Excel bytes
    2. Map GL accounts to 1120-S lines
    3. Aggregate mapped amounts
    4. Compute Page 1 (income/deductions)
    5. Compute Schedule K (pro-rata share items)
    6. Allocate K-1s to shareholders
    7. Calculate shareholder basis
    8. Compute Schedule L (balance sheet)
    9. Compute Schedule M-1 / M-2
    10. Build Form1120SResult
    11. Check reasonable compensation
    12. Generate outputs and K-1 handoff data

    Attributes:
        output_dir: Directory for output files.
        escalations: List of accumulated escalation reasons.
    """

    def __init__(self, output_dir: Path) -> None:
        """Initialize Business Tax Agent.

        Args:
            output_dir: Directory where output files will be written.
        """
        self.output_dir = output_dir
        self.escalations: list[str] = []

    async def process(
        self,
        entity_name: str,
        entity_ein: str,
        tax_year: int,
        trial_balance_bytes: bytes,
        shareholders: list[ShareholderInfo],
        session: "AsyncSession",
        prior_year_schedule_l: ScheduleL | None = None,
        prior_year_aaa: Decimal = ZERO,
        separately_stated: dict[str, Decimal] | None = None,
    ) -> BusinessTaxResult:
        """Process S-Corporation business tax return.

        Executes the complete 1120-S workflow from trial balance to outputs.

        Args:
            entity_name: S-Corporation name.
            entity_ein: Entity EIN (XX-XXXXXXX).
            tax_year: Tax year to process.
            trial_balance_bytes: Raw Excel bytes of trial balance.
            shareholders: List of shareholder information.
            session: Database session (for future use).
            prior_year_schedule_l: Prior year balance sheet (None for first year).
            prior_year_aaa: Prior year AAA balance for Schedule M-2.
            separately_stated: Optional separately stated items for Schedule K.

        Returns:
            BusinessTaxResult with all outputs and metadata.
        """
        logger.info(
            "business_tax_agent_start",
            entity_name=entity_name,
            entity_ein=entity_ein,
            tax_year=tax_year,
            shareholder_count=len(shareholders),
        )

        # Reset escalations for this run
        self.escalations = []

        # Step 1: Parse trial balance from Excel bytes
        logger.info("step_1_parse_trial_balance")
        trial_balance = parse_excel_trial_balance(
            trial_balance_bytes,
            entity_name=entity_name,
        )
        if not trial_balance.is_balanced:
            self.escalations.append(
                f"Trial balance is NOT balanced: "
                f"debits={trial_balance.total_debits}, "
                f"credits={trial_balance.total_credits}"
            )
            logger.warning(
                "trial_balance_unbalanced",
                total_debits=str(trial_balance.total_debits),
                total_credits=str(trial_balance.total_credits),
            )

        # Step 2: Map GL accounts to 1120-S lines
        logger.info("step_2_map_gl_accounts", entry_count=len(trial_balance.entries))
        mappings: list[GLMapping] = map_gl_to_1120s(trial_balance)
        for mapping in mappings:
            if mapping.confidence == ConfidenceLevel.LOW:
                self.escalations.append(
                    f"Low confidence GL mapping: '{mapping.account_name}' -> "
                    f"{mapping.form_line} ({mapping.reasoning})"
                )

        # Step 3: Aggregate mapped amounts
        logger.info("step_3_aggregate_amounts")
        mapped_amounts: dict[str, Decimal] = aggregate_mapped_amounts(
            trial_balance, mappings
        )

        # Step 4: Compute Page 1 (income/deductions)
        logger.info("step_4_compute_page1")
        page1: Page1Result = compute_page1(mapped_amounts)

        # Step 5: Compute Schedule K
        logger.info("step_5_compute_schedule_k")
        schedule_k: ScheduleK = compute_schedule_k(page1, separately_stated)
        if schedule_k.foreign_transactions != ZERO:
            self.escalations.append(
                "Foreign transactions detected on Schedule K "
                f"(${schedule_k.foreign_transactions}). Requires additional review."
            )
        if schedule_k.amt_items != ZERO:
            self.escalations.append(
                "AMT items detected on Schedule K "
                f"(${schedule_k.amt_items}). Requires additional review."
            )

        # Step 6: Allocate K-1s to shareholders
        logger.info("step_6_allocate_k1s", shareholder_count=len(shareholders))
        ownership_sum = sum(sh.ownership_pct for sh in shareholders)
        if ownership_sum != Decimal("100"):
            self.escalations.append(
                f"Ownership percentages sum to {ownership_sum}%, expected 100%"
            )
        # Check for mid-year ownership changes (v1: not supported)
        # In v1, we assume all shareholders are full-year shareholders
        allocated_k1s: list[dict[str, Decimal]] = []
        if ownership_sum == Decimal("100"):
            allocated_k1s = allocate_k1s(schedule_k, shareholders)
        else:
            # Allocate anyway for partial results, but already escalated
            try:
                allocated_k1s = allocate_k1s(schedule_k, shareholders)
            except ValueError:
                # If allocate_k1s raises on non-100% ownership, create empty dicts
                allocated_k1s = [{} for _ in shareholders]

        # Step 7: Calculate shareholder basis for each shareholder
        logger.info("step_7_calculate_basis")
        basis_results: list[BasisResult] = []
        for i, (sh, alloc) in enumerate(zip(shareholders, allocated_k1s)):
            basis_inputs = _build_basis_inputs(alloc, schedule_k, sh)
            basis = calculate_shareholder_basis(
                beginning_stock_basis=sh.beginning_stock_basis,
                beginning_debt_basis=sh.beginning_debt_basis,
                adjustments=basis_inputs,
                prior_suspended_losses=sh.suspended_losses,
            )
            basis_results.append(basis)
            logger.info(
                "shareholder_basis_computed",
                shareholder=sh.name,
                ending_stock_basis=str(basis.ending_stock_basis),
                ending_debt_basis=str(basis.ending_debt_basis),
                suspended_losses=str(basis.suspended_losses),
            )

        # Step 8: Compute Schedule L
        logger.info("step_8_compute_schedule_l")
        schedule_l: ScheduleL = compute_schedule_l(
            mapped_amounts=mapped_amounts,
            prior_year_schedule_l=prior_year_schedule_l,
            current_year_net_income=page1.ordinary_business_income,
            current_year_distributions=schedule_k.distributions,
        )
        if not schedule_l.is_balanced_ending:
            self.escalations.append(
                "Schedule L ending balance sheet is NOT balanced: "
                f"assets={schedule_l.total_assets_ending}, "
                f"liabilities+equity={schedule_l.total_liabilities_equity_ending}"
            )

        # Step 9: Compute Schedule M-1
        logger.info("step_9_compute_schedule_m1")
        # Book income = ordinary business income + tax-exempt income
        book_income = page1.ordinary_business_income + (
            schedule_k.tax_exempt_interest
            + schedule_k.other_tax_exempt_income
        )
        schedule_m1: ScheduleM1Result = compute_schedule_m1(
            book_income=book_income,
            tax_income=page1.ordinary_business_income,
            tax_exempt_income=(
                schedule_k.tax_exempt_interest
                + schedule_k.other_tax_exempt_income
            ),
            nondeductible_expenses=schedule_k.nondeductible_expenses,
        )

        # Step 10: Compute Schedule M-2
        logger.info("step_10_compute_schedule_m2")
        separately_stated_net = (
            schedule_k.interest_income
            + schedule_k.dividends
            + schedule_k.royalties
            + schedule_k.net_short_term_capital_gain
            + schedule_k.net_long_term_capital_gain
            + schedule_k.net_section_1231_gain
            + schedule_k.other_income_loss
            + schedule_k.net_rental_real_estate
            + schedule_k.other_rental_income
        )
        schedule_m2: ScheduleM2Result = compute_schedule_m2(
            aaa_beginning=prior_year_aaa,
            ordinary_income=schedule_k.ordinary_income,
            separately_stated_net=separately_stated_net,
            nondeductible_expenses=schedule_k.nondeductible_expenses,
            distributions=schedule_k.distributions,
        )

        # Step 11: Check reasonable compensation
        logger.info("step_11_check_reasonable_compensation")
        for sh in shareholders:
            if (
                sh.is_officer
                and sh.officer_compensation == ZERO
                and schedule_k.distributions > ZERO
            ):
                self.escalations.append(
                    f"Officer '{sh.name}' has zero compensation but entity "
                    f"has distributions of ${schedule_k.distributions}. "
                    "Review reasonable compensation requirement."
                )

        # Step 12: Build Form1120SResult
        logger.info("step_12_build_form_result")
        form_result = Form1120SResult(
            entity_name=entity_name,
            entity_ein=entity_ein,
            tax_year=tax_year,
            gross_receipts=page1.gross_receipts,
            cost_of_goods_sold=page1.cost_of_goods_sold,
            gross_profit=page1.gross_profit,
            total_income=page1.total_income,
            total_deductions=page1.total_deductions,
            ordinary_business_income=page1.ordinary_business_income,
            schedule_k=schedule_k,
            schedule_l=schedule_l,
            shareholders=shareholders,
            escalations=list(self.escalations),
            confidence=self._determine_confidence(mappings),
        )

        # Step 13: Generate outputs
        logger.info("step_13_generate_outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        drake_path = self.output_dir / f"1120s_drake_{tax_year}.xlsx"
        generate_1120s_drake_worksheet(
            result=form_result,
            output_path=drake_path,
            schedule_m1=schedule_m1,
            schedule_m2=schedule_m2,
        )

        k1_path = self.output_dir / f"k1_worksheets_{tax_year}.xlsx"
        generate_k1_worksheets(
            entity_name=entity_name,
            entity_ein=entity_ein,
            tax_year=tax_year,
            shareholders=shareholders,
            allocated_k1s=allocated_k1s,
            basis_results=basis_results,
            output_path=k1_path,
        )

        basis_path = self.output_dir / f"basis_worksheets_{tax_year}.xlsx"
        generate_basis_worksheets(
            entity_name=entity_name,
            tax_year=tax_year,
            shareholders=shareholders,
            basis_results=basis_results,
            output_path=basis_path,
        )

        notes_path = self.output_dir / f"preparer_notes_{tax_year}.md"
        generate_business_preparer_notes(
            result=form_result,
            basis_results=basis_results,
            escalations=self.escalations,
            output_path=notes_path,
        )

        # Step 14: Generate K-1 handoff data (FormK1 instances)
        logger.info("step_14_generate_k1_handoff")
        k1_handoff_data: list[FormK1] = []
        for sh, alloc, basis in zip(shareholders, allocated_k1s, basis_results):
            form_k1 = generate_k1_for_handoff(
                entity_name=entity_name,
                entity_ein=entity_ein,
                tax_year=tax_year,
                shareholder=sh,
                allocated_amounts=alloc,
                basis_result=basis,
            )
            k1_handoff_data.append(form_k1)

        # Step 15: Return result
        overall_confidence = self._determine_confidence(mappings).value
        result = BusinessTaxResult(
            drake_worksheet_path=drake_path,
            k1_worksheet_path=k1_path,
            basis_worksheet_path=basis_path,
            preparer_notes_path=notes_path,
            form_result=form_result,
            k1_handoff_data=k1_handoff_data,
            basis_results=basis_results,
            escalations=list(self.escalations),
            overall_confidence=overall_confidence,
        )

        logger.info(
            "business_tax_agent_complete",
            entity_name=entity_name,
            tax_year=tax_year,
            escalation_count=len(self.escalations),
            overall_confidence=overall_confidence,
        )

        return result

    def _determine_confidence(
        self,
        mappings: list[GLMapping],
    ) -> ConfidenceLevel:
        """Determine overall confidence from GL mapping results.

        Returns LOW if any LOW, MEDIUM if any MEDIUM, HIGH otherwise.

        Args:
            mappings: List of GL mappings with confidence levels.

        Returns:
            Overall ConfidenceLevel.
        """
        if not mappings:
            return ConfidenceLevel.HIGH

        confidences = [m.confidence for m in mappings]
        if ConfidenceLevel.LOW in confidences:
            return ConfidenceLevel.LOW
        if ConfidenceLevel.MEDIUM in confidences:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH


def _build_basis_inputs(
    allocated_amounts: dict[str, Decimal],
    schedule_k: ScheduleK,
    shareholder: ShareholderInfo,
) -> BasisAdjustmentInputs:
    """Build BasisAdjustmentInputs from allocated K-1 amounts.

    Separates income from loss items and maps allocated amounts to the
    BasisAdjustmentInputs fields per IRS ordering rules.

    Args:
        allocated_amounts: K-1 field -> Decimal for this shareholder.
        schedule_k: Entity-level Schedule K (for tax-exempt, nondeductible).
        shareholder: Shareholder info.

    Returns:
        Frozen BasisAdjustmentInputs for calculate_shareholder_basis.
    """
    # Ordinary income/loss
    ordinary = allocated_amounts.get("ordinary_business_income", ZERO)
    ordinary_income = max(ordinary, ZERO)
    ordinary_loss = abs(min(ordinary, ZERO))

    # Separately stated income items (positive amounts from Boxes 2-10)
    sep_income_fields = [
        "net_rental_real_estate",
        "other_rental_income",
        "interest_income",
        "dividend_income",
        "royalties",
        "net_short_term_capital_gain",
        "net_long_term_capital_gain",
        "net_section_1231_gain",
        "other_income",
    ]
    separately_stated_income = ZERO
    separately_stated_losses = ZERO
    for field_name in sep_income_fields:
        val = allocated_amounts.get(field_name, ZERO)
        if val > ZERO:
            separately_stated_income += val
        elif val < ZERO:
            separately_stated_losses += abs(val)

    # Section 179 is a loss/deduction item
    section_179 = allocated_amounts.get("section_179_deduction", ZERO)
    separately_stated_losses += section_179

    # Charitable contributions are deductions (reduce basis like losses)
    other_deductions = allocated_amounts.get("other_deductions", ZERO)
    separately_stated_losses += other_deductions

    # Tax-exempt income (allocated pro-rata based on ownership)
    pct_fraction = shareholder.ownership_pct / Decimal("100")
    tax_exempt = (
        schedule_k.tax_exempt_interest + schedule_k.other_tax_exempt_income
    ) * pct_fraction

    # Nondeductible expenses (allocated pro-rata)
    nondeductible = schedule_k.nondeductible_expenses * pct_fraction

    # Distributions (from allocated amounts)
    distributions = allocated_amounts.get("distributions", ZERO)

    return BasisAdjustmentInputs(
        ordinary_income=ordinary_income,
        separately_stated_income=separately_stated_income,
        tax_exempt_income=tax_exempt,
        non_dividend_distributions=distributions,
        nondeductible_expenses=nondeductible,
        ordinary_loss=ordinary_loss,
        separately_stated_losses=separately_stated_losses,
    )


async def business_tax_handler(task: "Task") -> None:
    """Handle business tax task from dispatcher.

    This function is registered with TaskDispatcher for task_type="business_tax".
    Creates a BusinessTaxAgent and demonstrates the dispatch pattern.

    Note: The dispatcher's AgentHandler type takes only Task (no session).
    Full implementation would extract parameters from task metadata.

    Args:
        task: Task to process.
    """
    logger.info(
        "business_tax_handler_invoked",
        task_id=task.id,
        task_type=task.task_type,
    )
    # In a full implementation, this would:
    # 1. Extract trial_balance_bytes, shareholders, etc. from task metadata/artifacts
    # 2. Create a database session
    # 3. Instantiate BusinessTaxAgent and call process()
    # 4. Update task status and create artifacts
    # For now, this stub demonstrates the registration pattern.
    logger.info(
        "business_tax_handler_stub",
        task_id=task.id,
        message="Stub handler - full implementation requires task metadata extraction",
    )
