"""Glossary freshness helpers for translation version invalidation.

Provides:
- ``GlossarySnapshot``: current glossary state (revision, hash, term count).
- ``compute_glossary_freshness``: classify a translation version as
  ``fresh``, ``stale``, or ``unknown`` relative to the current snapshot.

Stale detection is non-mutating: it never deactivates active versions
or rewrites stored translation files. Freshness is computed dynamically
on read/list.
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
STALE_REASON_REVISION_MISMATCH = "revision_mismatch"
STALE_REASON_HASH_MISMATCH = "hash_mismatch"
STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE = "current_snapshot_unavailable"

# Freshness state constants.
FRESHNESS_FRESH = "fresh"
FRESHNESS_STALE = "stale"
FRESHNESS_UNKNOWN = "unknown"


def compute_glossary_freshness(
    version: dict[str, Any],
    current: GlossarySnapshot | None,
) -> dict[str, Any]:
    """Classify a translation version's glossary freshness.

    Returns a dict with:
        - ``glossary_freshness``: one of ``fresh``, ``stale``, ``unknown``.
        - ``glossary_stale``: boolean convenience flag.
        - ``glossary_stale_reason``: deterministic reason string.
        - ``current_glossary_revision``: current revision or None.
        - ``current_glossary_hash``: current hash or None.

    Never mutates ``version`` or ``current``. Never deactivates active
    versions. Canonical versions without glossary metadata are rejected.
    """
    version_revision = version.get("glossary_revision")
    version_hash = version.get("glossary_hash")
    if type(version_revision) is not int or version_revision < 0:
        raise ValueError("Translation version requires a non-negative glossary_revision")

    if current is None:
        return {
            "glossary_freshness": FRESHNESS_UNKNOWN,
            "glossary_stale": False,
            "glossary_stale_reason": STALE_REASON_CURRENT_SNAPSHOT_UNAVAILABLE,
            "current_glossary_revision": None,
            "current_glossary_hash": None,
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


def compute_stale_active_translation_counts(
    versions: list[dict[str, Any]],
    current: GlossarySnapshot | None,
) -> dict[str, int | None]:
    """Count active translations by freshness state.

    Returns:
        - ``fresh_active_translation_count``
        - ``stale_active_translation_count``
        - ``current_glossary_revision``: current revision or None.
    """
    fresh = 0
    stale = 0
    for version in versions:
        freshness = compute_glossary_freshness(version, current)
        state = freshness.get("glossary_freshness")
        if state == FRESHNESS_FRESH:
            fresh += 1
        elif state == FRESHNESS_STALE:
            stale += 1

    return {
        "fresh_active_translation_count": fresh,
        "stale_active_translation_count": stale,
        "current_glossary_revision": current.revision if current else None,
    }
