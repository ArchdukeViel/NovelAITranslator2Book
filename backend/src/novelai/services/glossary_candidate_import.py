"""No-provider glossary candidate import from saved chapter text.

This service reads saved raw/translated chapter content and proposes
novel-scoped Reviewing candidates. It does not call providers, translate,
rewrite chapters, expose routes, or approve glossary entries.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryAlias
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository


class ChapterStorageReader(Protocol):
    """Storage methods used by the candidate importer."""

    def list_stored_chapters(self, novel_id: str) -> list[str]: ...

    def load_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None: ...

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None: ...


@dataclass(frozen=True)
class GlossaryCandidateOccurrence:
    """Compact evidence reference for one candidate observation."""

    chapter_storage_id: str
    chapter_id: int | None = None
    chapter_number: int | None = None
    source_site: str | None = None
    source_adapter: str | None = None
    source_novel_id: str | None = None
    raw_source_term: str | None = None
    observed_translated_term: str | None = None
    evidence_quality: str = "translated_only"


@dataclass
class GlossaryCandidateSuggestion:
    """In-memory suggestion created by no-provider heuristics."""

    canonical_term: str
    approved_translation: str
    term_type: str
    confidence: float
    occurrence_count: int
    chapter_count: int
    occurrences: list[GlossaryCandidateOccurrence] = field(default_factory=list)
    source: str = "saved_chapters"
    skipped_reason: str | None = None
    existing_entry_id: int | None = None


@dataclass
class GlossaryCandidateImportResult:
    """Summary of dry-run or apply-mode candidate import."""

    dry_run: bool
    candidates: list[GlossaryCandidateSuggestion]
    candidates_found: int
    candidates_created: int = 0
    candidates_merged: int = 0
    candidates_skipped: int = 0
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _ChapterSnapshot:
    storage_id: str
    db_chapter_id: int | None
    chapter_number: int | None
    raw_text: str
    translated_text: str
    source_site: str | None
    source_adapter: str | None
    source_novel_id: str | None


@dataclass
class _CandidateAccumulator:
    display: str
    normalized: str
    term_type: str
    occurrence_count: int = 0
    chapters: set[str] = field(default_factory=set)
    occurrences: list[GlossaryCandidateOccurrence] = field(default_factory=list)
    multiword: bool = False
    domain_hit: bool = False
    raw_signal: bool = False
    display_counts: Counter[str] = field(default_factory=Counter)

    def add(
        self,
        *,
        display: str,
        snapshot: _ChapterSnapshot,
        raw_source_term: str | None = None,
        evidence_quality: str = "translated_only",
        multiword: bool = False,
        domain_hit: bool = False,
        raw_signal: bool = False,
    ) -> None:
        self.occurrence_count += 1
        self.chapters.add(snapshot.storage_id)
        self.display_counts[display] += 1
        self.display = self.display_counts.most_common(1)[0][0]
        self.multiword = self.multiword or multiword
        self.domain_hit = self.domain_hit or domain_hit
        self.raw_signal = self.raw_signal or raw_signal
        self.occurrences.append(
            GlossaryCandidateOccurrence(
                chapter_storage_id=snapshot.storage_id,
                chapter_id=snapshot.db_chapter_id,
                chapter_number=snapshot.chapter_number,
                source_site=snapshot.source_site,
                source_adapter=snapshot.source_adapter,
                source_novel_id=snapshot.source_novel_id,
                raw_source_term=raw_source_term,
                observed_translated_term=display if evidence_quality != "clean_source" else None,
                evidence_quality=evidence_quality,
            )
        )


_TITLE_TOKEN = r"[A-Z][a-zA-Z]*(?:'[a-zA-Z]+)?"
_CONNECTOR = r"(?:of|the|and|de|du|la|le|von|van)"
_TITLE_PHRASE_RE = re.compile(rf"\b{_TITLE_TOKEN}(?:\s+(?:{_CONNECTOR}|{_TITLE_TOKEN}))*\b")
_KATAKANA_RE = re.compile(r"[\u30A1-\u30FA\u30FC]{2,}")
_WHITESPACE_RE = re.compile(r"\s+")

_COMMON_START_WORDS = {
    "A",
    "After",
    "All",
    "Also",
    "And",
    "As",
    "At",
    "Before",
    "But",
    "By",
    "For",
    "From",
    "He",
    "Her",
    "His",
    "I",
    "If",
    "In",
    "It",
    "Its",
    "My",
    "No",
    "Not",
    "On",
    "Once",
    "She",
    "So",
    "That",
    "The",
    "Then",
    "They",
    "This",
    "To",
    "We",
    "When",
    "While",
    "With",
    "You",
}
_GENERIC_WORDS = {
    "Chapter",
    "English",
    "Japanese",
    "Machine",
    "Translated",
    "Translation",
}
_DOMAIN_WORDS = {
    "Blessing",
    "Duke",
    "House",
    "Kingdom",
    "Knight",
    "Knights",
    "Magic",
    "Marquis",
    "Marquisate",
    "Order",
    "Realm",
    "Saint",
    "Skill",
    "Spirit",
    "Tree",
    "Village",
    "World",
}


class GlossaryCandidateImporter:
    """Import no-provider glossary Reviewing candidates from saved chapters."""

    def __init__(
        self,
        db: Session,
        storage: ChapterStorageReader,
        *,
        repository: GlossaryRepository | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.repository = repository or GlossaryRepository(db)

    def import_from_saved_chapters(
        self,
        novel_id: int,
        *,
        storage_novel_id: str | None = None,
        dry_run: bool = True,
        max_candidates: int = 100,
    ) -> GlossaryCandidateImportResult:
        """Return or apply conservative no-provider candidate suggestions."""

        storage_key = storage_novel_id or self._storage_key_for_novel(novel_id)
        warnings: list[str] = []
        snapshots = self._load_chapter_snapshots(novel_id, storage_key, warnings)
        accumulators = self._extract_candidates(snapshots)
        suggestions = self._build_suggestions(accumulators, max_candidates=max_candidates)
        result = GlossaryCandidateImportResult(
            dry_run=dry_run,
            candidates=suggestions,
            candidates_found=len(suggestions),
            warnings=warnings,
        )
        if dry_run:
            return result
        self._apply_suggestions(novel_id, result)
        return result

    def _storage_key_for_novel(self, novel_id: int) -> str:
        novel = self.db.get(Novel, novel_id)
        if novel is not None and novel.slug:
            return novel.slug
        return str(novel_id)

    def _load_chapter_snapshots(
        self,
        novel_id: int,
        storage_novel_id: str,
        warnings: list[str],
    ) -> list[_ChapterSnapshot]:
        chapter_ids = self._stored_chapter_ids(storage_novel_id)
        chapter_meta = self._chapter_metadata(novel_id)
        snapshots: list[_ChapterSnapshot] = []
        raw_seen = False
        translated_seen = False

        for storage_id in chapter_ids:
            raw = self.storage.load_chapter(storage_novel_id, storage_id) or {}
            translated = self.storage.load_translated_chapter(storage_novel_id, storage_id) or {}
            raw_text = raw.get("text") if isinstance(raw.get("text"), str) else ""
            translated_text = translated.get("text") if isinstance(translated.get("text"), str) else ""
            if not raw_text and not translated_text:
                continue
            raw_seen = raw_seen or bool(raw_text)
            translated_seen = translated_seen or bool(translated_text)
            db_chapter_id, chapter_number = chapter_meta.get(storage_id, (None, _int_or_none(storage_id)))
            snapshots.append(
                _ChapterSnapshot(
                    storage_id=storage_id,
                    db_chapter_id=db_chapter_id,
                    chapter_number=chapter_number,
                    raw_text=raw_text,
                    translated_text=translated_text,
                    source_site=_clean_source_site(raw.get("source_key")),
                    source_adapter=_clean_source_site(raw.get("input_adapter_key") or raw.get("source_key")),
                    source_novel_id=storage_novel_id,
                )
            )

        if not raw_seen:
            warnings.append("Raw chapter text was unavailable; imported candidates use translated text only.")
        if not translated_seen:
            warnings.append("Translated chapter text was unavailable; imported candidates use raw text only.")
        if not snapshots:
            warnings.append("No saved raw or translated chapter text was available for candidate import.")
        return snapshots

    def _stored_chapter_ids(self, storage_novel_id: str) -> list[str]:
        list_stored = getattr(self.storage, "list_stored_chapters", None)
        if callable(list_stored):
            return list_stored(storage_novel_id)
        list_translated = getattr(self.storage, "list_translated_chapters", None)
        if callable(list_translated):
            return list_translated(storage_novel_id)
        return []

    def _chapter_metadata(self, novel_id: int) -> dict[str, tuple[int | None, int | None]]:
        stmt = select(Chapter).where(Chapter.novel_id == novel_id)
        metadata: dict[str, tuple[int | None, int | None]] = {}
        for chapter in self.db.scalars(stmt):
            metadata[str(chapter.chapter_number)] = (chapter.id, chapter.chapter_number)
            if chapter.raw_storage_key:
                metadata[str(chapter.raw_storage_key)] = (chapter.id, chapter.chapter_number)
            if chapter.translated_storage_key:
                metadata[str(chapter.translated_storage_key)] = (chapter.id, chapter.chapter_number)
        return metadata

    def _extract_candidates(self, snapshots: list[_ChapterSnapshot]) -> dict[str, _CandidateAccumulator]:
        accumulators: dict[str, _CandidateAccumulator] = {}
        for snapshot in snapshots:
            self._extract_translated_candidates(snapshot, accumulators)
            self._extract_raw_katakana_candidates(snapshot, accumulators)
        return accumulators

    def _extract_translated_candidates(
        self,
        snapshot: _ChapterSnapshot,
        accumulators: dict[str, _CandidateAccumulator],
    ) -> None:
        for match in _TITLE_PHRASE_RE.finditer(snapshot.translated_text):
            candidate = _normalize_display(match.group(0))
            if not _is_valid_english_candidate(candidate):
                continue
            normalized = _normal_key(candidate)
            words = candidate.split()
            domain_hit = any(word.strip("'") in _DOMAIN_WORDS for word in words)
            accumulator = accumulators.get(normalized)
            if accumulator is None:
                accumulator = _CandidateAccumulator(
                    display=candidate,
                    normalized=normalized,
                    term_type=_infer_term_type(candidate),
                )
                accumulators[normalized] = accumulator
            accumulator.add(
                display=candidate,
                snapshot=snapshot,
                multiword=len(words) > 1,
                domain_hit=domain_hit,
            )

    def _extract_raw_katakana_candidates(
        self,
        snapshot: _ChapterSnapshot,
        accumulators: dict[str, _CandidateAccumulator],
    ) -> None:
        for match in _KATAKANA_RE.finditer(snapshot.raw_text):
            candidate = _normalize_display(match.group(0))
            if len(candidate) < 2:
                continue
            normalized = _normal_key(candidate)
            accumulator = accumulators.get(normalized)
            if accumulator is None:
                accumulator = _CandidateAccumulator(
                    display=candidate,
                    normalized=normalized,
                    term_type="other",
                )
                accumulators[normalized] = accumulator
            accumulator.add(
                display=candidate,
                snapshot=snapshot,
                raw_source_term=candidate,
                evidence_quality="clean_source",
                raw_signal=True,
            )

    def _build_suggestions(
        self,
        accumulators: dict[str, _CandidateAccumulator],
        *,
        max_candidates: int,
    ) -> list[GlossaryCandidateSuggestion]:
        suggestions: list[GlossaryCandidateSuggestion] = []
        for accumulator in accumulators.values():
            if accumulator.occurrence_count < 2 and not accumulator.domain_hit:
                continue
            confidence = _confidence(accumulator)
            if confidence < 0.2:
                continue
            suggestions.append(
                GlossaryCandidateSuggestion(
                    canonical_term=accumulator.display,
                    approved_translation=accumulator.display,
                    term_type=accumulator.term_type,
                    confidence=confidence,
                    occurrence_count=accumulator.occurrence_count,
                    chapter_count=len(accumulator.chapters),
                    occurrences=_compact_occurrences(accumulator.occurrences),
                )
            )
        suggestions.sort(key=lambda item: (-item.confidence, -item.chapter_count, item.canonical_term.casefold()))
        return suggestions[:max_candidates]

    def _apply_suggestions(self, novel_id: int, result: GlossaryCandidateImportResult) -> None:
        existing_entries = self.repository.list_glossary_entries_for_novel(novel_id)
        entries_by_term = {_normal_key(entry.canonical_term): entry for entry in existing_entries}
        blocked_aliases = self._blocked_aliases(novel_id)

        for suggestion in result.candidates:
            key = _normal_key(suggestion.canonical_term)
            if key in blocked_aliases:
                result.candidates_skipped += 1
                suggestion.skipped_reason = "blocked_alias_conflict"
                conflict = f"{suggestion.canonical_term} matches a rejected/banned alias for this novel."
                result.conflicts.append(conflict)
                continue

            existing = entries_by_term.get(key)
            if existing is not None and existing.status == "approved":
                result.candidates_skipped += 1
                suggestion.skipped_reason = "approved_entry_exists"
                suggestion.existing_entry_id = existing.id
                continue

            if existing is None:
                entry = self.repository.create_glossary_entry(
                    novel_id=novel_id,
                    canonical_term=suggestion.canonical_term,
                    term_type=suggestion.term_type,
                    approved_translation=suggestion.approved_translation,
                    status="candidate",
                    enforcement_level="none",
                    admin_notes="Imported as a Reviewing candidate from saved chapters.",
                    confidence=suggestion.confidence,
                    decision_source="candidate_import",
                    rationale="No-provider saved chapter candidate import.",
                )
                entries_by_term[key] = entry
                suggestion.existing_entry_id = entry.id
                result.candidates_created += 1
            else:
                entry = existing
                suggestion.existing_entry_id = entry.id
                if existing.status != "approved":
                    self.repository.update_glossary_entry(
                        existing.id,
                        novel_id=novel_id,
                        confidence=max(existing.confidence or 0.0, suggestion.confidence),
                    )
                    result.candidates_merged += 1

            self._add_provenance_for_suggestion(novel_id, entry.id, suggestion)

    def _blocked_aliases(self, novel_id: int) -> set[str]:
        stmt = select(NovelGlossaryAlias).where(
            NovelGlossaryAlias.novel_id == novel_id,
            NovelGlossaryAlias.alias_type.in_(("banned", "rejected")),
        )
        return {_normal_key(alias.alias_text) for alias in self.db.scalars(stmt)}

    def _add_provenance_for_suggestion(
        self,
        novel_id: int,
        entry_id: int,
        suggestion: GlossaryCandidateSuggestion,
    ) -> None:
        seen_refs = {
            (
                item.source_chapter_id,
                item.source_chapter_number,
                item.observed_translated_term,
                item.raw_source_term,
            )
            for item in self.repository.list_source_provenance_for_entry(entry_id, novel_id=novel_id)
        }
        for occurrence in suggestion.occurrences:
            ref_key = (
                occurrence.chapter_storage_id,
                occurrence.chapter_number,
                occurrence.observed_translated_term,
                occurrence.raw_source_term,
            )
            if ref_key in seen_refs:
                continue
            self.repository.add_source_provenance(
                novel_id=novel_id,
                entry_id=entry_id,
                source_site=occurrence.source_site or "saved_chapters",
                source_adapter=occurrence.source_adapter or "saved_chapters",
                source_novel_id=occurrence.source_novel_id,
                source_chapter_id=occurrence.chapter_storage_id,
                source_chapter_number=occurrence.chapter_number,
                chapter_id=occurrence.chapter_id,
                raw_source_term=occurrence.raw_source_term,
                observed_translated_term=occurrence.observed_translated_term,
                evidence_ref=f"saved_chapter:{occurrence.chapter_storage_id}",
                local_reference=f"chapter:{occurrence.chapter_storage_id}",
                evidence_quality=occurrence.evidence_quality,
                confidence=suggestion.confidence,
            )
            seen_refs.add(ref_key)


def _normalize_display(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value.strip(" \t\r\n.,;:!?()[]{}\"'")).strip()


def _normal_key(value: str) -> str:
    return _normalize_display(value).casefold()


def _is_valid_english_candidate(value: str) -> bool:
    if not value or value in _GENERIC_WORDS:
        return False
    words = value.split()
    if len(words) == 1:
        word = words[0]
        if word in _COMMON_START_WORDS or word in _GENERIC_WORDS:
            return False
        if len(word) < 3 and word not in {"UR"}:
            return False
    return len(words) <= 6


def _infer_term_type(value: str) -> str:
    words = set(value.split())
    if words & {"Village", "Kingdom", "Realm"}:
        return "place"
    if words & {"House"}:
        return "family_house"
    if words & {"Order", "Knight", "Knights"}:
        return "organization"
    if words & {"Blessing", "Magic", "Skill", "Sword"}:
        return "skill"
    if words & {"Duke", "Marquis", "Marquisate"}:
        return "title"
    if words & {"Tree", "World", "Spirit"}:
        return "concept"
    return "character" if len(words) == 1 else "other"


def _confidence(accumulator: _CandidateAccumulator) -> float:
    score = 0.2
    score += min(accumulator.occurrence_count, 8) * 0.05
    score += min(len(accumulator.chapters), 4) * 0.08
    if accumulator.multiword:
        score += 0.16
    if accumulator.domain_hit:
        score += 0.14
    if accumulator.raw_signal:
        score += 0.10
    return min(0.95, round(score, 3))


def _compact_occurrences(
    occurrences: list[GlossaryCandidateOccurrence],
    *,
    max_items: int = 5,
) -> list[GlossaryCandidateOccurrence]:
    compact: list[GlossaryCandidateOccurrence] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for occurrence in occurrences:
        key = (occurrence.chapter_storage_id, occurrence.raw_source_term, occurrence.observed_translated_term)
        if key in seen:
            continue
        seen.add(key)
        compact.append(occurrence)
        if len(compact) >= max_items:
            break
    return compact


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except ValueError:
        return None


def _clean_source_site(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
