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
For missing optional fields, use default values."""

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


__all__ = [
    "W2_EXTRACTION_PROMPT",
    "FORM_1099_INT_PROMPT",
    "FORM_1099_DIV_PROMPT",
    "FORM_1099_NEC_PROMPT",
]
