from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GlossaryTerm:
    source: str
    target: str
    locked: bool = True
    notes: str | None = None

    def normalized(self) -> GlossaryTerm:
        source = str(self.source).strip()
        target = str(self.target).strip()
        if not source:
            raise ValueError("Glossary source term cannot be empty.")
        if not target:
            raise ValueError("Glossary target term cannot be empty.")
        notes = self.notes.strip() if isinstance(self.notes, str) and self.notes.strip() else None
        return GlossaryTerm(
            source=source,
            target=target,
            locked=bool(self.locked),
            notes=notes,
        )


@dataclass
class Glossary:
    """A glossary of terms used to enforce consistent translations."""

    terms: dict[str, GlossaryTerm] = field(default_factory=dict)

    def add_term(
        self,
        source: str,
        target: str,
        notes: str | None = None,
        *,
        locked: bool = True,
    ) -> None:
        term = GlossaryTerm(source=source, target=target, locked=locked, notes=notes).normalized()
        self.terms[term.source] = term

    def as_entries(self) -> list[GlossaryTerm]:
        return sorted(
            (term.normalized() for term in self.terms.values()),
            key=lambda term: (term.source.casefold(), term.source),
        )

    @classmethod
    def from_entries(cls, entries: Iterable[GlossaryEntryLike]) -> Glossary:
        glossary = cls()
        for entry in normalize_glossary_entries(entries):
            glossary.terms[entry.source] = entry
        return glossary

    def translate(self, text: str) -> str:
        """Apply glossary term substitutions to translated text."""
        for term in sorted(self.as_entries(), key=lambda item: len(item.source), reverse=True):
            text = text.replace(term.source, term.target)
        return text


GlossaryEntryLike = GlossaryTerm | Mapping[str, Any]


def normalize_glossary_entry(entry: GlossaryEntryLike) -> GlossaryTerm:
    if isinstance(entry, GlossaryTerm):
        return entry.normalized()
    if isinstance(entry, Mapping):
        return GlossaryTerm(
            source=str(entry.get("source", "")),
            target=str(entry.get("target", "")),
            locked=bool(entry.get("locked", True)),
            notes=entry.get("notes") if isinstance(entry.get("notes"), str) else None,
        ).normalized()
    raise TypeError(f"Unsupported glossary entry type: {type(entry)!r}")


def normalize_glossary_entries(entries: Iterable[GlossaryEntryLike] | Glossary | None) -> list[GlossaryTerm]:
    if entries is None:
        return []
    if isinstance(entries, Glossary):
        return entries.as_entries()

    deduped: dict[str, GlossaryTerm] = {}
    for raw_entry in entries:
        entry = normalize_glossary_entry(raw_entry)
        deduped[entry.source] = entry
    return sorted(deduped.values(), key=lambda term: (term.source.casefold(), term.source))
