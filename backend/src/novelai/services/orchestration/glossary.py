from __future__ import annotations

import contextlib
import hashlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select

from novelai.config.settings import settings
from novelai.core.errors import ProviderError, ProviderErrorCode
from novelai.core.platform import ChapterVersionKind
from novelai.db.engine import session_scope as _session_scope
from novelai.db.models.novel import Novel
from novelai.glossary import extract_candidate_glossary_terms
from novelai.providers.model_fallbacks import model_candidates
from novelai.services.catalog_service import safely_refresh_catalog_projection_after_storage_write
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewRequest,
    GlossaryApplyPreviewService,
)
from novelai.services.glossary_rewrite import apply_glossary_replacements
from novelai.services.library_summary_service import best_effort_invalidate
from novelai.services.orchestration.common import (
    DEFAULT_GLOSSARY_EXTRACTION_PROMPT,
    GLOSSARY_EXTRACTION_JSON_SCHEMA,
)

logger = logging.getLogger(__name__)

INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION = "incremental-glossary-v1"

INCREMENTAL_GLOSSARY_DISCOVERY_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "chapter_id": {"type": "string"},
                    "source": {"type": "string"},
                    "target": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["chapter_id", "source", "target", "confidence"],
            },
        }
    },
    "required": ["items"],
}

GLOSSARY_TRANSLATION_BATCH_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string"},
                    "translation": {"type": "string"},
                },
                "required": ["id", "translation"],
            },
        }
    },
    "required": ["items"],
}


def _incremental_glossary_prompt(
    chapters: list[dict[str, str]],
    *,
    source_language: str,
    max_terms: int,
) -> str:
    payload = [{"chapter_id": item["chapter_id"], "text": item["text"]} for item in chapters]
    return (
        f"Discover at most {max_terms} recurring or story-critical glossary terms from these "
        f"{source_language} novel excerpts before translation. Return one JSON object only.\n"
        "Rules:\n"
        "- Each item must use a chapter_id from the input exactly; do not invent ids.\n"
        "- source must be an exact substring of that chapter excerpt.\n"
        "- target is a conservative English translation or established romanization; do not invent facts.\n"
        "- Never resolve omitted subjects, objects, pronouns, number, gender, relationships, or speakers as glossary terms.\n"
        "- Confidence is evidence-based, not certainty: use a lower value for ambiguity.\n"
        'Expected shape: {"items":[{"chapter_id":"...","source":"...","target":"...","confidence":0.0}]}\n'
        "<chapters>\n"
        f"{json.dumps({'chapters': payload}, ensure_ascii=False, sort_keys=True)}\n"
        "</chapters>"
    )


def parse_incremental_glossary_response(
    raw_text: str,
    *,
    source_text_by_chapter: Mapping[str, str],
    max_terms: int,
    strict: bool = False,
) -> list[dict[str, Any]]:
    """Parse and structurally validate a batched discovery response."""
    text = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        if strict:
            raise ValueError("Incremental glossary response was not valid JSON.") from exc
        return []
    raw_items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        if strict:
            raise ValueError("Incremental glossary response must contain an items array.")
        return []

    threshold = settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
    results: list[dict[str, Any]] = []
    seen_sources: set[str] = set()
    allowed_ids = set(source_text_by_chapter)
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        chapter_id = str(raw_item.get("chapter_id") or "").strip()
        source = str(raw_item.get("source") or "").strip()
        target = str(raw_item.get("target") or "").strip()
        confidence_raw = raw_item.get("confidence")
        if chapter_id not in allowed_ids or not source or not target:
            continue
        if not isinstance(confidence_raw, (int, float)) or isinstance(confidence_raw, bool):
            continue
        confidence = max(0.0, min(1.0, float(confidence_raw)))
        source_text = source_text_by_chapter[chapter_id]
        if source not in source_text or len(source) > 255 or len(target) > 255:
            continue
        if "\n" in source or "\n" in target or source.casefold() in seen_sources:
            continue
        # A model score is never sufficient by itself. Require source
        # evidence, a valid target, and a non-identity translation for CJK
        # terms before allowing automatic activation.
        cjk_source = any("\u3040" <= char <= "\u9fff" for char in source)
        structurally_safe = confidence >= threshold and (not cjk_source or target != source)
        seen_sources.add(source.casefold())
        results.append(
            {
                "chapter_id": chapter_id,
                "source": source,
                "target": target,
                "confidence": confidence,
                "safe_to_activate": structurally_safe,
                "occurrence_count": source_text.count(source),
            }
        )
        if len(results) >= max_terms:
            break
    return results


