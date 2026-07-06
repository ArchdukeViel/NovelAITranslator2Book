"""Resolve global + novel glossary entries into single sorted view.

Merges approved global entries with approved novel-scope entries,
applying novel-over-global override by normalized source term.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from novelai.db.models.glossary import NovelGlossaryEntry


@dataclass(frozen=True)
class ResolvedGlossaryTerm:
    """Single resolved term after merge."""

    source_text: str
    target_text: str
    scope: str
    novel_id: int | None
    status: str
    entry_id: int


@dataclass(frozen=True)
class ResolvedGlossary:
    """Resolved glossary output for a novel."""

    novel_id: int
    entries: tuple[ResolvedGlossaryTerm, ...]
    glossary_hash: str

    def __len__(self) -> int:
        return len(self.entries)

    def __getitem__(self, index: int) -> ResolvedGlossaryTerm:
        return self.entries[index]


class GlossaryResolver:
    """Merge global + novel-scope approved entries into resolved glossary."""

    def __init__(self, repo) -> None:
        self._repo = repo

    def resolve(self, novel_id: int) -> ResolvedGlossary:
        """Build resolved glossary: global base + novel overrides."""
        global_entries = self._repo.list_approved_global_entries()
        novel_entries = self._repo.list_glossary_entries_for_novel(
            novel_id, status="approved"
        )

        global_map: dict[str, ResolvedGlossaryTerm] = {}
        for e in global_entries:
            key = self._normalize(e.canonical_term)
            global_map[key] = self._to_term(e, scope="global")

        novel_map: dict[str, ResolvedGlossaryTerm] = {}
        for e in novel_entries:
            key = self._normalize(e.canonical_term)
            novel_map[key] = self._to_term(e, scope="novel")

        merged = dict(global_map)
        merged.update(novel_map)

        sorted_terms = tuple(
            sorted(merged.values(), key=lambda t: (t.source_text.lower(), t.entry_id))
        )

        return ResolvedGlossary(
            novel_id=novel_id,
            entries=sorted_terms,
            glossary_hash=self._compute_hash(sorted_terms),
        )

    @staticmethod
    def _normalize(term: str) -> str:
        """Case-fold + strip for override-key matching."""
        return term.strip().casefold()

    @staticmethod
    def _to_term(entry: NovelGlossaryEntry, *, scope: str) -> ResolvedGlossaryTerm:
        return ResolvedGlossaryTerm(
            source_text=entry.canonical_term,
            target_text=entry.approved_translation or "",
            scope=scope,
            novel_id=entry.novel_id,
            status=entry.status,
            entry_id=entry.id,
        )

    @staticmethod
    def _compute_hash(entries: tuple[ResolvedGlossaryTerm, ...]) -> str:
        """Deterministic SHA-256 of resolved entry list."""
        h = hashlib.sha256()
        for e in entries:
            h.update(
                f"{e.source_text}\0{e.target_text}\0{e.scope}\0{e.entry_id}\0".encode()
            )
        return h.hexdigest()
