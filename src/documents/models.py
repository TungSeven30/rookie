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
    FORM_K1 = "K-1"
    FORM_1099_B = "1099-B"
    FORM_1095_A = "1095-A"
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
        Formatted TIN in SSN or EIN format, or masked format if partially hidden.

    Raises:
        ValueError: If TIN is not valid after cleaning.
    """
    cleaned = re.sub(r"\s", "", value)
    
    # Handle masked SSNs like ***-**-1146 or XXX-XX-1146
    masked_ssn_pattern = r"[\*Xx]{3}-[\*Xx]{2}-(\d{4})"
    masked_match = re.fullmatch(masked_ssn_pattern, cleaned)
    if masked_match:
        # Return standardized masked format with last 4 digits
        return f"***-**-{masked_match.group(1)}"
    
    # Handle partially masked formats without dashes
    masked_no_dash = re.fullmatch(r"[\*Xx]+(\d{4})", cleaned)
    if masked_no_dash:
        return f"***-**-{masked_no_dash.group(1)}"
    
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


class FormK1(BaseModel):
    """Schedule K-1 data from Partnership (Form 1065) or S-Corp (Form 1120-S).

    K-1 forms report a partner's or shareholder's share of income, deductions,
    credits, and other items from pass-through entities. The form has three parts:
    - Part I: Information about the partnership/S-corp
    - Part II: Information about the partner/shareholder
    - Part III: Partner's/Shareholder's share of current year income, deductions, etc.
    """

    # Entity information (Part I)
    entity_name: str = Field(description="Partnership or S-corp name")
    entity_ein: EIN = Field(description="Entity's EIN")
    entity_type: str = Field(description="Entity type: 'partnership' or 's_corp'")
    tax_year: int = Field(description="Tax year of the K-1")

    # Partner/Shareholder information (Part II)
    recipient_name: str = Field(description="Partner or shareholder name")
    recipient_tin: TIN = Field(description="Partner's SSN or EIN")
    ownership_percentage: Decimal = Field(description="Ownership percentage")

    # Capital account (Part II, Item L) - for basis tracking
    capital_account_beginning: Decimal | None = Field(
        default=None, description="Beginning capital account"
    )
    capital_account_ending: Decimal | None = Field(
        default=None, description="Ending capital account"
    )
    current_year_increase: Decimal | None = Field(
        default=None, description="Current year increase"
    )
    current_year_decrease: Decimal | None = Field(
        default=None, description="Current year decrease"
    )

    # Debt basis (partnerships) - from K-1 supplemental
    share_of_recourse_liabilities: Decimal | None = Field(
        default=None, description="Share of recourse liabilities"
    )
    share_of_nonrecourse_liabilities: Decimal | None = Field(
        default=None, description="Share of nonrecourse liabilities"
    )
    share_of_qualified_nonrecourse: Decimal | None = Field(
        default=None, description="Share of qualified nonrecourse financing"
    )

    # Income items (Part III)
    ordinary_business_income: Decimal = Field(
        default=Decimal("0"), description="Box 1: Ordinary business income (loss)"
    )
    net_rental_real_estate: Decimal = Field(
        default=Decimal("0"), description="Box 2: Net rental real estate income (loss)"
    )
    other_rental_income: Decimal = Field(
        default=Decimal("0"), description="Box 3: Other net rental income (loss)"
    )
    guaranteed_payments: Decimal = Field(
        default=Decimal("0"), description="Box 4: Guaranteed payments"
    )
    interest_income: Decimal = Field(
        default=Decimal("0"), description="Box 5: Interest income"
    )
    dividend_income: Decimal = Field(
        default=Decimal("0"), description="Box 6a: Ordinary dividends"
    )
    royalties: Decimal = Field(default=Decimal("0"), description="Box 7: Royalties")
    net_short_term_capital_gain: Decimal = Field(
        default=Decimal("0"), description="Box 8: Net short-term capital gain (loss)"
    )
    net_long_term_capital_gain: Decimal = Field(
        default=Decimal("0"), description="Box 9a: Net long-term capital gain (loss)"
    )
    net_section_1231_gain: Decimal = Field(
        default=Decimal("0"), description="Box 10: Net section 1231 gain (loss)"
    )
    other_income: Decimal = Field(
        default=Decimal("0"), description="Box 11: Other income (loss)"
    )

    # Deductions
    section_179_deduction: Decimal = Field(
        default=Decimal("0"), description="Box 12: Section 179 deduction"
    )
    other_deductions: Decimal = Field(
        default=Decimal("0"), description="Box 13: Other deductions"
    )

    # Self-employment
    self_employment_earnings: Decimal = Field(
        default=Decimal("0"), description="Box 14: Self-employment earnings (loss)"
    )

    # Credits and foreign (simplified)
    credits: Decimal = Field(default=Decimal("0"), description="Box 15: Credits")
    foreign_transactions: Decimal = Field(
        default=Decimal("0"), description="Box 16: Foreign transactions (for escalation)"
    )

    # Distributions
    distributions: Decimal = Field(
        default=Decimal("0"), description="Box 19: Distributions"
    )

    # Metadata
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Extraction confidence level"
    )
    uncertain_fields: list[str] = Field(
        default_factory=list, description="Fields with low confidence"
    )

    @field_validator("entity_ein", mode="before")
    @classmethod
    def validate_entity_ein(cls, v: str) -> str:
        """Validate and format entity EIN."""
        return validate_ein(v)

    @field_validator("recipient_tin", mode="before")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (usually SSN for individuals)."""
        return validate_tin(v, default_format="ssn")

    @property
    def requires_basis_escalation(self) -> bool:
        """Check if basis limitation may affect loss deductibility.

        Escalate if:
        - Net K-1 loss > $10k AND no capital account info
        - This prevents silent disallowance of legitimate losses

        Returns:
            True if the K-1 should be escalated for basis review.
        """
        net_loss = self.ordinary_business_income + self.net_rental_real_estate
        has_significant_loss = net_loss < Decimal("-10000")
        missing_basis_info = self.capital_account_ending is None
        return has_significant_loss and missing_basis_info

    @property
    def total_k1_income(self) -> Decimal:
        """Sum of all income items from K-1.

        Returns:
            Total of all K-1 income boxes.
        """
        return (
            self.ordinary_business_income
            + self.net_rental_real_estate
            + self.other_rental_income
            + self.guaranteed_payments
            + self.interest_income
            + self.dividend_income
            + self.royalties
            + self.net_short_term_capital_gain
            + self.net_long_term_capital_gain
            + self.net_section_1231_gain
            + self.other_income
        )