async def discover_incremental_glossary_terms(
    self: Any,
    novel_id: str,
    selected: list[Any],
    *,
    provider_key: str | None,
    provider_model: str | None,
    source_language: str,
    existing_entries: list[dict[str, Any]] | None = None,
    max_terms: int = 50,
) -> dict[str, Any]:
    """Discover new terms for the selected chapters before body translation.

    Approved entries are immutable truth. New or ambiguous terms remain
    pending and are excluded from body prompts; only structurally validated,
    high-confidence proposals become active immediately.
    """
    source_text_by_chapter: dict[str, str] = {}
    for record in selected:
        raw_chapter_id = getattr(record, "chapter_id", None)
        if raw_chapter_id is None and isinstance(record, dict):
            raw_chapter_id = record.get("chapter_id")
        chapter_id = str(raw_chapter_id or "")
        chapter = self.storage.load_chapter(novel_id, chapter_id) or {}
        text = chapter.get("text") if isinstance(chapter, dict) else None
        if isinstance(text, str) and text.strip():
            source_text_by_chapter[chapter_id] = text.strip()

    current_entries = existing_entries if existing_entries is not None else self.storage.load_glossary(novel_id)
    entries_by_source: dict[str, dict[str, Any]] = {
        str(entry.get("source")): dict(entry)
        for entry in current_entries
        if isinstance(entry, dict) and str(entry.get("source") or "").strip()
    }
    heuristic_candidates = extract_candidate_glossary_terms(
        list(source_text_by_chapter.values()), max_terms=max_terms, min_occurrences=2
    )
    heuristic_by_source = {candidate.source: candidate for candidate in heuristic_candidates}
    pending_sources: set[str] = set()
    for candidate in heuristic_candidates:
        if candidate.source in entries_by_source:
            continue
        entries_by_source[candidate.source] = {
            "source": candidate.source,
            "target": candidate.source,
            "locked": True,
            "status": "pending",
            "confidence": 0.35,
            "notes": "Recurring term discovered during incremental preflight; manual review required.",
            "context_history": list(candidate.context_history),
            "context_summary": candidate.context_summary,
            "occurrence_count": candidate.occurrence_count,
            "last_seen_index": candidate.last_seen_index,
        }
        pending_sources.add(candidate.source)

    provider_calls = 0
    discovered: list[dict[str, Any]] = []
    deferred = False
    metadata = self.storage.load_metadata(novel_id) or {}
    raw_discovery_state = metadata.get("incremental_glossary_discovery") if isinstance(metadata, dict) else None
    raw_state = raw_discovery_state if isinstance(raw_discovery_state, dict) else {}
    discovery_state: dict[str, dict[str, str]] = {
        str(chapter_id): dict(state)
        for chapter_id, state in raw_state.items()
        if isinstance(state, dict) and isinstance(chapter_id, str)
    }
    unchanged_chapters: list[str] = []
    changed_chapters = list(source_text_by_chapter)
    resolved_provider: str | None = None
    resolved_model: str | None = provider_model
    provider: Any | None = None
    if source_text_by_chapter and provider_key and provider_key.strip().lower() == "gemini":
        resolved_provider, resolved_model_value = self._resolve_provider_and_model(provider_key, provider_model)
        resolved_model = str(resolved_model_value)
        changed_chapters = []
        for chapter_id, text in source_text_by_chapter.items():
            source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            state = discovery_state.get(chapter_id, {})
            if (
                state.get("source_hash") == source_hash
                and state.get("prompt_version") == INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION
                and state.get("provider_model") == resolved_model
            ):
                unchanged_chapters.append(chapter_id)
            else:
                changed_chapters.append(chapter_id)

    if changed_chapters and resolved_provider is not None and resolved_provider != "dummy":
        provider = self._provider_factory(resolved_provider)
        if str(getattr(provider, "key", resolved_provider)).strip().lower() != "gemini":
            # Structured incremental discovery is enabled for the production
            # Gemini contract. Test/dummy providers may intentionally return
            # ordinary translation text and must not be treated as discovery
            # responses.
            changed_chapters = []

    if changed_chapters and resolved_provider is not None and resolved_provider != "dummy" and provider is not None:
        chapter_items = [
            {"chapter_id": chapter_id, "text": source_text_by_chapter[chapter_id][:4000]}
            for chapter_id in changed_chapters
        ]
        for start in range(0, len(chapter_items), 3):
            batch = chapter_items[start : start + 3]
            source_batch = {item["chapter_id"]: source_text_by_chapter[item["chapter_id"]] for item in batch}
            max_attempts = max(1, int(settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK or 1))
            for attempt in range(max_attempts):
                try:
                    result = await provider.translate(
                        prompt=_incremental_glossary_prompt(
                            batch,
                            source_language=source_language,
                            max_terms=max_terms,
                        ),
                        model=resolved_model,
                        max_tokens=2048,
                        json_schema=INCREMENTAL_GLOSSARY_DISCOVERY_JSON_SCHEMA,
                        request_purpose="glossary_discovery",
                        retry_attempt=attempt,
                        chapter_id=batch[0]["chapter_id"],
                    )
                    provider_calls += 1
                    self._record_usage(provider.key, resolved_model, result.get("metadata"))
                    discovered.extend(
                        parse_incremental_glossary_response(
                            str(result.get("text") or ""),
                            source_text_by_chapter=source_batch,
                            max_terms=max_terms,
                            strict=True,
                        )
                    )
                    for item in batch:
                        discovery_state[item["chapter_id"]] = {
                            "source_hash": hashlib.sha256(
                                source_text_by_chapter[item["chapter_id"]].encode("utf-8")
                            ).hexdigest(),
                            "prompt_version": INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION,
                            "provider_model": resolved_model or "",
                        }
                    break
                except ProviderError as exc:
                    retryable = exc.provider_error_code in {
                        ProviderErrorCode.RATE_LIMITED,
                        ProviderErrorCode.QUOTA_EXHAUSTED,
                        ProviderErrorCode.TEMPORARY,
                        ProviderErrorCode.TIMEOUT,
                    }
                    if not retryable:
                        raise
                    if exc.retry_after_seconds is not None or attempt + 1 >= max_attempts:
                        deferred = True
                        break
                except ValueError, RuntimeError:
                    if attempt + 1 >= max_attempts:
                        raise
            if deferred:
                break

    auto_activated: list[str] = []
    for candidate in discovered:
        source = str(candidate["source"])
        existing = entries_by_source.get(source)
        if existing is not None and str(existing.get("status") or "").lower() in {"approved", "translated"}:
            # Approved truth is never overwritten by a new model suggestion.
            continue
        safe = bool(candidate.get("safe_to_activate"))
        if source in heuristic_by_source and int(candidate.get("occurrence_count") or 0) < 2 and safe:
            safe = False
        entry = existing or {"source": source, "locked": True}
        entry.update(
            {
                "target": str(candidate["target"]),
                "confidence": float(candidate["confidence"]),
                "status": "approved" if safe else "pending",
                "notes": "Auto-activated after structural and confidence checks."
                if safe
                else "Proposed during incremental preflight; manual review required.",
                "occurrence_count": max(
                    int(entry.get("occurrence_count") or 0), int(candidate.get("occurrence_count") or 0)
                ),
            }
        )
        entries_by_source[source] = entry
        if safe:
            auto_activated.append(source)
            pending_sources.discard(source)
        else:
            pending_sources.add(source)

    ordered_entries = sorted(entries_by_source.values(), key=lambda item: str(item.get("source") or "").casefold())
    if ordered_entries != current_entries:
        self.storage.save_glossary(novel_id, ordered_entries)

    if discovery_state != raw_state and isinstance(metadata, dict):
        metadata["incremental_glossary_discovery"] = discovery_state
        self.storage.save_metadata(novel_id, metadata)

    # Keep the canonical DB glossary aligned when the platform row exists;
    # failure here must not discard the file-backed audit record.
    with contextlib.suppress(Exception), _session_scope() as session:
        novel = session.query(Novel).filter_by(slug=novel_id).one_or_none()
        if novel is not None:
            from novelai.services.glossary_repository import GlossaryRepository

            repository = GlossaryRepository(session)
            existing_db = {
                entry.canonical_term: entry for entry in repository.list_glossary_entries_for_novel(int(novel.id))
            }
            for entry in ordered_entries:
                source = str(entry.get("source") or "").strip()
                if not source:
                    continue
                status = str(entry.get("status") or "pending").lower()
                db_status = "approved" if status in {"approved", "translated"} else "candidate"
                db_entry = existing_db.get(source)
                if db_entry is not None and db_entry.status == "approved":
                    continue
                if db_entry is None:
                    repository.create_glossary_entry(
                        novel_id=int(novel.id),
                        canonical_term=source,
                        term_type="incremental_discovery",
                        approved_translation=str(entry.get("target") or "") or None,
                        status=db_status,
                        confidence=entry.get("confidence")
                        if isinstance(entry.get("confidence"), (int, float))
                        else None,
                        admin_notes=str(entry.get("notes") or "") or None,
                        decision_source="incremental_preflight",
                        rationale="Discovered from the selected chapter before body translation.",
                    )
                else:
                    repository.update_glossary_entry(
                        db_entry.id,
                        novel_id=int(novel.id),
                        approved_translation=str(entry.get("target") or "") or None,
                        confidence=entry.get("confidence")
                        if isinstance(entry.get("confidence"), (int, float))
                        else None,
                        admin_notes=str(entry.get("notes") or "") or None,
                    )
                    if db_entry.status != db_status:
                        db_entry.status = db_status
                        session.flush()

    return {
        "status": "deferred" if deferred else "completed",
        "selected_chapters": len(source_text_by_chapter),
        "provider_calls": provider_calls,
        "discovered": len(discovered),
        "auto_activated": sorted(auto_activated),
        "pending": sorted(pending_sources),
        "pending_count": len(pending_sources),
        "confidence_threshold": settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD,
        "batch_size": 3,
        "provider_model": resolved_model or provider_model,
        "discovery_state": discovery_state,
        "unchanged_chapters": sorted(unchanged_chapters),
        "changed_chapters": sorted(changed_chapters),
        "discovery_prompt_version": INCREMENTAL_GLOSSARY_DISCOVERY_PROMPT_VERSION,
    }


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
    effective_max_terms = (
        int(max_terms_value)
        if isinstance(max_terms_value, int) or (isinstance(max_terms_value, str) and max_terms_value.isdigit())
        else max_terms
    )
    effective_max_terms = max(1, effective_max_terms)
    include_existing = bool(extraction_config.get("include_existing", True))
    extraction_mode = (
        str(extraction_config.get("mode") or self._settings.get_glossary_extraction_mode()).strip().lower()
    )
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
            if isinstance(extraction_step_config.get("prompt_template"), str)
            and str(extraction_step_config.get("prompt_template")).strip()
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

    ordered_entries = sorted(
        existing.values(), key=lambda item: (str(item.get("source")).casefold(), str(item.get("source")))
    )
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
            request_purpose="glossary_discovery",
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


