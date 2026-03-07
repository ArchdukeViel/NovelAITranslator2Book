from __future__ import annotations


def attribute_to_str(value: object) -> str | None:
    """Normalize a BeautifulSoup attribute value to a single string."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [part for part in value if isinstance(part, str)]
        return parts[0] if len(parts) == 1 else None
    return None
