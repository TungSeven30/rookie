"""Extraction prompts for tax documents.

This module contains detailed prompts for extracting data from each tax document type.
Separating prompts from extraction logic makes them easier to tune for accuracy and test.

Each prompt includes:
- Specific box descriptions for the form type
- Formatting expectations (SSN, EIN, currency)
- Confidence assessment requirements
- Instructions for handling uncertain or empty fields
"""

W2_EXTRACTION_PROMPT = """Extract all data from this W-2 Wage and Tax Statement.

For each field, extract the exact value shown. Box locations on a standard W-2:

**IDENTITY FIELDS:**
- Box a: Employee's Social Security Number (format as XXX-XX-XXXX)
- Box b: Employer Identification Number (format as XX-XXXXXXX)
- Box c: Employer's name, address, and ZIP code (extract just the name)
- Box e: Employee's first name, initial, and last name
- Box f: Employee's address and ZIP code (not extracted)

**COMPENSATION FIELDS (Required):**
- Box 1: Wages, tips, other compensation (total taxable wages)
- Box 2: Federal income tax withheld
- Box 3: Social security wages (may differ from Box 1)
- Box 4: Social security tax withheld
- Box 5: Medicare wages and tips
- Box 6: Medicare tax withheld

**OPTIONAL COMPENSATION FIELDS:**
- Box 7: Social security tips
- Box 8: Allocated tips
- Box 10: Dependent care benefits

**BOX 12 CODES:**
Box 12 contains letter codes with amounts. Common codes include:
- D: Elective deferrals to 401(k)
- E: Elective deferrals to 403(b)
- DD: Cost of employer-sponsored health coverage
- W: Employer contributions to HSA
Extract each code letter and its corresponding amount.

**BOX 13 CHECKBOXES:**
- Statutory employee: checked or unchecked
- Retirement plan: checked or unchecked (if Box 12 has retirement codes, this is likely checked)
- Third-party sick pay: checked or unchecked

**STATE TAX FIELDS:**
- Box 15: State and state ID (not extracted)
- Box 16: State wages, tips, etc.
- Box 17: State income tax

**CONFIDENCE ASSESSMENT:**
Set confidence level based on document quality:
- HIGH: All fields clearly visible and readable, no smudges or obscured text
- MEDIUM: Some fields partially obscured, faded, or at an angle
- LOW: Multiple critical fields (wages, taxes, SSN, EIN) hard to read

Add any field names you're uncertain about to the uncertain_fields list.
For empty monetary boxes, use 0 (zero).
For missing optional fields, use default values.

IMPORTANT:
- Do not round. Preserve cents exactly as shown (e.g., 78321.05).
- If multiple W-2 forms appear on the same page, do not sum or average values.
  Extract a single complete W-2 (prefer the largest/most complete copy) and
  add "multiple_forms_detected" to the uncertain_fields list."""

W2_MULTI_EXTRACTION_PROMPT = """Extract ALL W-2 forms visible on this page.

For each W-2 form, capture the same fields as a standard W-2:
- Box a (SSN), Box b (EIN), Box c (employer name), Box e (employee name)
- Box 1 wages, Box 2 federal withheld, Box 3/4 Social Security, Box 5/6 Medicare
- Box 7/8 tips, Box 10 dependent care, Box 12 codes, Box 13 checkboxes
- Box 16/17 state wages/tax

Rules:
- If the page contains multiple copies of the SAME W-2, keep only the most complete copy.
- If the page contains multiple distinct W-2s, return each as a separate entry.
- Do not sum or average values across forms.
- Preserve cents exactly as shown (e.g., 78321.05).
- If multiple W-2 forms appear on the page, add "multiple_forms_detected" to uncertain_fields.

Return a list named "forms" containing each W-2."""