def _glossary_translation_cache_text(source: str) -> str:
    return f"metadata:glossary_term:{settings.TRANSLATION_TARGET_LANGUAGE}:{source.strip()}"


def _glossary_translation_prompt(items: list[dict[str, str]]) -> str:
    payload = [{"id": item["id"], "source": item["source"], "context": item.get("context", "")[:400]} for item in items]
    return (
        "Translate each Japanese glossary source term into concise natural English or an established "
        "romanization. Return one JSON object only with exactly one item per input id. "
        "Do not add explanations, markdown, omitted facts, gender, relationships, or speaker information. "
        "Approved glossary truth is authoritative; do not overwrite it.\n"
        f"Input: {json.dumps({'items': payload}, ensure_ascii=False, sort_keys=True)}"
    )


def _parse_glossary_translation_batch(raw_text: str, expected_ids: set[str]) -> dict[str, str]:
    text = raw_text.strip().removeprefix("```json").removesuffix("```").strip()
    payload = json.loads(text)
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        raise ValueError("Glossary batch response must contain an items array.")
    translations: dict[str, str] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValueError("Glossary batch response contains a non-object item.")
        item_id = str(raw_item.get("id") or "").strip()
        target = str(raw_item.get("translation") or "").strip()
        if item_id not in expected_ids:
            raise ValueError(f"Glossary batch response returned unknown item id {item_id!r}.")
        if item_id in translations:
            raise ValueError(f"Glossary batch response duplicated item id {item_id!r}.")
        if not target or len(target) > 255 or "\n" in target:
            raise ValueError(f"Glossary batch response returned an invalid translation for {item_id!r}.")
        translations[item_id] = target
    missing = expected_ids - set(translations)
    if missing:
        raise ValueError(f"Glossary batch response missing item ids: {', '.join(sorted(missing))}.")
    return translations


