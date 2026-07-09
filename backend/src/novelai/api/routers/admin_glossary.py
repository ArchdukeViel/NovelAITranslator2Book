"""Owner/admin glossary management routes.

These endpoints expose source-agnostic per-novel glossary data access only.
They do not run glossary QA, inject prompts, repair chapters, scrape sources,
or expose user display override management.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session, get_orchestrator, get_storage
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

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
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
    scope: Literal["global", "novel"] = "novel"
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
    novel_id: int | None
    scope: str
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
    novel_id: int
    glossary_status: str
    glossary_revision: int


class GlossaryBatchApproveResponse(BaseModel):
    novel_id: int
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
    delta_fraction: float = 0.0


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


class GlossaryApplyCommitRequest(BaseModel):
    entry_ids: list[int] | None = None
    include_all_approved: bool = False
    chapter_numbers: list[int] | None = None
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    max_chapters: int = Field(default=20, ge=1, le=200)
    dry_run: bool = False
    max_delta_fraction: float = 0.15
    force_needs_review: bool = False
    batch_id: str | None = None


class ChapterApplyResultResponse(BaseModel):
    chapter_id: str
    status: str
    replacements_made: int
    delta_fraction: float
    new_version_id: str | None = None
    previous_version_id: str | None = None
    block_reason: str | None = None
    error: str | None = None


class GlossaryApplyCommitResponse(BaseModel):
    novel_id: str
    dry_run: bool
    batch_id: str | None
    glossary_revision: int
    chapters: list[ChapterApplyResultResponse]
    total_applied: int
    total_skipped: int
    total_blocked: int
    total_failed: int
    message: str


class GlossaryApplyRollbackRequest(BaseModel):
    batch_id: str


class GlossaryApplyRollbackResponse(BaseModel):
    novel_id: str
    batch_id: str
    reverted_chapters: list[ChapterApplyResultResponse]
    total_reverted: int
    message: str


class ChapterVersionActivateResponse(BaseModel):
    novel_id: str
    chapter_storage_id: str
    version_id: str
    activated: bool
    message: str


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
    payload: Any = dump() if callable(dump) else body.dict()
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
        scope=entry.scope,
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
                delta_fraction=chapter.delta_fraction,
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
    novel_key: int = _require_novel(session, novel_id).id
    entries = _repo(session).list_glossary_entries_for_novel(
        novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).create_glossary_entry(
            novel_id=novel_key,
            scope=body.scope,
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
    "/novels/{novel_id}/glossary/apply/commit",
    response_model=GlossaryApplyCommitResponse,
)
async def commit_glossary_apply(
    novel_id: str,
    body: GlossaryApplyCommitRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    orchestrator=Depends(get_orchestrator),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyCommitResponse:
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
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Prevent dry-run from making changes
    if body.dry_run:
        return GlossaryApplyCommitResponse(
            novel_id=novel_id,
            dry_run=True,
            batch_id=body.batch_id,
            glossary_revision=getattr(novel, "glossary_revision", 0) or 0,
            chapters=[
                ChapterApplyResultResponse(
                    chapter_id=ch.chapter_storage_id,
                    status="skipped" if ch.safe_count == 0 else "applied",
                    replacements_made=max(ch.safe_count, ch.needs_review_count),
                    delta_fraction=ch.delta_fraction,
                )
                for ch in result.chapters
            ],
            total_applied=sum(1 for ch in result.chapters if ch.safe_count > 0),
            total_skipped=sum(1 for ch in result.chapters if ch.safe_count == 0),
            total_blocked=0,
            total_failed=0,
            message="Dry-run completed. Set dry_run=false to apply.",
        )

    # Apply via orchestration
    apply_result = await orchestrator.apply_glossary_to_chapters(
        novel_id,
        entry_ids=body.entry_ids,
        include_all_approved=body.include_all_approved,
        chapter_numbers=body.chapter_numbers,
        chapter_start=body.chapter_start,
        chapter_end=body.chapter_end,
        max_chapters=body.max_chapters,
        dry_run=False,
        max_delta_fraction=body.max_delta_fraction,
        force_needs_review=body.force_needs_review,
        batch_id=body.batch_id,
    )

    return GlossaryApplyCommitResponse(
        novel_id=apply_result.novel_id,
        dry_run=False,
        batch_id=apply_result.batch_id,
        glossary_revision=apply_result.glossary_revision,
        chapters=[
            ChapterApplyResultResponse(
                chapter_id=ch.chapter_id,
                status=ch.status,
                replacements_made=ch.replacements_made,
                delta_fraction=ch.delta_fraction,
                new_version_id=ch.new_version_id,
                previous_version_id=ch.previous_version_id,
                block_reason=ch.block_reason,
                error=ch.error,
            )
            for ch in apply_result.chapters
        ],
        total_applied=apply_result.total_applied,
        total_skipped=apply_result.total_skipped,
        total_blocked=apply_result.total_blocked,
        total_failed=apply_result.total_failed,
        message="Glossary apply completed.",
    )


@router.post(
    "/novels/{novel_id}/glossary/apply/rollback",
    response_model=GlossaryApplyRollbackResponse,
)
async def rollback_glossary_apply(
    novel_id: str,
    body: GlossaryApplyRollbackRequest,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryApplyRollbackResponse:
    """Revert all glossary-apply versions created in a given batch.

    Uses batch_id that was recorded when the apply was committed.
    """
    from novelai.core.platform import ChapterVersionKind

    meta = storage.load_metadata(novel_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Novel metadata not found.")

    chapter_ids = meta.get("chapter_ids", []) if isinstance(meta, dict) else []
    reverted: list[ChapterApplyResultResponse] = []

    for ch_id in chapter_ids:
        translated = storage.load_translated_chapter(novel_id, ch_id)
        if not translated:
            continue
        batch_id = translated.get("batch_id")
        if batch_id != body.batch_id:
            continue
        version_kind = translated.get("version_kind")
        if version_kind != ChapterVersionKind.GLOSSARY_APPLY.value:
            continue
        # Activate the previous version
        prev_version_id = translated.get("base_version_id") or translated.get("previous_version_id")
        if prev_version_id:
            try:
                storage.activate_translated_chapter_version(
                    novel_id,
                    ch_id,
                    prev_version_id,
                )
                reverted.append(
                    ChapterApplyResultResponse(
                        chapter_id=ch_id,
                        status="reverted",
                        replacements_made=0,
                        delta_fraction=0.0,
                        new_version_id=prev_version_id,
                        previous_version_id=translated.get("version_id"),
                    )
                )
            except Exception as exc:
                reverted.append(
                    ChapterApplyResultResponse(
                        chapter_id=ch_id,
                        status="failed",
                        replacements_made=0,
                        delta_fraction=0.0,
                        error=str(exc),
                    )
                )

    return GlossaryApplyRollbackResponse(
        novel_id=novel_id,
        batch_id=body.batch_id,
        reverted_chapters=reverted,
        total_reverted=len(reverted),
        message=f"Rollback completed. {len(reverted)} chapters reverted.",
    )


@router.post(
    "/novels/{novel_id}/glossary/apply/chapters/{chapter_id}/versions/{version_id}/activate",
    response_model=ChapterVersionActivateResponse,
)
async def activate_chapter_version(
    novel_id: str,
    chapter_id: str,
    version_id: str,
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> ChapterVersionActivateResponse:
    """Activate a specific translation version for a chapter."""
    try:
        storage.activate_translated_chapter_version(novel_id, chapter_id, version_id)
        return ChapterVersionActivateResponse(
            novel_id=novel_id,
            chapter_storage_id=chapter_id,
            version_id=version_id,
            activated=True,
            message="Version activated.",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    novel_key: int = _require_novel(session, novel_id).id
    entry = _repo(session).get_glossary_entry(entry_id, novel_id=novel_key)
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).update_glossary_entry(
            entry_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).change_glossary_entry_status(
            entry_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).lock_glossary_entry(
            entry_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).unlock_glossary_entry(
            entry_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        entry = _repo(session).deprecate_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale if body else None,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


class ApproveTranslationChangeRequest(BaseModel):
    new_translation: NonEmptyStr
    rationale: NonEmptyStr | None = None


class ApproveTranslationChangeResponse(BaseModel):
    entry_id: int
    canonical_term: str
    approved_translation: str
    glossary_revision: int | None
    updated_at: str | None


@router.post(
    "/novels/{novel_id}/glossary/entries/{entry_id}/approve-translation-change",
    response_model=ApproveTranslationChangeResponse,
)
async def approve_translation_change(
    novel_id: str,
    entry_id: int,
    body: ApproveTranslationChangeRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> ApproveTranslationChangeResponse:
    """Approve an edited translation as the new approved glossary translation."""
    novel_key: int = _require_novel(session, novel_id).id
    actor_id = _owner_user_id(owner)
    try:
        repo = _repo(session)
        from novelai.db.models.glossary import NovelGlossaryEntry
        from novelai.db.models.novel import Novel

        entry = session.get(NovelGlossaryEntry, entry_id)
        if entry is None:
            raise LookupError("Glossary entry not found")
        if entry.scope == "novel" and entry.novel_id != novel_key:
            raise LookupError("Entry does not belong to this novel")
        if entry.owner_locked and actor_id is None:
            raise LookupError("Owner-locked entry requires owner permission")

        updated = repo.update_glossary_entry(
            entry_id,
            novel_id=novel_key,
            actor_user_id=actor_id,
            approved_translation=body.new_translation,
        )

        repo.create_decision_event(
            novel_id=novel_key,
            event_type="approve",
            glossary_entry_id=entry_id,
            actor_user_id=actor_id,
            old_value={"approved_translation": entry.approved_translation},
            new_value={"approved_translation": body.new_translation},
            rationale=body.rationale,
            decision_source="owner",
        )

        novel = session.get(Novel, novel_key)
        glossary_revision = int(novel.glossary_revision) if novel else None

        return ApproveTranslationChangeResponse(
            entry_id=updated.id,
            canonical_term=updated.canonical_term,
            approved_translation=updated.approved_translation or "",
            glossary_revision=glossary_revision,
            updated_at=updated.updated_at.isoformat() if updated.updated_at else None,
        )
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        return [_alias_response(alias) for alias in _repo(session).list_aliases_for_entry(entry_id, novel_id=novel_key)]
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        alias = _repo(session).add_glossary_alias(
            entry_id=entry_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    fields = _body_fields(body)
    rationale = fields.pop("rationale", None)
    try:
        alias = _repo(session).update_glossary_alias(
            alias_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        alias = _repo(session).remove_or_deprecate_glossary_alias(
            alias_id,
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    return [_provenance_response(item) for item in _repo(session).list_source_provenance_for_novel(novel_key)]


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/provenance", response_model=list[GlossaryProvenanceResponse])
async def list_entry_glossary_provenance(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryProvenanceResponse]:
    novel_key: int = _require_novel(session, novel_id).id
    try:
        return [
            _provenance_response(item)
            for item in _repo(session).list_source_provenance_for_entry(entry_id, novel_id=novel_key)
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        item = _repo(session).add_source_provenance(
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    return [_event_response(event) for event in _repo(session).list_decision_events_for_novel(novel_key)]


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/events", response_model=list[GlossaryDecisionEventResponse])
async def list_entry_glossary_decision_events(
    novel_id: str,
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryDecisionEventResponse]:
    novel_key: int = _require_novel(session, novel_id).id
    try:
        return [
            _event_response(event)
            for event in _repo(session).list_decision_events_for_entry(entry_id, novel_id=novel_key)
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
    novel_key: int = _require_novel(session, novel_id).id
    repo = _repo(session)
    if chapter_id is not None:
        findings = repo.list_qa_findings_for_chapter(chapter_id, novel_id=novel_key, status=status)
    else:
        findings = repo.list_qa_findings_for_novel(novel_key, status=status)
    return [_qa_response(finding) for finding in findings]


@router.post("/novels/{novel_id}/glossary/qa-findings", response_model=GlossaryQAFindingResponse)
async def create_manual_glossary_qa_finding(
    novel_id: str,
    body: GlossaryQAFindingCreateRequest,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> GlossaryQAFindingResponse:
    novel_key: int = _require_novel(session, novel_id).id
    try:
        finding = _repo(session).create_qa_finding(
            novel_id=novel_key,
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
    novel_key: int = _require_novel(session, novel_id).id
    try:
        finding = _repo(session).update_qa_finding_status(
            finding_id,
            novel_id=novel_key,
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
        novel_id=updated.id,
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
        novel_id=novel.id,
        glossary_status=novel.glossary_status,
        glossary_revision=novel.glossary_revision,
    )


# ── Glossary Sync Bridge ─────────────────────────────────────────────

_LAST_SYNC_TIMESTAMPS: dict[str, str] = {}


class GlossarySyncRequest(BaseModel):
    dry_run: bool = False


class GlossarySyncResponse(BaseModel):
    novel_id: str
    dry_run: bool
    created: int
    updated: int
    skipped: int
    errors: list[dict[str, str]]
    synced_terms: list[str]


class GlossarySyncStatusResponse(BaseModel):
    novel_id: str
    file_approved_count: int
    db_approved_count: int
    in_sync: bool
    last_sync_at: str | None
    recommendation: str


@router.post(
    "/novels/{novel_id}/glossary/sync-to-db",
    response_model=GlossarySyncResponse,
)
async def sync_glossary_to_db(
    novel_id: str,
    body: GlossarySyncRequest,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossarySyncResponse:
    """Sync file-glossary entries into the DB glossary table (owner-only).

    Returns HTTP 404 when the novel does not exist in storage.
    Returns HTTP 422 with ``"novel_not_in_db"`` when the novel slug has
    no corresponding rows table row.
    """
    from novelai.services.glossary_sync_service import GlossarySyncService

    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found in storage")

    try:
        result = GlossarySyncService(
            GlossaryRepository(session), storage
        ).sync_from_file(novel_id, dry_run=body.dry_run)
    except ValueError as exc:
        msg = str(exc)
        if "novel_not_in_db" in msg:
            raise HTTPException(
                status_code=422,
                detail="Novel slug has no corresponding database row (cannot resolve platform_novel_id).",
            ) from exc
        raise HTTPException(status_code=422, detail=msg) from exc

    if not body.dry_run:
        from datetime import UTC, datetime

        _LAST_SYNC_TIMESTAMPS[novel_id] = datetime.now(UTC).isoformat().replace(
            "+00:00", "Z"
        )

    return GlossarySyncResponse(
        novel_id=result.novel_id,
        dry_run=result.dry_run,
        created=result.created,
        updated=result.updated,
        skipped=result.skipped,
        errors=result.errors,
        synced_terms=result.synced_terms,
    )


@router.get(
    "/novels/{novel_id}/glossary/sync-status",
    response_model=GlossarySyncStatusResponse,
)
async def get_glossary_sync_status(
    novel_id: str,
    session: Session = Depends(get_db_session),
    storage: StorageService = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossarySyncStatusResponse:
    """Return sync status between file and DB glossaries (owner-only, read-only)."""
    from novelai.db.models.novel import Novel

    # Count file approved entries
    file_entries = storage.load_glossary(novel_id)
    file_approved_count = sum(
        1
        for e in file_entries
        if isinstance(e, dict) and str(e.get("status") or "").strip().lower() == "approved"
    )

    # Count DB approved entries
    novel_row: Novel | None = (
        session.query(Novel).filter(Novel.slug == novel_id).one_or_none()
    )
    db_approved_count = 0
    if novel_row is not None:
        db_approved_count = len(
            [
                e
                for e in GlossaryRepository(session).list_glossary_entries_for_novel(
                    novel_row.id, status="approved"
                )
            ]
        )

    in_sync = file_approved_count == db_approved_count and db_approved_count > 0

    if in_sync:
        recommendation = "healthy"
    elif file_approved_count > 0 and db_approved_count == 0:
        recommendation = "sync_required"
    elif file_approved_count == 0 and db_approved_count == 0:
        recommendation = "empty"
    else:
        recommendation = "sync_required"

    return GlossarySyncStatusResponse(
        novel_id=novel_id,
        file_approved_count=file_approved_count,
        db_approved_count=db_approved_count,
        in_sync=in_sync,
        last_sync_at=_LAST_SYNC_TIMESTAMPS.get(novel_id),
        recommendation=recommendation,
    )


# ── Glossary suggestion endpoints ──────────────────────────────────────────


class SuggestionResponse(BaseModel):
    id: str
    source_term: str
    occurrence_count: int
    chapter_count: int
    context_snippets: list[str] = Field(default_factory=list)
    source: str = "frequency"
    status: str = "pending"
    term_type: str = "character"
    confidence: float = 0.5
    approved_translation: str | None = None
    rejection_reason: str | None = None
    created_at: str = ""
    updated_at: str | None = None


class SuggestionAcceptRequest(BaseModel):
    modified_translation: str | None = None


class SuggestionRejectRequest(BaseModel):
    reason: str | None = None


def _suggestion_service(storage: StorageService = Depends(get_storage)) -> Any:
    from novelai.services.glossary.suggestion_service import GlossarySuggestionService

    return GlossarySuggestionService(base_dir=storage.base_dir)


@router.get("/novels/{novel_id}/glossary/suggestions", response_model=list[SuggestionResponse])
async def list_glossary_suggestions(
    novel_id: str,
    status: str | None = None,
    source: str | None = None,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> list[SuggestionResponse]:
    """List glossary suggestions for a novel with optional status/source filter."""
    _require_novel(session, novel_id)
    suggestions = sug_svc.list_suggestions(
        novel_id,
        status=status if status in ("pending", "accepted", "rejected") else None,
        source=source if source in ("frequency", "llm") else None,
    )
    return [SuggestionResponse(**s.model_dump(exclude_none=False)) for s in suggestions]


@router.post("/novels/{novel_id}/glossary/suggestions/{suggestion_id}/accept", response_model=SuggestionResponse)
async def accept_glossary_suggestion(
    novel_id: str,
    suggestion_id: str,
    body: SuggestionAcceptRequest,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    storage: StorageService = Depends(get_storage),
    owner=Depends(require_role("owner")),
) -> SuggestionResponse:
    """Accept a suggestion and add it as a glossary entry."""
    novel = _require_novel(session, novel_id)
    result = sug_svc.accept(novel_id, suggestion_id, modified_translation=body.modified_translation)
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")

    # Add as DB glossary entry
    translation = result.approved_translation or result.source_term
    try:
        repo = _repo(session)
        repo.create_glossary_entry(
            novel_id=novel.id,
            canonical_term=result.source_term,
            term_type=result.term_type,
            approved_translation=translation,
            status="approved",
            confidence=result.confidence,
            actor_user_id=_owner_user_id(owner),
            decision_source="owner",
        )
        # Invalidate translation cache
        from novelai.services.cache.translation_cache import TranslationCacheService
        try:
            TranslationCacheService().invalidate(novel_id)
        except Exception:
            pass
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create glossary entry: {exc}") from exc

    return SuggestionResponse(**result.model_dump(exclude_none=False))


@router.post("/novels/{novel_id}/glossary/suggestions/{suggestion_id}/reject", response_model=SuggestionResponse)
async def reject_glossary_suggestion(
    novel_id: str,
    suggestion_id: str,
    body: SuggestionRejectRequest,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> SuggestionResponse:
    """Reject a suggestion."""
    _require_novel(session, novel_id)
    result = sug_svc.reject(novel_id, suggestion_id, reason=body.reason)
    if result is None:
        raise HTTPException(status_code=404, detail="Suggestion not found or already reviewed")
    return SuggestionResponse(**result.model_dump(exclude_none=False))


class BulkActionResult(BaseModel):
    count: int
    items: list[SuggestionResponse]


@router.post("/novels/{novel_id}/glossary/suggestions/accept-all", response_model=BulkActionResult)
async def accept_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Accept all pending suggestions."""
    _require_novel(session, novel_id)
    results = sug_svc.accept_all(novel_id)
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )


