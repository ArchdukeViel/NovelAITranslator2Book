"""PostgreSQL advisory lock helper functions using deterministic 64-bit hashing."""

from __future__ import annotations

import hashlib
import struct

from sqlalchemy import text
from sqlalchemy.orm import Session


def string_to_advisory_lock_id(val: str) -> int:
    """Convert any string key to a signed 64-bit integer suitable for pg_advisory_lock."""
    digest = hashlib.sha256(val.encode("utf-8")).digest()
    # Unpack first 8 bytes as signed 64-bit integer
    (val_int,) = struct.unpack(">q", digest[:8])
    return val_int


def try_advisory_lock(session: Session, key: str) -> bool:
    """Attempt non-blocking lock acquisition using pg_try_advisory_lock."""
    lock_id = string_to_advisory_lock_id(key)
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        result = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": lock_id},
        ).scalar()
        return bool(result)
    return True


def advisory_unlock(session: Session, key: str) -> bool:
    """Release advisory lock."""
    lock_id = string_to_advisory_lock_id(key)
    bind = session.get_bind()
    if bind and bind.dialect.name == "postgresql":
        result = session.execute(
            text("SELECT pg_advisory_unlock(:lock_id)"),
            {"lock_id": lock_id},
        ).scalar()
        return bool(result)
    return True