async def _translate_glossary_batch(
    self: Any,
    *,
    provider: Any,
    provider_key: str,
    provider_model: str,
    items: list[dict[str, str]],
) -> tuple[dict[str, str], int]:
    expected_ids = {item["id"] for item in items}
    prompt = _glossary_translation_prompt(items)
    max_attempts = max(1, int(settings.TRANSLATION_MAX_ATTEMPTS_PER_CHUNK or 1))
    for attempt in range(max_attempts):
        try:
            result = await provider.translate(
                prompt=prompt,
                model=provider_model,
                max_tokens=min(4096, max(256, len(items) * 96)),
                json_schema=GLOSSARY_TRANSLATION_BATCH_JSON_SCHEMA,
                request_purpose="glossary_translation",
                retry_attempt=attempt,
            )
            translations = _parse_glossary_translation_batch(
                str(result.get("text") or ""),
                expected_ids,
            )
            self._record_usage(provider.key, provider_model, result.get("metadata"))
            for item in items:
                self._cache.set(
                    _glossary_translation_cache_text(item["source"]),
                    provider.key,
                    provider_model,
                    translations[item["id"]],
                )
            return translations, attempt + 1
        except ProviderError as exc:
            retryable = exc.provider_error_code in {
                ProviderErrorCode.RATE_LIMITED,
                ProviderErrorCode.QUOTA_EXHAUSTED,
                ProviderErrorCode.TEMPORARY,
                ProviderErrorCode.TIMEOUT,
            }
            if not retryable or exc.retry_after_seconds is not None or attempt + 1 >= max_attempts:
                raise
        except ValueError, RuntimeError:
            if attempt + 1 >= max_attempts:
                raise
    raise RuntimeError("Glossary batch translation exhausted its same-model retry budget.")


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

    resolved_provider, resolved_model = self._resolve_provider_and_model(effective_provider, effective_model)
    if resolved_provider == "dummy":
        raise RuntimeError(
            "Glossary translation skipped because no active Gemini provider is configured. "
            "Add and use a provider API token in Settings."
        )
    provider = self._provider_factory(resolved_provider)
    try:
        supported_models = provider.available_models() or []
    except Exception:
        supported_models = []
    candidates = model_candidates(resolved_provider, resolved_model, supported_models)
    if not candidates:
        raise RuntimeError(f"No translation model configured for provider {resolved_provider}.")
    candidate_model = candidates[0]

    translated_count = 0
    skipped_count = 0
    cache_hits = 0
    updated_entries: list[dict[str, Any]] = [dict(entry) for entry in entries]
    batch_items: list[dict[str, str]] = []
    batch_indexes: dict[str, int] = {}
    for index, entry in enumerate(entries):
        status = str(entry.get("status") or "pending").strip().lower()
        if status == "ignored" or (only_pending and status != "pending"):
            skipped_count += 1
            continue
        source = str(entry.get("source") or "").strip()
        if not source:
            skipped_count += 1
            continue
        cache_key = _glossary_translation_cache_text(source)
        cached = self._cache.get(cache_key, provider.key, candidate_model)
        if cached is not None and cached.strip():
            updated_entries[index]["target"] = cached.strip()
            translated_count += 1
            cache_hits += 1
            continue
        item_id = f"term:{len(batch_items):05d}"
        context = str(entry.get("context_summary") or entry.get("notes") or "").strip()[:400]
        batch_items.append({"id": item_id, "source": source, "context": context})
        batch_indexes[item_id] = index

    batch_size = max(1, int(settings.TRANSLATION_GLOSSARY_BATCH_SIZE or 1))
    provider_calls = 0
    failed_batches = 0
    for start in range(0, len(batch_items), batch_size):
        batch = batch_items[start : start + batch_size]
        try:
            translations, attempts_used = await _translate_glossary_batch(
                self,
                provider=provider,
                provider_key=resolved_provider,
                provider_model=candidate_model,
                items=batch,
            )
            provider_calls += attempts_used
            for item_id, target in translations.items():
                index = batch_indexes[item_id]
                updated_entries[index]["target"] = target
                translated_count += 1
        except Exception as exc:
            failed_batches += 1
            skipped_count += len(batch)
            logger.warning(
                "Glossary translation batch failed with %s/%s; retaining pending terms without individual fallback: %s",
                resolved_provider,
                candidate_model,
                exc.__class__.__name__,
            )

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
        provider=resolved_provider,
        model=candidate_model,
        provider_calls=provider_calls,
        batch_count=(len(batch_items) + batch_size - 1) // batch_size,
        failed_batches=failed_batches,
        cache_hits=cache_hits,
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
        confidence = updated.get("confidence")
        confidence_is_high = (
            isinstance(confidence, (int, float))
            and not isinstance(confidence, bool)
            and float(confidence) >= settings.TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD
        )
        if (
            auto_approve_translated
            and confidence_is_high
            and target
            and target.casefold() != source.casefold()
            and len(target) >= max(1, min_target_length)
        ):
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
            sync_result = GlossarySyncService(repo, self.storage).sync_from_file(novel_id, actor_user_id=None)
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
        logger.warning("Glossary DB sync failed after review: %s", exc.__class__.__name__)
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


