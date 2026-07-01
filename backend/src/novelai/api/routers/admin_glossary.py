"""Owner/admin glossary management routes.

These endpoints expose source-agnostic per-novel glossary data access only.
They do not run glossary QA, inject prompts, repair chapters, scrape sources,
or expose user display override management.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, constr
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.db.models.glossary import (
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
)
from novelai.db.models.novel import Novel
from novelai.providers.base import TranslationProvider
from novelai.providers.registry import get_provider
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewRequest as ApplyPreviewServiceRequest,
)
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewResult as ApplyPreviewServiceResult,
)
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewService,
)
from novelai.services.glossary_candidate_import import GlossaryCandidateImporter, GlossaryCandidateImportResult
from novelai.services.glossary_provider_suggestion import (
    GlossaryProviderSuggestionService,
    ProviderGlossarySuggestionResult,
)
from novelai.services.glossary_repository import GlossaryRepository
from novelai.storage.service import StorageService

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])

NonEmptyStr = constr(strip_whitespace=True, min_length=1)
EntryStatus = Literal["candidate", "recommended", "approved", "rejected", "deprecated"]
TermType = Literal[
    "character",
    "family_house",
    "place",
    "organization",
    "title",
    "rank",
    "skill",
    "magic",
    "species",
    "item",
    "artifact",
    "concept",
    "phrase",
    "other",
]
AliasType = Literal["allowed", "rejected", "banned", "deprecated", "observed", "source_variant"]
AliasAppliesTo = Literal["source_text", "translated_text", "prompt", "qa", "public_display"]
QASeverity = Literal["info", "warning", "error", "blocker"]
QAFindingStatus = Literal["open", "accepted", "dismissed", "fixed"]
CandidateImportMode = Literal["preview", "apply"]
CandidateImportAction = Literal["preview", "created", "merged", "skipped", "conflict"]


class GlossaryEntryCreateRequest(BaseModel):
    canonical_term: NonEmptyStr
    term_type: TermType
    approved_translation: NonEmptyStr | None = None
    status: EntryStatus = "candidate"
    enforcement_level: Literal["none", "info", "warning", "error", "blocker"] = "none"
    owner_locked: bool = False
    public_visible: bool = False
    public_description: NonEmptyStr | None = None
    admin_notes: NonEmptyStr | None = None
    confidence: float | None = None
    replacement_policy: Literal["never_auto_replace", "preview_required", "manual_only", "safe_exact", "no_replacement"] = "preview_required"
    matching_policy: Literal[
        "exact_phrase",
        "case_insensitive_phrase",
        "word_boundary",
        "source_text_only",
        "translated_text_only",
        "regex_reviewed",
        "manual_only",
        "custom",
    ] = "exact_phrase"
    first_seen_chapter_id: int | None = None
    first_seen_chapter_number: int | None = None
    last_seen_chapter_id: int | None = None
    last_seen_chapter_number: int | None = None
    rationale: NonEmptyStr | None = None


class GlossaryEntryUpdateRequest(BaseModel):
    canonical_term: NonEmptyStr | None = None
    term_type: TermType | None = None
    approved_translation: NonEmptyStr | None = None
    enforcement_level: Literal["none", "info", "warning", "error", "blocker"] | None = None
    public_visible: bool | None = None
    public_description: NonEmptyStr | None = None
    admin_notes: NonEmptyStr | None = None
    confidence: float | None = None
    replacement_policy: Literal["never_auto_replace", "preview_required", "manual_only", "safe_exact", "no_replacement"] | None = None
    matching_policy: Literal[
        "exact_phrase",
        "case_insensitive_phrase",
        "word_boundary",
        "source_text_only",
        "translated_text_only",
        "regex_reviewed",
        "manual_only",
        "custom",
    ] | None = None
    first_seen_chapter_id: int | None = None
    first_seen_chapter_number: int | None = None
    last_seen_chapter_id: int | None = None
    last_seen_chapter_number: int | None = None


class GlossaryEntryStatusRequest(BaseModel):
    status: EntryStatus
    rationale: NonEmptyStr | None = None


class GlossaryDecisionRequest(BaseModel):
    rationale: NonEmptyStr | None = None


class GlossaryEntryResponse(BaseModel):
    id: int
    novel_id: int
    canonical_term: str
    term_type: str
    approved_translation: str | None
    status: str
    enforcement_level: str
    owner_locked: bool
    public_visible: bool
    public_description: str | None
    admin_notes: str | None
    confidence: float | None
    replacement_policy: str
    matching_policy: str
    first_seen_chapter_id: int | None
    first_seen_chapter_number: int | None
    last_seen_chapter_id: int | None
    last_seen_chapter_number: int | None
    created_by_user_id: int | None
    updated_by_user_id: int | None
    created_at: datetime
    updated_at: datetime
    deprecated_at: datetime | None


class GlossaryAliasCreateRequest(BaseModel):
    alias_text: NonEmptyStr
    alias_type: AliasType = "observed"
    language: NonEmptyStr | None = None
    text_origin: NonEmptyStr | None = None
    applies_to: AliasAppliesTo | None = None
    matching_policy: Literal[
        "exact_phrase",
        "case_insensitive_phrase",
        "word_boundary",
        "source_text_only",
        "translated_text_only",
        "regex_reviewed",
        "manual_only",
        "custom",
    ] | None = None
    notes: NonEmptyStr | None = None
    rationale: NonEmptyStr | None = None


class GlossaryAliasUpdateRequest(BaseModel):
    alias_text: NonEmptyStr | None = None
    alias_type: AliasType | None = None
    language: NonEmptyStr | None = None
    text_origin: NonEmptyStr | None = None
    applies_to: AliasAppliesTo | None = None
    matching_policy: Literal[
        "exact_phrase",
        "case_insensitive_phrase",
        "word_boundary",
        "source_text_only",
        "translated_text_only",
        "regex_reviewed",
        "manual_only",
        "custom",
    ] | None = None
    notes: NonEmptyStr | None = None
    rationale: NonEmptyStr | None = None


class GlossaryAliasResponse(BaseModel):
    id: int
    glossary_entry_id: int
    novel_id: int
    alias_text: str
    alias_type: str
    language: str | None
    text_origin: str | None
    applies_to: str | None
    matching_policy: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class GlossaryProvenanceCreateRequest(BaseModel):
    source_site: NonEmptyStr
    source_adapter: NonEmptyStr
    source_novel_id: NonEmptyStr | None = None
    source_url: NonEmptyStr | None = None
    source_chapter_id: NonEmptyStr | None = None
    source_chapter_number: int | None = None
    chapter_id: int | None = None
    raw_source_term: NonEmptyStr | None = None
    observed_translated_term: NonEmptyStr | None = None
    evidence_ref: NonEmptyStr | None = None
    local_reference: NonEmptyStr | None = None
    evidence_quality: Literal["clean_source", "mojibake", "translated_only", "metadata_only", "manual_owner_decision"] | None = None
    confidence: float | None = None


class GlossaryProvenanceResponse(BaseModel):
    id: int
    glossary_entry_id: int | None
    novel_id: int
    source_site: str
    source_adapter: str
    source_novel_id: str | None
    source_url: str | None
    source_chapter_id: str | None
    source_chapter_number: int | None
    chapter_id: int | None
    raw_source_term: str | None
    observed_translated_term: str | None
    evidence_ref: str | None
    local_reference: str | None
    evidence_quality: str | None
    confidence: float | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


class GlossaryDecisionEventResponse(BaseModel):
    id: int
    novel_id: int
    glossary_entry_id: int | None
    alias_id: int | None
    actor_user_id: int | None
    event_type: str
    old_value_json: str | None
    new_value_json: str | None
    rationale: str | None
    decision_source: str
    created_at: datetime


class GlossaryQAFindingCreateRequest(BaseModel):
    finding_type: Literal[
        "banned_alias",
        "inconsistent_alias",
        "missing_canonical",
        "unresolved_term",
        "source_mismatch",
        "replacement_risk",
    ]
    severity: QASeverity = "warning"
    status: QAFindingStatus = "open"
    chapter_id: int | None = None
    glossary_entry_id: int | None = None
    matched_text: NonEmptyStr | None = None
    suggested_text: NonEmptyStr | None = None
    context_ref: NonEmptyStr | None = None


class GlossaryQAFindingStatusRequest(BaseModel):
    status: QAFindingStatus
    reviewer_notes: NonEmptyStr | None = None


class GlossaryQAFindingResponse(BaseModel):
    id: int
    novel_id: int
    chapter_id: int | None
    glossary_entry_id: int | None
    finding_type: str
    severity: str
    matched_text: str | None
    suggested_text: str | None
    context_ref: str | None
    status: str
    reviewer_user_id: int | None
    reviewer_notes: str | None
    created_at: datetime
    resolved_at: datetime | None


class GlossaryCandidateImportRequest(BaseModel):
    max_candidates: int = Field(default=100, ge=1, le=500)


class GlossaryProviderSuggestionRequest(BaseModel):
    max_candidates: int = Field(default=50, ge=1, le=100)
    max_chapters: int = Field(default=3, ge=1, le=20)
    max_chars: int = Field(default=8000, ge=1000, le=50000)
    chapter_scope: Literal["latest", "all", "range"] = "latest"
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    provider: NonEmptyStr | None = None
    provider_model: NonEmptyStr | None = None


class GlossaryStatusTransitionRequest(BaseModel):
    target_status: Literal["glossary_pending", "glossary_ready", "glossary_skipped"]


class GlossaryStatusTransitionResponse(BaseModel):
    novel_id: str
    glossary_status: str
    glossary_revision: int


class GlossaryBatchApproveResponse(BaseModel):
    novel_id: str
    approved_count: int
    glossary_status: str
    glossary_revision: int


class GlossaryApplyPreviewRequest(BaseModel):
    entry_ids: list[int] | None = None
    include_all_approved: bool = False
    chapter_numbers: list[int] | None = None
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    max_chapters: int = Field(default=20, ge=1, le=200)
    max_matches: int = Field(default=100, ge=1, le=1000)


class GlossaryCandidateSummary(BaseModel):
    term: str
    translation: str
    term_type: str
    confidence: float
    frequency: int
    chapter_count: int
    chapter_numbers: list[int]
    chapter_refs: list[str]
    action: CandidateImportAction
    notes: str | None = None


class GlossaryCandidateImportResponse(BaseModel):
    novel_id: int
    mode: CandidateImportMode
    candidates_found: int
    candidates_created: int
    candidates_merged: int
    candidates_skipped: int
    conflicts: list[str]
    warnings: list[str]
    candidates: list[GlossaryCandidateSummary]


class GlossaryProviderCandidateSummary(BaseModel):
    raw_term: str
    term: str
    translation: str
    term_type: str
    confidence: float
    aliases: list[str]
    alias_count: int
    chapter_refs: list[str]
    action: CandidateImportAction
    rationale: str | None = None
    notes: str | None = None


class GlossaryProviderSuggestionResponse(BaseModel):
    novel_id: int
    mode: CandidateImportMode
    provider_mode: str
    provider_label: str
    candidates_found: int
    candidates_created: int
    candidates_merged: int
    candidates_skipped: int
    conflicts: list[str]
    warnings: list[str]
    provider_warnings: list[str]
    scanned_chapter_count: int
    highest_scanned_chapter_number: int | None
    candidates: list[GlossaryProviderCandidateSummary]


class GlossaryReplacementPreviewResponse(BaseModel):
    glossary_entry_id: int
    canonical_term: str
    old_text: str
    new_text: str
    risk_status: Literal["safe", "needs_review", "blocked"]
    reason_codes: list[str]
    note: str
    start_offset: int
    end_offset: int
    before_snippet: str
    after_snippet: str


class GlossaryChapterApplyPreviewResponse(BaseModel):
    chapter_storage_id: str
    chapter_id: int | None
    chapter_number: int | None
    replacement_count: int
    safe_count: int
    needs_review_count: int
    blocked_count: int
    replacements: list[GlossaryReplacementPreviewResponse]


class GlossaryApplyPreviewResponse(BaseModel):
    novel_id: int
    scanned_chapter_count: int
    matched_chapter_count: int
    skipped_chapter_count: int
    total_match_count: int
    safe_match_count: int
    needs_review_match_count: int
    blocked_match_count: int
    entry_count: int
    warnings: list[str]
    chapters: list[GlossaryChapterApplyPreviewResponse]


class _TranslationProviderGlossarySuggestionAdapter:
    def __init__(self, provider: TranslationProvider, *, provider_model: str | None = None) -> None:
        self.provider = provider
        self.provider_model = provider_model
        self.provider_label = provider.key

    async def suggest_glossary_candidates(self, prompt: str) -> str:
        try:
            result = await self.provider.translate(
                prompt,
                model=self.provider_model,
                max_tokens=4096,
                expect_json=True,
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                ProviderErrorCode.UNKNOWN,
                provider_key=self.provider.key,
                provider_model=self.provider_model,
                message="Provider suggestion request failed",
            ) from exc
        text = result.get("text") if isinstance(result, Mapping) else None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError(
                ProviderErrorCode.EMPTY_OUTPUT,
                provider_key=self.provider.key,
                provider_model=self.provider_model,
                message="Provider returned empty output",
            )
        return text


def _body_fields(body: BaseModel) -> dict[str, Any]:
    fields = getattr(body, "model_fields_set", None)
    if fields is None:
        fields = getattr(body, "__fields_set__", set())
    dump = getattr(body, "model_dump", None)
    payload = dump() if callable(dump) else body.dict()
    return {name: payload[name] for name in fields if name in payload}


def _require_novel(session: Session, novel_ref: str) -> Novel:
    novel = session.execute(select(Novel).where(Novel.slug == novel_ref)).scalar_one_or_none()
    if novel is None and novel_ref.isdigit():
        novel = session.get(Novel, int(novel_ref))
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


def _repo(session: Session) -> GlossaryRepository:
    return GlossaryRepository(session)


def _owner_user_id(owner: Any) -> int | None:
    return owner.user_id if isinstance(getattr(owner, "user_id", None), int) else None


def _raise_repo_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def _entry_response(entry: NovelGlossaryEntry) -> GlossaryEntryResponse:
    return GlossaryEntryResponse(
        id=entry.id,
        novel_id=entry.novel_id,
        canonical_term=entry.canonical_term,
        term_type=entry.term_type,
        approved_translation=entry.approved_translation,
        status=entry.status,
        enforcement_level=entry.enforcement_level,
        owner_locked=entry.owner_locked,
        public_visible=entry.public_visible,
        public_description=entry.public_description,
        admin_notes=entry.admin_notes,
        confidence=entry.confidence,
        replacement_policy=entry.replacement_policy,
        matching_policy=entry.matching_policy,
        first_seen_chapter_id=entry.first_seen_chapter_id,
        first_seen_chapter_number=entry.first_seen_chapter_number,
        last_seen_chapter_id=entry.last_seen_chapter_id,
        last_seen_chapter_number=entry.last_seen_chapter_number,
        created_by_user_id=entry.created_by_user_id,
        updated_by_user_id=entry.updated_by_user_id,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        deprecated_at=entry.deprecated_at,
    )


def _alias_response(alias: NovelGlossaryAlias) -> GlossaryAliasResponse:
    return GlossaryAliasResponse(
        id=alias.id,
        glossary_entry_id=alias.glossary_entry_id,
        novel_id=alias.novel_id,
        alias_text=alias.alias_text,
        alias_type=alias.alias_type,
        language=alias.language,
        text_origin=alias.text_origin,
        applies_to=alias.applies_to,
        matching_policy=alias.matching_policy,
        notes=alias.notes,
        created_at=alias.created_at,
        updated_at=alias.updated_at,
    )


def _provenance_response(item: NovelGlossarySourceProvenance) -> GlossaryProvenanceResponse:
    return GlossaryProvenanceResponse(
        id=item.id,
        glossary_entry_id=item.glossary_entry_id,
        novel_id=item.novel_id,
        source_site=item.source_site,
        source_adapter=item.source_adapter,
        source_novel_id=item.source_novel_id,
        source_url=item.source_url,
        source_chapter_id=item.source_chapter_id,
        source_chapter_number=item.source_chapter_number,
        chapter_id=item.chapter_id,
        raw_source_term=item.raw_source_term,
        observed_translated_term=item.observed_translated_term,
        evidence_ref=item.evidence_ref,
        local_reference=item.local_reference,
        evidence_quality=item.evidence_quality,
        confidence=item.confidence,
        first_seen_at=item.first_seen_at,
        last_seen_at=item.last_seen_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _event_response(event: NovelGlossaryDecisionEvent) -> GlossaryDecisionEventResponse:
    return GlossaryDecisionEventResponse(
        id=event.id,
        novel_id=event.novel_id,
        glossary_entry_id=event.glossary_entry_id,
        alias_id=event.alias_id,
        actor_user_id=event.actor_user_id,
        event_type=event.event_type,
        old_value_json=event.old_value_json,
        new_value_json=event.new_value_json,
        rationale=event.rationale,
        decision_source=event.decision_source,
        created_at=event.created_at,
    )


def _qa_response(finding: NovelGlossaryQAFinding) -> GlossaryQAFindingResponse:
    return GlossaryQAFindingResponse(
        id=finding.id,
        novel_id=finding.novel_id,
        chapter_id=finding.chapter_id,
        glossary_entry_id=finding.glossary_entry_id,
        finding_type=finding.finding_type,
        severity=finding.severity,
        matched_text=finding.matched_text,
        suggested_text=finding.suggested_text,
        context_ref=finding.context_ref,
        status=finding.status,
        reviewer_user_id=finding.reviewer_user_id,
        reviewer_notes=finding.reviewer_notes,
        created_at=finding.created_at,
        resolved_at=finding.resolved_at,
    )


def _candidate_import_action(mode: CandidateImportMode, action: str | None) -> CandidateImportAction:
    if mode == "preview":
        return "preview"
    if action in {"created", "merged", "skipped", "conflict"}:
        return cast(CandidateImportAction, action)
    return "skipped"


def _candidate_import_note(action: CandidateImportAction, skipped_reason: str | None) -> str | None:
    if skipped_reason == "blocked_alias_conflict":
        return "Candidate matches a rejected or banned alias for this novel."
    if skipped_reason == "approved_entry_exists":
        return "An approved glossary entry already exists for this term."
    if action == "created":
        return "Created as a Reviewing candidate from saved chapters."
    if action == "merged":
        return "Merged into an existing non-approved glossary candidate."
    return None


def _candidate_import_response(
    novel_id: int,
    mode: CandidateImportMode,
    result: GlossaryCandidateImportResult,
) -> GlossaryCandidateImportResponse:
    candidates: list[GlossaryCandidateSummary] = []
    for candidate in result.candidates:
        action = _candidate_import_action(mode, candidate.action)
        chapter_numbers = sorted(
            {
                occurrence.chapter_number
                for occurrence in candidate.occurrences
                if occurrence.chapter_number is not None
            }
        )
        chapter_refs = sorted({occurrence.chapter_storage_id for occurrence in candidate.occurrences})
        candidates.append(
            GlossaryCandidateSummary(
                term=candidate.canonical_term,
                translation=candidate.approved_translation,
                term_type=candidate.term_type,
                confidence=candidate.confidence,
                frequency=candidate.occurrence_count,
                chapter_count=candidate.chapter_count,
                chapter_numbers=chapter_numbers,
                chapter_refs=chapter_refs,
                action=action,
                notes=_candidate_import_note(action, candidate.skipped_reason),
            )
        )
    return GlossaryCandidateImportResponse(
        novel_id=novel_id,
        mode=mode,
        candidates_found=result.candidates_found,
        candidates_created=result.candidates_created,
        candidates_merged=result.candidates_merged,
        candidates_skipped=result.candidates_skipped,
        conflicts=result.conflicts,
        warnings=result.warnings,
        candidates=candidates,
    )


def _provider_suggestion_action(mode: CandidateImportMode, action: str | None) -> CandidateImportAction:
    if mode == "preview":
        return "preview"
    if action in {"created", "merged", "skipped", "conflict"}:
        return cast(CandidateImportAction, action)
    return "skipped"


def _provider_suggestion_note(action: CandidateImportAction, skipped_reason: str | None) -> str | None:
    if skipped_reason == "blocked_alias_conflict":
        return "Candidate matches a rejected or banned alias for this novel."
    if skipped_reason == "approved_entry_exists":
        return "An approved glossary entry already exists for this term."
    if action == "created":
        return "Created as a Reviewing candidate from provider-assisted saved chapter suggestions."
    if action == "merged":
        return "Merged into an existing non-approved glossary candidate."
    return None


def _provider_suggestion_response(
    novel_id: int,
    mode: CandidateImportMode,
    result: ProviderGlossarySuggestionResult,
    *,
    provider_label: str,
) -> GlossaryProviderSuggestionResponse:
    candidates: list[GlossaryProviderCandidateSummary] = []
    for candidate in result.candidates:
        action = _provider_suggestion_action(mode, candidate.action)
        aliases = [alias.alias_text for alias in candidate.aliases[:5]]
        candidates.append(
            GlossaryProviderCandidateSummary(
                raw_term=candidate.raw_term,
                term=candidate.raw_term,
                translation=candidate.suggested_translation,
                term_type=candidate.term_type,
                confidence=candidate.confidence,
                aliases=aliases,
                alias_count=len(candidate.aliases),
                chapter_refs=candidate.chapter_refs,
                action=action,
                rationale=candidate.rationale,
                notes=_provider_suggestion_note(action, candidate.skipped_reason),
            )
        )
    return GlossaryProviderSuggestionResponse(
        novel_id=novel_id,
        mode=mode,
        provider_mode="configured_translation_provider",
        provider_label=provider_label,
        candidates_found=result.candidates_found,
        candidates_created=result.candidates_created,
        candidates_merged=result.candidates_merged,
        candidates_skipped=result.candidates_skipped,
        conflicts=result.conflicts,
        warnings=result.warnings,
        provider_warnings=result.provider_warnings,
        scanned_chapter_count=result.scanned_chapter_count,
        highest_scanned_chapter_number=result.highest_scanned_chapter_number,
        candidates=candidates,
    )


def _apply_preview_response(result: ApplyPreviewServiceResult) -> GlossaryApplyPreviewResponse:
    return GlossaryApplyPreviewResponse(
        novel_id=result.novel_id,
        scanned_chapter_count=result.scanned_chapter_count,
        matched_chapter_count=result.matched_chapter_count,
        skipped_chapter_count=result.skipped_chapter_count,
        total_match_count=result.total_match_count,
        safe_match_count=result.safe_match_count,
        needs_review_match_count=result.needs_review_match_count,
        blocked_match_count=result.blocked_match_count,
        entry_count=result.entry_count,
        warnings=result.warnings,
        chapters=[
            GlossaryChapterApplyPreviewResponse(
                chapter_storage_id=chapter.chapter_storage_id,
                chapter_id=chapter.chapter_id,
                chapter_number=chapter.chapter_number,
                replacement_count=chapter.replacement_count,
                safe_count=chapter.safe_count,
                needs_review_count=chapter.needs_review_count,
                blocked_count=chapter.blocked_count,
                replacements=[
                    GlossaryReplacementPreviewResponse(
                        glossary_entry_id=replacement.glossary_entry_id,
                        canonical_term=replacement.canonical_term,
                        old_text=replacement.old_text,
                        new_text=replacement.new_text,
                        risk_status=replacement.risk_status,
                        reason_codes=replacement.reason_codes,
                        note=replacement.note,
                        start_offset=replacement.start_offset,
                        end_offset=replacement.end_offset,
                        before_snippet=replacement.before_snippet,
                        after_snippet=replacement.after_snippet,
                    )
                    for replacement in chapter.replacements
                ],
            )
            for chapter in result.chapters
        ],
    )


def _provider_error_status(exc: ProviderError) -> int:
    if exc.provider_error_code == ProviderErrorCode.CONTEXT_TOO_LARGE:
        return 400
    if exc.provider_error_code == ProviderErrorCode.RATE_LIMITED:
        return 429
    if exc.provider_error_code == ProviderErrorCode.TIMEOUT:
        return 504
    if exc.provider_error_code in {
        ProviderErrorCode.QUOTA_EXHAUSTED,
        ProviderErrorCode.MODEL_UNAVAILABLE,
        ProviderErrorCode.MODEL_DEPRECATED,
    }:
        return 503
    return 502


def _safe_provider_error_detail(exc: ProviderError) -> str:
    messages = {
        ProviderErrorCode.RATE_LIMITED: "Provider rate limit reached.",
        ProviderErrorCode.QUOTA_EXHAUSTED: "Provider quota exhausted.",
        ProviderErrorCode.MODEL_UNAVAILABLE: "Provider model unavailable.",
        ProviderErrorCode.MODEL_DEPRECATED: "Provider model deprecated.",
        ProviderErrorCode.CONTEXT_TOO_LARGE: "Provider context window exceeded.",
        ProviderErrorCode.SAFETY_BLOCKED: "Provider safety filter blocked the response.",
        ProviderErrorCode.TIMEOUT: "Provider request timed out.",
        ProviderErrorCode.EMPTY_OUTPUT: "Provider returned empty output.",
        ProviderErrorCode.PARTIAL_OUTPUT: "Provider returned partial output.",
        ProviderErrorCode.INVALID_JSON: "Provider returned invalid JSON.",
        ProviderErrorCode.UNKNOWN: "Provider suggestion request failed.",
    }
    return messages.get(exc.provider_error_code, "Provider suggestion request failed.")


@router.get("/novels/{novel_id}/glossary", response_model=list[GlossaryEntryResponse])
async def list_glossary_entries(
    novel_id: str,
    status: str | None = None,
    term_type: str | None = None,
    public_visible: bool | None = None,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryEntryResponse]:
    novel_id = _require_novel(session, novel_id).id
    entries = _repo(session).list_glossary_entries_for_novel(
        novel_id,
        status=status,
        term_type=term_type,
        public_visible=public_visible,
    )
    return [_entry_response(entry) for entry in entries]


@router.post("/novels/{novel_id}/glossary", response_model=GlossaryEntryResponse)
async def create_glossary_entry(
    novel_id: str,
    body: GlossaryEntryCreateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).create_glossary_entry(
            novel_id=novel_id,
            canonical_term=body.canonical_term,
            term_type=body.term_type,
            approved_translation=body.approved_translation,
            status=body.status,
            enforcement_level=body.enforcement_level,
            owner_locked=body.owner_locked,
            public_visible=body.public_visible,
            public_description=body.public_description,
            admin_notes=body.admin_notes,
            confidence=body.confidence,
            replacement_policy=body.replacement_policy,
            matching_policy=body.matching_policy,
            first_seen_chapter_id=body.first_seen_chapter_id,
            first_seen_chapter_number=body.first_seen_chapter_number,
            last_seen_chapter_id=body.last_seen_chapter_id,
            last_seen_chapter_number=body.last_seen_chapter_number,
            actor_user_id=_owner_user_id(owner),
            decision_source="owner",
            rationale=body.rationale,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post(
    "/novels/{novel_id}/glossary/candidates/import/preview",
    response_model=GlossaryCandidateImportResponse,
)
async def preview_glossary_candidate_import(
    novel_id: str,
    body: GlossaryCandidateImportRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryCandidateImportResponse:
    novel = _require_novel(session, novel_id)
    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(
        novel.id,
        dry_run=True,
        max_candidates=body.max_candidates,
    )
    return _candidate_import_response(novel.id, "preview", result)


@router.post(
    "/novels/{novel_id}/glossary/candidates/import/apply",
    response_model=GlossaryCandidateImportResponse,
)
async def apply_glossary_candidate_import(
    novel_id: str,
    body: GlossaryCandidateImportRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryCandidateImportResponse:
    novel = _require_novel(session, novel_id)
    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(
        novel.id,
        dry_run=False,
        max_candidates=body.max_candidates,
    )
    return _candidate_import_response(novel.id, "apply", result)


@router.post(
    "/novels/{novel_id}/glossary/apply/preview",
    response_model=GlossaryApplyPreviewResponse,
)
async def preview_glossary_apply(
    novel_id: str,
    body: GlossaryApplyPreviewRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyPreviewResponse:
    if not body.entry_ids and not body.include_all_approved:
        raise HTTPException(status_code=422, detail="entry_ids or include_all_approved is required.")
    novel = _require_novel(session, novel_id)
    try:
        result = GlossaryApplyPreviewService(session, storage).preview(
            novel.id,
            ApplyPreviewServiceRequest(
                entry_ids=body.entry_ids,
                include_all_approved=body.include_all_approved,
                chapter_numbers=body.chapter_numbers,
                chapter_start=body.chapter_start,
                chapter_end=body.chapter_end,
                max_chapters=body.max_chapters,
                max_matches=body.max_matches,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _apply_preview_response(result)


@router.post(
    "/novels/{novel_id}/glossary/candidates/provider/preview",
    response_model=GlossaryProviderSuggestionResponse,
)
async def preview_glossary_provider_suggestions(
    novel_id: str,
    body: GlossaryProviderSuggestionRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryProviderSuggestionResponse:
    novel = _require_novel(session, novel_id)
    try:
        provider = get_provider(body.provider)
        adapter = _TranslationProviderGlossarySuggestionAdapter(provider, provider_model=body.provider_model)
        result = await GlossaryProviderSuggestionService(session, storage, adapter).suggest_from_saved_chapters_async(
            novel.id,
            dry_run=True,
            max_candidates=body.max_candidates,
            max_chapters=body.max_chapters,
            max_prompt_chars=body.max_chars,
            chapter_scope=body.chapter_scope,
            chapter_start=body.chapter_start,
            chapter_end=body.chapter_end,
        )
    except KeyError as exc:
        raise HTTPException(status_code=503, detail="Provider is not configured.") from exc
    except ProviderError as exc:
        raise HTTPException(status_code=_provider_error_status(exc), detail=_safe_provider_error_detail(exc)) from exc
    return _provider_suggestion_response(novel.id, "preview", result, provider_label=adapter.provider_label)


@router.post(
    "/novels/{novel_id}/glossary/candidates/provider/apply",
    response_model=GlossaryProviderSuggestionResponse,
)
async def apply_glossary_provider_suggestions(
    novel_id: str,
    body: GlossaryProviderSuggestionRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryProviderSuggestionResponse:
    novel = _require_novel(session, novel_id)
    try:
        provider = get_provider(body.provider)
        adapter = _TranslationProviderGlossarySuggestionAdapter(provider, provider_model=body.provider_model)
        result = await GlossaryProviderSuggestionService(session, storage, adapter).suggest_from_saved_chapters_async(
            novel.id,
            dry_run=False,
            max_candidates=body.max_candidates,
            max_chapters=body.max_chapters,
            max_prompt_chars=body.max_chars,
            chapter_scope=body.chapter_scope,
            chapter_start=body.chapter_start,
            chapter_end=body.chapter_end,
        )
    except KeyError as exc:
        raise HTTPException(status_code=503, detail="Provider is not configured.") from exc
    except ProviderError as exc:
        raise HTTPException(status_code=_provider_error_status(exc), detail=_safe_provider_error_detail(exc)) from exc
    return _provider_suggestion_response(novel.id, "apply", result, provider_label=adapter.provider_label)


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def get_glossary_entry(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    entry = _repo(session).get_glossary_entry(entry_id, novel_id=novel_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Glossary entry not found")
    return _entry_response(entry)


@router.patch("/novels/{novel_id}/glossary/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def update_glossary_entry(
    novel_id: str,
    entry_id: int,
    body: GlossaryEntryUpdateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).update_glossary_entry(
            entry_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            **_body_fields(body),
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/status", response_model=GlossaryEntryResponse)
async def change_glossary_entry_status(
    novel_id: str,
    entry_id: int,
    body: GlossaryEntryStatusRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).change_glossary_entry_status(
            entry_id,
            novel_id=novel_id,
            status=body.status,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale,
            decision_source="owner",
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/lock", response_model=GlossaryEntryResponse)
async def lock_glossary_entry(
    novel_id: str,
    entry_id: int,
    body: GlossaryDecisionRequest | None = None,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).lock_glossary_entry(
            entry_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale if body else None,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/unlock", response_model=GlossaryEntryResponse)
async def unlock_glossary_entry(
    novel_id: str,
    entry_id: int,
    body: GlossaryDecisionRequest | None = None,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).unlock_glossary_entry(
            entry_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale if body else None,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/deprecate", response_model=GlossaryEntryResponse)
async def deprecate_glossary_entry(
    novel_id: str,
    entry_id: int,
    body: GlossaryDecisionRequest | None = None,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).deprecate_glossary_entry(
            entry_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale if body else None,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/aliases", response_model=list[GlossaryAliasResponse])
async def list_glossary_aliases(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryAliasResponse]:
    novel_id = _require_novel(session, novel_id).id
    try:
        return [_alias_response(alias) for alias in _repo(session).list_aliases_for_entry(entry_id, novel_id=novel_id)]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/aliases", response_model=GlossaryAliasResponse)
async def add_glossary_alias(
    novel_id: str,
    entry_id: int,
    body: GlossaryAliasCreateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        alias = _repo(session).add_glossary_alias(
            entry_id=entry_id,
            novel_id=novel_id,
            alias_text=body.alias_text,
            alias_type=body.alias_type,
            language=body.language,
            text_origin=body.text_origin,
            applies_to=body.applies_to,
            matching_policy=body.matching_policy,
            notes=body.notes,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale,
        )
        return _alias_response(alias)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.patch("/novels/{novel_id}/glossary/aliases/{alias_id}", response_model=GlossaryAliasResponse)
async def update_glossary_alias(
    novel_id: str,
    alias_id: int,
    body: GlossaryAliasUpdateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    novel_id = _require_novel(session, novel_id).id
    fields = _body_fields(body)
    rationale = fields.pop("rationale", None)
    try:
        alias = _repo(session).update_glossary_alias(
            alias_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            rationale=rationale,
            **fields,
        )
        return _alias_response(alias)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/aliases/{alias_id}/deprecate", response_model=GlossaryAliasResponse)
async def deprecate_glossary_alias(
    novel_id: str,
    alias_id: int,
    body: GlossaryDecisionRequest | None = None,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        alias = _repo(session).remove_or_deprecate_glossary_alias(
            alias_id,
            novel_id=novel_id,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale if body else None,
        )
        return _alias_response(alias)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/provenance", response_model=list[GlossaryProvenanceResponse])
async def list_novel_glossary_provenance(
    novel_id: str,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryProvenanceResponse]:
    novel_id = _require_novel(session, novel_id).id
    return [_provenance_response(item) for item in _repo(session).list_source_provenance_for_novel(novel_id)]


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/provenance", response_model=list[GlossaryProvenanceResponse])
async def list_entry_glossary_provenance(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryProvenanceResponse]:
    novel_id = _require_novel(session, novel_id).id
    try:
        return [
            _provenance_response(item)
            for item in _repo(session).list_source_provenance_for_entry(entry_id, novel_id=novel_id)
        ]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/provenance", response_model=GlossaryProvenanceResponse)
async def add_glossary_provenance(
    novel_id: str,
    entry_id: int,
    body: GlossaryProvenanceCreateRequest,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> GlossaryProvenanceResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        item = _repo(session).add_source_provenance(
            novel_id=novel_id,
            entry_id=entry_id,
            source_site=body.source_site,
            source_adapter=body.source_adapter,
            source_novel_id=body.source_novel_id,
            source_url=body.source_url,
            source_chapter_id=body.source_chapter_id,
            source_chapter_number=body.source_chapter_number,
            chapter_id=body.chapter_id,
            raw_source_term=body.raw_source_term,
            observed_translated_term=body.observed_translated_term,
            evidence_ref=body.evidence_ref,
            local_reference=body.local_reference,
            evidence_quality=body.evidence_quality,
            confidence=body.confidence,
        )
        return _provenance_response(item)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/events", response_model=list[GlossaryDecisionEventResponse])
async def list_novel_glossary_decision_events(
    novel_id: str,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryDecisionEventResponse]:
    novel_id = _require_novel(session, novel_id).id
    return [_event_response(event) for event in _repo(session).list_decision_events_for_novel(novel_id)]


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/events", response_model=list[GlossaryDecisionEventResponse])
async def list_entry_glossary_decision_events(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryDecisionEventResponse]:
    novel_id = _require_novel(session, novel_id).id
    try:
        return [
            _event_response(event)
            for event in _repo(session).list_decision_events_for_entry(entry_id, novel_id=novel_id)
        ]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/qa-findings", response_model=list[GlossaryQAFindingResponse])
async def list_glossary_qa_findings(
    novel_id: str,
    chapter_id: int | None = None,
    status: str | None = None,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryQAFindingResponse]:
    novel_id = _require_novel(session, novel_id).id
    repo = _repo(session)
    if chapter_id is not None:
        findings = repo.list_qa_findings_for_chapter(chapter_id, novel_id=novel_id, status=status)
    else:
        findings = repo.list_qa_findings_for_novel(novel_id, status=status)
    return [_qa_response(finding) for finding in findings]


@router.post("/novels/{novel_id}/glossary/qa-findings", response_model=GlossaryQAFindingResponse)
async def create_manual_glossary_qa_finding(
    novel_id: str,
    body: GlossaryQAFindingCreateRequest,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> GlossaryQAFindingResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        finding = _repo(session).create_qa_finding(
            novel_id=novel_id,
            finding_type=body.finding_type,
            severity=body.severity,
            status=body.status,
            chapter_id=body.chapter_id,
            glossary_entry_id=body.glossary_entry_id,
            matched_text=body.matched_text,
            suggested_text=body.suggested_text,
            context_ref=body.context_ref,
        )
        return _qa_response(finding)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.patch("/novels/{novel_id}/glossary/qa-findings/{finding_id}/status", response_model=GlossaryQAFindingResponse)
async def update_glossary_qa_finding_status(
    novel_id: str,
    finding_id: int,
    body: GlossaryQAFindingStatusRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryQAFindingResponse:
    novel_id = _require_novel(session, novel_id).id
    try:
        finding = _repo(session).update_qa_finding_status(
            finding_id,
            novel_id=novel_id,
            status=body.status,
            reviewer_user_id=_owner_user_id(owner),
            reviewer_notes=body.reviewer_notes,
        )
        return _qa_response(finding)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post(
    "/novels/{novel_id}/glossary/batch-approve",
    response_model=GlossaryBatchApproveResponse,
)
async def batch_approve_glossary_candidates(
    novel_id: str,
    body: GlossaryDecisionRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryBatchApproveResponse:
    """Approve all non-approved glossary candidates and mark the novel ready."""
    from novelai.services.glossary_status_service import GlossaryStatusService

    novel = _require_novel(session, novel_id)
    repo = _repo(session)
    actor_user_id = _owner_user_id(owner)
    approved_count = 0
    for entry in repo.list_glossary_entries_for_novel(novel.id):
        if entry.status not in {"candidate", "recommended"}:
            continue
        if not isinstance(entry.approved_translation, str) or not entry.approved_translation.strip():
            repo.update_glossary_entry(
                entry.id,
                novel_id=novel.id,
                approved_translation=entry.canonical_term,
                actor_user_id=actor_user_id,
            )
        repo.change_glossary_entry_status(
            entry.id,
            novel_id=novel.id,
            status="approved",
            actor_user_id=actor_user_id,
            rationale=body.rationale or "Owner approved all glossary candidates during onboarding.",
            decision_source="owner",
        )
        approved_count += 1
    updated = GlossaryStatusService(session).transition_status(
        novel.slug,
        target_status="glossary_ready",
        actor_user_id=actor_user_id,
    )
    return GlossaryBatchApproveResponse(
        novel_id=updated.slug,
        approved_count=approved_count,
        glossary_status=updated.glossary_status,
        glossary_revision=updated.glossary_revision,
    )


@router.patch(
    "/novels/{novel_id}/glossary-status",
    response_model=GlossaryStatusTransitionResponse,
)
async def transition_glossary_status(
    novel_id: str,
    body: GlossaryStatusTransitionRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryStatusTransitionResponse:
    """Transition a novel's glossary_status to a new value.

    - Requires ``owner`` role (HTTP 403 otherwise).
    - Returns HTTP 404 when the novel does not exist.
    - Returns HTTP 422 when ``target_status`` is not a recognised value
      (Pydantic ``Literal`` rejects it before the handler is invoked).
    - Increments ``glossary_revision`` when ``target_status`` is
      ``glossary_ready``; leaves it unchanged otherwise.
    - Writes a ``NovelGlossaryDecisionEvent`` audit record for every
      successful transition.
    """
    from novelai.services.glossary_status_service import GlossaryStatusService

    try:
        novel = GlossaryStatusService(session).transition_status(
            novel_id,
            target_status=body.target_status,
            actor_user_id=_owner_user_id(owner),
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GlossaryStatusTransitionResponse(
        novel_id=novel.slug,
        glossary_status=novel.glossary_status,
        glossary_revision=novel.glossary_revision,
    )
