"""Owner/admin glossary management routes.

These endpoints expose source-agnostic per-novel glossary data access only.
They do not run glossary QA, inject prompts, repair chapters, scrape sources,
or expose user display override management.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.admin_glossary_apply import router as _apply_router
from novelai.api.routers.admin_glossary_candidates import router as _candidates_router
from novelai.api.routers.admin_glossary_provider import router as _provider_router
from novelai.api.routers.admin_glossary_suggestions import router as _suggestions_router
from novelai.api.routers.dependencies import get_glossary_workflow_service
from novelai.api.schemas.admin_glossary import (
    ApproveTranslationChangeRequest,
    ApproveTranslationChangeResponse,
    GlossaryAliasCreateRequest,
    GlossaryAliasResponse,
    GlossaryAliasUpdateRequest,
    GlossaryBatchApproveResponse,
    GlossaryDecisionEventResponse,
    GlossaryDecisionRequest,
    GlossaryEntryCreateRequest,
    GlossaryEntryResponse,
    GlossaryEntryStatusRequest,
    GlossaryEntryUpdateRequest,
    GlossaryProvenanceCreateRequest,
    GlossaryProvenanceResponse,
    GlossaryQAFindingCreateRequest,
    GlossaryQAFindingResponse,
    GlossaryQAFindingStatusRequest,
    GlossaryStatusTransitionRequest,
    GlossaryStatusTransitionResponse,
    GlossarySyncRequest,
    GlossarySyncResponse,
    GlossarySyncStatusResponse,
    _alias_response,
    _body_fields,
    _entry_response,
    _event_response,
    _owner_user_id,
    _provenance_response,
    _qa_response,
    _raise_repo_error,
)

router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


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


# Eager merge — sub-routers are imported at top of file (circular import
# broken by the shared api/schemas/admin_glossary module).
router.routes.extend(_candidates_router.routes)
router.routes.extend(_apply_router.routes)
router.routes.extend(_provider_router.routes)
router.routes.extend(_suggestions_router.routes)
