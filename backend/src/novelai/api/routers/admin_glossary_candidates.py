"""Admin glossary candidate import endpoints — extracted from admin_glossary.py.

Candidate import preview/apply endpoints and their helpers.
CRUD, apply, provider, and suggestion endpoints are in other split files.
"""

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.admin_glossary import (
    CandidateImportAction,
    CandidateImportMode,
    GlossaryCandidateImportRequest,
    GlossaryCandidateImportResponse,
    GlossaryCandidateSummary,
    _require_novel,
)
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.services.glossary_candidate_import import (
    GlossaryCandidateImporter,
    GlossaryCandidateImportResult,
)
router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


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


@router.post(
    "/novels/{novel_id}/glossary/candidates/import/preview",
    response_model=GlossaryCandidateImportResponse,
)
async def preview_glossary_candidate_import(
    novel_id: str,
    body: GlossaryCandidateImportRequest,
    session: Session = Depends(get_db_session),
    storage: Any = Depends(get_storage),
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
    storage: Any = Depends(get_storage),
    _owner=Depends(require_role("owner")),
) -> GlossaryCandidateImportResponse:
    novel = _require_novel(session, novel_id)
    result = GlossaryCandidateImporter(session, storage).import_from_saved_chapters(
        novel.id,
        dry_run=False,
        max_candidates=body.max_candidates,
    )
    return _candidate_import_response(novel.id, "apply", result)
