"""Glossary freshness helpers for translation version invalidation.

Provides:
- ``GlossarySnapshot``: current glossary state (revision, hash, term count).
- ``compute_glossary_freshness``: classify a translation version as
  ``fresh``, ``stale``, ``legacy_unknown``, or ``unknown`` relative to
  the current snapshot.

Stale detection is non-mutating: it never deactivates active versions
or rewrites stored translation files. Freshness is computed dynamically
on read/list so legacy versions remain loadable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GlossarySnapshot:
    """Current glossary state for a novel.

    Attributes:
        revision: Monotonic glossary revision counter.
        hash: Stable hash of approved glossary content, or None if
            hash computation is not available.
        approved_term_count: Number of approved terms, or None if
            unknown.
    """

    revision: int
    hash: str | None = None
    approved_term_count: int | None = None


# Stale reason constants (REQ-6, design §"Stale Reasons").
STALE_REASON_FRESH = "fresh"
STALE_REASON_LEGACY_MISSING_REVISION = "legacy_missing_revision"
STALE_REASON_REVISION_MISMATCH = "revision_mismatch"
STALE_REASON_HASH_MISMATCH = "hash_mismatch"
STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE = "current_snapshot_unavailable"

# Freshness state constants.
FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_LEGACY_UNKNOWN = "legacy_unknown"
FRESHNESS_UNKNOWN = "unknown"


def compute_glossary_freshness(
    version: dict[str, Any],
    current: GlossarySnapshot | None,
) -> dict[str, Any]:
    """Classify a translation version's glossary freshness.

    Returns a dict with:
        - ``glossary_freshness``: one of ``fresh``, ``stale``,
          ``legacy_unknown``, ``unknown``.
        - ``glossary_stale``: boolean convenience flag.
        - ``glossary_stale_reason``: deterministic reason string.
        - ``current_glossary_revision``: current revision or None.
        - ``current_glossary_hash``: current hash or None.

    Never mutates ``version`` or ``current``. Never deactivates active
    versions. Legacy versions without glossary metadata are reported as
    ``legacy_unknown`` rather than treated as errors.
    """
    if current is None:
        return {
            "glossary_freshness": FRESHNESS_UNKNOWN,
            "glossary_stale": False,
            "glossary_stale_reason": STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE,
            "current_glossary_revision": None,
            "current_glossary_hash": None,
        }

    version_revision = version.get("glossary_revision")
    version_hash = version.get("glossary_hash")

    if not isinstance(version_revision, int):
        return {
            "glossary_freshness": FRESHNESS_LEGACY_UNKNOWN,
            "glossary_stale": current.revision > 0,
            "glossary_stale_reason": STALE_REASON_LEGACY_MISSING_REVISION,
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    if version_revision < current.revision:
        return {
            "glossary_freshness": FRESHNESS_STALE,
            "glossary_stale": True,
            "glossary_stale_reason": STALE_REASON_REVISION_MISMATCH,
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    if (
        isinstance(current.hash, str)
        and current.hash
        and isinstance(version_hash, str)
        and version_hash
        and version_hash != current.hash
    ):
        return {
            "glossary_freshness": FRESHNESS_STALE,
            "glossary_stale": True,
            "glossary_stale_reason": STALE_REASON_HASH_MISMATCH,
            "current_glossary_revision": current.revision,
            "current_glossary_hash": current.hash,
        }

    return {
        "glossary_freshness": FRESHNESS_FRESH,
        "glossary_stale": False,
        "glossary_stale_reason": STALE_REASON_FRESH,
        "current_glossary_revision": current.revision,
        "current_glossary_hash": current.hash,
    }
