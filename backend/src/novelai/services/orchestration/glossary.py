from __future__ import annotations

import contextlib
import json
import logging
from typing import Any

from novelai.glossary import extract_candidate_glossary_terms
from novelai.services.orchestration.common import (
    DEFAULT_GLOSSARY_EXTRACTION_PROMPT,
    GLOSSARY_EXTRACTION_JSON_SCHEMA,
)

logger = logging.getLogger(__name__)


async def extract_glossary_terms(
    self: Any,
    novel_id: str,
    chapters: str = "all",
    *,
    max_terms: int = 50,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; import or scrape a novel first.")

    extraction_config = config if isinstance(config, dict) else {}
    effective_chapters = str(extraction_config.get("chapters") or chapters)
    max_terms_value = extraction_config.get("max_terms", max_terms)
    effective_max_terms = int(max_terms_value) if isinstance(max_terms_value, int) or (isinstance(max_terms_value, str) and max_terms_value.isdigit()) else max_terms
    effective_max_terms = max(1, effective_max_terms)
    include_existing = bool(extraction_config.get("include_existing", True))
    extraction_mode = str(extraction_config.get("mode") or self._settings.get_glossary_extraction_mode()).strip().lower()
    if extraction_mode not in {"heuristic", "llm", "hybrid"}:
        extraction_mode = "heuristic"

    extraction_step_config = self._resolve_workflow_step_config("glossary_extraction", meta)
    profile_provider, profile_model = self._resolve_workflow_profile("glossary_extraction", meta)
    config_provider = extraction_config.get("provider")
    config_model = extraction_config.get("model")
    if isinstance(config_provider, str) and config_provider.strip():
        profile_provider = config_provider.strip()
    if isinstance(config_model, str) and config_model.strip():
        profile_model = config_model.strip()
    prompt_template_override = extraction_config.get("prompt_template")
    effective_prompt_template = (
        prompt_template_override
        if isinstance(prompt_template_override, str) and prompt_template_override.strip()
        else (
            extraction_step_config.get("prompt_template")
            if isinstance(extraction_step_config.get("prompt_template"), str) and str(extraction_step_config.get("prompt_template")).strip()
            else self._settings.get_glossary_extraction_prompt_template()
        )
    )

    selected_numbers = self._selected_chapter_numbers(meta, effective_chapters)
    texts: list[str] = []
    for number in selected_numbers:
        chapter_id = str(number)
        media_state = self.storage.load_chapter_media_state(novel_id, chapter_id) or {}
        if bool(media_state.get("ocr_required")) and str(media_state.get("ocr_status") or "").lower() == "reviewed":
            ocr_text = media_state.get("ocr_text")
            if isinstance(ocr_text, str) and ocr_text.strip():
                texts.append(ocr_text)
                continue
        chapter = self.storage.load_chapter(novel_id, chapter_id)
        if chapter and isinstance(chapter.get("text"), str) and chapter["text"].strip():
            texts.append(chapter["text"])

    heuristic_candidates = extract_candidate_glossary_terms(texts, max_terms=effective_max_terms)
    llm_candidates: list[str] = []
    source_language = self._infer_source_language(str(meta.get("input_adapter_key") or ""), meta) or "Unknown"

    if extraction_mode in {"llm", "hybrid"} and texts:
        llm_candidates = await self._extract_glossary_terms_with_llm(
            texts,
            provider_key=profile_provider,
            provider_model=profile_model,
            max_terms=effective_max_terms,
            source_language=source_language,
            prompt_template=effective_prompt_template,
            step_config=extraction_step_config,
        )

    merged_candidates: list[dict[str, Any]] = []
    if extraction_mode in {"heuristic", "hybrid"}:
        for candidate in heuristic_candidates:
            merged_candidates.append(
                {
                    "source": candidate.source,
                    "target": candidate.target,
                    "locked": candidate.locked,
                    "notes": candidate.notes,
                    "status": candidate.status,
                    "context_history": list(candidate.context_history),
                    "context_summary": candidate.context_summary,
                    "occurrence_count": candidate.occurrence_count,
                    "last_seen_index": candidate.last_seen_index,
                }
            )

    if extraction_mode in {"llm", "hybrid"}:
        for term in llm_candidates:
            stripped = term.strip()
            if not stripped:
                continue
            occurrence_count = sum(text.count(stripped) for text in texts)
            merged_candidates.append(
                {
                    "source": stripped,
                    "target": stripped,
                    "locked": True,
                    "notes": None,
                    "status": "pending",
                    "context_history": [stripped],
                    "context_summary": stripped,
                    "occurrence_count": max(occurrence_count, 1),
                    "last_seen_index": -1,
                }
            )

    candidates = merged_candidates
    existing = {}
    if include_existing:
        existing = {
            entry["source"]: dict(entry)
            for entry in self.storage.load_glossary(novel_id)
            if isinstance(entry, dict) and isinstance(entry.get("source"), str)
        }
    added = 0
    for candidate in candidates:
        source = str(candidate.get("source") or "")
        if not source or source in existing:
            continue
        existing[source] = dict(candidate)
        added += 1

    ordered_entries = sorted(existing.values(), key=lambda item: (str(item.get("source")).casefold(), str(item.get("source"))))
    self.storage.save_glossary(novel_id, ordered_entries)
    return self._phase_payload(
        phase="phase1_glossary_extraction",
        status="completed",
        message="Glossary candidates extracted.",
        novel_id=novel_id,
        selected_chapters=len(selected_numbers),
        candidates_found=len(candidates),
        added=added,
        total_terms=len(ordered_entries),
        provider=profile_provider,
        model=profile_model,
        config={
            "chapters": effective_chapters,
            "max_terms": effective_max_terms,
            "include_existing": include_existing,
            "mode": extraction_mode,
            "llm_candidates": len(llm_candidates),
        },
    )


async def _extract_glossary_terms_with_llm(
    self: Any,
    texts: list[str],
    *,
    provider_key: str | None,
    provider_model: str | None,
    max_terms: int,
    source_language: str,
    prompt_template: str | None,
    step_config: dict[str, Any] | None = None,
) -> list[str]:
    if not texts:
        return []

    resolved_provider, resolved_model = self._resolve_provider_and_model(provider_key, provider_model)
    if resolved_provider == "dummy":
        return []

    provider = self._provider_factory(resolved_provider)
    llm_kwargs: dict[str, Any] = {}
    raw_kwargs = step_config.get("kwargs") if isinstance(step_config, dict) else None
    if isinstance(raw_kwargs, dict):
        for key, value in raw_kwargs.items():
            if isinstance(key, str):
                llm_kwargs[key] = value
    temperature = step_config.get("temperature") if isinstance(step_config, dict) else None
    if isinstance(temperature, (int, float)):
        llm_kwargs["temperature"] = float(temperature)

    extracted_terms: list[str] = []
    seen: set[str] = set()
    template = prompt_template or DEFAULT_GLOSSARY_EXTRACTION_PROMPT

    for text in texts:
        if len(extracted_terms) >= max_terms:
            break
        excerpt = text.strip()[:6000]
        if not excerpt:
            continue
        prompt = template.format(
            text=excerpt,
            max_terms=max_terms,
            source_language=source_language,
        )
        result = await provider.translate(
            prompt=prompt,
            model=resolved_model,
            json_schema=GLOSSARY_EXTRACTION_JSON_SCHEMA,
            **llm_kwargs,
        )
        self._record_usage(provider.key, resolved_model, result.get("metadata"))
        parsed_terms = self._parse_llm_glossary_terms(str(result.get("text") or ""), max_terms=max_terms)
        for term in parsed_terms:
            normalized = term.strip()
            if not normalized:
                continue
            lower_key = normalized.casefold()
            if lower_key in seen:
                continue
            seen.add(lower_key)
            extracted_terms.append(normalized)
            if len(extracted_terms) >= max_terms:
                break

    return extracted_terms[:max_terms]


def _parse_llm_glossary_terms(raw_text: str, *, max_terms: int) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []

    parsed_terms: list[str] = []
    with contextlib.suppress(Exception):
        payload = json.loads(text)
        if isinstance(payload, list):
            for item in payload:
                if isinstance(item, str):
                    parsed_terms.append(item)
                elif isinstance(item, dict):
                    source = item.get("source")
                    if isinstance(source, str):
                        parsed_terms.append(source)
        elif isinstance(payload, dict):
            terms = payload.get("terms")
            if isinstance(terms, list):
                for item in terms:
                    if isinstance(item, str):
                        parsed_terms.append(item)
                    elif isinstance(item, dict):
                        source = item.get("source")
                        if isinstance(source, str):
                            parsed_terms.append(source)

    if not parsed_terms:
        for line in text.splitlines():
            token = line.strip().lstrip("-*0123456789. ").strip()
            if token:
                parsed_terms.append(token)

    deduped: list[str] = []
    seen: set[str] = set()
    for term in parsed_terms:
        normalized = term.strip().strip('"')
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
        if len(deduped) >= max_terms:
            break
    return deduped


async def translate_glossary_terms(
    self: Any,
    novel_id: str,
    *,
    provider_key: str | None = None,
    provider_model: str | None = None,
    only_pending: bool = True,
) -> dict[str, Any]:
    """Translate glossary term targets using a dedicated low-cost phase.

    This keeps human approval in the loop by leaving term status unchanged.
    """
    entries = [entry for entry in self.storage.load_glossary(novel_id) if isinstance(entry, dict)]
    if not entries:
        return {
            "novel_id": novel_id,
            "translated": 0,
            "skipped": 0,
            "total_terms": 0,
        }

    meta = self.storage.load_metadata(novel_id) or {}
    profile_provider, profile_model = self._resolve_workflow_profile("glossary_translation", meta)
    effective_provider = provider_key or profile_provider
    effective_model = provider_model or profile_model

    translated_count = 0
    skipped_count = 0
    updated_entries: list[dict[str, Any]] = []

    for entry in entries:
        status = str(entry.get("status") or "pending").strip().lower()
        if status == "ignored":
            skipped_count += 1
            updated_entries.append(dict(entry))
            continue
        if only_pending and status != "pending":
            skipped_count += 1
            updated_entries.append(dict(entry))
            continue

        source = str(entry.get("source") or "").strip()
        if not source:
            skipped_count += 1
            updated_entries.append(dict(entry))
            continue

        try:
            target = await self._translate_text(
                source,
                provider_key=effective_provider,
                provider_model=effective_model,
            )
        except Exception:
            # Keep the term as-is so one failure does not block the whole phase.
            skipped_count += 1
            updated_entries.append(dict(entry))
            continue

        updated = dict(entry)
        updated["target"] = target
        updated_entries.append(updated)
        translated_count += 1

    ordered_entries = sorted(
        updated_entries,
        key=lambda item: (
            str(item.get("folder") or "").casefold(),
            str(item.get("source") or "").casefold(),
            str(item.get("source") or ""),
        ),
    )
    self.storage.save_glossary(novel_id, ordered_entries)
    return self._phase_payload(
        phase="phase1b_glossary_translation",
        status="completed",
        message="Glossary translation completed.",
        novel_id=novel_id,
        translated=translated_count,
        skipped=skipped_count,
        total_terms=len(ordered_entries),
        provider=effective_provider,
        model=effective_model,
    )


async def review_glossary_terms(
    self: Any,
    novel_id: str,
    *,
    auto_approve_translated: bool = True,
    min_target_length: int = 2,
) -> dict[str, Any]:
    """Apply basic rule-based glossary review for pending terms.

    Designed to be extensible for future LLM-assisted review.
    """
    entries = [entry for entry in self.storage.load_glossary(novel_id) if isinstance(entry, dict)]
    if not entries:
        return self._phase_payload(
            phase="phase1c_glossary_review",
            status="completed",
            message="No glossary terms to review.",
            novel_id=novel_id,
            reviewed=0,
            approved=0,
            pending=0,
            ignored=0,
        )

    meta = self.storage.load_metadata(novel_id) or {}
    profile_provider, profile_model = self._resolve_workflow_profile("glossary_review", meta)

    reviewed = 0
    approved = 0
    pending = 0
    ignored = 0
    updated_entries: list[dict[str, Any]] = []
    for entry in entries:
        updated = dict(entry)
        source = str(updated.get("source") or "").strip()
        target = str(updated.get("target") or "").strip()
        status = str(updated.get("status") or "pending").strip().lower()

        if status == "ignored":
            ignored += 1
            updated_entries.append(updated)
            continue

        reviewed += 1
        if auto_approve_translated and target and target.casefold() != source.casefold() and len(target) >= max(1, min_target_length):
            updated["status"] = "approved"
            updated["review_reason"] = "auto_approved_rule"
            approved += 1
        else:
            updated["status"] = "pending"
            updated["review_reason"] = "needs_manual_review"
            pending += 1
        updated_entries.append(updated)

    self.storage.save_glossary(
        novel_id,
        sorted(
            updated_entries,
            key=lambda item: (
                str(item.get("folder") or "").casefold(),
                str(item.get("source") or "").casefold(),
                str(item.get("source") or ""),
            ),
        ),
    )

    # Best-effort sync to DB glossary
    db_sync: dict[str, Any] = {"skipped": True, "reason": "sync_not_run"}
    try:
        from novelai.db.engine import session_scope
        from novelai.services.glossary_repository import GlossaryRepository
        from novelai.services.glossary_sync_service import GlossarySyncService

        with session_scope() as session:
            repo = GlossaryRepository(session)
            sync_result = GlossarySyncService(repo, self.storage).sync_from_file(
                novel_id, actor_user_id=None
            )
        db_sync = {
            "created": sync_result.created,
            "updated": sync_result.updated,
            "skipped": sync_result.skipped,
            "error_count": len(sync_result.errors),
        }
    except ValueError as exc:
        if "novel_not_in_db" in str(exc):
            db_sync = {"skipped": True, "reason": "novel_not_in_db"}
        else:
            logger.warning("Glossary DB sync failed: %s", exc)
            db_sync = {"skipped": True, "reason": "sync_error"}
    except Exception as exc:
        logger.warning(
            "Glossary DB sync failed after review: %s", exc.__class__.__name__
        )
        db_sync = {"skipped": True, "reason": "sync_error"}

    return self._phase_payload(
        phase="phase1c_glossary_review",
        status="completed",
        message="Glossary review completed.",
        novel_id=novel_id,
        reviewed=reviewed,
        approved=approved,
        pending=pending,
        ignored=ignored,
        provider=profile_provider,
        model=profile_model,
        db_sync=db_sync,
    )

