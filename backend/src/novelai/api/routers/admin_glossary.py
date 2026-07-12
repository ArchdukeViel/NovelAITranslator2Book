"""Owner/admin glossary management routes.

These endpoints expose source-agnostic per-novel glossary data access only.
They do not run glossary QA, inject prompts, repair chapters, scrape sources,
or expose user display override management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_glossary_workflow_service
from novelai.core.errors import ProviderError, ProviderErrorCode

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
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryEntryResponse]:
    try:
        entries = svc.list_glossary_entries(
            novel_id,
            status=status,
            term_type=term_type,
            public_visible=public_visible,
        )
        return [_entry_response(entry) for entry in entries]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary", response_model=GlossaryEntryResponse)
async def create_glossary_entry(
    novel_id: str,
    body: GlossaryEntryCreateRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.create_glossary_entry(
            novel_id,
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


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def get_glossary_entry(
    novel_id: str,
    entry_id: int,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.get_glossary_entry(novel_id, entry_id)
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.patch("/novels/{novel_id}/glossary/entries/{entry_id}", response_model=GlossaryEntryResponse)
async def update_glossary_entry(
    novel_id: str,
    entry_id: int,
    body: GlossaryEntryUpdateRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.update_glossary_entry(
            novel_id,
            entry_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.change_glossary_entry_status(
            novel_id,
            entry_id,
            status=body.status,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.lock_glossary_entry(
            novel_id,
            entry_id,
            rationale=body.rationale if body else None,
            actor_user_id=_owner_user_id(owner),
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.unlock_glossary_entry(
            novel_id,
            entry_id,
            rationale=body.rationale if body else None,
            actor_user_id=_owner_user_id(owner),
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.deprecate_glossary_entry(
            novel_id,
            entry_id,
            rationale=body.rationale if body else None,
            actor_user_id=_owner_user_id(owner),
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> ApproveTranslationChangeResponse:
    try:
        result = svc.approve_translation_change(
            novel_id,
            entry_id,
            new_translation=body.new_translation,
            rationale=body.rationale,
            actor_user_id=_owner_user_id(owner),
        )
        entry = result["entry"]
        return ApproveTranslationChangeResponse(
            entry_id=entry.id,
            canonical_term=entry.canonical_term,
            approved_translation=entry.approved_translation or "",
            glossary_revision=result["glossary_revision"],
            updated_at=entry.updated_at.isoformat() if entry.updated_at else None,
        )
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/aliases", response_model=list[GlossaryAliasResponse])
async def list_glossary_aliases(
    novel_id: str,
    entry_id: int,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryAliasResponse]:
    try:
        return [_alias_response(alias) for alias in svc.list_glossary_aliases(novel_id, entry_id)]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/aliases", response_model=GlossaryAliasResponse)
async def add_glossary_alias(
    novel_id: str,
    entry_id: int,
    body: GlossaryAliasCreateRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    try:
        alias = svc.add_glossary_alias(
            novel_id,
            entry_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    fields = _body_fields(body)
    rationale = fields.pop("rationale", None)
    try:
        alias = svc.update_glossary_alias(
            novel_id,
            alias_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryAliasResponse:
    try:
        alias = svc.deprecate_glossary_alias(
            novel_id,
            alias_id,
            rationale=body.rationale if body else None,
            actor_user_id=_owner_user_id(owner),
        )
        return _alias_response(alias)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/provenance", response_model=list[GlossaryProvenanceResponse])
async def list_novel_glossary_provenance(
    novel_id: str,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryProvenanceResponse]:
    try:
        return [_provenance_response(item) for item in svc.list_novel_provenance(novel_id)]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/provenance", response_model=list[GlossaryProvenanceResponse])
async def list_entry_glossary_provenance(
    novel_id: str,
    entry_id: int,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryProvenanceResponse]:
    try:
        return [
            _provenance_response(item)
            for item in svc.list_entry_provenance(novel_id, entry_id)
        ]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/entries/{entry_id}/provenance", response_model=GlossaryProvenanceResponse)
async def add_glossary_provenance(
    novel_id: str,
    entry_id: int,
    body: GlossaryProvenanceCreateRequest,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossaryProvenanceResponse:
    try:
        item = svc.add_provenance(
            novel_id,
            entry_id,
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
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryDecisionEventResponse]:
    try:
        return [_event_response(event) for event in svc.list_novel_decision_events(novel_id)]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/entries/{entry_id}/events", response_model=list[GlossaryDecisionEventResponse])
async def list_entry_glossary_decision_events(
    novel_id: str,
    entry_id: int,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryDecisionEventResponse]:
    try:
        return [
            _event_response(event)
            for event in svc.list_entry_decision_events(novel_id, entry_id)
        ]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.get("/novels/{novel_id}/glossary/qa-findings", response_model=list[GlossaryQAFindingResponse])
async def list_glossary_qa_findings(
    novel_id: str,
    chapter_id: int | None = None,
    status: str | None = None,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryQAFindingResponse]:
    try:
        findings = svc.list_qa_findings(
            novel_id,
            chapter_id=chapter_id,
            status=status,
        )
        return [_qa_response(finding) for finding in findings]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/novels/{novel_id}/glossary/qa-findings", response_model=GlossaryQAFindingResponse)
async def create_manual_glossary_qa_finding(
    novel_id: str,
    body: GlossaryQAFindingCreateRequest,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossaryQAFindingResponse:
    try:
        finding = svc.create_qa_finding(
            novel_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryQAFindingResponse:
    try:
        finding = svc.update_qa_finding_status(
            novel_id,
            finding_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryBatchApproveResponse:
    try:
        result = svc.batch_approve_candidates(
            novel_id,
            rationale=body.rationale,
            actor_user_id=_owner_user_id(owner),
        )
        novel = result["novel"]
        return GlossaryBatchApproveResponse(
            novel_id=novel.id,
            approved_count=result["approved_count"],
            glossary_status=novel.glossary_status,
            glossary_revision=novel.glossary_revision,
        )
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.patch(
    "/novels/{novel_id}/glossary-status",
    response_model=GlossaryStatusTransitionResponse,
)
async def transition_glossary_status(
    novel_id: str,
    body: GlossaryStatusTransitionRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryStatusTransitionResponse:
    try:
        novel = svc.transition_glossary_status(
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
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossarySyncResponse:
    try:
        result = svc.sync_from_file(novel_id, dry_run=body.dry_run)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        msg = str(exc)
        if "novel_not_in_db" in msg:
            raise HTTPException(
                status_code=422,
                detail="Novel slug has no corresponding database row (cannot resolve platform_novel_id).",
            ) from exc
        raise HTTPException(status_code=422, detail=msg) from exc

    if not body.dry_run:
        svc.record_sync_timestamp(novel_id)

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
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossarySyncStatusResponse:
    try:
        status_data = svc.get_sync_status(novel_id)
        return GlossarySyncStatusResponse(**status_data)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


# ── Global glossary endpoints ────────────────────────────────────

@router.get("/glossary/global", response_model=list[GlossaryEntryResponse])
async def list_global_glossary_entries(
    status: str | None = None,
    term_type: str | None = None,
    public_visible: bool | None = None,
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> list[GlossaryEntryResponse]:
    try:
        entries = svc.list_global_glossary_entries(
            status=status,
            term_type=term_type,
            public_visible=public_visible,
        )
        return [_entry_response(entry) for entry in entries]
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.post("/glossary/global", response_model=GlossaryEntryResponse)
async def create_global_glossary_entry(
    body: GlossaryEntryCreateRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.create_global_glossary_entry(
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
    svc=Depends(get_glossary_workflow_service),
    _owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.get_global_glossary_entry(entry_id)
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


@router.patch("/glossary/global/{entry_id}", response_model=GlossaryEntryResponse)
async def update_global_glossary_entry(
    entry_id: int,
    body: GlossaryEntryUpdateRequest,
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.update_global_glossary_entry(
            entry_id,
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
    svc=Depends(get_glossary_workflow_service),
    owner=Depends(require_role("owner")),
) -> GlossaryEntryResponse:
    try:
        entry = svc.change_global_glossary_entry_status(
            entry_id,
            status=body.status,
            actor_user_id=_owner_user_id(owner),
            rationale=body.rationale,
        )
        return _entry_response(entry)
    except (LookupError, ValueError) as exc:
        _raise_repo_error(exc)
        raise AssertionError("unreachable") from exc


# ---------------------------------------------------------------------------
# Re-exports — unified router for backward compatibility
# ---------------------------------------------------------------------------

from novelai.api.routers.admin_glossary_apply import router as _apply_router  # noqa: E402
from novelai.api.routers.admin_glossary_candidates import router as _candidates_router  # noqa: E402
from novelai.api.routers.admin_glossary_provider import router as _provider_router  # noqa: E402
from novelai.api.routers.admin_glossary_suggestions import router as _suggestions_router  # noqa: E402

router.routes.extend(_candidates_router.routes)
router.routes.extend(_apply_router.routes)
router.routes.extend(_provider_router.routes)
router.routes.extend(_suggestions_router.routes)
