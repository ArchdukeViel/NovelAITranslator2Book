"""Utility helpers for Novel AI."""


def format_usd(amount: float, decimals: int = 4) -> str:
    """Format a USD amount for human-readable display."""
    if decimals < 0:
        raise ValueError("decimals must be >= 0.")
    return f"${amount:,.{decimals}f}"