FORM_1099_INT_PROMPT = """Extract all data from this 1099-INT Interest Income form.

For each field, extract the exact value shown. Box locations on a standard 1099-INT:

**IDENTITY FIELDS:**
- PAYER'S name, street address, city, state, ZIP (extract just the payer name)
- PAYER'S TIN: Taxpayer Identification Number (format as XX-XXXXXXX for EIN)
- RECIPIENT'S TIN: Social Security Number (format as XXX-XX-XXXX)

**INTEREST INCOME FIELDS:**
- Box 1: Interest income (total taxable interest - REQUIRED)
- Box 2: Early withdrawal penalty
- Box 3: Interest on U.S. Savings Bonds and Treasury obligations
- Box 4: Federal income tax withheld
- Box 5: Investment expenses
- Box 6: Foreign tax paid
- Box 7: Foreign country or U.S. possession (not extracted as monetary)
- Box 8: Tax-exempt interest
- Box 9: Specified private activity bond interest

**CONFIDENCE ASSESSMENT:**
Set confidence level based on document quality:
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Interest income (Box 1) or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Interest income (Box 1) is the most critical field."""

FORM_1099_DIV_PROMPT = """Extract all data from this 1099-DIV Dividends and Distributions form.

For each field, extract the exact value shown. Box locations on a standard 1099-DIV:

**IDENTITY FIELDS:**
- PAYER'S name, street address, city, state, ZIP (extract just the payer name)
- PAYER'S TIN: Taxpayer Identification Number (format as XX-XXXXXXX for EIN)
- RECIPIENT'S TIN: Social Security Number (format as XXX-XX-XXXX)

**DIVIDEND FIELDS:**
- Box 1a: Total ordinary dividends (REQUIRED - all taxable dividends)
- Box 1b: Qualified dividends (portion of 1a eligible for lower tax rate)
- Box 2a: Total capital gain distributions
- Box 2b: Unrecap. Sec. 1250 gain
- Box 2c: Section 1202 gain
- Box 2d: Collectibles (28%) gain
- Box 3: Nondividend distributions (return of capital)
- Box 4: Federal income tax withheld
- Box 5: Section 199A dividends (REIT dividends eligible for 20% deduction)
- Box 6: Investment expenses (not always present)
- Box 7: Foreign tax paid
- Box 8: Foreign country or U.S. possession (not extracted as monetary)
- Box 9-11: Various less common fields (not extracted)
- Box 12: Exempt-interest dividends (from municipal bonds)

**CONFIDENCE ASSESSMENT:**
Set confidence level based on document quality:
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Total ordinary dividends (Box 1a) or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Total ordinary dividends (Box 1a) is the most critical field."""

FORM_1099_NEC_PROMPT = """Extract all data from this 1099-NEC Nonemployee Compensation form.

For each field, extract the exact value shown. Box locations on a standard 1099-NEC:

**IDENTITY FIELDS:**
- PAYER'S name, street address, city, state, ZIP (extract just the payer name)
- PAYER'S TIN: Taxpayer Identification Number (format as XX-XXXXXXX for EIN)
- RECIPIENT'S name (the independent contractor)
- RECIPIENT'S TIN: Social Security Number (format as XXX-XX-XXXX)

**COMPENSATION FIELDS:**
- Box 1: Nonemployee compensation (REQUIRED - total amount paid)
- Box 2: If checked, payer made direct sales of $5,000 or more (checkbox, not amount)
- Box 4: Federal income tax withheld (if backup withholding applies)

**STATE TAX FIELDS:**
- Box 5: State tax withheld
- Box 6: State/Payer's state no. (not extracted)
- Box 7: State income (not extracted separately)

**CONFIDENCE ASSESSMENT:**
Set confidence level based on document quality:
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Nonemployee compensation (Box 1) or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Box 2 (direct sales) is a checkbox, return true if checked, false otherwise.
Nonemployee compensation (Box 1) is the most critical field - this is the total paid."""


