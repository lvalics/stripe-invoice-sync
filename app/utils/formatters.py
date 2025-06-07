"""
Utility functions for formatting data
"""
from typing import Union


def format_stripe_amount(amount: Union[int, float, str], currency: str) -> float:
    """Convert Stripe amount (in cents) to decimal amount"""
    # Stripe uses smallest currency unit (cents for USD/EUR/RON)
    # Some currencies like JPY don't have decimal places
    zero_decimal_currencies = ["JPY", "KRW", "VND", "CLP", "PYG", "UGX"]
    
    amount_float = float(amount)
    
    if currency.upper() in zero_decimal_currencies:
        return amount_float
    else:
        return amount_float / 100.0


def format_cui(cui: str) -> str:
    """Format Romanian CUI (add/remove RO prefix as needed)"""
    cui_clean = cui.strip().upper()
    
    # Remove any existing RO prefix
    if cui_clean.startswith("RO"):
        cui_clean = cui_clean[2:]
    
    # Remove any spaces or special characters
    cui_clean = ''.join(c for c in cui_clean if c.isdigit())
    
    return cui_clean


def format_cui_with_prefix(cui: str) -> str:
    """Format Romanian CUI with RO prefix"""
    cui_clean = format_cui(cui)
    if cui_clean and cui_clean != "-":
        return f"RO{cui_clean}"
    return cui_clean


def format_invoice_number(series: str, number: Union[int, str]) -> str:
    """Format invoice number with series"""
    return f"{series}-{str(number).zfill(6)}"


def format_address(address_dict: dict) -> str:
    """Format address dictionary to string"""
    parts = []
    
    if address_dict.get("line1"):
        parts.append(address_dict["line1"])
    if address_dict.get("line2"):
        parts.append(address_dict["line2"])
    if address_dict.get("city"):
        parts.append(address_dict["city"])
    if address_dict.get("state"):
        parts.append(address_dict["state"])
    if address_dict.get("postal_code"):
        parts.append(address_dict["postal_code"])
    if address_dict.get("country"):
        parts.append(address_dict["country"])
    
    return ", ".join(parts)


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate string to maximum length"""
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix