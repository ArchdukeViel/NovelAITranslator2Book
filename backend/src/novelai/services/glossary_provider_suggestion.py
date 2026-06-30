"""Provider-assisted glossary candidate suggestions from saved chapter text.

This service builds bounded provider prompts from saved raw/translated chapter
content and validates provider JSON into backend Reviewing candidates. It does
not hardcode any provider, translate, rewrite chapters, approve entries, expose
routes, or run automatically.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable
from dataclasses import dataclass, field
from inspect import isawaitable
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.db.models.chapter import Chapter
from novelai.db.models.glossary import NovelGlossaryAlias
from novelai.db.models.novel import Novel
from novelai.services.glossary_candidate_import import (
    ChapterStorageReader,
    _clean_source_site,
    _int_or_none,
    _normal_key,
    _normalize_display,
)
from novelai.services.glossary_repository import GlossaryRepository


class GlossarySuggestionProvider(Protocol):
    """Injected provider/client contract for provider-assisted suggestions."""

    def suggest_glossary_candidates(self, prompt: str) -> str | Awaitable[str]: ...


@dataclass(frozen=True)
class ProviderGlossaryAlias:
    """Validated alias suggested by a provider."""

    alias_text: str
    alias_type: str = "observed"
    applies_to: str | None = None
    notes: str | None = None


@dataclass
class ProviderGlossaryCandidate:
    """Validated provider candidate ready for dry-run preview or apply."""

    raw_term: str
    suggested_translation: str
    term_type: str
    confidence: float
    aliases: list[ProviderGlossaryAlias] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    rationale: str | None = None
    chapter_refs: list[str] = field(default_factory=list)
    action: str | None = None
    skipped_reason: str | None = None
    existing_entry_id: int | None = None


@dataclass
class ProviderGlossarySuggestionResult:
    """Summary of a provider-assisted dry-run or apply pass."""

    dry_run: bool
    candidates: list[ProviderGlossaryCandidate]
    candidates_found: int
    candidates_created: int = 0
    candidates_merged: int = 0
    candidates_skipped: int = 0
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _ChapterPromptContext:
    storage_id: str
    db_chapter_id: int | None
    chapter_number: int | None
    raw_text: str
    translated_text: str
    source_site: str | None
    source_adapter: str | None
    source_novel_id: str | None


_SUPPORTED_TERM_TYPES = {
    "character",
    "place",
    "organization",
    "family_house",
    "title",
    "skill",
    "concept",
    "item",
    "other",
}
_SAFE_ALIAS_TYPES = {"observed", "source_variant", "rejected"}
_GENERIC_TERMS = {
    "chapter",
    "english",
    "japanese",
    "machine",
    "translated",
    "translation",
    "novel",
    "story",
}
_MAX_TERM_CHARS = 120
_MAX_NOTE_CHARS = 240
_MAX_EVIDENCE_CHARS = 160


class GlossaryProviderSuggestionService:
    """Suggest and optionally save provider-assisted glossary candidates."""

    def __init__(
        self,
        db: Session,
        storage: ChapterStorageReader,
        provider: GlossarySuggestionProvider,
        *,
        repository: GlossaryRepository | None = None,
    ) -> None:
        self.db = db
        self.storage = storage
        self.provider = provider
        self.repository = repository or GlossaryRepository(db)

    def suggest_from_saved_chapters(
        self,
        novel_id: int,
        *,
        storage_novel_id: str | None = None,
        dry_run: bool = True,
        max_candidates: int = 50,
        max_chapters: int = 3,
        max_prompt_chars: int = 8000,
        max_chapter_chars: int = 1200,
    ) -> ProviderGlossarySuggestionResult:
        """Run provider-assisted glossary suggestion from saved chapter context."""

        max_candidates = _bounded_int(max_candidates, minimum=1, maximum=100)
        max_chapters = _bounded_int(max_chapters, minimum=1, maximum=20)
        max_prompt_chars = _bounded_int(max_prompt_chars, minimum=1000, maximum=50000)
        max_chapter_chars = _bounded_int(max_chapter_chars, minimum=200, maximum=10000)

        storage_key = storage_novel_id or self._storage_key_for_novel(novel_id)
        warnings: list[str] = []
        provider_warnings: list[str] = []
        chapters = self._load_chapter_contexts(
            novel_id,
            storage_key,
            max_chapters=max_chapters,
            max_chapter_chars=max_chapter_chars,
            warnings=warnings,
        )
        if not chapters:
            return ProviderGlossarySuggestionResult(
                dry_run=dry_run,
                candidates=[],
                candidates_found=0,
                warnings=warnings,
            )
        prompt = self._build_prompt(
            novel_id,
            storage_key,
            chapters,
            max_candidates=max_candidates,
            max_prompt_chars=max_prompt_chars,
            warnings=warnings,
        )
        response_text = self.provider.suggest_glossary_candidates(prompt)
        candidates = self._parse_provider_response(
            response_text,
            chapters,
            max_candidates=max_candidates,
            warnings=warnings,
            provider_warnings=provider_warnings,
        )
        result = ProviderGlossarySuggestionResult(
            dry_run=dry_run,
            candidates=candidates,
            candidates_found=len(candidates),
            warnings=warnings,
            provider_warnings=provider_warnings,
        )
        if dry_run:
            return result
        self._apply_candidates(novel_id, result, chapters)
        return result

    async def suggest_from_saved_chapters_async(
        self,
        novel_id: int,
        *,
        storage_novel_id: str | None = None,
        dry_run: bool = True,
        max_candidates: int = 50,
        max_chapters: int = 3,
        max_prompt_chars: int = 8000,
        max_chapter_chars: int = 1200,
    ) -> ProviderGlossarySuggestionResult:
        """Async variant for API routes using async translation providers."""

        max_candidates = _bounded_int(max_candidates, minimum=1, maximum=100)
        max_chapters = _bounded_int(max_chapters, minimum=1, maximum=20)
        max_prompt_chars = _bounded_int(max_prompt_chars, minimum=1000, maximum=50000)
        max_chapter_chars = _bounded_int(max_chapter_chars, minimum=200, maximum=10000)

        storage_key = storage_novel_id or self._storage_key_for_novel(novel_id)
        warnings: list[str] = []
        provider_warnings: list[str] = []
        chapters = self._load_chapter_contexts(
            novel_id,
            storage_key,
            max_chapters=max_chapters,
            max_chapter_chars=max_chapter_chars,
            warnings=warnings,
        )
        if not chapters:
            return ProviderGlossarySuggestionResult(
                dry_run=dry_run,
                candidates=[],
                candidates_found=0,
                warnings=warnings,
            )
        prompt = self._build_prompt(
            novel_id,
            storage_key,
            chapters,
            max_candidates=max_candidates,
            max_prompt_chars=max_prompt_chars,
            warnings=warnings,
        )
        maybe_response = self.provider.suggest_glossary_candidates(prompt)
        response_text = await maybe_response if isawaitable(maybe_response) else maybe_response
        candidates = self._parse_provider_response(
            response_text,
            chapters,
            max_candidates=max_candidates,
            warnings=warnings,
            provider_warnings=provider_warnings,
        )
        result = ProviderGlossarySuggestionResult(
            dry_run=dry_run,
            candidates=candidates,
            candidates_found=len(candidates),
            warnings=warnings,
            provider_warnings=provider_warnings,
        )
        if dry_run:
            return result
        self._apply_candidates(novel_id, result, chapters)
        return result

    def _storage_key_for_novel(self, novel_id: int) -> str:
        novel = self.db.get(Novel, novel_id)
        if novel is not None and novel.slug:
            return novel.slug
        return str(novel_id)

    def _load_chapter_contexts(
        self,
        novel_id: int,
        storage_novel_id: str,
        *,
        max_chapters: int,
        max_chapter_chars: int,
        warnings: list[str],
    ) -> list[_ChapterPromptContext]:
        chapter_ids = self._stored_chapter_ids(storage_novel_id)[:max_chapters]
        chapter_meta = self._chapter_metadata(novel_id)
        contexts: list[_ChapterPromptContext] = []
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
            contexts.append(
                _ChapterPromptContext(
                    storage_id=storage_id,
                    db_chapter_id=db_chapter_id,
                    chapter_number=chapter_number,
                    raw_text=_truncate(raw_text, max_chapter_chars),
                    translated_text=_truncate(translated_text, max_chapter_chars),
                    source_site=_clean_source_site(raw.get("source_key")),
                    source_adapter=_clean_source_site(raw.get("input_adapter_key") or raw.get("source_key")),
                    source_novel_id=storage_novel_id,
                )
            )

        if not raw_seen:
            warnings.append("Raw chapter text was unavailable; provider context uses translated text only.")
        if not translated_seen:
            warnings.append("Translated chapter text was unavailable; provider context uses raw text only.")
        if not contexts:
            warnings.append("No saved raw or translated chapter text was available for provider suggestions.")
        return contexts

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

    def _build_prompt(
        self,
        novel_id: int,
        storage_novel_id: str,
        chapters: list[_ChapterPromptContext],
        *,
        max_candidates: int,
        max_prompt_chars: int,
        warnings: list[str],
    ) -> str:
        existing = self.repository.list_glossary_entries_for_novel(novel_id)
        existing_lines = [
            f"- {entry.canonical_term} => {entry.approved_translation or ''} [{entry.status}]"
            for entry in existing[:40]
        ]
        sections = [
            "Return strict JSON only with a top-level candidates array and optional warnings array.",
            "Suggest glossary candidates only. Do not translate, rewrite, repair, summarize, or approve chapters.",
            "Each candidate must include raw_term, suggested_translation, term_type, confidence, aliases, evidence, and rationale.",
            "Use Reviewing candidates only. Avoid common words, duplicates, long excerpts, provider/model names, and uncertain invented source terms.",
            "Use compact chapter references instead of copyrighted excerpts. Return an empty candidates array if there are no good candidates.",
            f"Novel id: {novel_id}; storage novel id: {storage_novel_id}; max candidates: {max_candidates}.",
            "Existing glossary terms to avoid or merge:\n" + ("\n".join(existing_lines) if existing_lines else "- none"),
        ]
        for chapter in chapters:
            sections.append(
                "\n".join(
                    [
                        f"Chapter ref: {chapter.storage_id}; chapter number: {chapter.chapter_number or 'unknown'}",
                        f"Raw text:\n{chapter.raw_text or '[unavailable]'}",
                        f"Translated text:\n{chapter.translated_text or '[unavailable]'}",
                    ]
                )
            )
        prompt = "\n\n".join(sections)
        if len(prompt) > max_prompt_chars:
            warnings.append("Provider prompt was truncated to the configured character budget.")
            prompt = prompt[: max_prompt_chars - 18].rstrip() + "\n[context truncated]"
        return prompt

    def _parse_provider_response(
        self,
        response_text: str,
        chapters: list[_ChapterPromptContext],
        *,
        max_candidates: int,
        warnings: list[str],
        provider_warnings: list[str],
    ) -> list[ProviderGlossaryCandidate]:
        try:
            payload = json.loads(response_text)
        except json.JSONDecodeError:
            warnings.append("Provider returned invalid JSON; no candidates were imported.")
            return []
        if not isinstance(payload, dict):
            warnings.append("Provider JSON must be an object; no candidates were imported.")
            return []

        for warning in payload.get("warnings", []):
            message = warning.get("message") if isinstance(warning, dict) else warning
            text = _clean_text(message, max_chars=_MAX_NOTE_CHARS)
            if text:
                provider_warnings.append(text)

        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list):
            warnings.append("Provider JSON did not include a candidates array; no candidates were imported.")
            return []

        candidates_by_key: dict[tuple[str, str], ProviderGlossaryCandidate] = {}
        valid_chapter_refs = {chapter.storage_id for chapter in chapters}
        default_ref = chapters[0].storage_id if chapters else None
        for index, item in enumerate(raw_candidates[:max_candidates], start=1):
            if not isinstance(item, dict):
                provider_warnings.append(f"Candidate {index} was skipped because it was not an object.")
                continue
            candidate = self._candidate_from_payload(
                item,
                index=index,
                valid_chapter_refs=valid_chapter_refs,
                default_ref=default_ref,
                provider_warnings=provider_warnings,
            )
            if candidate is None:
                continue
            key = (_normal_key(candidate.raw_term), _normal_key(candidate.suggested_translation))
            existing = candidates_by_key.get(key)
            if existing is None:
                candidates_by_key[key] = candidate
                continue
            existing.confidence = max(existing.confidence, candidate.confidence)
            existing.aliases = _merge_aliases(existing.aliases, candidate.aliases)
            existing.evidence = _merge_strings(existing.evidence, candidate.evidence, max_items=5)
            existing.chapter_refs = _merge_strings(existing.chapter_refs, candidate.chapter_refs, max_items=5)
        return list(candidates_by_key.values())

    def _candidate_from_payload(
        self,
        item: dict[str, Any],
        *,
        index: int,
        valid_chapter_refs: set[str],
        default_ref: str | None,
        provider_warnings: list[str],
    ) -> ProviderGlossaryCandidate | None:
        raw_term = _clean_text(item.get("raw_term"), max_chars=_MAX_TERM_CHARS)
        translation = _clean_text(item.get("suggested_translation"), max_chars=_MAX_TERM_CHARS)
        if not raw_term or not translation:
            provider_warnings.append(f"Candidate {index} was skipped because term or translation was blank.")
            return None
        if _is_generic_or_excerpt(raw_term) or _is_generic_or_excerpt(translation):
            provider_warnings.append(f"Candidate {index} was skipped because it looked generic or excerpt-like.")
            return None

        confidence = _coerce_confidence(item.get("confidence"))
        if confidence is None:
            provider_warnings.append(f"Candidate {index} was skipped because confidence was not numeric.")
            return None
        term_type = _normalize_term_type(item.get("term_type"))
        if term_type == "other" and _clean_text(item.get("term_type"), max_chars=64) not in {None, "", "other"}:
            provider_warnings.append(f"Candidate {index} used an unsupported term_type and was normalized to other.")

        aliases = self._aliases_from_payload(item.get("aliases"), provider_warnings=provider_warnings, index=index)
        evidence, chapter_refs = self._evidence_from_payload(
            item.get("evidence"),
            valid_chapter_refs=valid_chapter_refs,
            default_ref=default_ref,
        )
        rationale = _clean_text(item.get("rationale"), max_chars=_MAX_NOTE_CHARS)
        return ProviderGlossaryCandidate(
            raw_term=raw_term,
            suggested_translation=translation,
            term_type=term_type,
            confidence=confidence,
            aliases=aliases,
            evidence=evidence,
            rationale=rationale,
            chapter_refs=chapter_refs,
        )

    def _aliases_from_payload(
        self,
        value: Any,
        *,
        provider_warnings: list[str],
        index: int,
    ) -> list[ProviderGlossaryAlias]:
        if not isinstance(value, list):
            return []
        aliases: list[ProviderGlossaryAlias] = []
        seen: set[tuple[str, str]] = set()
        for raw_alias in value[:10]:
            if isinstance(raw_alias, str):
                alias_text = _clean_text(raw_alias, max_chars=_MAX_TERM_CHARS)
                alias_type = "observed"
                applies_to = None
                notes = None
            elif isinstance(raw_alias, dict):
                alias_text = _clean_text(raw_alias.get("alias_text"), max_chars=_MAX_TERM_CHARS)
                alias_type = _clean_text(raw_alias.get("alias_type"), max_chars=32) or "observed"
                applies_to = _clean_text(raw_alias.get("applies_to"), max_chars=64)
                notes = _clean_text(raw_alias.get("reason") or raw_alias.get("notes"), max_chars=_MAX_NOTE_CHARS)
            else:
                continue
            if not alias_text:
                continue
            if alias_type not in _SAFE_ALIAS_TYPES:
                provider_warnings.append(
                    f"Candidate {index} alias {alias_text!r} used unsupported alias_type and was skipped."
                )
                continue
            key = (_normal_key(alias_text), alias_type)
            if key in seen:
                continue
            seen.add(key)
            aliases.append(
                ProviderGlossaryAlias(
                    alias_text=alias_text,
                    alias_type=alias_type,
                    applies_to=applies_to,
                    notes=notes,
                )
            )
        return aliases

    def _evidence_from_payload(
        self,
        value: Any,
        *,
        valid_chapter_refs: set[str],
        default_ref: str | None,
    ) -> tuple[list[str], list[str]]:
        evidence: list[str] = []
        chapter_refs: list[str] = []
        if isinstance(value, list):
            for item in value[:8]:
                ref: str | None = None
                if isinstance(item, dict):
                    ref = _clean_text(
                        item.get("source_chapter_id") or item.get("context_ref") or item.get("chapter_ref"),
                        max_chars=64,
                    )
                    if ref and ref.startswith("chapter:"):
                        ref = ref.removeprefix("chapter:")
                    summary = _clean_text(
                        item.get("summary") or item.get("reason") or item.get("context_ref"),
                        max_chars=_MAX_EVIDENCE_CHARS,
                    )
                else:
                    summary = _clean_text(item, max_chars=_MAX_EVIDENCE_CHARS)
                if ref and (not valid_chapter_refs or ref in valid_chapter_refs):
                    chapter_refs = _merge_strings(chapter_refs, [ref], max_items=5)
                if summary and not _looks_like_long_excerpt(summary):
                    evidence = _merge_strings(evidence, [summary], max_items=5)
        if not chapter_refs and default_ref is not None:
            chapter_refs = [default_ref]
        return evidence, chapter_refs

    def _apply_candidates(
        self,
        novel_id: int,
        result: ProviderGlossarySuggestionResult,
        chapters: list[_ChapterPromptContext],
    ) -> None:
        existing_entries = self.repository.list_glossary_entries_for_novel(novel_id)
        entries_by_term = {_normal_key(entry.canonical_term): entry for entry in existing_entries}
        blocked_aliases = self._blocked_aliases(novel_id)

        for candidate in result.candidates:
            key = _normal_key(candidate.raw_term)
            if key in blocked_aliases:
                result.candidates_skipped += 1
                candidate.skipped_reason = "blocked_alias_conflict"
                candidate.action = "conflict"
                result.conflicts.append(f"{candidate.raw_term} matches a rejected/banned alias for this novel.")
                continue

            existing = entries_by_term.get(key)
            if existing is not None and existing.status == "approved":
                result.candidates_skipped += 1
                candidate.skipped_reason = "approved_entry_exists"
                candidate.existing_entry_id = existing.id
                candidate.action = "skipped"
                continue

            if existing is None:
                entry = self.repository.create_glossary_entry(
                    novel_id=novel_id,
                    canonical_term=candidate.raw_term,
                    term_type=candidate.term_type,
                    approved_translation=candidate.suggested_translation,
                    status="candidate",
                    enforcement_level="none",
                    confidence=candidate.confidence,
                    decision_source="provider_suggestion",
                    rationale="Provider-assisted saved chapter glossary suggestion.",
                )
                entries_by_term[key] = entry
                result.candidates_created += 1
                candidate.action = "created"
            else:
                entry = existing
                self.repository.update_glossary_entry(
                    entry.id,
                    novel_id=novel_id,
                    confidence=max(entry.confidence or 0.0, candidate.confidence),
                )
                result.candidates_merged += 1
                candidate.action = "merged"
            candidate.existing_entry_id = entry.id
            self._add_aliases(novel_id, entry.id, candidate)
            self._add_provenance(novel_id, entry.id, candidate, chapters)

    def _blocked_aliases(self, novel_id: int) -> set[str]:
        stmt = select(NovelGlossaryAlias).where(
            NovelGlossaryAlias.novel_id == novel_id,
            NovelGlossaryAlias.alias_type.in_(("banned", "rejected")),
        )
        return {_normal_key(alias.alias_text) for alias in self.db.scalars(stmt)}

    def _add_aliases(self, novel_id: int, entry_id: int, candidate: ProviderGlossaryCandidate) -> None:
        existing_aliases = {
            (_normal_key(alias.alias_text), alias.alias_type)
            for alias in self.repository.list_aliases_for_entry(entry_id, novel_id=novel_id)
        }
        blocked = {_normal_key(candidate.raw_term), _normal_key(candidate.suggested_translation)}
        for alias in candidate.aliases:
            key = (_normal_key(alias.alias_text), alias.alias_type)
            if key in existing_aliases or key[0] in blocked:
                continue
            self.repository.add_glossary_alias(
                entry_id=entry_id,
                novel_id=novel_id,
                alias_text=alias.alias_text,
                alias_type=alias.alias_type,
                applies_to=alias.applies_to,
                notes=alias.notes,
                rationale="Provider-assisted alias observation.",
            )
            existing_aliases.add(key)

    def _add_provenance(
        self,
        novel_id: int,
        entry_id: int,
        candidate: ProviderGlossaryCandidate,
        chapters: list[_ChapterPromptContext],
    ) -> None:
        chapters_by_ref = {chapter.storage_id: chapter for chapter in chapters}
        seen_refs = {
            (item.source_chapter_id, item.raw_source_term, item.observed_translated_term)
            for item in self.repository.list_source_provenance_for_entry(entry_id, novel_id=novel_id)
        }
        for ref in candidate.chapter_refs[:5]:
            chapter = chapters_by_ref.get(ref)
            source_chapter_number = chapter.chapter_number if chapter is not None else _int_or_none(ref)
            db_chapter_id = chapter.db_chapter_id if chapter is not None else None
            ref_key = (ref, candidate.raw_term, candidate.suggested_translation)
            if ref_key in seen_refs:
                continue
            self.repository.add_source_provenance(
                novel_id=novel_id,
                entry_id=entry_id,
                source_site=(chapter.source_site if chapter is not None else None) or "provider_suggestion",
                source_adapter=(chapter.source_adapter if chapter is not None else None) or "provider_suggestion",
                source_novel_id=chapter.source_novel_id if chapter is not None else None,
                source_chapter_id=ref,
                source_chapter_number=source_chapter_number,
                chapter_id=db_chapter_id,
                raw_source_term=candidate.raw_term,
                observed_translated_term=candidate.suggested_translation,
                evidence_ref=f"provider_suggestion:{ref}",
                local_reference=f"chapter:{ref}",
                evidence_quality="translated_only",
                confidence=candidate.confidence,
            )
            seen_refs.add(ref_key)


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _clean_text(value: Any, *, max_chars: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = _normalize_display(value)
    if not text:
        return None
    return _truncate(text, max_chars)


def _truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 15].rstrip() + " [truncated]"


def _coerce_confidence(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return round(max(0.0, min(1.0, confidence)), 3)


def _normalize_term_type(value: Any) -> str:
    text = _clean_text(value, max_chars=64)
    if text is None:
        return "other"
    normalized = text.casefold().replace("-", "_").replace(" ", "_")
    return normalized if normalized in _SUPPORTED_TERM_TYPES else "other"


def _is_generic_or_excerpt(value: str) -> bool:
    normalized = _normal_key(value)
    return normalized in _GENERIC_TERMS or _looks_like_long_excerpt(value)


def _looks_like_long_excerpt(value: str) -> bool:
    words = value.split()
    return len(value) > _MAX_TERM_CHARS or len(words) > 8 or "\n" in value


def _merge_strings(left: list[str], right: list[str], *, max_items: int) -> list[str]:
    merged = list(left)
    seen = {_normal_key(item) for item in merged}
    for item in right:
        key = _normal_key(item)
        if key in seen:
            continue
        merged.append(item)
        seen.add(key)
        if len(merged) >= max_items:
            break
    return merged


def _merge_aliases(
    left: list[ProviderGlossaryAlias],
    right: list[ProviderGlossaryAlias],
) -> list[ProviderGlossaryAlias]:
    merged = list(left)
    seen = {(_normal_key(alias.alias_text), alias.alias_type) for alias in merged}
    for alias in right:
        key = (_normal_key(alias.alias_text), alias.alias_type)
        if key in seen:
            continue
        merged.append(alias)
        seen.add(key)
    return merged