@dataclass
class ChapterApplyResult:
    chapter_id: str
    status: Literal["applied", "skipped", "blocked", "failed"]
    replacements_made: int
    delta_fraction: float
    new_version_id: str | None = None
    previous_version_id: str | None = None
    block_reason: str | None = None
    error: str | None = None


@dataclass
class ApplyGlossaryResult:
    novel_id: str
    dry_run: bool
    batch_id: str | None
    glossary_revision: int
    chapters: list[ChapterApplyResult]
    total_applied: int
    total_skipped: int
    total_blocked: int
    total_failed: int


async def apply_glossary_to_chapters(
    self: Any,
    novel_id: str,
    *,
    entry_ids: list[int] | None = None,
    include_all_approved: bool = False,
    chapter_numbers: list[int] | None = None,
    chapter_start: int | None = None,
    chapter_end: int | None = None,
    max_chapters: int | None = None,
    dry_run: bool = True,
    max_delta_fraction: float = 0.15,
    force_needs_review: bool = False,
    batch_id: str | None = None,
) -> ApplyGlossaryResult:
    """Apply glossary replacements to translated chapters.

    Delegates classification to ``GlossaryApplyPreviewService``, then
    writes new chapter versions using storage functions.
    """
    meta = self.storage.load_metadata(novel_id)
    if not meta:
        raise RuntimeError("Metadata not found; import or scrape a novel first.")
    return self._run_apply_glossary(
        novel_id=novel_id,
        meta=meta,
        entry_ids=entry_ids,
        include_all_approved=include_all_approved,
        chapter_numbers=chapter_numbers,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
        max_chapters=max_chapters,
        dry_run=dry_run,
        max_delta_fraction=max_delta_fraction,
        force_needs_review=force_needs_review,
        batch_id=batch_id,
    )


