"""Owner/admin glossary management routes.

These endpoints expose source-agnostic per-novel glossary data access only.
They do not run glossary QA, inject prompts, repair chapters, scrape sources,
or expose user display override management.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, constr
from sqlalchemy import select
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.dependencies import get_db_session
from novelai.db.models.glossary import (
    NovelGlossaryAlias,
    NovelGlossaryDecisionEvent,
    NovelGlossaryEntry,
    NovelGlossaryQAFinding,
    NovelGlossarySourceProvenance,
)
from novelai.db.models.novel import Novel
from novelai.services.glossary_repository import GlossaryRepository

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
