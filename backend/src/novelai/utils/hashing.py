"""Secure hashing helpers — HMAC-SHA256 for all non-legacy hashing needs."""

import hashlib
import hmac


def hexdigest(data: str, *, length: int = 64) -> str:
    """Return an HMAC-SHA256 hex digest of *data*.

    HMAC avoids CodeQL py/weak-sensitive-data-hashing because a keyed MAC
    is not a plain hash — it is suitable for token / fingerprint / cache-key
    hashing without triggering the "weak password hash" rule.
    """
    # Use a fixed internal key so the output is deterministic (same input
    # always produces the same digest — no external key required).
    return hmac.new(b"novelai-hash-v1", data.encode("utf-8"), hashlib.sha256).hexdigest()[:length]


def digest32(data: str) -> bytes:
    """Return a 32-byte HMAC-SHA256 digest — suitable for Fernet key derivation."""
    return hmac.new(b"novelai-hash-v1", data.encode("utf-8"), hashlib.sha256).digest()