FORM_1098_PROMPT = """Extract all data from this 1098 Mortgage Interest Statement form.

For each field, extract the exact value shown. Box locations on a standard 1098:

**IDENTITY FIELDS:**
- RECIPIENT'S/LENDER'S name (the mortgage company)
- RECIPIENT'S/LENDER'S TIN (format as XX-XXXXXXX for EIN)
- PAYER'S/BORROWER'S name
- PAYER'S/BORROWER'S TIN (format as XXX-XX-XXXX for SSN)

**MORTGAGE FIELDS:**
- Box 1: Mortgage interest received from payer(s)/borrower(s) (REQUIRED)
- Box 2: Outstanding mortgage principal as of 1/1
- Box 3: Mortgage origination date
- Box 4: Refund of overpaid interest
- Box 5: Mortgage insurance premiums
- Box 6: Points paid on purchase of principal residence
- Box 7: Is address of property securing mortgage same as payer's/borrower's address? (checkbox)
- Box 8: Address or description of property securing mortgage
- Box 10: Property taxes paid (if reported)

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Mortgage interest (Box 1) or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Mortgage interest (Box 1) is the most critical field."""


FORM_1099_R_PROMPT = """Extract all data from this 1099-R Distributions From Pensions form.

For each field, extract the exact value shown. Box locations on a standard 1099-R:

**IDENTITY FIELDS:**
- PAYER'S name (the retirement plan administrator)
- PAYER'S TIN (format as XX-XXXXXXX for EIN)
- RECIPIENT'S name
- RECIPIENT'S TIN (format as XXX-XX-XXXX for SSN)

**DISTRIBUTION FIELDS:**
- Box 1: Gross distribution (REQUIRED - total amount distributed)
- Box 2a: Taxable amount (may be blank if not determined)
- Box 2b: Taxable amount not determined (checkbox)
- Box 2b: Total distribution (checkbox)
- Box 3: Capital gain (included in Box 2a)
- Box 4: Federal income tax withheld
- Box 5: Employee contributions/Designated Roth contributions or insurance premiums
- Box 6: Net unrealized appreciation in employer's securities
- Box 7: Distribution code(s) (REQUIRED - e.g., 1, 7, G, etc.)
- Box 7: IRA/SEP/SIMPLE (checkbox)
- Box 8: Other amount
- Box 9a: Your percentage of total distribution
- Box 9b: Total employee contributions
- Box 12: State tax withheld

**DISTRIBUTION CODES (Box 7):**
Common codes include:
- 1: Early distribution, no known exception
- 2: Early distribution, exception applies
- 3: Disability
- 4: Death
- 7: Normal distribution
- G: Direct rollover
- L: Loans treated as distributions

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Gross distribution (Box 1), distribution code (Box 7), or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Gross distribution (Box 1) and distribution code (Box 7) are the most critical fields."""


FORM_1099_G_PROMPT = """Extract all data from this 1099-G Government Payments form.

For each field, extract the exact value shown. Box locations on a standard 1099-G:

**IDENTITY FIELDS:**
- PAYER'S name (the government agency)
- PAYER'S TIN (format as XX-XXXXXXX for EIN)
- RECIPIENT'S name
- RECIPIENT'S TIN (format as XXX-XX-XXXX for SSN)

**PAYMENT FIELDS:**
- Box 1: Unemployment compensation (taxable unemployment benefits)
- Box 2: State or local income tax refunds, credits, or offsets
- Box 3: Box 2 amount is for tax year (year the refund relates to)
- Box 4: Federal income tax withheld
- Box 5: RTAA payments (Reemployment Trade Adjustment Assistance)
- Box 6: Taxable grants
- Box 7: Agriculture payments
- Box 8: Check if Box 2 is trade or business income (checkbox)
- Box 10a: Market gain
- Box 10b: Unreported profit sharing distributions
- Box 11: State income tax withheld

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Unemployment comp (Box 1), state tax refund (Box 2), or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Unemployment compensation (Box 1) and state tax refund (Box 2) are the most critical fields."""


