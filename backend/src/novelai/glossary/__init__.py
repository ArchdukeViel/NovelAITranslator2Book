"""Glossary / terminology management."""

from novelai.glossary.glossary import (
    Glossary,
    GlossaryEntryLike,
    GlossaryTerm,
    canonical_glossary_hash,
    extract_candidate_glossary_terms,
    extract_term_context,
    glossary_status_counts,
    normalize_glossary_entries,
    normalize_glossary_entry,
    rank_glossary_terms_for_text,
    summarize_term_context,
)

__all__ = [
    "Glossary",
    "GlossaryEntryLike",
    "GlossaryTerm",
    "canonical_glossary_hash",
    "extract_candidate_glossary_terms",
    "extract_term_context",
    "glossary_status_counts",
    "normalize_glossary_entries",
    "normalize_glossary_entry",
    "rank_glossary_terms_for_text",
    "summarize_term_context",
]
