from __future__ import annotations

import hashlib
import json
from typing import Any

from novelai.storage.common import _utc_now_iso


def _trace_dir(self: Any):
    path = self.runtime_path("traceability")
    self._mkdirs(path)
    return path


def _read_json_file(self: Any, path, default: Any) -> Any:
    if not self._path_exists(path):
        return default
    try:
        data = json.loads(self._read_text(path))
    except json.JSONDecodeError, OSError:
        return default
    return data


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _scope_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _chapter_scope(payload: dict[str, Any]) -> str:
    explicit = _scope_part(payload.get("chapter_scope"))
    if explicit is not None:
        return explicit
    chapter_ids = _list_strings(payload.get("chapter_ids") or payload.get("chapter_id"))
    return "+".join(chapter_ids) if chapter_ids else "chapter_unknown"


def _run_scope(payload: dict[str, Any]) -> str:
    for key in ("translation_run_id", "run_id", "job_id", "activity_id"):
        value = _scope_part(payload.get(key))
        if value is not None:
            return value
    return "run_manual"


def _pipeline_event_id(payload: dict[str, Any]) -> str:
    supplied = _scope_part(payload.get("event_id"))
    if supplied is not None:
        return supplied
    identity_payload = {key: value for key, value in payload.items() if key not in {"event_id", "timestamp"}}
    serialized = json.dumps(identity_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return f"event_{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:32]}"


def _append_pipeline_events(self: Any, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    path = self._trace_dir() / "pipeline_events.json"
    existing = self._read_json_file(path, [])
    stored_events = [dict(event) for event in existing if isinstance(event, dict)] if isinstance(existing, list) else []
    existing_by_id = {_pipeline_event_id(event): event for event in stored_events}
    stored: list[dict[str, Any]] = []
    changed = False
    for event in events:
        if not isinstance(event, dict):
            continue
        payload = _as_dict(event)
        payload["event_id"] = _pipeline_event_id(payload)
        payload["timestamp"] = str(payload.get("timestamp") or _utc_now_iso())
        previous = existing_by_id.get(payload["event_id"])
        if previous is not None:
            stored.append(dict(previous))
            continue
        stored_events.append(payload)
        existing_by_id[payload["event_id"]] = payload
        stored.append(dict(payload))
        changed = True
    if changed:
        self._write_text_atomic(path, json.dumps(stored_events, ensure_ascii=False, indent=2))
    return stored


def append_pipeline_event(self: Any, event: dict[str, Any] | Any) -> dict[str, Any]:
    stored = _append_pipeline_events(self, [_as_dict(event)])
    return stored[0] if stored else {}


def append_pipeline_events(self: Any, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _append_pipeline_events(self, events)


def list_pipeline_events(
    self: Any,
    *,
    job_id: str | None = None,
    activity_id: str | None = None,
    novel_id: str | None = None,
    chapter_id: str | None = None,
) -> list[dict[str, Any]]:
    path = self._trace_dir() / "pipeline_events.json"
    events = self._read_json_file(path, [])
    if not isinstance(events, list):
        return []
    filtered = [dict(event) for event in events if isinstance(event, dict)]
    for key, value in (
        ("job_id", job_id),
        ("activity_id", activity_id),
        ("novel_id", novel_id),
        ("chapter_id", chapter_id),
    ):
        if isinstance(value, str) and value.strip():
            filtered = [event for event in filtered if event.get(key) == value]
    return filtered


def _merge_chunk_state(states: dict[str, Any], state: dict[str, Any] | Any, now: str) -> dict[str, Any]:
    payload = _as_dict(state)
    chunk_id = payload.get("chunk_id")
    novel_id = payload.get("novel_id")
    if not isinstance(chunk_id, str) or not chunk_id.strip():
        raise ValueError("chunk_id is required.")
    if not isinstance(novel_id, str) or not novel_id.strip():
        raise ValueError("novel_id is required.")

    payload["created_at"] = str(payload.get("created_at") or now)
    payload["updated_at"] = now
    run_scope = _run_scope(payload)
    chapter_scope = _chapter_scope(payload)
    payload["translation_run_id"] = run_scope
    payload["chapter_scope"] = chapter_scope
    key = f"{novel_id}:{run_scope}:{chapter_scope}:{chunk_id}"
    existing = states.get(key)
    merged = {**existing, **payload} if isinstance(existing, dict) else payload
    states[key] = merged
    return dict(merged)


def upsert_chunk_state(self: Any, state: dict[str, Any] | Any) -> dict[str, Any]:
    path = self._trace_dir() / "chunk_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        states = {}
    merged = _merge_chunk_state(states, state, _utc_now_iso())
    self._write_text(path, json.dumps(states, ensure_ascii=False, indent=2))
    return merged


def upsert_chunk_states(self: Any, states_to_merge: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coalesce safe progress-state writes into one read/modify/write cycle."""

    path = self._trace_dir() / "chunk_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        states = {}
    now = _utc_now_iso()
    stored = [_merge_chunk_state(states, state, now) for state in states_to_merge if isinstance(state, dict)]
    if stored:
        self._write_text(path, json.dumps(states, ensure_ascii=False, indent=2))
    return stored


def load_chunk_states(
    self: Any,
    *,
    novel_id: str | None = None,
    chapter_id: str | None = None,
    status: str | None = None,
    translation_run_id: str | None = None,
) -> list[dict[str, Any]]:
    path = self._trace_dir() / "chunk_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        return []
    items = [dict(value) for value in states.values() if isinstance(value, dict)]
    if isinstance(novel_id, str) and novel_id.strip():
        items = [item for item in items if item.get("novel_id") == novel_id]
    if isinstance(chapter_id, str) and chapter_id.strip():
        items = [
            item
            for item in items
            if chapter_id in [str(value) for value in item.get("chapter_ids", [])]
            or item.get("chapter_id") == chapter_id
        ]
    if isinstance(translation_run_id, str) and translation_run_id.strip():
        items = [item for item in items if _run_scope(item) == translation_run_id]
    if isinstance(status, str) and status.strip():
        items = [item for item in items if item.get("status") == status]
    return items


def save_scheduler_state(self: Any, job_id: str, model_states: list[dict[str, Any] | Any]) -> dict[str, Any]:
    normalized_job_id = job_id.strip() if isinstance(job_id, str) else ""
    if not normalized_job_id:
        raise ValueError("job_id is required.")
    payload = {
        "job_id": normalized_job_id,
        "updated_at": _utc_now_iso(),
        "model_states": [_as_dict(state) for state in model_states],
    }
    path = self._trace_dir() / "scheduler_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        states = {}
    states[normalized_job_id] = payload
    self._write_text_atomic(path, json.dumps(states, ensure_ascii=False, indent=2))
    return dict(payload)


def load_scheduler_state(self: Any, job_id: str) -> dict[str, Any] | None:
    path = self._trace_dir() / "scheduler_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        return None
    payload = states.get(job_id)
    return dict(payload) if isinstance(payload, dict) else None


def load_all_scheduler_states(self: Any) -> dict[str, Any]:
    """Load all persisted scheduler states across all jobs."""
    path = self._trace_dir() / "scheduler_states.json"
    states = self._read_json_file(path, {})
    if not isinstance(states, dict):
        return {}
    return {job_id: dict(payload) for job_id, payload in states.items() if isinstance(payload, dict)}
