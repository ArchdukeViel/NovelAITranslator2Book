"""Kakuyomu source subpackage."""

from novelai.sources.kakuyomu.parser import (
    BODY_SELECTORS,
    REMOVE_FROM_BODY_SELECTORS,
    TITLE_SELECTORS,
    apollo_record,
    apollo_ref,
    extract_chapters_from_next_data,
    next_data_apollo_state,
)

__all__ = [
    "BODY_SELECTORS",
    "REMOVE_FROM_BODY_SELECTORS",
    "TITLE_SELECTORS",
    "apollo_record",
    "apollo_ref",
    "extract_chapters_from_next_data",
    "next_data_apollo_state",
]
