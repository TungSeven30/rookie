"""SSTB (Specified Service Trade or Business) classification.

This module provides automatic classification of businesses as SSTBs
for QBI deduction (Section 199A) purposes.

Reference: IRS Reg. 1.199A-5

Example:
    >>> from src.agents.personal_tax.sstb import classify_sstb
    >>> is_sstb, reason = classify_sstb("541110", "Legal services", "Smith Law")
    >>> is_sstb
    True
    >>> reason
    "NAICS 541110 is Legal services"
"""

from __future__ import annotations

# SSTB classification by NAICS code prefix
# Reference: IRS Reg. 1.199A-5
SSTB_NAICS_PREFIXES: dict[str, str] = {
    # Health
    "621": "Health care services",
    "6211": "Offices of physicians",
    "6212": "Offices of dentists",
    "6213": "Offices of other health practitioners",
    "622": "Hospitals",
    # Law
    "5411": "Legal services",
    "541110": "Offices of lawyers",
    # Accounting
    "5412": "Accounting, tax prep, bookkeeping",
    "541211": "Offices of certified public accountants",
    "541213": "Tax preparation services",
    "541219": "Other accounting services",
    # Actuarial science
    "524292": "Third party administration of insurance",
    # Performing arts
    "7111": "Performing arts companies",
    "7112": "Spectator sports",
    "711": "Performing arts, sports",
    # Consulting
    "5416": "Management, scientific, technical consulting",
    "541611": "Administrative management consulting",
    "541612": "Human resources consulting",
    "541613": "Marketing consulting",
    "541614": "Process, physical distribution consulting",
    "541618": "Other management consulting",
    # Athletics
    "611620": "Sports and recreation instruction",
    "713940": "Fitness and recreational sports centers",
    # Financial services
    "523": "Securities, commodity contracts, investments",
    "5231": "Securities and commodity exchanges",
    "5239": "Other financial investment activities",
    "523110": "Investment banking",
    "523120": "Securities brokerage",
    "523130": "Commodity contracts dealing",
    "523140": "Commodity contracts brokerage",
    "523920": "Portfolio management",
    "523930": "Investment advice",
    # Brokerage services
    "5312": "Offices of real estate agents and brokers",
    "531210": "Offices of real estate agents and brokers",
}

# Keywords that suggest SSTB regardless of NAICS code
SSTB_KEYWORDS: list[str] = [
    # Legal
    "law firm",
    "attorney",
    "lawyer",
    "legal services",
    # Medical
    "physician",
    "doctor",
    "medical",
    "dental",
    "dentist",
    "chiropractic",
    "optometry",
    "veterinary",
    # Accounting
    "cpa",
    "accountant",
    "accounting",
    "tax prep",
    "bookkeeping",
    # Consulting
    "consulting",
    "consultant",
    # Financial
    "financial advisor",
    "investment advisor",
    "wealth management",
    "portfolio management",
    # Brokerage
    "broker",
    "brokerage",
    # Performing arts
    "actor",
    "actress",
    "musician",
    "athlete",
    "sports",
    "performer",
]


def classify_sstb(
    naics_code: str,
    business_activity: str,
    business_name: str,
) -> tuple[bool, str | None]:
    """Classify whether a business is an SSTB.

    Specified Service Trade or Business (SSTB) includes businesses providing
    services in health, law, accounting, actuarial science, performing arts,
    consulting, athletics, financial services, or brokerage services.

    Args:
        naics_code: 6-digit NAICS business code from Schedule C.
        business_activity: Description of business activity.
        business_name: Name of the business.

    Returns:
        Tuple of (is_sstb, reason):
        - is_sstb: True if business is classified as SSTB.
        - reason: Explanation of why, or None if not SSTB.

    Example:
        >>> is_sstb, reason = classify_sstb("541110", "Offices of lawyers", "Smith Law")
        >>> is_sstb
        True
        >>> "Legal services" in reason
        True
    """
    # Check NAICS code first (most reliable)
    # Check from longest to shortest prefix for best match
    for prefix_length in [6, 5, 4, 3]:
        code_prefix = naics_code[:prefix_length]
        if code_prefix in SSTB_NAICS_PREFIXES:
            description = SSTB_NAICS_PREFIXES[code_prefix]
            return True, f"NAICS {naics_code} is {description}"

    # Check keywords in activity/name
    combined_text = f"{business_activity} {business_name}".lower()
    for keyword in SSTB_KEYWORDS:
        if keyword in combined_text:
            return True, f"Business description contains '{keyword}'"

    return False, None


def is_sstb(
    naics_code: str,
    business_activity: str = "",
    business_name: str = "",
) -> bool:
    """Simple check if business is an SSTB.

    Args:
        naics_code: 6-digit NAICS business code.
        business_activity: Description of business activity.
        business_name: Name of the business.

    Returns:
        True if business is classified as SSTB, False otherwise.

    Example:
        >>> is_sstb("541110")  # Law office
        True
        >>> is_sstb("238220")  # Plumbing
        False
    """
    result, _ = classify_sstb(naics_code, business_activity, business_name)
    return result