FORM_1098_T_PROMPT = """Extract all data from this 1098-T Tuition Statement form.

For each field, extract the exact value shown. Box locations on a standard 1098-T:

**IDENTITY FIELDS:**
- FILER'S name (the educational institution)
- FILER'S TIN (format as XX-XXXXXXX for EIN)
- STUDENT'S name
- STUDENT'S TIN (format as XXX-XX-XXXX for SSN)

**TUITION FIELDS:**
- Box 1: Payments received for qualified tuition and related expenses
- Box 4: Adjustments made for a prior year
- Box 5: Scholarships or grants
- Box 6: Adjustments to scholarships or grants for a prior year
- Box 7: Check if Box 1 includes amounts for an academic period beginning January-March (checkbox)
- Box 8: Check if at least half-time student (checkbox)
- Box 9: Check if graduate student (checkbox)
- Box 10: Insurance contract reimbursement/refund

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Payments received (Box 1), scholarships (Box 5), or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Payments received (Box 1) and scholarships (Box 5) are the most critical fields for education credits."""


FORM_5498_PROMPT = """Extract all data from this 5498 IRA Contribution Information form.

For each field, extract the exact value shown. Box locations on a standard 5498:

**IDENTITY FIELDS:**
- TRUSTEE'S or ISSUER'S name (the financial institution)
- TRUSTEE'S or ISSUER'S TIN (format as XX-XXXXXXX for EIN)
- PARTICIPANT'S name
- PARTICIPANT'S TIN (format as XXX-XX-XXXX for SSN)

**CONTRIBUTION FIELDS:**
- Box 1: IRA contributions (other than amounts in boxes 2-4, 8-10, 13a, and 14a)
- Box 2: Rollover contributions
- Box 3: Roth IRA conversion amount
- Box 4: Recharacterized contributions
- Box 5: Fair market value of account
- Box 6: Life insurance cost included in box 1
- Box 7: Checkbox for IRA type (IRA, SEP, SIMPLE, Roth IRA)
- Box 8: SEP contributions
- Box 9: SIMPLE contributions
- Box 10: Roth IRA contributions
- Box 11: Check if RMD required for next year (checkbox)
- Box 12: RMD date
- Box 13a: Postponed/late contribution
- Box 14a: Repayments
- Box 15a: FMV of certain specified assets

**IRA TYPE (Box 7):**
Look for checkboxes indicating: IRA, SEP, SIMPLE, or Roth IRA

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: IRA contributions (Box 1), Roth contributions (Box 10), or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
IRA contributions (Box 1) and Roth IRA contributions (Box 10) are the most critical fields."""


FORM_1099_S_PROMPT = """Extract all data from this 1099-S Proceeds From Real Estate Transactions form.

For each field, extract the exact value shown. Box locations on a standard 1099-S:

**IDENTITY FIELDS:**
- FILER'S name (the closing agent or attorney)
- FILER'S TIN (format as XX-XXXXXXX for EIN)
- TRANSFEROR'S name (the seller)
- TRANSFEROR'S TIN (format as XXX-XX-XXXX for SSN)

**TRANSACTION FIELDS:**
- Box 1: Date of closing (REQUIRED - format as YYYY-MM-DD or MM/DD/YYYY)
- Box 2: Gross proceeds (REQUIRED - total sale price)
- Box 3: Address or legal description of property (REQUIRED)
- Box 4: Check if transferor received or will receive property or services as part of consideration (checkbox)
- Box 5: Buyer's part of real estate tax

**CONFIDENCE ASSESSMENT:**
- HIGH: All fields clearly visible and readable
- MEDIUM: Some fields partially obscured or unclear
- LOW: Gross proceeds (Box 2), closing date (Box 1), or identity fields hard to read

Add any uncertain field names to the uncertain_fields list.
For empty boxes, use 0 (zero).
Gross proceeds (Box 2), closing date (Box 1), and property address (Box 3) are the most critical fields."""


__all__ = [
    "W2_EXTRACTION_PROMPT",
    "W2_MULTI_EXTRACTION_PROMPT",
    "FORM_1099_INT_PROMPT",
    "FORM_1099_DIV_PROMPT",
    "FORM_1099_NEC_PROMPT",
    "FORM_1098_PROMPT",
    "FORM_1099_R_PROMPT",
    "FORM_1099_G_PROMPT",
    "FORM_1098_T_PROMPT",
    "FORM_5498_PROMPT",
    "FORM_1099_S_PROMPT",
]
