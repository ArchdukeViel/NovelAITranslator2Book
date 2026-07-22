"""Frequency-based glossary term suggestion extraction from chapter text.

Extracts candidate glossary terms from translated chapter text using:
- N-gram frequency counting
- Optional LLM-based extraction for proper nouns (via provider)
- Excludes terms already in novel glossary
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Pattern for CJK ideograph runs (2-5 characters, kanji only, no kana)
_CJK_NGRAM = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]{2,5}")
# Pattern for capitalized multi-word terms
_LATIN_TERM = re.compile(r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,}){0,2}\b")


class GlossaryReader(Protocol):
    """Minimal interface to check existing glossary terms."""

    def list_glossary_entries_for_novel(
        self,
        novel_id: int,
        *,
        status: str | None = None,
        term_type: str | None = None,
        public_visible: bool | None = None,
    ) -> list[Any]: ...

    def get_glossary_entry(self, entry_id: int, *, novel_id: int | None = None) -> Any | None: ...


@dataclass
class TermSuggestion:
    """One extracted term suggestion."""

    source_term: str
    occurrence_count: int
    chapter_count: int
    context_snippets: list[str]
    source: str  # "frequency" or "llm"
    term_type: str = "character"
    confidence: float = 0.5


class SuggestionExtractor:
    """Extract glossary term candidates from chapter text."""

    def __init__(
        self,
        glossary_reader: GlossaryReader | None = None,
        *,
        min_frequency: int = 2,
        max_suggestions: int = 50,
    ) -> None:
        self.glossary_reader = glossary_reader
        self.min_frequency = min_frequency
        self.max_suggestions = max_suggestions

    def extract(
        self,
        novel_id: int | str,
        chapters: list[dict[str, Any]],
        *,
        existing_terms: set[str] | None = None,
    ) -> list[TermSuggestion]:
        """Extract term suggestions from chapter texts.

        Args:
            novel_id: Platform novel ID (int for DB, str for storage).
            chapters: List of dicts with 'chapter_id', 'translated_text' keys.
            existing_terms: Set of canonical terms to exclude.

        Returns:
            Sorted list of TermSuggestion (highest occurrence first).
        """
        try:
            return self._extract(novel_id, chapters, existing_terms=existing_terms)
        except Exception as exc:
            logger.warning("Suggestion extraction failed for novel %s: %s", novel_id, exc)
            return []

    def _extract(
        self,
        novel_id: int | str,
        chapters: list[dict[str, Any]],
        *,
        existing_terms: set[str] | None = None,
    ) -> list[TermSuggestion]:
        if existing_terms is None and self.glossary_reader is not None and isinstance(novel_id, int):
            existing = self.glossary_reader.list_glossary_entries_for_novel(novel_id)
            existing_terms = {e.canonical_term for e in existing} if existing else set()
        existing_terms = existing_terms or set()

        # Frequency counting per term per chapter
        term_chapters: dict[str, set[str]] = {}
        term_snippets: dict[str, list[str]] = {}
        term_counts: Counter = Counter()

        for ch in chapters:
            ch_id = str(ch.get("chapter_id", ""))
            text = ch.get("translated_text") or ""
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")

            seen_this_chapter: set[str] = set()

            # CJK n-grams
            for match in _CJK_NGRAM.finditer(normalized):
                term = match.group(0).strip()
                if term in existing_terms:
                    continue
                term_counts[term] += 1
                seen_this_chapter.add(term)
                _add_snippet(term_snippets, term, normalized, match.start(), match.end())

            # Latin capitalized terms
            for match in _LATIN_TERM.finditer(normalized):
                term = match.group(0).strip()
                if term in existing_terms:
                    continue
                term_counts[term] += 1
                seen_this_chapter.add(term)
                _add_snippet(term_snippets, term, normalized, match.start(), match.end())

            for term in seen_this_chapter:
                term_chapters.setdefault(term, set()).add(ch_id)

        # Build suggestions
        suggestions: list[TermSuggestion] = []
        for term, count in term_counts.most_common(self.max_suggestions * 2):
            if count < self.min_frequency:
                continue
            suggestions.append(
                TermSuggestion(
                    source_term=term,
                    occurrence_count=count,
                    chapter_count=len(term_chapters.get(term, set())),
                    context_snippets=term_snippets.get(term, [])[:3],
                    source="frequency",
                    confidence=min(0.9, 0.3 + count * 0.1),
                )
            )
            if len(suggestions) >= self.max_suggestions:
                break

        suggestions.sort(key=lambda s: (-s.occurrence_count, s.source_term.casefold()))
        return suggestions


def _add_snippet(
    snippets: dict[str, list[str]],
    term: str,
    text: str,
    start: int,
    end: int,
    radius: int = 40,
) -> None:
    if len(snippets.get(term, [])) >= 3:
        return
    ctx_start = max(0, start - radius)
    ctx_end = min(len(text), end + radius)
    snippet = text[ctx_start:ctx_end].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    if snippet:
        snippets.setdefault(term, []).append(snippet)
