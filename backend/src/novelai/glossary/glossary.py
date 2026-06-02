from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any


TERM_STATUSES = {"pending", "approved", "ignored", "translated"}
_CJK_TERM_PATTERN = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]{2,12}")
_LATIN_TERM_PATTERN = re.compile(r"\b[A-Z][A-Za-z]{2,}(?:\s+[A-Z][A-Za-z]{2,}){0,2}\b")


def _normalize_context_history(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        cleaned = value.strip()
        return (cleaned,) if cleaned else ()
    if not isinstance(value, Iterable):
        return ()

    history: list[str] = []
    for item in value:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                history.append(cleaned)
    return tuple(history)


def summarize_term_context(
    context_history: Iterable[str],
    *,
    max_items: int = 3,
    max_chars: int = 240,
) -> str | None:
    """Build a compact summary from historical context observations."""
    deduped: list[str] = []
    for raw in context_history:
        if not isinstance(raw, str):
            continue
        cleaned = raw.strip()
        if not cleaned or cleaned in deduped:
            continue
        deduped.append(cleaned)
        if len(deduped) >= max_items:
            break

    if not deduped:
        return None

    summary = " | ".join(deduped)
    return summary[: max_chars - 1] + "..." if len(summary) > max_chars else summary


def extract_term_context(text: str, term: str, *, radius: int = 40) -> str | None:
    """Extract a short snippet around a term occurrence for context memory."""
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not normalized_text.strip() or not term.strip():
        return None

    idx = normalized_text.casefold().find(term.casefold())
    if idx < 0:
        return None

    start = max(0, idx - radius)
    end = min(len(normalized_text), idx + len(term) + radius)
    snippet = normalized_text[start:end].strip()
    if not snippet:
        return None
    return re.sub(r"\s+", " ", snippet)


def rank_glossary_terms_for_text(
    text: str,
    terms: Iterable[GlossaryTerm],
    *,
    chunk_index: int = 0,
    max_entries: int = 12,
    max_context_chars: int = 1200,
) -> list[GlossaryTerm]:
    """Rank glossary entries by chunk relevance and return the top subset."""
    normalized_text = text.casefold()
    ranked: list[tuple[float, GlossaryTerm]] = []

    for term in terms:
        if term.status == "ignored":
            continue

        source_cf = term.source.casefold()
        contains_source = source_cf in normalized_text

        score = 0.0
        if contains_source:
            score += 10.0
        if term.status in {"approved", "translated"}:
            score += 1.0
        if term.occurrence_count > 0:
            score += min(term.occurrence_count, 10) * 0.1
        if term.last_seen_index is not None:
            distance = abs(chunk_index - term.last_seen_index)
            score += max(0.0, 1.0 - (distance * 0.1))
        if term.context_summary:
            score += 0.25

        if score > 0.0:
            ranked.append((score, term))

    ranked.sort(key=lambda item: (-item[0], item[1].source.casefold(), item[1].source))

    selected: list[GlossaryTerm] = []
    used_chars = 0
    for _, term in ranked:
        if len(selected) >= max_entries:
            break
        term_cost = len(term.source) + len(term.target)
        if term.context_summary:
            term_cost += len(term.context_summary)
        if selected and used_chars + term_cost > max_context_chars:
            break
        selected.append(term)
        used_chars += term_cost

    return selected


@dataclass
class GlossaryTerm:
    source: str
    target: str
    locked: bool = True
    notes: str | None = None
    status: str = "approved"
    context_history: tuple[str, ...] = field(default_factory=tuple)
    context_summary: str | None = None
    occurrence_count: int = 0
    last_seen_index: int | None = None

    def normalized(self) -> GlossaryTerm:
        source = str(self.source).strip()
        target = str(self.target).strip()
        if not source:
            raise ValueError("Glossary source term cannot be empty.")
        if not target:
            raise ValueError("Glossary target term cannot be empty.")
        notes = self.notes.strip() if isinstance(self.notes, str) and self.notes.strip() else None
        status = str(self.status).strip().lower() or "approved"
        if status not in TERM_STATUSES:
            raise ValueError(
                "Glossary term status must be one of: pending, approved, ignored, translated."
            )
        context_history = _normalize_context_history(self.context_history)
        context_summary = (
            self.context_summary.strip()
            if isinstance(self.context_summary, str) and self.context_summary.strip()
            else summarize_term_context(context_history)
        )
        try:
            occurrence_raw = int(self.occurrence_count)
        except (TypeError, ValueError):
            occurrence_raw = 0
        occurrence_count = occurrence_raw if occurrence_raw > 0 else 0
        last_seen_index = self.last_seen_index if isinstance(self.last_seen_index, int) else None

        return GlossaryTerm(
            source=source,
            target=target,
            locked=bool(self.locked),
            notes=notes,
            status=status,
            context_history=context_history,
            context_summary=context_summary,
            occurrence_count=occurrence_count,
            last_seen_index=last_seen_index,
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
        occurrence_value = entry.get("occurrence_count", 0)
        try:
            occurrence_count = int(occurrence_value or 0)
        except (TypeError, ValueError):
            occurrence_count = 0

        last_seen_raw = entry.get("last_seen_index")
        try:
            last_seen_index = int(last_seen_raw) if last_seen_raw is not None else None
        except (TypeError, ValueError):
            last_seen_index = None

        return GlossaryTerm(
            source=str(entry.get("source", "")),
            target=str(entry.get("target", "")),
            locked=bool(entry.get("locked", True)),
            notes=entry.get("notes") if isinstance(entry.get("notes"), str) else None,
            status=str(entry.get("status", "approved")),
            context_history=_normalize_context_history(entry.get("context_history")),
            context_summary=entry.get("context_summary") if isinstance(entry.get("context_summary"), str) else None,
            occurrence_count=occurrence_count,
            last_seen_index=last_seen_index,
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


def glossary_status_counts(entries: Iterable[GlossaryEntryLike] | Glossary | None) -> dict[str, int]:
    """Return normalized glossary status counters for reporting surfaces."""
    normalized_entries = normalize_glossary_entries(entries)
    counts = {
        "pending": 0,
        "approved": 0,
        "ignored": 0,
        "translated": 0,
        "reviewed": 0,
        "total": len(normalized_entries),
    }
    for entry in normalized_entries:
        counts[entry.status] += 1
        if entry.status != "pending":
            counts["reviewed"] += 1
    return counts


def extract_candidate_glossary_terms(
    texts: Iterable[str],
    *,
    max_terms: int = 50,
    min_occurrences: int = 2,
) -> list[GlossaryTerm]:
    """Heuristically extract recurring glossary candidates from imported text."""
    candidates: dict[str, list[str]] = {}

    for raw_text in texts:
        if not isinstance(raw_text, str):
            continue
        normalized_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        for pattern in (_CJK_TERM_PATTERN, _LATIN_TERM_PATTERN):
            for match in pattern.finditer(normalized_text):
                term = match.group(0).strip()
                if not term:
                    continue
                snippet = extract_term_context(normalized_text, term, radius=48) or term
                candidates.setdefault(term, []).append(snippet)

    ranked_terms: list[GlossaryTerm] = []
    for term, history in candidates.items():
        if len(history) < min_occurrences:
            continue
        ranked_terms.append(
            GlossaryTerm(
                source=term,
                target=term,
                locked=True,
                status="pending",
                context_history=tuple(history[:8]),
                context_summary=summarize_term_context(history),
                occurrence_count=len(history),
            ).normalized()
        )

    ranked_terms.sort(key=lambda item: (-item.occurrence_count, item.source.casefold(), item.source))
    return ranked_terms[:max_terms]