class Form1099B(BaseModel):
    """Form 1099-B Proceeds from Broker and Barter Exchange Transactions.

    Reports sales of stocks, bonds, commodities, and other securities.
    Each transaction shows proceeds, cost basis (if reported), and holding period.
    """

    # Payer/Recipient
    payer_name: str = Field(description="Broker or barter exchange name")
    payer_tin: TIN = Field(description="Broker's TIN")
    recipient_tin: TIN = Field(description="Recipient's TIN")
    account_number: str | None = Field(default=None, description="Account number")

    # Transaction details
    description: str = Field(description="Security name/description")
    date_acquired: str | None = Field(
        default=None, description="Date acquired (may be 'Various')"
    )
    date_sold: str = Field(description="Date of sale")
    proceeds: Decimal = Field(description="Box 1d: Proceeds from sale")
    cost_basis: Decimal | None = Field(
        default=None, description="Box 1e: Cost or other basis (may be blank)"
    )

    # Gain/loss calculation
    gain_loss: Decimal | None = Field(
        default=None, description="Calculated or reported gain/loss"
    )
    wash_sale_loss_disallowed: Decimal = Field(
        default=Decimal("0"), description="Box 1g: Wash sale loss disallowed"
    )

    # Classification
    is_short_term: bool = Field(
        default=False, description="Box 2: Short-term (held ≤1 year)"
    )
    is_long_term: bool = Field(
        default=False, description="Box 3: Long-term (held >1 year)"
    )
    basis_reported_to_irs: bool = Field(
        default=True, description="Box 12: Basis reported to IRS"
    )

    # Special types
    is_collectibles: bool = Field(
        default=False, description="Collectibles (28% rate)"
    )
    is_qof: bool = Field(default=False, description="Qualified Opportunity Fund")

    # Metadata
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Extraction confidence level"
    )
    uncertain_fields: list[str] = Field(
        default_factory=list, description="Fields with low confidence"
    )

    @field_validator("payer_tin", mode="before")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN (usually EIN)."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin", mode="before")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (usually SSN)."""
        return validate_tin(v, default_format="ssn")

    @property
    def requires_basis_escalation(self) -> bool:
        """Check if transaction needs basis escalation.

        Escalate when cost basis is missing and was not reported to IRS.
        This means the taxpayer must provide basis information.

        Returns:
            True if basis escalation is needed.
        """
        return self.cost_basis is None and not self.basis_reported_to_irs


class Form1099BSummary(BaseModel):
    """Aggregated 1099-B summary for high-volume broker statements.

    When a broker statement has >50 transactions, extract category totals
    instead of individual transactions. This matches IRS Form 8949 categories:
    - Category A: Short-term, basis reported to IRS
    - Category B: Short-term, basis NOT reported to IRS
    - Category D: Long-term, basis reported to IRS
    - Category E: Long-term, basis NOT reported to IRS
    """

    # Payer info (same for all transactions)
    payer_name: str = Field(description="Broker name")
    payer_tin: TIN = Field(description="Broker's TIN")
    recipient_tin: TIN = Field(description="Recipient's TIN")

    # Category A: Short-term, basis reported to IRS
    cat_a_proceeds: Decimal = Field(
        default=Decimal("0"), description="Category A total proceeds"
    )
    cat_a_cost_basis: Decimal = Field(
        default=Decimal("0"), description="Category A total cost basis"
    )
    cat_a_adjustments: Decimal = Field(
        default=Decimal("0"), description="Category A adjustments (wash sales, etc.)"
    )
    cat_a_gain_loss: Decimal = Field(
        default=Decimal("0"), description="Category A net gain/loss"
    )
    cat_a_transaction_count: int = Field(
        default=0, description="Number of Category A transactions"
    )

    # Category B: Short-term, basis NOT reported to IRS
    cat_b_proceeds: Decimal = Field(
        default=Decimal("0"), description="Category B total proceeds"
    )
    cat_b_cost_basis: Decimal | None = Field(
        default=None, description="Category B cost basis (may need client input)"
    )
    cat_b_adjustments: Decimal = Field(
        default=Decimal("0"), description="Category B adjustments"
    )
    cat_b_transaction_count: int = Field(
        default=0, description="Number of Category B transactions"
    )

    # Category D: Long-term, basis reported to IRS
    cat_d_proceeds: Decimal = Field(
        default=Decimal("0"), description="Category D total proceeds"
    )
    cat_d_cost_basis: Decimal = Field(
        default=Decimal("0"), description="Category D total cost basis"
    )
    cat_d_adjustments: Decimal = Field(
        default=Decimal("0"), description="Category D adjustments"
    )
    cat_d_gain_loss: Decimal = Field(
        default=Decimal("0"), description="Category D net gain/loss"
    )
    cat_d_transaction_count: int = Field(
        default=0, description="Number of Category D transactions"
    )

    # Category E: Long-term, basis NOT reported to IRS
    cat_e_proceeds: Decimal = Field(
        default=Decimal("0"), description="Category E total proceeds"
    )
    cat_e_cost_basis: Decimal | None = Field(
        default=None, description="Category E cost basis (may need client input)"
    )
    cat_e_adjustments: Decimal = Field(
        default=Decimal("0"), description="Category E adjustments"
    )
    cat_e_transaction_count: int = Field(
        default=0, description="Number of Category E transactions"
    )

    # Wash sale totals (summed across all categories)
    total_wash_sale_disallowed: Decimal = Field(
        default=Decimal("0"), description="Total wash sale loss disallowed"
    )

    # Collectibles and other special categories
    collectibles_gain: Decimal = Field(
        default=Decimal("0"), description="Collectibles gain (28% rate)"
    )
    section_1202_gain: Decimal = Field(
        default=Decimal("0"), description="Section 1202 qualified small business stock gain"
    )

    # Metadata
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Extraction confidence level"
    )
    total_transaction_count: int = Field(
        default=0, description="Total number of transactions"
    )

    @field_validator("payer_tin", mode="before")
    @classmethod
    def validate_payer_tin(cls, v: str) -> str:
        """Validate payer TIN (usually EIN)."""
        return validate_tin(v, default_format="ein")

    @field_validator("recipient_tin", mode="before")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (usually SSN)."""
        return validate_tin(v, default_format="ssn")

    @property
    def has_missing_basis(self) -> bool:
        """Check if any non-reported categories need basis input.

        Returns:
            True if Category B or E has transactions but no cost basis.
        """
        return (
            (self.cat_b_transaction_count > 0 and self.cat_b_cost_basis is None)
            or (self.cat_e_transaction_count > 0 and self.cat_e_cost_basis is None)
        )

    @property
    def total_short_term_gain_loss(self) -> Decimal:
        """Total short-term gain/loss from categories A and B.

        Returns:
            Combined short-term gain/loss.
        """
        cat_a = self.cat_a_gain_loss
        cat_b = (
            self.cat_b_proceeds - (self.cat_b_cost_basis or Decimal("0"))
            if self.cat_b_cost_basis is not None
            else Decimal("0")
        )
        return cat_a + cat_b

    @property
    def total_long_term_gain_loss(self) -> Decimal:
        """Total long-term gain/loss from categories D and E.

        Returns:
            Combined long-term gain/loss.
        """
        cat_d = self.cat_d_gain_loss
        cat_e = (
            self.cat_e_proceeds - (self.cat_e_cost_basis or Decimal("0"))
            if self.cat_e_cost_basis is not None
            else Decimal("0")
        )
        return cat_d + cat_e


