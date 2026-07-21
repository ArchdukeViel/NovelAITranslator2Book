from __future__ import annotations

from typing import Any

from novelai.api.models import ActivityListResponse, ActivityRecordResponse

_PROGRESS_KEYS = (
    "current_stage",
    "current_label",
    "completed",
    "total",
    "paused_reason",
    "resume_after",
    "errors",
    "warnings",
    "model_states",
)


def translation_provider_response(item: dict[str, Any]) -> dict[str, Any]:
    response = dict(item)
    if "provider" in response:
        response["provider_key"] = response["provider"]
    if "model" in response:
        response["provider_model"] = response["model"]
    return response


def translated_chapter_response(novel_id: str, chapter_id: str, translated: dict[str, Any]) -> dict[str, Any]:
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        **translation_provider_response(translated),
    }


def _metadata_dict(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _progress_dict(metadata: dict[str, Any]) -> dict[str, Any]:
    progress = metadata.get("progress")
    return dict(progress) if isinstance(progress, dict) else {}


def activity_record_response(item: dict[str, Any]) -> ActivityRecordResponse:
    normalized = dict(item)
    normalized.pop("provider", None)
    normalized.pop("model", None)
    metadata = _metadata_dict(normalized)
    progress = _progress_dict(metadata)
    activity_id = str(normalized.get("id") or normalized.get("activity_id") or normalized.get("job_id") or "")
    normalized["activity_id"] = str(normalized.get("activity_id") or activity_id)
    normalized["job_id"] = str(normalized.get("job_id") or activity_id)
    normalized["provider_key"] = normalized.get("provider_key") or metadata.get("provider_key")
    normalized["provider_model"] = normalized.get("provider_model") or metadata.get("provider_model")
    normalized["metadata"] = metadata
    for key in _PROGRESS_KEYS:
        if key in normalized and normalized.get(key) is not None:
            continue
        if key in progress:
            normalized[key] = progress.get(key)
        elif key in metadata:
            normalized[key] = metadata.get(key)
    normalized.setdefault("errors", [])
    normalized.setdefault("warnings", [])
    normalized.setdefault("model_states", [])
    return ActivityRecordResponse.model_validate(normalized)


def activity_list_response(items: list[dict[str, Any]]) -> ActivityListResponse:
    normalized = [activity_record_response(item) for item in items]
    return ActivityListResponse(activity=normalized, jobs=normalized)
