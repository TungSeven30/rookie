"""Pydantic models for tax document extraction.

This module defines validated data models for common tax forms:
- W2Data: Employee wage and tax statement
- Form1099INT: Interest income
- Form1099DIV: Dividend income
- Form1099NEC: Non-employee compensation

All monetary fields use Decimal for precision.
SSN and EIN fields are validated and formatted consistently.
"""

from __future__ import annotations

import re
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


class DocumentType(str, Enum):
    """Type of tax document."""

    W2 = "W2"
    FORM_1099_INT = "1099-INT"
    FORM_1099_DIV = "1099-DIV"
    FORM_1099_NEC = "1099-NEC"
    UNKNOWN = "UNKNOWN"


class ConfidenceLevel(str, Enum):
    """Extraction confidence level."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def validate_ssn(value: str) -> str:
    """Validate and format SSN.

    Args:
        value: SSN string, with or without dashes/spaces.

    Returns:
        Formatted SSN as XXX-XX-XXXX.

    Raises:
        ValueError: If SSN is not exactly 9 digits after cleaning.
    """
    # Strip all non-digit characters
    digits = re.sub(r"\D", "", value)

    if len(digits) != 9:
        raise ValueError(f"SSN must be exactly 9 digits, got {len(digits)}")

    # Format as XXX-XX-XXXX
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


def validate_ein(value: str) -> str:
    """Validate and format EIN.

    Args:
        value: EIN string, with or without dash.

    Returns:
        Formatted EIN as XX-XXXXXXX.

    Raises:
        ValueError: If EIN is not exactly 9 digits after cleaning.
    """
    # Strip all non-digit characters
    digits = re.sub(r"\D", "", value)

    if len(digits) != 9:
        raise ValueError(f"EIN must be exactly 9 digits, got {len(digits)}")

    # Format as XX-XXXXXXX
    return f"{digits[:2]}-{digits[2:]}"


def _format_ssn(digits: str) -> str:
    """Format 9-digit string as SSN."""
    return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"


def _format_ein(digits: str) -> str:
    """Format 9-digit string as EIN."""
    return f"{digits[:2]}-{digits[2:]}"


def validate_tin(value: str, default_format: str) -> str:
    """Validate and format TIN as SSN or EIN.

    Args:
        value: TIN string, with or without separators.
        default_format: "ssn" or "ein" when input is ambiguous.

    Returns:
        Formatted TIN in SSN or EIN format.

    Raises:
        ValueError: If TIN is not exactly 9 digits after cleaning.
    """
    cleaned = re.sub(r"\s", "", value)
    digits = re.sub(r"\D", "", cleaned)

    if len(digits) != 9:
        raise ValueError(f"TIN must be exactly 9 digits, got {len(digits)}")

    if re.fullmatch(r"\d{3}-\d{2}-\d{4}", cleaned):
        return _format_ssn(digits)
    if re.fullmatch(r"\d{2}-\d{7}", cleaned):
        return _format_ein(digits)

    if default_format == "ssn":
        return _format_ssn(digits)
    if default_format == "ein":
        return _format_ein(digits)

    raise ValueError("default_format must be 'ssn' or 'ein'")


# Type aliases for annotated fields
SSN = Annotated[str, Field(description="Social Security Number (XXX-XX-XXXX)")]
EIN = Annotated[str, Field(description="Employer Identification Number (XX-XXXXXXX)")]
TIN = Annotated[str, Field(description="Taxpayer Identification Number (SSN or EIN)")]


class Box12Code(BaseModel):
    """W-2 Box 12 code and amount pair."""

    code: str = Field(description="Box 12 code (e.g., D, E, DD)")
    amount: Decimal = Field(description="Amount for this code")


class W2Data(BaseModel):
    """W-2 Wage and Tax Statement data.

    Represents extracted data from IRS Form W-2. All box numbers reference
    the standard W-2 form layout.
    """

    # Identity fields
    employee_ssn: SSN = Field(description="Employee SSN (Box a)")
    employer_ein: EIN = Field(description="Employer EIN (Box b)")
    employer_name: str = Field(description="Employer name (Box c)")
    employee_name: str = Field(description="Employee name (Box e)")

    # Compensation fields (required)
    wages_tips_compensation: Decimal = Field(description="Box 1: Wages, tips, other compensation")
    federal_tax_withheld: Decimal = Field(description="Box 2: Federal income tax withheld")
    social_security_wages: Decimal = Field(description="Box 3: Social security wages")
    social_security_tax: Decimal = Field(description="Box 4: Social security tax withheld")
    medicare_wages: Decimal = Field(description="Box 5: Medicare wages and tips")
    medicare_tax: Decimal = Field(description="Box 6: Medicare tax withheld")

    # Optional compensation fields
    social_security_tips: Decimal = Field(default=Decimal("0"), description="Box 7: Social security tips")
    allocated_tips: Decimal = Field(default=Decimal("0"), description="Box 8: Allocated tips")
    dependent_care_benefits: Decimal = Field(default=Decimal("0"), description="Box 10: Dependent care benefits")

    # Box 12 codes (retirement, insurance, etc.)
    box_12_codes: list[Box12Code] = Field(default_factory=list, description="Box 12: Various codes and amounts")

    # Box 13 checkboxes
    statutory_employee: bool = Field(default=False, description="Box 13: Statutory employee")
    retirement_plan: bool = Field(default=False, description="Box 13: Retirement plan")
    third_party_sick_pay: bool = Field(default=False, description="Box 13: Third-party sick pay")

    # State fields (optional)
    state_wages: Decimal = Field(default=Decimal("0"), description="Box 16: State wages, tips, etc.")
    state_tax_withheld: Decimal = Field(default=Decimal("0"), description="Box 17: State income tax")

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("employee_ssn")
    @classmethod
    def validate_employee_ssn(cls, v: str) -> str:
        """Validate and format employee SSN."""
        return validate_ssn(v)

    @field_validator("employer_ein")
    @classmethod
    def validate_employer_ein(cls, v: str) -> str:
        """Validate and format employer EIN."""
        return validate_ein(v)


class Form1099INT(BaseModel):
    """1099-INT Interest Income data.

    Represents extracted data from IRS Form 1099-INT.
    """

    # Identity fields
    payer_name: str = Field(description="Payer's name")
    payer_tin: TIN = Field(description="Payer's TIN")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Interest fields
    interest_income: Decimal = Field(description="Box 1: Interest income")
    early_withdrawal_penalty: Decimal = Field(default=Decimal("0"), description="Box 2: Early withdrawal penalty")
    interest_us_savings_bonds: Decimal = Field(default=Decimal("0"), description="Box 3: Interest on U.S. Savings Bonds and Treasury obligations")
    federal_tax_withheld: Decimal = Field(default=Decimal("0"), description="Box 4: Federal income tax withheld")
    investment_expenses: Decimal = Field(default=Decimal("0"), description="Box 5: Investment expenses")
    foreign_tax_paid: Decimal = Field(default=Decimal("0"), description="Box 6: Foreign tax paid")
    tax_exempt_interest: Decimal = Field(default=Decimal("0"), description="Box 8: Tax-exempt interest")
    private_activity_bond_interest: Decimal = Field(default=Decimal("0"), description="Box 9: Specified private activity bond interest")

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("payer_tin")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN (can be EIN or SSN)."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ssn")


class Form1099DIV(BaseModel):
    """1099-DIV Dividend Income data.

    Represents extracted data from IRS Form 1099-DIV.
    """

    # Identity fields
    payer_name: str = Field(description="Payer's name")
    payer_tin: TIN = Field(description="Payer's TIN")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Dividend fields
    total_ordinary_dividends: Decimal = Field(description="Box 1a: Total ordinary dividends")
    qualified_dividends: Decimal = Field(default=Decimal("0"), description="Box 1b: Qualified dividends")
    total_capital_gain_distributions: Decimal = Field(default=Decimal("0"), description="Box 2a: Total capital gain distributions")
    unrecaptured_1250_gain: Decimal = Field(default=Decimal("0"), description="Box 2b: Unrecap. Sec. 1250 gain")
    section_1202_gain: Decimal = Field(default=Decimal("0"), description="Box 2c: Section 1202 gain")
    collectibles_gain: Decimal = Field(default=Decimal("0"), description="Box 2d: Collectibles (28%) gain")
    nondividend_distributions: Decimal = Field(default=Decimal("0"), description="Box 3: Nondividend distributions")
    federal_tax_withheld: Decimal = Field(default=Decimal("0"), description="Box 4: Federal income tax withheld")
    section_199a_dividends: Decimal = Field(default=Decimal("0"), description="Box 5: Section 199A dividends")
    foreign_tax_paid: Decimal = Field(default=Decimal("0"), description="Box 7: Foreign tax paid")
    exempt_interest_dividends: Decimal = Field(default=Decimal("0"), description="Box 12: Exempt-interest dividends")

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("payer_tin")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ssn")


class Form1099NEC(BaseModel):
    """1099-NEC Nonemployee Compensation data.

    Represents extracted data from IRS Form 1099-NEC.
    """

    # Identity fields
    payer_name: str = Field(description="Payer's name")
    payer_tin: TIN = Field(description="Payer's TIN")
    recipient_name: str = Field(description="Recipient's name")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Compensation fields
    nonemployee_compensation: Decimal = Field(description="Box 1: Nonemployee compensation")
    direct_sales: bool = Field(default=False, description="Box 2: Payer made direct sales of $5,000 or more")
    federal_tax_withheld: Decimal = Field(default=Decimal("0"), description="Box 4: Federal income tax withheld")
    state_tax_withheld: Decimal = Field(default=Decimal("0"), description="Boxes 5-7: State tax withheld")

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("payer_tin")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (SSN or EIN)."""
        return validate_tin(v, default_format="ssn")
