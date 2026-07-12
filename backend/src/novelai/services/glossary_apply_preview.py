"""Preview-only approved glossary term replacement for saved translations.

This service scans storage-backed translated chapter text and reports exact
replacement candidates. It does not write chapter text, create backups, create
audit records, approve glossary entries, call providers, scrape, or translate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryAlias, NovelGlossaryEntry
from novelai.db.models.novel import Novel


class TranslatedChapterReader(Protocol):
    def list_stored_chapters(self, novel_id: str) -> list[str]: ...

    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None: ...


RiskStatus = Literal["safe", "needs_review", "blocked"]

_OLD_VARIANT_ALIAS_TYPES = {"rejected", "banned", "deprecated"}
_DEFAULT_MAX_CHAPTERS = 20
_DEFAULT_MAX_MATCHES = 100
_MAX_SNIPPET_CHARS = 220
_SNIPPET_CONTEXT_CHARS = 70


@dataclass(frozen=True)
class GlossaryApplyPreviewRequest:
    entry_ids: list[int] | None = None
    include_all_approved: bool = False
    chapter_numbers: list[int] | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    max_chapters: int = _DEFAULT_MAX_CHAPTERS
    max_matches: int = _DEFAULT_MAX_MATCHES
    max_delta_fraction: float = 0.15


@dataclass(frozen=True)
class GlossaryReplacementPreview:
    glossary_entry_id: int
    canonical_term: str
    old_text: str
    new_text: str
    risk_status: RiskStatus
    reason_codes: list[str]
    note: str
    start_offset: int
    end_offset: int
    before_snippet: str
    after_snippet: str


@dataclass(frozen=True)
class GlossaryChapterPreview:
    chapter_storage_id: str
    chapter_id: int | None
    chapter_number: int | None
    replacement_count: int
    safe_count: int
    needs_review_count: int
    blocked_count: int
    replacements: list[GlossaryReplacementPreview]
    delta_fraction: float = 0.0


@dataclass(frozen=True)
class GlossaryApplyPreviewResult:
    novel_id: int
    scanned_chapter_count: int
    matched_chapter_count: int
    skipped_chapter_count: int
    total_match_count: int
    safe_match_count: int
    needs_review_match_count: int
    blocked_match_count: int
    entry_count: int
    warnings: list[str] = field(default_factory=list)
    chapters: list[GlossaryChapterPreview] = field(default_factory=list)


@dataclass(frozen=True)
class _VariantSpec:
    entry_id: int
    canonical_term: str
    old_text: str
    new_text: str
    alias_type: str


@dataclass(frozen=True)
class _ChapterContext:
    storage_id: str
    db_chapter_id: int | None
    chapter_number: int | None
    text: str


class GlossaryApplyPreviewService:
    """Preview exact approved glossary replacements in saved translations."""

    def __init__(self, db: Session, storage: TranslatedChapterReader) -> None:
        self.db = db
        self.storage = storage

    def preview(self, novel_id: int, request: GlossaryApplyPreviewRequest) -> GlossaryApplyPreviewResult:
        if not request.entry_ids and not request.include_all_approved:
            raise ValueError("entry_ids or include_all_approved is required for glossary apply preview.")

        warnings: list[str] = []
        max_chapters = _bounded_int(request.max_chapters, minimum=1, maximum=200)
        max_matches = _bounded_int(request.max_matches, minimum=1, maximum=1000)
        specs = self._variant_specs(novel_id, request, warnings)
        chapters = self._load_chapters(novel_id, request, max_chapters=max_chapters, warnings=warnings)

        if not specs:
            return GlossaryApplyPreviewResult(
                novel_id=novel_id,
                scanned_chapter_count=len(chapters),
                matched_chapter_count=0,
                skipped_chapter_count=0,
                total_match_count=0,
                safe_match_count=0,
                needs_review_match_count=0,
                blocked_match_count=0,
                entry_count=0,
                warnings=warnings,
                chapters=[],
            )

        blocked_variants = _conflicting_variants(specs)
        all_banned_outputs = {spec.old_text for spec in specs if spec.alias_type in {"banned", "rejected"}}
        chapter_previews: list[GlossaryChapterPreview] = []
        total_matches = 0
        safe_matches = 0
        review_matches = 0
        blocked_matches = 0
        capped = False

        for chapter in chapters:
            replacements: list[GlossaryReplacementPreview] = []
            for spec in specs:
                for start, end in _find_occurrences(chapter.text, spec.old_text):
                    if total_matches >= max_matches:
                        capped = True
                        break
                    preview = self._preview_match(
                        text=chapter.text,
                        spec=spec,
                        start=start,
                        end=end,
                        blocked_variants=blocked_variants,
                        banned_outputs=all_banned_outputs,
                    )
                    replacements.append(preview)
                    total_matches += 1
                    if preview.risk_status == "safe":
                        safe_matches += 1
                    elif preview.risk_status == "needs_review":
                        review_matches += 1
                    else:
                        blocked_matches += 1
                if capped:
                    break
            delta_fraction = 0.0
            if replacements and chapter.text:
                safe_repls = [r for r in replacements if r.risk_status == "safe"]
                if safe_repls:
                    simulated = chapter.text
                    for r in reversed(safe_repls):
                        simulated = simulated[: r.start_offset] + r.new_text + simulated[r.end_offset :]
                    df = (len(simulated) - len(chapter.text)) / max(1, len(chapter.text))
                    delta_fraction = abs(df)
            if replacements:
                chapter_previews.append(
                    GlossaryChapterPreview(
                        chapter_storage_id=chapter.storage_id,
                        chapter_id=chapter.db_chapter_id,
                        chapter_number=chapter.chapter_number,
                        replacement_count=len(replacements),
                        safe_count=sum(1 for item in replacements if item.risk_status == "safe"),
                        needs_review_count=sum(1 for item in replacements if item.risk_status == "needs_review"),
                        blocked_count=sum(1 for item in replacements if item.risk_status == "blocked"),
                        replacements=replacements,
                        delta_fraction=delta_fraction,
                    )
                )
            if capped:
                break

        if capped:
            warnings.append(f"Preview stopped after reaching the max match safety cap of {max_matches}.")

        return GlossaryApplyPreviewResult(
            novel_id=novel_id,
            scanned_chapter_count=len(chapters),
            matched_chapter_count=len(chapter_previews),
            skipped_chapter_count=0,
            total_match_count=total_matches,
            safe_match_count=safe_matches,
            needs_review_match_count=review_matches,
            blocked_match_count=blocked_matches,
            entry_count=len({spec.entry_id for spec in specs}),
            warnings=warnings,
            chapters=chapter_previews,
        )

    def _variant_specs(
        self,
        novel_id: int,
        request: GlossaryApplyPreviewRequest,
        warnings: list[str],
    ) -> list[_VariantSpec]:
        entries = self._eligible_entries(novel_id, request, warnings)
        if not entries:
            warnings.append("No approved glossary entries with old target-side variants were eligible for preview.")
            return []

        stmt = (
            select(NovelGlossaryAlias)
            .where(
                NovelGlossaryAlias.novel_id == novel_id,
                NovelGlossaryAlias.glossary_entry_id.in_([entry.id for entry in entries]),
                NovelGlossaryAlias.alias_type.in_(_OLD_VARIANT_ALIAS_TYPES),
            )
            .order_by(NovelGlossaryAlias.alias_text, NovelGlossaryAlias.id)
        )
        aliases_by_entry: dict[int, list[NovelGlossaryAlias]] = {}
        for alias in self.db.scalars(stmt):
            aliases_by_entry.setdefault(alias.glossary_entry_id, []).append(alias)

        specs: list[_VariantSpec] = []
        seen: set[tuple[int, str]] = set()
        for entry in entries:
            approved = _clean_text(entry.approved_translation)
            if approved is None:
                continue
            for alias in aliases_by_entry.get(entry.id, []):
                old = _clean_text(alias.alias_text)
                if old is None or _normal_key(old) == _normal_key(approved):
                    continue
                key = (entry.id, _normal_key(old))
                if key in seen:
                    continue
                seen.add(key)
                specs.append(
                    _VariantSpec(
                        entry_id=entry.id,
                        canonical_term=entry.canonical_term,
                        old_text=old,
                        new_text=approved,
                        alias_type=alias.alias_type,
                    )
                )
        if not specs:
            warnings.append("Approved entries were found, but none had rejected, banned, or deprecated aliases to scan.")
        return specs

    def _eligible_entries(
        self,
        novel_id: int,
        request: GlossaryApplyPreviewRequest,
        warnings: list[str],
    ) -> list[NovelGlossaryEntry]:
        stmt = select(NovelGlossaryEntry).where(
            NovelGlossaryEntry.novel_id == novel_id,
            NovelGlossaryEntry.status == "approved",
            NovelGlossaryEntry.canonical_term != "",
            NovelGlossaryEntry.approved_translation.is_not(None),
            NovelGlossaryEntry.approved_translation != "",
        )
        requested_ids = set(request.entry_ids or [])
        if requested_ids and not request.include_all_approved:
            stmt = stmt.where(NovelGlossaryEntry.id.in_(requested_ids))
        stmt = stmt.order_by(NovelGlossaryEntry.canonical_term, NovelGlossaryEntry.id)
        entries = list(self.db.scalars(stmt))
        found_ids = {entry.id for entry in entries}
        missing_or_ineligible = sorted(requested_ids - found_ids)
        if missing_or_ineligible:
            warnings.append(
                "Some requested glossary entries were missing, non-approved, or outside this novel: "
                + ", ".join(str(item) for item in missing_or_ineligible)
                + "."
            )
        return entries

    def _load_chapters(
        self,
        novel_id: int,
        request: GlossaryApplyPreviewRequest,
        *,
        max_chapters: int,
        warnings: list[str],
    ) -> list[_ChapterContext]:
        storage_key = self._storage_key_for_novel(novel_id)
        storage_ids = self._translated_chapter_ids(storage_key)
        metadata = self._chapter_metadata(novel_id)
        selected_ids = self._select_chapter_ids(storage_ids, metadata, request)
        if len(selected_ids) > max_chapters:
            warnings.append(f"Preview scanned {max_chapters} of {len(selected_ids)} translated chapters due to the safety cap.")
            selected_ids = selected_ids[:max_chapters]

        chapters: list[_ChapterContext] = []
        skipped_missing_text = 0
        for storage_id in selected_ids:
            payload = self.storage.load_translated_chapter(storage_key, storage_id) or {}
            text = payload.get("text") if isinstance(payload.get("text"), str) else ""
            if not text:
                skipped_missing_text += 1
                continue
            db_chapter_id, chapter_number = metadata.get(storage_id, (None, _int_or_none(storage_id)))
            chapters.append(
                _ChapterContext(
                    storage_id=storage_id,
                    db_chapter_id=db_chapter_id,
                    chapter_number=chapter_number,
                    text=text,
                )
            )
        if skipped_missing_text:
            warnings.append(f"Skipped {skipped_missing_text} translated chapter(s) without text.")
        return chapters

    def _storage_key_for_novel(self, novel_id: int) -> str:
        novel = self.db.get(Novel, novel_id)
        if novel is not None and novel.slug:
            return novel.slug
        return str(novel_id)

    def _translated_chapter_ids(self, storage_novel_id: str) -> list[str]:
        list_translated = getattr(self.storage, "list_translated_chapters", None)
        if callable(list_translated):
            result = list_translated(storage_novel_id)
            return result if isinstance(result, list) else []
        return self.storage.list_stored_chapters(storage_novel_id)

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

    def _select_chapter_ids(
        self,
        storage_ids: list[str],
        metadata: dict[str, tuple[int | None, int | None]],
        request: GlossaryApplyPreviewRequest,
    ) -> list[str]:
        numbers = set(request.chapter_numbers or [])
        start = request.chapter_start
        end = request.chapter_end
        if start is not None and end is not None and start > end:
            start, end = end, start

        selected: list[str] = []
        for storage_id in storage_ids:
            number = metadata.get(storage_id, (None, _int_or_none(storage_id)))[1]
            if numbers and number not in numbers:
                continue
            if start is not None and (number is None or number < start):
                continue
            if end is not None and (number is None or number > end):
                continue
            selected.append(storage_id)
        selected.sort(key=lambda item: (metadata.get(item, (None, _int_or_none(item)))[1] is None, metadata.get(item, (None, _int_or_none(item)))[1] or 0, item))
        return selected

    def _preview_match(
        self,
        *,
        text: str,
        spec: _VariantSpec,
        start: int,
        end: int,
        blocked_variants: set[str],
        banned_outputs: set[str],
    ) -> GlossaryReplacementPreview:
        reason_codes: list[str] = []
        risk: RiskStatus = "safe"
        if _normal_key(spec.old_text) in blocked_variants:
            risk = "blocked"
            reason_codes.append("old_variant_conflict")
        if _normal_key(spec.new_text) in {_normal_key(item) for item in banned_outputs}:
            risk = "blocked"
            reason_codes.append("replacement_creates_banned_variant")
        if risk != "blocked":
            if not _has_safe_boundary(text, start, end, spec.old_text):
                risk = "needs_review"
                reason_codes.append("boundary_uncertain")
            if _contains_case_insensitive(text, spec.new_text):
                risk = "needs_review"
                reason_codes.append("chapter_already_contains_new_text")
        if not reason_codes:
            reason_codes.append("exact_standalone_match")
        note = _note_for(risk, reason_codes)
        return GlossaryReplacementPreview(
            glossary_entry_id=spec.entry_id,
            canonical_term=spec.canonical_term,
            old_text=spec.old_text,
            new_text=spec.new_text,
            risk_status=risk,
            reason_codes=reason_codes,
            note=note,
            start_offset=start,
            end_offset=end,
            before_snippet=_snippet(text, start, end),
            after_snippet=_snippet(text[:start] + spec.new_text + text[end:], start, start + len(spec.new_text)),
        )


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _clean_text(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    return text or None


def _normal_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _int_or_none(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _find_occurrences(text: str, needle: str) -> list[tuple[int, int]]:
    if not needle:
        return []
    matches: list[tuple[int, int]] = []
    start = 0
    while True:
        index = text.find(needle, start)
        if index < 0:
            break
        end = index + len(needle)
        matches.append((index, end))
        start = end
    return matches


def _conflicting_variants(specs: list[_VariantSpec]) -> set[str]:
    by_variant: dict[str, set[str]] = {}
    for spec in specs:
        by_variant.setdefault(_normal_key(spec.old_text), set()).add(_normal_key(spec.new_text))
    return {variant for variant, translations in by_variant.items() if len(translations) > 1}


def _has_safe_boundary(text: str, start: int, end: int, needle: str) -> bool:
    if not any(char.isascii() and char.isalnum() for char in needle):
        return True
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not _is_ascii_word_char(before) and not _is_ascii_word_char(after)


def _is_ascii_word_char(value: str) -> bool:
    return bool(value) and value.isascii() and (value.isalnum() or value == "_")


def _contains_case_insensitive(text: str, needle: str) -> bool:
    return bool(needle) and needle.casefold() in text.casefold()


def _snippet(text: str, start: int, end: int) -> str:
    left = max(0, start - _SNIPPET_CONTEXT_CHARS)
    right = min(len(text), end + _SNIPPET_CONTEXT_CHARS)
    snippet = text[left:right].replace("\n", " ")
    if left > 0:
        snippet = "... " + snippet
    if right < len(text):
        snippet += " ..."
    if len(snippet) <= _MAX_SNIPPET_CHARS:
        return snippet
    return snippet[: _MAX_SNIPPET_CHARS - 15].rstrip() + " ... [truncated]"


def _note_for(risk: RiskStatus, reason_codes: list[str]) -> str:
    if risk == "blocked":
        return "Blocked because the old variant or replacement conflicts with another glossary rule."
    if risk == "needs_review":
        return "Needs owner review before apply because the match may be ambiguous."
    return "Safe exact standalone replacement candidate."
