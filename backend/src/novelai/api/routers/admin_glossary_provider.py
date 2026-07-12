"""Admin glossary provider suggestion endpoints — extracted from admin_glossary.py.

Provider suggestion preview/apply endpoints, the provider adapter, and their helpers.
CRUD, candidates, apply, and suggestion endpoints are in other split files.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from novelai.api.auth.roles import require_role
from novelai.api.auth.security import require_csrf_for_unsafe_methods
from novelai.api.routers.admin_glossary import (
    CandidateImportAction,
    CandidateImportMode,
    GlossaryProviderCandidateSummary,
    GlossaryProviderSuggestionRequest,
    GlossaryProviderSuggestionResponse,
    _provider_error_status,
    _require_novel,
    _safe_provider_error_detail,
)
from novelai.api.routers.dependencies import get_db_session, get_storage
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.providers.base import TranslationProvider
from novelai.providers.registry import get_provider
from novelai.services.glossary_provider_suggestion import (
    GlossaryProviderSuggestionService,
    ProviderGlossarySuggestionResult,
)
router = APIRouter(dependencies=[Depends(require_csrf_for_unsafe_methods)])


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


@router.post(
    "/novels/{novel_id}/glossary/candidates/provider/preview",
    response_model=GlossaryProviderSuggestionResponse,
)
async def preview_glossary_provider_suggestions(
    novel_id: str,
    body: GlossaryProviderSuggestionRequest,
    session: Session = Depends(get_db_session),
    storage: Any = Depends(get_storage),
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
    storage: Any = Depends(get_storage),
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