@router.post("/novels/{novel_id}/glossary/suggestions/reject-all", response_model=BulkActionResult)
async def reject_all_glossary_suggestions(
    novel_id: str,
    session: Session = Depends(get_db_session),
    sug_svc: Any = Depends(_suggestion_service),
    owner=Depends(require_role("owner")),
) -> BulkActionResult:
    """Reject all pending suggestions."""
    _require_novel(session, novel_id)
    results = sug_svc.reject_all(novel_id)
    return BulkActionResult(
        count=len(results),
        items=[SuggestionResponse(**r.model_dump(exclude_none=False)) for r in results],
    )


# ── Global glossary endpoints ────────────────────────────────────

@router.get("/glossary/global", response_model=list[GlossaryEntryResponse])
async def list_global_glossary_entries(
    status: str | None = None,
    term_type: str | None = None,
    public_visible: bool | None = None,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryEntryResponse]:
    entries = _repo(session).list_glossary_entries_global(
        status=status,
        term_type=term_type,
        public_visible=public_visible,
    )
    return [_entry_response(entry) for entry in entries]

@router.post("/glossary/global", response_model=GlossaryEntryResponse)
async def create_global_glossary_entry(
    body: GlossaryEntryCreateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = _repo(session).create_glossary_entry(
            novel_id=None,
            scope="global",
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

@router.get("/glossary/global/{entry_id}", response_model=GlossaryEntryResponse)
async def get_global_glossary_entry(
    entry_id: int,
    session: Session = Depends(get_db_session),
    _owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    entry = _repo(session)._require_entry_global(entry_id)
    return _entry_response(entry)

@router.patch("/glossary/global/{entry_id}", response_model=GlossaryEntryResponse)
async def update_global_glossary_entry(
    entry_id: int,
    body: GlossaryEntryUpdateRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = _repo(session).update_glossary_entry(
            entry_id,
            novel_id=None,
            actor_user_id=_owner_user_id(owner),
            **_body_fields(body),
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc

@router.post("/glossary/global/{entry_id}/status", response_model=GlossaryEntryResponse)
async def change_global_glossary_entry_status(
    entry_id: int,
    body: GlossaryEntryStatusRequest,
    session: Session = Depends(get_db_session),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = _repo(session).change_glossary_entry_status(
            entry_id,
            novel_id=None,
            status=body.status,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc
