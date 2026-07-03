"""Confirmed approved glossary repair apply and rollback.

This module builds on preview-only matching. It recomputes preview from current
saved translated chapter text, applies only allowed exact replacements, writes a
storage-backed event/backup ledger, and supports rollback by event id.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol
from uuid import uuid4

from novelai.core.platform import ChapterVersionKind
from novelai.services.glossary_apply_preview import (
    GlossaryApplyPreviewRequest,
    GlossaryApplyPreviewResult,
    GlossaryApplyPreviewService,
    GlossaryReplacementPreview,
)
from novelai.utils import atomic_write


class GlossaryApplyStorage(Protocol):
    def load_translated_chapter(self, novel_id: str, chapter_id: str) -> dict[str, Any] | None: ...

    def save_translated_chapter(
        self,
        novel_id: str,
        chapter_id: str,
        text: str,
        provider: str | None = None,
        model: str | None = None,
        confidence_score: float | None = None,
        polish_needed: bool | None = None,
        confidence_details: dict[str, Any] | None = None,
        source_hash: str | None = None,
        version_kind: ChapterVersionKind = ChapterVersionKind.MANUAL_EDIT,
    ) -> Any: ...


ApplyStatus = Literal["applied", "partially_applied", "failed", "rolled_back"]

_MAX_CHAPTERS = 200
_MAX_REPLACEMENTS = 1000


@dataclass(frozen=True)
class GlossaryApplyRequest:
    entry_ids: list[int] | None = None
    include_all_approved: bool = False
    chapter_numbers: list[int] | None = None
    chapter_start: int | None = None
    chapter_end: int | None = None
    max_chapters: int = 20
    max_replacements: int = 100
    allow_needs_review: bool = False
    confirm: bool = False
    created_by: int | None = None


@dataclass(frozen=True)
class GlossaryAppliedChapter:
    chapter_storage_id: str
    chapter_id: int | None
    chapter_number: int | None
    replacement_count: int
    original_hash: str
    applied_hash: str


@dataclass(frozen=True)
class GlossaryApplyResult:
    apply_event_id: str | None
    platform_novel_id: int
    storage_novel_id: str
    status: ApplyStatus
    preview: GlossaryApplyPreviewResult
    applied_chapters: list[GlossaryAppliedChapter] = field(default_factory=list)
    replacement_count: int = 0
    skipped_match_count: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class GlossaryApplyEventSummary:
    apply_event_id: str
    platform_novel_id: int
    storage_novel_id: str
    status: str
    created_at: str
    created_by: int | None
    chapter_count: int
    replacement_count: int
    rollback_status: str
    rolled_back_at: str | None = None


@dataclass(frozen=True)
class GlossaryRollbackResult:
    apply_event_id: str
    platform_novel_id: int
    storage_novel_id: str
    status: Literal["rolled_back", "already_rolled_back", "failed"]
    restored_chapter_count: int
    warnings: list[str] = field(default_factory=list)


class GlossaryApplyService:
    """Apply and rollback owner-confirmed approved glossary repairs."""

    def __init__(self, preview_service: GlossaryApplyPreviewService, storage: GlossaryApplyStorage) -> None:
        self.preview_service = preview_service
        self.storage = storage

    def confirm_apply(self, novel_id: int, request: GlossaryApplyRequest) -> GlossaryApplyResult:
        if not request.confirm:
            raise ValueError("confirm=true is required to apply glossary replacements.")

        preview_request = GlossaryApplyPreviewRequest(
            entry_ids=request.entry_ids,
            include_all_approved=request.include_all_approved,
            chapter_numbers=request.chapter_numbers,
            chapter_start=request.chapter_start,
            chapter_end=request.chapter_end,
            max_chapters=request.max_chapters,
            max_matches=request.max_replacements,
        )
        preview = self.preview_service.preview(novel_id, preview_request)
        storage_novel_id = self.preview_service._storage_key_for_novel(novel_id)
        warnings = list(preview.warnings)
        applicable_by_chapter = self._applicable_replacements(preview, allow_needs_review=request.allow_needs_review)
        skipped_match_count = preview.total_match_count - sum(len(items) for items in applicable_by_chapter.values())
        if not applicable_by_chapter:
            warnings.append("No safe glossary replacements were available to apply.")
            return GlossaryApplyResult(
                apply_event_id=None,
                platform_novel_id=novel_id,
                storage_novel_id=storage_novel_id,
                status="failed",
                preview=preview,
                replacement_count=0,
                skipped_match_count=skipped_match_count,
                warnings=warnings,
            )

        event_id = f"glossary_apply_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
        event = self._build_event(
            event_id,
            novel_id=novel_id,
            storage_novel_id=storage_novel_id,
            request=request,
            preview=preview,
            applicable_by_chapter=applicable_by_chapter,
            warnings=warnings,
        )
        self._write_event(storage_novel_id, event_id, event)

        applied: list[GlossaryAppliedChapter] = []
        failed = False
        for chapter in preview.chapters:
            replacements = applicable_by_chapter.get(chapter.chapter_storage_id)
            if not replacements:
                continue
            original = self._chapter_text(storage_novel_id, chapter.chapter_storage_id)
            if original is None:
                warnings.append(f"Skipped chapter {chapter.chapter_storage_id}: translated text was missing at apply time.")
                failed = True
                continue
            next_text = _apply_replacements(original, replacements)
            try:
                self.storage.save_translated_chapter(
                    storage_novel_id,
                    chapter.chapter_storage_id,
                    next_text,
                    provider="glossary_apply",
                    model=None,
                    source_hash=_hash_text(original),
                    version_kind=ChapterVersionKind.MANUAL_EDIT,
                )
            except Exception as exc:  # pragma: no cover - defensive against storage failures
                warnings.append(f"Failed to write chapter {chapter.chapter_storage_id}: {exc}")
                failed = True
                continue
            applied.append(
                GlossaryAppliedChapter(
                    chapter_storage_id=chapter.chapter_storage_id,
                    chapter_id=chapter.chapter_id,
                    chapter_number=chapter.chapter_number,
                    replacement_count=len(replacements),
                    original_hash=_hash_text(original),
                    applied_hash=_hash_text(next_text),
                )
            )

        status: ApplyStatus = "applied"
        if failed or len(applied) < len(applicable_by_chapter):
            status = "partially_applied" if applied else "failed"
        event["status"] = status
        event["warnings"] = warnings
        event["applied_chapters"] = [item.__dict__ for item in applied]
        self._write_event(storage_novel_id, event_id, event)
        return GlossaryApplyResult(
            apply_event_id=event_id,
            platform_novel_id=novel_id,
            storage_novel_id=storage_novel_id,
            status=status,
            preview=preview,
            applied_chapters=applied,
            replacement_count=sum(item.replacement_count for item in applied),
            skipped_match_count=skipped_match_count,
            warnings=warnings,
        )

    def list_events(self, novel_id: int) -> list[GlossaryApplyEventSummary]:
        storage_novel_id = self.preview_service._storage_key_for_novel(novel_id)
        events: list[GlossaryApplyEventSummary] = []
        for path in sorted(getattr(self.storage, "_glob")(self._event_dir(storage_novel_id), "*.json")):  # noqa: B009
            event = self._read_event_path(path)
            if not event or event.get("platform_novel_id") != novel_id:
                continue
            events.append(_event_summary(event))
        return sorted(events, key=lambda item: item.created_at, reverse=True)

    def rollback(self, novel_id: int, apply_event_id: str, *, created_by: int | None = None) -> GlossaryRollbackResult:
        storage_novel_id = self.preview_service._storage_key_for_novel(novel_id)
        event = self._read_event(storage_novel_id, apply_event_id)
        if event is None or event.get("platform_novel_id") != novel_id:
            raise LookupError("Glossary apply event not found.")
        if event.get("rollback_status") == "rolled_back":
            return GlossaryRollbackResult(
                apply_event_id=apply_event_id,
                platform_novel_id=novel_id,
                storage_novel_id=storage_novel_id,
                status="already_rolled_back",
                restored_chapter_count=0,
                warnings=["Apply event was already rolled back."],
            )

        warnings: list[str] = []
        restored = 0
        for chapter in event.get("chapters", []):
            if not isinstance(chapter, dict):
                continue
            storage_id = chapter.get("chapter_storage_id")
            original_text = chapter.get("original_text")
            applied_hash = chapter.get("applied_hash")
            if not isinstance(storage_id, str) or not isinstance(original_text, str) or not isinstance(applied_hash, str):
                warnings.append("Skipped malformed backup chapter record.")
                continue
            current = self._chapter_text(storage_novel_id, storage_id)
            if current is None:
                warnings.append(f"Cannot rollback chapter {storage_id}: current translated text is missing.")
                continue
            if _hash_text(current) != applied_hash:
                warnings.append(f"Cannot rollback chapter {storage_id}: current text no longer matches applied hash.")
                continue
            self.storage.save_translated_chapter(
                storage_novel_id,
                storage_id,
                original_text,
                provider="glossary_rollback",
                model=None,
                source_hash=_hash_text(current),
                version_kind=ChapterVersionKind.ROLLBACK,
            )
            restored += 1

        if restored:
            event["status"] = "rolled_back"
            event["rollback_status"] = "rolled_back"
            event["rolled_back_at"] = _utcnow()
            event["rolled_back_by"] = created_by
            self._write_event(storage_novel_id, apply_event_id, event)
            return GlossaryRollbackResult(
                apply_event_id=apply_event_id,
                platform_novel_id=novel_id,
                storage_novel_id=storage_novel_id,
                status="rolled_back",
                restored_chapter_count=restored,
                warnings=warnings,
            )

        return GlossaryRollbackResult(
            apply_event_id=apply_event_id,
            platform_novel_id=novel_id,
            storage_novel_id=storage_novel_id,
            status="failed",
            restored_chapter_count=0,
            warnings=warnings or ["No chapters were restored."],
        )

    def _applicable_replacements(
        self,
        preview: GlossaryApplyPreviewResult,
        *,
        allow_needs_review: bool,
    ) -> dict[str, list[GlossaryReplacementPreview]]:
        applicable: dict[str, list[GlossaryReplacementPreview]] = {}
        allowed = {"safe", "needs_review"} if allow_needs_review else {"safe"}
        for chapter in preview.chapters:
            replacements = [item for item in chapter.replacements if item.risk_status in allowed]
            replacements = _non_overlapping(replacements)
            if replacements:
                applicable[chapter.chapter_storage_id] = replacements
        return applicable

    def _build_event(
        self,
        event_id: str,
        *,
        novel_id: int,
        storage_novel_id: str,
        request: GlossaryApplyRequest,
        preview: GlossaryApplyPreviewResult,
        applicable_by_chapter: dict[str, list[GlossaryReplacementPreview]],
        warnings: list[str],
    ) -> dict[str, Any]:
        chapters: list[dict[str, Any]] = []
        glossary_entry_ids: set[int] = set()
        old_variants: set[str] = set()
        approved_translations: set[str] = set()
        for chapter in preview.chapters:
            replacements = applicable_by_chapter.get(chapter.chapter_storage_id)
            if not replacements:
                continue
            original = self._chapter_text(storage_novel_id, chapter.chapter_storage_id)
            if original is None:
                continue
            applied = _apply_replacements(original, replacements)
            for replacement in replacements:
                glossary_entry_ids.add(replacement.glossary_entry_id)
                old_variants.add(replacement.old_text)
                approved_translations.add(replacement.new_text)
            chapters.append(
                {
                    "chapter_storage_id": chapter.chapter_storage_id,
                    "chapter_id": chapter.chapter_id,
                    "chapter_number": chapter.chapter_number,
                    "original_text": original,
                    "original_hash": _hash_text(original),
                    "applied_hash": _hash_text(applied),
                    "replacement_count": len(replacements),
                    "replacements": [_replacement_payload(item) for item in replacements],
                }
            )

        return {
            "apply_event_id": event_id,
            "platform_novel_id": novel_id,
            "storage_novel_id": storage_novel_id,
            "status": "pending",
            "created_at": _utcnow(),
            "created_by": request.created_by,
            "chapters": chapters,
            "applied_chapters": [],
            "glossary_entry_ids": sorted(glossary_entry_ids),
            "old_variants_replaced": sorted(old_variants),
            "approved_translations_inserted": sorted(approved_translations),
            "replacement_count": sum(len(items) for items in applicable_by_chapter.values()),
            "warnings": warnings,
            "rollback_status": "available",
            "rolled_back_at": None,
            "rolled_back_by": None,
        }

    def _chapter_text(self, storage_novel_id: str, chapter_storage_id: str) -> str | None:
        payload = self.storage.load_translated_chapter(storage_novel_id, chapter_storage_id) or {}
        text = payload.get("text")
        return text if isinstance(text, str) else None

    def _event_dir(self, storage_novel_id: str) -> Path:
        novel_dir = getattr(self.storage, "_novel_dir")(storage_novel_id)  # noqa: B009
        path = novel_dir / "glossary_apply_events"
        getattr(self.storage, "_mkdirs")(path)  # noqa: B009
        return path

    def _event_path(self, storage_novel_id: str, apply_event_id: str) -> Path:
        safe_id = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in apply_event_id)
        return self._event_dir(storage_novel_id) / f"{safe_id}.json"

    def _write_event(self, storage_novel_id: str, apply_event_id: str, event: dict[str, Any]) -> None:
        atomic_write(self._event_path(storage_novel_id, apply_event_id), json.dumps(event, ensure_ascii=False, indent=2))

    def _read_event(self, storage_novel_id: str, apply_event_id: str) -> dict[str, Any] | None:
        return self._read_event_path(self._event_path(storage_novel_id, apply_event_id))

    def _read_event_path(self, path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(getattr(self.storage, "_read_text")(path))  # noqa: B009
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None


def _apply_replacements(text: str, replacements: list[GlossaryReplacementPreview]) -> str:
    result = text
    for replacement in sorted(replacements, key=lambda item: item.start_offset, reverse=True):
        result = result[: replacement.start_offset] + replacement.new_text + result[replacement.end_offset :]
    return result


def _non_overlapping(replacements: list[GlossaryReplacementPreview]) -> list[GlossaryReplacementPreview]:
    selected: list[GlossaryReplacementPreview] = []
    occupied: list[tuple[int, int]] = []
    for replacement in sorted(replacements, key=lambda item: (item.start_offset, -(item.end_offset - item.start_offset))):
        if any(replacement.start_offset < end and replacement.end_offset > start for start, end in occupied):
            continue
        selected.append(replacement)
        occupied.append((replacement.start_offset, replacement.end_offset))
    return selected


def _replacement_payload(replacement: GlossaryReplacementPreview) -> dict[str, Any]:
    return {
        "glossary_entry_id": replacement.glossary_entry_id,
        "canonical_term": replacement.canonical_term,
        "old_text": replacement.old_text,
        "new_text": replacement.new_text,
        "risk_status": replacement.risk_status,
        "reason_codes": replacement.reason_codes,
        "start_offset": replacement.start_offset,
        "end_offset": replacement.end_offset,
    }


def _event_summary(event: dict[str, Any]) -> GlossaryApplyEventSummary:
    return GlossaryApplyEventSummary(
        apply_event_id=str(event.get("apply_event_id") or ""),
        platform_novel_id=int(event.get("platform_novel_id") or 0),
        storage_novel_id=str(event.get("storage_novel_id") or ""),
        status=str(event.get("status") or "failed"),
        created_at=str(event.get("created_at") or ""),
        created_by=event.get("created_by") if isinstance(event.get("created_by"), int) else None,
        chapter_count=len(event.get("chapters") or []),
        replacement_count=int(event.get("replacement_count") or 0),
        rollback_status=str(event.get("rollback_status") or "unknown"),
        rolled_back_at=event.get("rolled_back_at") if isinstance(event.get("rolled_back_at"), str) else None,
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()
