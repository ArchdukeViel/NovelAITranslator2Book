"""Shared admin glossary schemas, type aliases, and helpers.

Extracted from admin_glossary.py to break circular imports between the
five glossary router modules.  Outside api/routers/ so the router-layer
guard (no db.models/storage.service imports in routers) stays clean.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.core.errors import ProviderError, ProviderErrorCode

# ── Type aliases ──────────────────────────────────────────────────────

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

# ── Request / Response schemas ────────────────────────────────────────


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
    provider_key: NonEmptyStr = "gemini"
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


class ApproveTranslationChangeRequest(BaseModel):
    new_translation: NonEmptyStr
    rationale: NonEmptyStr | None = None


class ApproveTranslationChangeResponse(BaseModel):
    entry_id: int
    canonical_term: str
    approved_translation: str
    glossary_revision: int | None
    updated_at: str | None


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


# ── Shared helpers ────────────────────────────────────────────────────


def _body_fields(body: BaseModel) -> dict[str, Any]:
    fields = getattr(body, "model_fields_set", None)
    if fields is None:
        fields = getattr(body, "__fields_set__", set())
    dump = getattr(body, "model_dump", None)
    payload: Any = dump() if callable(dump) else body.dict()
    return {name: payload[name] for name in fields if name in payload}


def _require_novel(session: Session, novel_ref: str) -> Any:
    from novelai.db.models.novel import Novel

    novel = session.execute(select(Novel).where(Novel.slug == novel_ref)).scalar_one_or_none()
    if novel is None and novel_ref.isdigit():
        novel = session.get(Novel, int(novel_ref))
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


def _repo(session: Session) -> Any:
    from novelai.services.glossary_repository import GlossaryRepository

    return GlossaryRepository(session)


def _owner_user_id(owner: Any) -> int | None:
    return owner.user_id if isinstance(getattr(owner, "user_id", None), int) else None


def _raise_repo_error(exc: Exception) -> None:
    if isinstance(exc, LookupError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def _entry_response(entry: Any) -> GlossaryEntryResponse:
    return GlossaryEntryResponse.model_validate(entry, from_attributes=True)


def _alias_response(alias: Any) -> GlossaryAliasResponse:
    return GlossaryAliasResponse.model_validate(alias, from_attributes=True)


def _provenance_response(item: Any) -> GlossaryProvenanceResponse:
    return GlossaryProvenanceResponse.model_validate(item, from_attributes=True)


def _event_response(event: Any) -> GlossaryDecisionEventResponse:
    return GlossaryDecisionEventResponse.model_validate(event, from_attributes=True)


def _qa_response(finding: Any) -> GlossaryQAFindingResponse:
    return GlossaryQAFindingResponse.model_validate(finding, from_attributes=True)


def _provider_error_status(exc: ProviderError) -> int:
    if exc.provider_error_code == ProviderErrorCode.CONFIGURATION:
        return 503
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
        ProviderErrorCode.CONFIGURATION: "Provider is not configured.",
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