class Form1095A(BaseModel):
    """Form 1095-A Health Insurance Marketplace Statement.

    Reports monthly health insurance marketplace coverage, premiums, SLCSP amounts,
    and advance payments of the premium tax credit. Used to reconcile PTC on Form 8962.
    """

    # Recipient information
    recipient_name: str = Field(description="Recipient's name")
    recipient_tin: TIN = Field(description="Recipient's TIN (SSN)")
    recipient_address: str | None = Field(default=None, description="Recipient's address")

    # Marketplace information
    marketplace_id: str | None = Field(
        default=None, description="Marketplace identifier"
    )
    policy_number: str | None = Field(default=None, description="Policy number")

    # Coverage dates
    coverage_start_date: str | None = Field(
        default=None, description="Coverage start date"
    )
    coverage_termination_date: str | None = Field(
        default=None, description="Coverage termination date (if terminated)"
    )

    # Monthly data (lists of 12 values for Jan-Dec)
    monthly_enrollment_premium: list[Decimal] = Field(
        default_factory=lambda: [Decimal("0")] * 12,
        description="Box 21-32: Monthly enrollment premiums",
    )
    monthly_slcsp_premium: list[Decimal] = Field(
        default_factory=lambda: [Decimal("0")] * 12,
        description="Box 33-44: Monthly SLCSP premiums",
    )
    monthly_advance_ptc: list[Decimal] = Field(
        default_factory=lambda: [Decimal("0")] * 12,
        description="Box 45-56: Monthly advance payments of PTC",
    )

    # Annual totals (convenience fields)
    annual_enrollment_premium: Decimal = Field(
        default=Decimal("0"), description="Total enrollment premium for the year"
    )
    annual_slcsp_premium: Decimal = Field(
        default=Decimal("0"), description="Total SLCSP premium for the year"
    )
    annual_advance_ptc: Decimal = Field(
        default=Decimal("0"), description="Total advance PTC for the year"
    )

    # Metadata
    confidence: ConfidenceLevel = Field(
        default=ConfidenceLevel.HIGH, description="Extraction confidence level"
    )
    uncertain_fields: list[str] = Field(
        default_factory=list, description="Fields with low confidence"
    )

    @field_validator("recipient_tin", mode="before")
    @classmethod
    def validate_recipient_tin(cls, v: str) -> str:
        """Validate recipient TIN (SSN)."""
        return validate_tin(v, default_format="ssn")
