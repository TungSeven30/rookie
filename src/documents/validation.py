"""Document validation for extracted tax form data.

This module provides validation logic to catch extraction errors and data
inconsistencies before calculations. Validators check individual documents
and cross-document consistency.

Example:
    >>> from src.documents.validation import DocumentValidator
    >>> validator = DocumentValidator()
    >>> result = validator.validate_k1(k1_data)
    >>> if not result.is_valid:
    ...     print(f"Errors: {result.errors}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING

from src.tax.year_config import get_tax_year_config

if TYPE_CHECKING:
    from src.documents.models import Form1099B, FormK1, W2Data


@dataclass
class ValidationResult:
    """Result of document validation.

    Attributes:
        is_valid: True if no errors were found.
        errors: List of critical errors that must be resolved.
        warnings: List of potential issues that should be reviewed.
        corrections_applied: List of auto-corrections made during validation.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    corrections_applied: list[str] = field(default_factory=list)


class DocumentValidator:
    """Validate extracted document data for consistency and accuracy.

    This validator checks for common extraction errors and data inconsistencies
    that could cause incorrect tax calculations. Use this after extraction but
    before feeding data into tax calculators.

    Example:
        >>> validator = DocumentValidator()
        >>> result = validator.validate_w2(w2_data)
        >>> if result.warnings:
        ...     print(f"Review these issues: {result.warnings}")
    """

    SS_TAX_RATE = Decimal("0.062")
    MEDICARE_TAX_RATE = Decimal("0.0145")

    def validate_w2(self, w2: "W2Data", tax_year: int = 2024) -> ValidationResult:
        """Validate W-2 data for consistency.

        Checks:
        - Federal withholding doesn't exceed wages
        - Social Security wages don't exceed the annual cap
        - Social Security tax is approximately 6.2% of SS wages
        - Medicare tax is approximately 1.45% of Medicare wages

        Args:
            w2: W2Data model to validate.
            tax_year: Tax year for Social Security wage base checks.

        Returns:
            ValidationResult with any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []
        ss_wage_cap = get_tax_year_config(tax_year).ss_wage_base

        # Federal withholding shouldn't exceed wages
        if w2.federal_tax_withheld and w2.wages_tips_compensation:
            if w2.federal_tax_withheld > w2.wages_tips_compensation:
                errors.append(
                    f"Federal withholding ({w2.federal_tax_withheld}) "
                    f"exceeds wages ({w2.wages_tips_compensation})"
                )

        # Social Security wages have a cap
        if w2.social_security_wages and w2.social_security_wages > ss_wage_cap:
            warnings.append(
                f"Social Security wages ({w2.social_security_wages}) "
                f"exceed {tax_year} cap ({ss_wage_cap})"
            )

        # SS tax should be ~6.2% of SS wages (with tolerance for rounding)
        if w2.social_security_wages and w2.social_security_tax:
            capped_wages = min(w2.social_security_wages, ss_wage_cap)
            expected_ss_tax = capped_wages * self.SS_TAX_RATE
            tolerance = Decimal("10")
            if abs(w2.social_security_tax - expected_ss_tax) > tolerance:
                warnings.append(
                    f"Social Security tax ({w2.social_security_tax}) "
                    f"doesn't match expected ({expected_ss_tax:.2f} at 6.2%)"
                )

        # Medicare tax should be ~1.45% of Medicare wages
        if w2.medicare_wages and w2.medicare_tax:
            expected_medicare_tax = w2.medicare_wages * self.MEDICARE_TAX_RATE
            tolerance = Decimal("10")
            if abs(w2.medicare_tax - expected_medicare_tax) > tolerance:
                warnings.append(
                    f"Medicare tax ({w2.medicare_tax}) "
                    f"doesn't match expected ({expected_medicare_tax:.2f} at 1.45%)"
                )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_k1(self, k1: "FormK1") -> ValidationResult:
        """Validate K-1 data for consistency.

        Checks:
        - Ownership percentage is between 0 and 100
        - Entity type is valid (partnership or s_corp)
        - S-corps don't have guaranteed payments (Box 4)
        - Large losses trigger basis verification warning

        Args:
            k1: FormK1 model to validate.

        Returns:
            ValidationResult with any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Ownership percentage should be 0-100
        if k1.ownership_percentage is not None:
            if not (Decimal("0") <= k1.ownership_percentage <= Decimal("100")):
                errors.append(f"Invalid ownership percentage: {k1.ownership_percentage}%")

        # Entity type validation
        if k1.entity_type not in ("partnership", "s_corp"):
            errors.append(f"Invalid entity type: {k1.entity_type}")

        # S-corps shouldn't have guaranteed payments (Box 4)
        if k1.entity_type == "s_corp":
            if k1.guaranteed_payments and k1.guaranteed_payments != Decimal("0"):
                warnings.append(
                    f"S-corp K-1 has guaranteed payments ({k1.guaranteed_payments}) - "
                    "verify this is correct (S-corps typically don't have GP)"
                )

        # K-1 with huge losses relative to income is suspicious
        total_income = (k1.ordinary_business_income or Decimal("0")) + (
            k1.net_rental_real_estate or Decimal("0")
        )
        if total_income < Decimal("-100000"):
            warnings.append(
                f"Large K-1 loss ({total_income}) - verify basis and at-risk limitations"
            )

        # Check if basis escalation might be needed
        if k1.requires_basis_escalation:
            warnings.append(
                "K-1 shows significant loss but no capital account ending balance - "
                "gather basis documentation to verify loss deductibility"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_1099b(self, form: "Form1099B") -> ValidationResult:
        """Validate 1099-B transaction data.

        Checks:
        - Proceeds are positive
        - Basis reported flag matches cost_basis presence
        - Transaction isn't marked both short-term and long-term
        - Wash sale loss doesn't exceed the actual loss

        Args:
            form: Form1099B model to validate.

        Returns:
            ValidationResult with any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Proceeds must be positive
        if form.proceeds is not None and form.proceeds <= Decimal("0"):
            errors.append(f"Invalid proceeds: {form.proceeds}")

        # If cost basis reported to IRS, it should exist
        if form.basis_reported_to_irs and form.cost_basis is None:
            warnings.append(
                "Basis reported to IRS but not extracted - verify document"
            )

        # Can't be both short-term and long-term
        if form.is_short_term and form.is_long_term:
            errors.append("Transaction marked as both short-term and long-term")

        # Wash sale shouldn't exceed loss
        if (
            form.cost_basis is not None
            and form.proceeds is not None
            and form.proceeds < form.cost_basis
        ):
            loss = form.cost_basis - form.proceeds
            if form.wash_sale_loss_disallowed and form.wash_sale_loss_disallowed > loss:
                errors.append(
                    f"Wash sale disallowed ({form.wash_sale_loss_disallowed}) "
                    f"exceeds loss ({loss})"
                )

        # Check if basis escalation needed (cost_basis missing for non-reported)
        if form.requires_basis_escalation:
            warnings.append(
                f"Transaction '{form.description}' has no cost basis and basis not "
                "reported to IRS - gather purchase records"
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_cross_document(
        self,
        w2s: "list[W2Data]",
        k1s: "list[FormK1]",
        forms_1099: list,
    ) -> ValidationResult:
        """Cross-document consistency validation.

        Checks that all documents appear to be for the same taxpayer by
        comparing the last 4 digits of TINs across all documents.

        Args:
            w2s: List of W2Data models.
            k1s: List of FormK1 models.
            forms_1099: List of 1099 form models (INT, DIV, B, etc.).

        Returns:
            ValidationResult with any errors or warnings.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # Collect last 4 digits of TINs from all documents
        tins: set[str] = set()

        for w2 in w2s:
            if w2.employee_ssn:
                tin_last4 = w2.employee_ssn.replace("-", "")[-4:]
                tins.add(tin_last4)

        for k1 in k1s:
            if k1.recipient_tin:
                tin_last4 = k1.recipient_tin.replace("-", "")[-4:]
                tins.add(tin_last4)

        for form in forms_1099:
            if hasattr(form, "recipient_tin") and form.recipient_tin:
                tin_last4 = form.recipient_tin.replace("-", "")[-4:]
                tins.add(tin_last4)

        if len(tins) > 1:
            warnings.append(
                f"Multiple TIN last-4 found across documents: {tins}. "
                "Verify all documents are for the same taxpayer."
            )

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
