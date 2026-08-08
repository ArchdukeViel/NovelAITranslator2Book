"""Glossary candidate extraction regression: the loop previously returned
``ranked_terms[:max_terms]`` from inside the per-term branch, so only
the first qualifying term ever surfaced. This test asserts all qualifying
terms come back in the documented order."""

from __future__ import annotations

from novelai.glossary import extract_candidate_glossary_terms


def test_extract_candidate_glossary_terms_returns_all_qualifying_terms() -> None:
    """Three repeating terms must all surface (issue: only the first did)."""
    # Three sentence-initial Latin nouns each repeated exactly three
    # times. Each qualifies under ``min_occurrences=3``. Before the
    # dedent only the first qualifying term came back because the
    # ``return ranked_terms[:max_terms]`` lived inside the per-term
    # branch of the qualifying loop.
    text = (
        "Suspense carries the narrative forward. "
        "Pacing carries the prose past every paragraph. "
        "Mystery carries the reader past the third act. "
        "Suspense builds because tension compounds. "
        "Pacing builds because readers expect rhythm. "
        "Mystery builds because the trail never lies. "
        "Suspense opens every chapter on a dare. "
        "Pacing opens every chapter with a hook. "
        "Mystery opens every chapter with a question."
    )
    result = extract_candidate_glossary_terms([text], max_terms=20, min_occurrences=3)
    sources = {term.source for term in result}
    assert {"Suspense", "Mystery", "Pacing"}.issubset(sources)
    assert len(result) >= 3


def test_extract_candidate_glossary_terms_respects_max_terms() -> None:
    text = "Alpha beta gamma delta alpha beta gamma delta Alpha beta gamma delta alpha beta gamma delta"
    result = extract_candidate_glossary_terms([text], max_terms=2, min_occurrences=2)
    assert len(result) <= 2
