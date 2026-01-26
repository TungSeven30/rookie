"""Tax year-specific constants and thresholds.

This module centralizes tax year-specific values like wage bases, deduction amounts,
and rate thresholds to avoid hardcoding values throughout the codebase.

Example:
    >>> from src.tax.year_config import get_tax_year_config
    >>> config = get_tax_year_config(2024)
    >>> print(f"SS wage base: {config.ss_wage_base}")
    SS wage base: 168600
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class TaxYearConfig:
    """Tax year-specific constants and thresholds.

    All monetary values are Decimal for precision in tax calculations.
    This dataclass is frozen to prevent accidental modification.

    Attributes:
        tax_year: The tax year these values apply to.
        ss_wage_base: Social Security wage base limit.
        ss_rate_employee: Employee Social Security rate (typically 6.2%).
        ss_rate_employer: Employer Social Security rate (typically 6.2%).
        medicare_rate: Medicare tax rate (typically 1.45%).
        additional_medicare_threshold_single: Threshold for additional Medicare (single).
        additional_medicare_threshold_mfj: Threshold for additional Medicare (MFJ).
        additional_medicare_rate: Additional Medicare rate (typically 0.9%).
    """

    tax_year: int

    # Social Security / Medicare
    ss_wage_base: Decimal
    ss_rate_employee: Decimal = Decimal("0.062")
    ss_rate_employer: Decimal = Decimal("0.062")
    medicare_rate: Decimal = Decimal("0.0145")
    additional_medicare_threshold_single: Decimal = Decimal("200000")
    additional_medicare_threshold_mfj: Decimal = Decimal("250000")
    additional_medicare_threshold_mfs: Decimal = Decimal("125000")
    additional_medicare_rate: Decimal = Decimal("0.009")

    # Self-employment tax (combined employer + employee rates)
    se_ss_rate: Decimal = Decimal("0.124")  # 12.4% (6.2% x 2)
    se_medicare_rate: Decimal = Decimal("0.029")  # 2.9% (1.45% x 2)
    se_net_earnings_factor: Decimal = Decimal("0.9235")  # 92.35% of net SE income

    # Standard deductions
    standard_deduction_single: Decimal = Decimal("0")
    standard_deduction_mfj: Decimal = Decimal("0")
    standard_deduction_mfs: Decimal = Decimal("0")
    standard_deduction_hoh: Decimal = Decimal("0")
    standard_deduction_qw: Decimal = Decimal("0")
    additional_deduction_65_blind: Decimal = Decimal("0")

    # QBI (Qualified Business Income) deduction thresholds
    qbi_threshold_single: Decimal = Decimal("0")
    qbi_threshold_mfj: Decimal = Decimal("0")
    qbi_phaseout: Decimal = Decimal("50000")  # Phaseout range

    # Capital gains brackets
    ltcg_0_threshold_single: Decimal = Decimal("0")
    ltcg_0_threshold_mfj: Decimal = Decimal("0")
    ltcg_15_threshold_single: Decimal = Decimal("0")
    ltcg_15_threshold_mfj: Decimal = Decimal("0")

    # Capital loss limit
    capital_loss_limit: Decimal = Decimal("3000")
    capital_loss_limit_mfs: Decimal = Decimal("1500")

    # Premium Tax Credit (ACA) - Federal Poverty Level
    fpl_1_person: Decimal = Decimal("0")
    fpl_per_additional: Decimal = Decimal("0")

    # Passive Activity Loss limits
    pal_allowance: Decimal = Decimal("25000")
    pal_phaseout_start: Decimal = Decimal("100000")
    pal_phaseout_end: Decimal = Decimal("150000")

    @property
    def se_tax_deduction_rate(self) -> Decimal:
        """Deductible portion of SE tax (50%)."""
        return Decimal("0.5")


# 2024 Configuration - IRS published values
TAX_YEAR_2024 = TaxYearConfig(
    tax_year=2024,
    ss_wage_base=Decimal("168600"),
    # Standard deductions
    standard_deduction_single=Decimal("14600"),
    standard_deduction_mfj=Decimal("29200"),
    standard_deduction_mfs=Decimal("14600"),
    standard_deduction_hoh=Decimal("21900"),
    standard_deduction_qw=Decimal("29200"),
    additional_deduction_65_blind=Decimal("1550"),
    # QBI thresholds
    qbi_threshold_single=Decimal("191950"),
    qbi_threshold_mfj=Decimal("383900"),
    qbi_phaseout=Decimal("50000"),
    # Capital gains (0%/15%/20% brackets)
    ltcg_0_threshold_single=Decimal("47025"),
    ltcg_0_threshold_mfj=Decimal("94050"),
    ltcg_15_threshold_single=Decimal("518900"),
    ltcg_15_threshold_mfj=Decimal("583750"),
    # ACA Federal Poverty Level (2024 guidelines)
    fpl_1_person=Decimal("14580"),
    fpl_per_additional=Decimal("5140"),
)

# 2025 Configuration - projected values (update when IRS releases official numbers)
TAX_YEAR_2025 = TaxYearConfig(
    tax_year=2025,
    ss_wage_base=Decimal("176100"),
    # Standard deductions (estimated)
    standard_deduction_single=Decimal("15000"),
    standard_deduction_mfj=Decimal("30000"),
    standard_deduction_mfs=Decimal("15000"),
    standard_deduction_hoh=Decimal("22500"),
    standard_deduction_qw=Decimal("30000"),
    additional_deduction_65_blind=Decimal("1600"),
    # QBI thresholds (estimated)
    qbi_threshold_single=Decimal("197300"),
    qbi_threshold_mfj=Decimal("394600"),
    qbi_phaseout=Decimal("50000"),
    # Capital gains (estimated)
    ltcg_0_threshold_single=Decimal("48350"),
    ltcg_0_threshold_mfj=Decimal("96700"),
    ltcg_15_threshold_single=Decimal("533400"),
    ltcg_15_threshold_mfj=Decimal("600050"),
    # ACA Federal Poverty Level (estimated)
    fpl_1_person=Decimal("15060"),
    fpl_per_additional=Decimal("5380"),
)

# Registry of available tax year configurations
TAX_YEAR_CONFIGS: dict[int, TaxYearConfig] = {
    2024: TAX_YEAR_2024,
    2025: TAX_YEAR_2025,
}


def get_tax_year_config(year: int) -> TaxYearConfig:
    """Get configuration for a specific tax year.

    Args:
        year: The tax year (e.g., 2024).

    Returns:
        TaxYearConfig for the specified year.

    Raises:
        ValueError: If no configuration exists for the requested year.

    Example:
        >>> config = get_tax_year_config(2024)
        >>> print(config.ss_wage_base)
        168600
    """
    if year not in TAX_YEAR_CONFIGS:
        available = sorted(TAX_YEAR_CONFIGS.keys())
        raise ValueError(
            f"No tax configuration for year {year}. Available years: {available}"
        )
    return TAX_YEAR_CONFIGS[year]
