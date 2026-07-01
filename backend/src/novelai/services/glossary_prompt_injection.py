"""Build prompt-safe glossary blocks from owner-approved novel terms.

This service is intentionally standalone. It does not call providers, start
translation jobs, mutate storage, rewrite saved chapters, or wire itself into
the translation pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from novelai.db.models.glossary import NovelGlossaryAlias, NovelGlossaryEntry
from novelai.services.glossary_repository import GlossaryRepository

MATCH_ALIAS_TYPES = {"allowed", "observed", "source_variant"}
AVOID_ALIAS_TYPES = {"rejected", "banned"}


@dataclass(frozen=True)
class GlossaryPromptInjectionOptions:
    max_terms: int = 20
    max_block_chars: int = 2000
    max_avoid_variants_per_term: int = 3

    def normalized(self) -> GlossaryPromptInjectionOptions:
        return GlossaryPromptInjectionOptions(
            max_terms=max(0, int(self.max_terms)),
            max_block_chars=max(0, int(self.max_block_chars)),
            max_avoid_variants_per_term=max(0, int(self.max_avoid_variants_per_term)),
        )


@dataclass(frozen=True)
class PromptGlossaryTerm:
    entry_id: int
    term: str
    translation: str
    owner_locked: bool
    avoid_variants: tuple[str, ...] = field(default_factory=tuple)
    matched_in_raw: bool = False
    matched_in_translated_context: bool = False


@dataclass(frozen=True)
class SkippedGlossaryTerm:
    entry_id: int
    term: str
    reason: str


@dataclass(frozen=True)
class PromptGlossaryBlock:
    rendered_text: str
    included_terms: tuple[PromptGlossaryTerm, ...]
    skipped_terms: tuple[SkippedGlossaryTerm, ...]
    warnings: tuple[str, ...]
    conflict_warnings: tuple[str, ...]
    empty: bool
    truncated: bool
    locked_term_count: int = 0


class GlossaryPromptInjectionService:
    """Create deterministic prompt glossary blocks scoped to one platform novel."""

    def __init__(self, repository: GlossaryRepository) -> None:
        self.repository = repository

    def build_for_chapter(
        self,
        novel_id: int,
        raw_chapter_text: str | None = None,
        translated_context: str | None = None,
        options: GlossaryPromptInjectionOptions | None = None,
    ) -> PromptGlossaryBlock:
        opts = (options or GlossaryPromptInjectionOptions()).normalized()
        entries = self.repository.list_glossary_entries_for_novel(novel_id, status="approved")
        eligible, skipped = self._eligible_entries(entries)
        conflicts = self._conflict_warnings(eligible)
        ranked = self._rank_entries(
            eligible,
            raw_chapter_text=raw_chapter_text,
            translated_context=translated_context,
        )
        return self._render_block(ranked, skipped=skipped, conflicts=conflicts, options=opts)

    def _eligible_entries(
        self,
        entries: list[NovelGlossaryEntry],
    ) -> tuple[list[NovelGlossaryEntry], list[SkippedGlossaryTerm]]:
        eligible: list[NovelGlossaryEntry] = []
        skipped: list[SkippedGlossaryTerm] = []

        for entry in entries:
            term = _clean(entry.canonical_term)
            translation = _clean(entry.approved_translation)
            if not term:
                skipped.append(SkippedGlossaryTerm(entry.id, "", "missing_canonical_term"))
                continue
            if not translation:
                skipped.append(SkippedGlossaryTerm(entry.id, term, "missing_approved_translation"))
                continue
            eligible.append(entry)

        return eligible, skipped

    def _rank_entries(
        self,
        entries: list[NovelGlossaryEntry],
        *,
        raw_chapter_text: str | None,
        translated_context: str | None,
    ) -> list[PromptGlossaryTerm]:
        ranked: list[tuple[tuple[object, ...], PromptGlossaryTerm]] = []
        raw_text = _fold(raw_chapter_text)
        translated_text = _fold(translated_context)
        has_context = bool(raw_text or translated_text)

        for entry in entries:
            term = _clean(entry.canonical_term)
            translation = _clean(entry.approved_translation)
            aliases = _clean_aliases(entry.aliases)
            match_terms = [term, *[alias.alias_text for alias in aliases if alias.alias_type in MATCH_ALIAS_TYPES]]
            matched_raw = _any_contains(raw_text, match_terms)
            matched_translated = _any_contains(translated_text, match_terms)
            avoid_variants = tuple(
                _dedupe(
                    list(
                        alias.alias_text
                        for alias in aliases
                        if alias.alias_type in AVOID_ALIAS_TYPES and _clean(alias.alias_text)
                    )
                )
            )
            prompt_term = PromptGlossaryTerm(
                entry_id=entry.id,
                term=term,
                translation=translation,
                owner_locked=bool(entry.owner_locked),
                avoid_variants=avoid_variants,
                matched_in_raw=matched_raw,
                matched_in_translated_context=matched_translated,
            )
            matched_score = 2 if matched_raw else 1 if matched_translated else 0
            fallback_score = 1 if not has_context else 0
            rank_key = (
                -matched_score,
                -int(bool(entry.owner_locked)),
                -int(bool(avoid_variants)),
                -_confidence_score(entry.confidence),
                -_timestamp_score(entry.updated_at or entry.created_at),
                term.casefold(),
                term,
                entry.id,
                -fallback_score,
            )
            ranked.append((rank_key, prompt_term))

        ranked.sort(key=lambda item: item[0])
        return [item[1] for item in ranked]

    def _render_block(
        self,
        ranked_terms: list[PromptGlossaryTerm],
        *,
        skipped: list[SkippedGlossaryTerm],
        conflicts: list[str],
        options: GlossaryPromptInjectionOptions,
    ) -> PromptGlossaryBlock:
        warnings: list[str] = []
        skipped_terms = list(skipped)
        selected: list[PromptGlossaryTerm] = []
        truncated = False

        for term in ranked_terms:
            if len(selected) >= options.max_terms:
                skipped_terms.append(SkippedGlossaryTerm(term.entry_id, term.term, "max_terms_exceeded"))
                truncated = True
                continue
            candidate_terms = [*selected, term]
            candidate_text = _render_text(candidate_terms, options=options)
            if len(candidate_text) > options.max_block_chars:
                skipped_terms.append(SkippedGlossaryTerm(term.entry_id, term.term, "max_block_chars_exceeded"))
                truncated = True
                continue
            selected.append(term)

        rendered = _render_text(selected, options=options) if selected else ""
        if rendered and len(rendered) > options.max_block_chars:
            rendered = ""
            skipped_terms.extend(SkippedGlossaryTerm(term.entry_id, term.term, "max_block_chars_exceeded") for term in selected)
            selected = []
            truncated = True

        if skipped:
            warnings.append("glossary_entry_missing_required_field")
        if truncated:
            warnings.append("glossary_prompt_truncated")
        if not rendered:
            warnings.append("glossary_prompt_empty")

        return PromptGlossaryBlock(
            rendered_text=rendered,
            included_terms=tuple(selected),
            skipped_terms=tuple(skipped_terms),
            warnings=tuple(_dedupe(warnings)),
            conflict_warnings=tuple(conflicts),
            empty=not bool(rendered),
            truncated=truncated,
            locked_term_count=sum(1 for t in selected if t.owner_locked),
        )

    def _conflict_warnings(self, entries: list[NovelGlossaryEntry]) -> list[str]:
        warnings: list[str] = []
        canonical_terms: dict[str, NovelGlossaryEntry] = {}
        translations: dict[str, NovelGlossaryEntry] = {}

        for entry in entries:
            term_key = _clean(entry.canonical_term).casefold()
            translation_key = _clean(entry.approved_translation).casefold()
            existing = canonical_terms.get(term_key)
            if existing is not None and _clean(existing.approved_translation) != _clean(entry.approved_translation):
                warnings.append(f"conflict: canonical term {entry.canonical_term!r} maps to multiple translations")
            canonical_terms[term_key] = entry
            if translation_key:
                translations[translation_key] = entry

        for entry in entries:
            for alias in _clean_aliases(entry.aliases):
                alias_key = alias.alias_text.casefold()
                other_canonical = canonical_terms.get(alias_key)
                if other_canonical is not None and other_canonical.id != entry.id:
                    warnings.append(
                        f"conflict: alias {alias.alias_text!r} for {entry.canonical_term!r} "
                        f"matches approved canonical term {other_canonical.canonical_term!r}"
                    )
                if alias.alias_type in AVOID_ALIAS_TYPES:
                    other_translation = translations.get(alias_key)
                    if other_translation is not None and other_translation.id != entry.id:
                        warnings.append(
                            f"conflict: rejected alias {alias.alias_text!r} for {entry.canonical_term!r} "
                            f"matches approved translation for {other_translation.canonical_term!r}"
                        )

        return list(_dedupe(warnings))


def _render_text(terms: list[PromptGlossaryTerm], *, options: GlossaryPromptInjectionOptions) -> str:
    if not terms:
        return ""

    lines = [
        "GLOSSARY FOR THIS NOVEL",
        "These are approved owner glossary rules. Use them consistently when the source term appears.",
        "The glossary is authoritative. If a source term appears below you MUST use its approved translation.",
        "",
    ]

    locked_terms = [t for t in terms if t.owner_locked]
    advisory_terms = [t for t in terms if not t.owner_locked]

    if locked_terms:
        lines.append("LOCKED (override any other translation):")
        for term in locked_terms:
            lines.append(f"- {term.term} => {term.translation}")
        lines.append("")

    if advisory_terms:
        lines.append("APPROVED (preferred translation):")
        for term in advisory_terms:
            lines.append(f"- {term.term} => {term.translation}")
        lines.append("")

    avoid_lines: list[str] = []
    for term in terms:
        for variant in term.avoid_variants[: options.max_avoid_variants_per_term]:
            avoid_lines.append(f"- {term.term}: avoid \"{variant}\"")

    if avoid_lines:
        lines.extend(["Avoid these rejected variants:", *avoid_lines])

    return "\n".join(lines).rstrip()


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _fold(value: str | None) -> str:
    return value.casefold() if isinstance(value, str) else ""


def _any_contains(text: str, terms: list[str]) -> bool:
    if not text:
        return False
    return any((cleaned := _clean(term)) and cleaned.casefold() in text for term in terms)


def _clean_aliases(aliases: list[NovelGlossaryAlias]) -> list[NovelGlossaryAlias]:
    return [alias for alias in aliases if _clean(alias.alias_text)]


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold() if isinstance(value, str) else value
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return tuple(result)


def _confidence_score(value: float | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _timestamp_score(value: datetime | None) -> float:
    if value is None:
        return 0.0
    return value.timestamp()
