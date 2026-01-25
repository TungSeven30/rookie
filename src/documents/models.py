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
    FORM_1098 = "1098"
    FORM_1099_R = "1099-R"
    FORM_1099_G = "1099-G"
    FORM_1098_T = "1098-T"
    FORM_5498 = "5498"
    FORM_1099_S = "1099-S"
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


class W2Batch(BaseModel):
    """Batch of W-2 forms extracted from a single page."""

    forms: list[W2Data] = Field(
        default_factory=list, description="Extracted W-2 forms from the page."
    )


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


class Form1098(BaseModel):
    """1098 Mortgage Interest Statement data.

    Represents extracted data from IRS Form 1098.
    """

    # Identity fields
    lender_name: str = Field(description="Recipient/Lender name")
    lender_tin: TIN = Field(description="Recipient/Lender TIN")
    borrower_name: str = Field(description="Payer/Borrower name")
    borrower_tin: TIN = Field(description="Payer/Borrower TIN")

    # Mortgage fields
    mortgage_interest: Decimal = Field(description="Box 1: Mortgage interest received")
    points_paid: Decimal = Field(default=Decimal("0"), description="Box 6: Points paid on purchase")
    mortgage_insurance_premiums: Decimal = Field(
        default=Decimal("0"), description="Box 5: Mortgage insurance premiums"
    )
    property_taxes_paid: Decimal = Field(
        default=Decimal("0"), description="Box 10: Property taxes paid (if reported)"
    )
    refund_of_overpaid_interest: Decimal = Field(
        default=Decimal("0"), description="Box 4: Refund of overpaid interest"
    )
    outstanding_mortgage_principal: Decimal = Field(
        default=Decimal("0"), description="Box 2: Outstanding mortgage principal"
    )
    mortgage_origination_date: str | None = Field(
        default=None, description="Box 3: Mortgage origination date"
    )
    property_address: str | None = Field(
        default=None, description="Box 8: Property address"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("lender_tin")
    @classmethod
    def validate_lender_tin(cls, v: str) -> str:
        """Validate lender TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("borrower_tin")
    @classmethod
    def validate_borrower_tin(cls, v: str) -> str:
        """Validate borrower TIN."""
        return validate_tin(v, default_format="ssn")


class Form1099R(BaseModel):
    """1099-R Retirement Distributions data.

    Represents extracted data from IRS Form 1099-R.
    """

    # Identity fields
    payer_name: str = Field(description="Payer's name")
    payer_tin: TIN = Field(description="Payer's TIN")
    recipient_name: str = Field(description="Recipient's name")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Distribution fields
    gross_distribution: Decimal = Field(description="Box 1: Gross distribution")
    taxable_amount: Decimal | None = Field(
        default=None, description="Box 2a: Taxable amount (None if not determined)"
    )
    taxable_amount_not_determined: bool = Field(
        default=False, description="Box 2b: Taxable amount not determined"
    )
    total_distribution: bool = Field(
        default=False, description="Box 2b: Total distribution"
    )
    capital_gain: Decimal = Field(
        default=Decimal("0"), description="Box 3: Capital gain (included in box 2a)"
    )
    federal_tax_withheld: Decimal = Field(
        default=Decimal("0"), description="Box 4: Federal income tax withheld"
    )
    employee_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 5: Employee contributions/designated Roth"
    )
    net_unrealized_appreciation: Decimal = Field(
        default=Decimal("0"), description="Box 6: Net unrealized appreciation in employer's securities"
    )
    distribution_code: str = Field(description="Box 7: Distribution code(s)")
    ira_sep_simple: bool = Field(
        default=False, description="Box 7: IRA/SEP/SIMPLE checkbox"
    )
    other_amount: Decimal = Field(
        default=Decimal("0"), description="Box 8: Other amount"
    )
    total_employee_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 9b: Total employee contributions"
    )
    state_tax_withheld: Decimal = Field(
        default=Decimal("0"), description="Box 12: State tax withheld"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("payer_tin")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN."""
        return validate_tin(v, default_format="ssn")


class Form1099G(BaseModel):
    """1099-G Government Payments data.

    Represents extracted data from IRS Form 1099-G.
    """

    # Identity fields
    payer_name: str = Field(description="Payer's name (government agency)")
    payer_tin: TIN = Field(description="Payer's TIN")
    recipient_name: str = Field(description="Recipient's name")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Payment fields
    unemployment_compensation: Decimal = Field(
        default=Decimal("0"), description="Box 1: Unemployment compensation"
    )
    state_local_tax_refund: Decimal = Field(
        default=Decimal("0"), description="Box 2: State or local income tax refunds, credits, or offsets"
    )
    box_2_year: int | None = Field(
        default=None, description="Box 3: Box 2 amount is for tax year"
    )
    federal_tax_withheld: Decimal = Field(
        default=Decimal("0"), description="Box 4: Federal income tax withheld"
    )
    reemployment_trade_adjustment: Decimal = Field(
        default=Decimal("0"), description="Box 5: RTAA payments"
    )
    taxable_grants: Decimal = Field(
        default=Decimal("0"), description="Box 6: Taxable grants"
    )
    agriculture_payments: Decimal = Field(
        default=Decimal("0"), description="Box 7: Agriculture payments"
    )
    state_tax_withheld: Decimal = Field(
        default=Decimal("0"), description="Box 11: State income tax withheld"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("payer_tin")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN."""
        return validate_tin(v, default_format="ssn")


class Form1098T(BaseModel):
    """1098-T Tuition Statement data.

    Represents extracted data from IRS Form 1098-T.
    """

    # Identity fields
    institution_name: str = Field(description="Filer's name (educational institution)")
    institution_tin: TIN = Field(description="Filer's TIN")
    student_name: str = Field(description="Student's name")
    student_tin: TIN = Field(description="Student's TIN")

    # Tuition fields
    payments_received: Decimal = Field(
        default=Decimal("0"), description="Box 1: Payments received for qualified tuition"
    )
    scholarships_grants: Decimal = Field(
        default=Decimal("0"), description="Box 5: Scholarships or grants"
    )
    adjustments_prior_year: Decimal = Field(
        default=Decimal("0"), description="Box 4: Adjustments made for a prior year"
    )
    scholarships_adjustments_prior_year: Decimal = Field(
        default=Decimal("0"), description="Box 6: Adjustments to scholarships for prior year"
    )
    at_least_half_time: bool = Field(
        default=False, description="Box 8: At least half-time student"
    )
    graduate_student: bool = Field(
        default=False, description="Box 9: Graduate student"
    )
    insurance_contract_reimbursement: Decimal = Field(
        default=Decimal("0"), description="Box 10: Ins. contract reimbursement/refund"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("institution_tin")
    @classmethod
    def validate_institution_tin(cls, v: str) -> str:
        """Validate institution TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("student_tin")
    @classmethod
    def validate_student_tin(cls, v: str) -> str:
        """Validate student TIN."""
        return validate_tin(v, default_format="ssn")


class Form5498(BaseModel):
    """5498 IRA Contribution Information data.

    Represents extracted data from IRS Form 5498.
    """

    # Identity fields
    trustee_name: str = Field(description="Trustee's or issuer's name")
    trustee_tin: TIN = Field(description="Trustee's TIN")
    participant_name: str = Field(description="Participant's name")
    participant_tin: TIN = Field(description="Participant's TIN")

    # Contribution fields
    ira_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 1: IRA contributions (other than rollover/Roth/SEP/SIMPLE)"
    )
    rollover_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 2: Rollover contributions"
    )
    roth_ira_conversion: Decimal = Field(
        default=Decimal("0"), description="Box 3: Roth IRA conversion amount"
    )
    recharacterized_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 4: Recharacterized contributions"
    )
    fair_market_value: Decimal = Field(
        default=Decimal("0"), description="Box 5: Fair market value of account"
    )
    life_insurance_cost: Decimal = Field(
        default=Decimal("0"), description="Box 6: Life insurance cost included in box 1"
    )
    ira_type: str | None = Field(
        default=None, description="Box 7: IRA type checkbox (IRA, SEP, SIMPLE, Roth IRA)"
    )
    sep_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 8: SEP contributions"
    )
    simple_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 9: SIMPLE contributions"
    )
    roth_ira_contributions: Decimal = Field(
        default=Decimal("0"), description="Box 10: Roth IRA contributions"
    )
    rmd_required_next_year: bool = Field(
        default=False, description="Box 11: Check if RMD required for next year"
    )
    rmd_date: str | None = Field(
        default=None, description="Box 12: RMD date"
    )
    postponed_contribution: Decimal = Field(
        default=Decimal("0"), description="Box 13a: Postponed contribution"
    )
    repayments: Decimal = Field(
        default=Decimal("0"), description="Box 14a: Repayments"
    )
    fmv_specific_assets: Decimal = Field(
        default=Decimal("0"), description="Box 15a: FMV of certain specified assets"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("trustee_tin")
    @classmethod
    def validate_trustee_tin(cls, v: str) -> str:
        """Validate trustee TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("participant_tin")
    @classmethod
    def validate_participant_tin(cls, v: str) -> str:
        """Validate participant TIN."""
        return validate_tin(v, default_format="ssn")


class Form1099S(BaseModel):
    """1099-S Proceeds from Real Estate Transactions data.

    Represents extracted data from IRS Form 1099-S.
    """

    # Identity fields
    filer_name: str = Field(description="Filer's name")
    filer_tin: TIN = Field(description="Filer's TIN")
    transferor_name: str = Field(description="Transferor's name")
    transferor_tin: TIN = Field(description="Transferor's TIN")

    # Transaction fields
    closing_date: str = Field(description="Box 1: Date of closing")
    gross_proceeds: Decimal = Field(description="Box 2: Gross proceeds")
    property_address: str = Field(description="Box 3: Address or legal description")
    transferor_received_property: bool = Field(
        default=False, description="Box 4: Transferor received property or services"
    )
    buyer_part_of_real_estate_tax: Decimal = Field(
        default=Decimal("0"), description="Box 5: Buyer's part of real estate tax"
    )

    # Extraction metadata
    confidence: ConfidenceLevel = Field(description="Extraction confidence level")
    uncertain_fields: list[str] = Field(default_factory=list, description="Fields with low confidence")

    @field_validator("filer_tin")
    @classmethod
    def validate_filer_tin(cls, v: str) -> str:
        """Validate filer TIN."""
        return validate_tin(v, default_format="ein")

    @field_validator("transferor_tin")
    @classmethod
    def validate_transferor_tin(cls, v: str) -> str:
        """Validate transferor TIN."""
        return validate_tin(v, default_format="ssn")
