"""Currency formatting utilities."""

# Mapping of currency codes to their display symbols
_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "CA$",
    "AUD": "A$",
}


def cents_to_display(cents: int, currency: str = "USD") -> str:
    """Convert an integer amount in cents to a human-readable display string.

    Args:
        cents: The monetary amount in the smallest currency unit (e.g. 4500 for $45.00).
        currency: ISO 4217 currency code. Defaults to "USD".

    Returns:
        Formatted string, e.g. "$45.00" for cents=4500, currency="USD".
    """
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency.upper() + " ")
    major = cents // 100
    minor = cents % 100
    return f"{symbol}{major}.{minor:02d}"