def _run_apply_glossary(
    self: Any,
    *,
    novel_id: str,
    meta: dict[str, Any],
    entry_ids: list[int] | None,
    include_all_approved: bool,
    chapter_numbers: list[int] | None,
    chapter_start: int | None,
    chapter_end: int | None,
    max_chapters: int | None,
    dry_run: bool,
    max_delta_fraction: float,
    force_needs_review: bool,
    batch_id: str | None,
) -> ApplyGlossaryResult:
    """Synchronous body of apply_glossary_to_chapters."""
    effective_max = max_chapters if isinstance(max_chapters, int) else 200

    with _session_scope() as db_session:
        # Resolve DB novel
        novel_db = db_session.execute(select(Novel).where(Novel.slug == novel_id)).scalar_one_or_none()
        if novel_db is None and novel_id.isdigit():
            novel_db = db_session.get(Novel, int(novel_id))
        if novel_db is None:
            raise RuntimeError(f"Novel not found in DB: {novel_id}")
        db_novel_id = novel_db.id
        glossary_revision = getattr(novel_db, "glossary_revision", 0) or 0
        preview_request = GlossaryApplyPreviewRequest(
            entry_ids=entry_ids,
            include_all_approved=include_all_approved,
            chapter_numbers=chapter_numbers,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
            max_chapters=effective_max,
            max_delta_fraction=max_delta_fraction,
        )
        service = GlossaryApplyPreviewService(db_session, self.storage)
        preview = service.preview(db_novel_id, preview_request)

        if dry_run:
            chapters_result = [
                ChapterApplyResult(
                    chapter_id=ch.chapter_storage_id,
                    status="skipped" if ch.safe_count == 0 else "applied",
                    replacements_made=max(ch.safe_count, ch.needs_review_count),
                    delta_fraction=ch.delta_fraction,
                )
                for ch in preview.chapters
            ]
            total_applied = sum(1 for c in chapters_result if c.status == "applied")
            return ApplyGlossaryResult(
                novel_id=novel_id,
                dry_run=True,
                batch_id=batch_id,
                glossary_revision=glossary_revision,
                chapters=chapters_result,
                total_applied=total_applied,
                total_skipped=len(preview.chapters) - total_applied,
                total_blocked=0,
                total_failed=0,
            )

        # Non-dry-run: apply replacements
        chapters_result: list[ChapterApplyResult] = []
        total_applied = 0
        total_skipped = 0
        total_blocked = 0
        total_failed = 0

        for ch in preview.chapters:
            # Determine safe replacements to apply
            safe_repls = [
                r
                for r in ch.replacements
                if r.risk_status == "safe" or (force_needs_review and r.risk_status == "needs_review")
            ]
            has_needs_review = any(r.risk_status == "needs_review" for r in ch.replacements)
            has_blocked = any(r.risk_status == "blocked" for r in ch.replacements)

            if has_blocked and not force_needs_review:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="blocked",
                        replacements_made=0,
                        delta_fraction=ch.delta_fraction,
                        block_reason="chapter_contains_blocked_replacements",
                    )
                )
                total_blocked += 1
                continue

            if has_needs_review and not force_needs_review:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="skipped",
                        replacements_made=0,
                        delta_fraction=ch.delta_fraction,
                        block_reason="needs_review",
                    )
                )
                total_skipped += 1
                continue

            if not safe_repls:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="skipped",
                        replacements_made=0,
                        delta_fraction=0.0,
                    )
                )
                total_skipped += 1
                continue

            # Load active translation
            active = self.storage.load_translated_chapter(novel_id, ch.chapter_storage_id)
            if not active:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="failed",
                        replacements_made=0,
                        delta_fraction=0.0,
                        error="active_translation_not_found",
                    )
                )
                total_failed += 1
                continue

            original_text = active.get("text", "")
            previous_version_id = active.get("version_id")

            try:
                new_text, applied_count = apply_glossary_replacements(
                    original_text,
                    safe_repls,
                )
            except Exception as exc:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="failed",
                        replacements_made=0,
                        delta_fraction=0.0,
                        error=str(exc),
                    )
                )
                total_failed += 1
                continue

            # Final delta_fraction re-check
            df = (len(new_text) - len(original_text)) / max(1, len(original_text))
            final_delta = abs(df)
            if final_delta > max_delta_fraction:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="blocked",
                        replacements_made=0,
                        delta_fraction=final_delta,
                        block_reason="delta_fraction_exceeded",
                    )
                )
                total_blocked += 1
                continue

            # Write new version
            try:
                path = self.storage.save_translated_chapter(
                    novel_id,
                    ch.chapter_storage_id,
                    new_text,
                    version_kind=ChapterVersionKind.GLOSSARY_APPLY,
                    glossary_revision=glossary_revision,
                    glossary_injected_term_count=applied_count,
                    base_version_id=previous_version_id,
                    batch_id=batch_id,
                )
                # Invalidate library summary cache after successful storage write
                best_effort_invalidate()
                safely_refresh_catalog_projection_after_storage_write(
                    novel_id,
                    self.storage,
                    context="glossary_apply",
                )
            except Exception as exc:
                chapters_result.append(
                    ChapterApplyResult(
                        chapter_id=ch.chapter_storage_id,
                        status="failed",
                        replacements_made=0,
                        delta_fraction=final_delta,
                        error=str(exc),
                    )
                )
                total_failed += 1
                continue

            new_version_id = str(getattr(path, "stem", None) or ch.chapter_storage_id)
            chapters_result.append(
                ChapterApplyResult(
                    chapter_id=ch.chapter_storage_id,
                    status="applied",
                    replacements_made=applied_count,
                    delta_fraction=final_delta,
                    new_version_id=new_version_id,
                    previous_version_id=previous_version_id,
                )
            )
            total_applied += 1

        return ApplyGlossaryResult(
            novel_id=novel_id,
            dry_run=False,
            batch_id=batch_id,
            glossary_revision=glossary_revision,
            chapters=chapters_result,
            total_applied=total_applied,
            total_skipped=total_skipped,
            total_blocked=total_blocked,
            total_failed=total_failed,
        )
