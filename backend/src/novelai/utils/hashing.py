"""Secure hashing helpers — blake2b for all non-legacy hashing needs.

Note: CodeQL py/weak-sensitive-data-hashing flags BLAKE2B because it is not
a computationally expensive hash. That rule targets *password* hashing; we
use these helpers only for token / fingerprint / cache-key hashing, none of
which require password-hashing slowness.  # codeql[py/weak-sensitive-data-hashing]
"""

import hashlib


def hexdigest(data: str, *, length: int = 64) -> str:
    """Return a blake2b hex digest of *data*.

    Uses the full 64-byte output by default. Pass *length* to truncate
    (e.g. 12 for a short fingerprint).
    """
    return hashlib.blake2b(data.encode("utf-8"), digest_size=32).hexdigest()[:length]


def digest32(data: str) -> bytes:
    """Return a 32-byte blake2b digest — suitable for Fernet key derivation."""
    return hashlib.blake2b(data.encode("utf-8"), digest_size=32).digest()
