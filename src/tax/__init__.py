"""Tax calculation utilities and year-specific configurations."""

from src.tax.year_config import (
    TAX_YEAR_2024,
    TAX_YEAR_2025,
    TAX_YEAR_CONFIGS,
    TaxYearConfig,
    get_tax_year_config,
)

__all__ = [
    "TaxYearConfig",
    "TAX_YEAR_2024",
    "TAX_YEAR_2025",
    "TAX_YEAR_CONFIGS",
    "get_tax_year_config",
]
