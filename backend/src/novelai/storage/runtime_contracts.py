from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from novelai.infrastructure.http.cache import FetchCacheEntry
from novelai.storage.common import _utc_now_iso

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
_SENSITIVE_KEY_PARTS = ("api_key", "authorization", "cookie", "secret", "token")

# Max age (in days) for runtime translation data before it's eligible for
# automatic cleanup.  Completed/failed translation bundles, chunk outputs,
# chunk attempts, and provider request records older than this threshold
# are purged by :func:`cleanup_expired_runtime_data`.
RUNTIME_DATA_MAX_AGE_DAYS = 14


class StorageFetchCache:
    """FetchService-compatible cache adapter backed by StorageService methods."""

    def __init__(self, storage: Any) -> None:
        self._storage = storage

    def get(self, source_key: str, url: str) -> FetchCacheEntry | None:
        entry = self._storage.read_fetch_cache_entry(source_key, url)
        if entry is None:
            return None
        body_text = entry.get("body_text")
        text = body_text if isinstance(body_text, str) else ""
        return FetchCacheEntry(
            requested_url=str(entry.get("url") or url),
            final_url=str(entry.get("canonical_url") or entry.get("final_url") or url),
            status_code=int(entry.get("status_code") or 0),
            headers={str(key).lower(): str(value) for key, value in dict(entry.get("headers") or {}).items()},
            text=text,
            body=text.encode("utf-8"),
            source_key=str(entry.get("source_key") or source_key),
            fetched_at=str(entry.get("fetched_at") or _utc_now_iso()),
        )

    def set(self, entry: FetchCacheEntry) -> None:
        self._storage.save_fetch_cache_entry(
            {
                "url": entry.requested_url,
                "final_url": entry.final_url,
                "status_code": entry.status_code,
                "headers": entry.headers,
                "body_text": entry.text,
                "source_key": entry.source_key,
                "fetched_at": entry.fetched_at,
            }
        )

    def conditional_headers(self, source_key: str, url: str) -> dict[str, str]:
        return self._storage.fetch_cache_conditional_headers(source_key, url)


def _runtime_dir(self: Any):
    path = self.base_dir / "runtime"
    self._mkdirs(path)
    return path


def _translation_runtime_dir(self: Any):
    path = self._runtime_dir() / "translation"
    self._mkdirs(path)
    return path


def _fetch_cache_dir(self: Any):
    path = self._runtime_dir() / "fetch_cache"
    self._mkdirs(path)
    return path


def _read_json_file(self: Any, path: Any, default: Any) -> Any:
    if not self._path_exists(path):
        return default
    try:
        text = self._read_text(path)
        if not text.strip():
            logger.debug("Empty/whitespace file: %s — returning default.", path.name)
            return default
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Corrupt JSON file: %s — returning default.", path.name)
        return default
    except OSError:
        return default


def _as_dict(value: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        payload = to_dict()
        if isinstance(payload, dict):
            return dict(payload)
    return {}


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_key(*parts: Any) -> str:
    return ":".join(str(part) for part in parts if part is not None)


def _scope_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _chapter_scope_from_payload(payload: dict[str, Any]) -> str:
    explicit = _scope_part(payload.get("chapter_scope"))
    if explicit is not None:
        return explicit
    chapter_ids = _list_strings(payload.get("chapter_ids") or payload.get("chapter_id"))
    return "+".join(chapter_ids) if chapter_ids else "chapter_unknown"


def _run_scope_from_payload(payload: dict[str, Any]) -> str:
    for key in ("translation_run_id", "run_id", "job_id", "activity_id"):
        value = _scope_part(payload.get(key))
        if value is not None:
            return value
    return "run_manual"


def _runtime_scope(payload: dict[str, Any]) -> tuple[str, str]:
    return _run_scope_from_payload(payload), _chapter_scope_from_payload(payload)


def _runtime_record_key(novel_id: str, payload: dict[str, Any], chunk_id: str, *tail: Any) -> str:
    run_scope, chapter_scope = _runtime_scope(payload)
    return _record_key(novel_id, run_scope, chapter_scope, chunk_id, *tail)


def _matches_runtime_scope(item: dict[str, Any], payload: dict[str, Any]) -> bool:
    expected_run = _scope_part(payload.get("translation_run_id") or payload.get("run_id") or payload.get("job_id") or payload.get("activity_id"))
    if expected_run is not None and _run_scope_from_payload(item) != expected_run:
        return False

    requested_chapter_scope = _scope_part(payload.get("chapter_scope"))
    requested_chapter_ids = _list_strings(payload.get("chapter_ids") or payload.get("chapter_id"))
    if requested_chapter_scope is None and not requested_chapter_ids:
        return True

    if requested_chapter_scope is not None:
        return _chapter_scope_from_payload(item) == requested_chapter_scope

    item_chapter_ids = _list_strings(item.get("chapter_ids") or item.get("chapter_id"))
    return item_chapter_ids == requested_chapter_ids


def _list_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, tuple):
        return [str(item) for item in value if item is not None]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered == "headers" or any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                continue
            sanitized[key_text] = _redact_sensitive(item)
        return sanitized
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _read_mapping(self: Any, path: Any) -> dict[str, Any]:
    payload = _read_json_file(self, path, {})
    return payload if isinstance(payload, dict) else {}


def _write_mapping(self: Any, path: Any, payload: dict[str, Any]) -> None:
    self._write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def save_translation_chunks(self: Any, novel_id: str, chunks: list[dict[str, Any] | Any]) -> list[dict[str, Any]]:
    normalized_novel_id = novel_id.strip() if isinstance(novel_id, str) else ""
    if not normalized_novel_id:
        raise ValueError("novel_id is required.")

    path = self._translation_runtime_dir() / "chunks.json"
    records = _read_mapping(self, path)
    now = _utc_now_iso()
    stored: list[dict[str, Any]] = []
    for chunk in chunks:
        payload = _as_dict(chunk)
        chunk_id = str(payload.get("chunk_id") or "").strip()
        if not chunk_id:
            raise ValueError("chunk_id is required.")

        source_text = payload.get("source_text")
        source_text_hash = payload.get("source_text_hash")
        if not isinstance(source_text_hash, str) or not source_text_hash.strip():
            source_text_hash = _hash_text(source_text) if isinstance(source_text, str) else None

        run_scope, chapter_scope = _runtime_scope(payload)
        key = _runtime_record_key(normalized_novel_id, payload, chunk_id)
        existing = records.get(key)
        created_at = existing.get("created_at") if isinstance(existing, dict) else None
        record = {
            **(existing if isinstance(existing, dict) else {}),
            **payload,
            "schema_version": SCHEMA_VERSION,
            "chunk_id": chunk_id,
            "novel_id": normalized_novel_id,
            "chapter_ids": _list_strings(payload.get("chapter_ids") or payload.get("chapter_id")),
            "chapter_scope": chapter_scope,
            "translation_run_id": run_scope,
            "runtime_key": key,
            "paragraph_ids": _list_strings(payload.get("paragraph_ids")),
            "paragraph_hashes": _list_strings(payload.get("paragraph_hashes")),
            "source_text_hash": source_text_hash,
            "char_count": int(payload.get("char_count") or (len(source_text) if isinstance(source_text, str) else 0)),
            "status": str(payload.get("status") or "pending"),
            "attempt_count": int(payload.get("attempt_count") or payload.get("attempt_number") or 0),
            "created_at": str(payload.get("created_at") or created_at or now),
            "updated_at": now,
        }
        records[key] = record
        stored.append(dict(record))

    _write_mapping(self, path, records)
    return stored


def read_translation_chunks(
    self: Any,
    novel_id: str | None = None,
    *,
    status: str | None = None,
    translation_run_id: str | None = None,
    chapter_id: str | None = None,
    chapter_ids: list[str] | tuple[str, ...] | str | None = None,
    chapter_scope: str | None = None,
) -> list[dict[str, Any]]:
    path = self._translation_runtime_dir() / "chunks.json"
    records = _read_mapping(self, path)
    items = [dict(item) for item in records.values() if isinstance(item, dict)]
    if isinstance(novel_id, str) and novel_id.strip():
        items = [item for item in items if item.get("novel_id") == novel_id]
    if isinstance(status, str) and status.strip():
        items = [item for item in items if item.get("status") == status]
    scope_payload = {
        "translation_run_id": translation_run_id,
        "chapter_id": chapter_id,
        "chapter_ids": chapter_ids,
        "chapter_scope": chapter_scope,
    }
    if any(value for value in scope_payload.values()):
        items = [item for item in items if _matches_runtime_scope(item, scope_payload)]
    return items


def update_translation_chunk_status(
    self: Any,
    novel_id: str,
    chunk_id: str,
    status: str,
    **fields: Any,
) -> dict[str, Any]:
    existing = self.read_translation_chunks(
        novel_id,
        translation_run_id=fields.get("translation_run_id"),
        chapter_id=fields.get("chapter_id"),
        chapter_ids=fields.get("chapter_ids"),
        chapter_scope=fields.get("chapter_scope"),
    )
    for record in existing:
        if record.get("chunk_id") == chunk_id:
            updated = {**record, **fields, "status": status}
            return self.save_translation_chunks(novel_id, [updated])[0]
    created = {"chunk_id": chunk_id, **fields, "status": status}
    return self.save_translation_chunks(novel_id, [created])[0]


def save_chunk_attempt_record(self: Any, attempt: dict[str, Any] | Any) -> dict[str, Any]:
    payload = _redact_sensitive(_as_dict(attempt))
    novel_id = str(payload.get("novel_id") or "").strip()
    chunk_id = str(payload.get("chunk_id") or "").strip()
    if not novel_id:
        raise ValueError("novel_id is required.")
    if not chunk_id:
        raise ValueError("chunk_id is required.")

    now = _utc_now_iso()
    try:
        attempt_number = int(payload.get("attempt_number") or 0)
    except (TypeError, ValueError):
        attempt_number = 0
    if attempt_number < 0:
        attempt_number = 0

    path = self._translation_runtime_dir() / "chunk_attempts.json"
    records = _read_mapping(self, path)
    run_scope, chapter_scope = _runtime_scope(payload)
    attempt_id = str(payload.get("attempt_id") or _runtime_record_key(novel_id, payload, chunk_id, attempt_number)).strip()
    existing = records.get(attempt_id)
    created_at = existing.get("created_at") if isinstance(existing, dict) else None
    record = {
        **(existing if isinstance(existing, dict) else {}),
        **payload,
        "schema_version": SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "chunk_id": chunk_id,
        "novel_id": novel_id,
        "chapter_ids": _list_strings(payload.get("chapter_ids") or payload.get("chapter_id")),
        "chapter_scope": chapter_scope,
        "translation_run_id": run_scope,
        "runtime_key": attempt_id,
        "paragraph_ids": _list_strings(payload.get("paragraph_ids")),
        "attempt_number": attempt_number,
        "status": str(payload.get("status") or "pending"),
        "created_at": str(payload.get("created_at") or created_at or now),
        "updated_at": now,
    }
    records[attempt_id] = record
    _write_mapping(self, path, records)
    return dict(record)


def list_chunk_attempt_records(
    self: Any,
    *,
    novel_id: str | None = None,
    chunk_id: str | None = None,
    status: str | None = None,
    translation_run_id: str | None = None,
    chapter_id: str | None = None,
    chapter_ids: list[str] | tuple[str, ...] | str | None = None,
    chapter_scope: str | None = None,
) -> list[dict[str, Any]]:
    path = self._translation_runtime_dir() / "chunk_attempts.json"
    records = _read_mapping(self, path)
    items = [dict(item) for item in records.values() if isinstance(item, dict)]
    for key, value in (("novel_id", novel_id), ("chunk_id", chunk_id), ("status", status)):
        if isinstance(value, str) and value.strip():
            items = [item for item in items if item.get(key) == value]
    scope_payload = {
        "translation_run_id": translation_run_id,
        "chapter_id": chapter_id,
        "chapter_ids": chapter_ids,
        "chapter_scope": chapter_scope,
    }
    if any(value for value in scope_payload.values()):
        items = [item for item in items if _matches_runtime_scope(item, scope_payload)]
    return items


def save_translation_bundle(self: Any, bundle: dict[str, Any] | Any) -> dict[str, Any]:
    payload = _as_dict(bundle)
    novel_id = str(payload.get("novel_id") or "").strip()
    bundle_id = str(payload.get("bundle_id") or "").strip()
    if not novel_id:
        raise ValueError("novel_id is required.")
    if not bundle_id:
        raise ValueError("bundle_id is required.")

    path = self._translation_runtime_dir() / "bundles.json"
    records = _read_mapping(self, path)
    key = _record_key(novel_id, bundle_id)
    existing = records.get(key)
    now = _utc_now_iso()
    record = {
        **(existing if isinstance(existing, dict) else {}),
        **payload,
        "schema_version": SCHEMA_VERSION,
        "bundle_id": bundle_id,
        "novel_id": novel_id,
        "chunk_ids": _list_strings(payload.get("chunk_ids")),
        "chapter_ids": _list_strings(payload.get("chapter_ids")),
        "paragraph_ids": _list_strings(payload.get("paragraph_ids")),
        "status": str(payload.get("status") or "pending"),
        "created_at": str(payload.get("created_at") or (existing.get("created_at") if isinstance(existing, dict) else None) or now),
        "updated_at": now,
    }
    records[key] = record
    _write_mapping(self, path, records)
    return dict(record)


def read_translation_bundle(self: Any, novel_id: str, bundle_id: str) -> dict[str, Any] | None:
    path = self._translation_runtime_dir() / "bundles.json"
    record = _read_mapping(self, path).get(_record_key(novel_id, bundle_id))
    return dict(record) if isinstance(record, dict) else None


def delete_translation_bundle(self: Any, novel_id: str, bundle_id: str) -> bool:
    path = self._translation_runtime_dir() / "bundles.json"
    records = _read_mapping(self, path)
    key = _record_key(novel_id, bundle_id)
    if key not in records:
        return False
    del records[key]
    _write_mapping(self, path, records)
    return True


def save_translation_output(self: Any, output: dict[str, Any] | Any) -> dict[str, Any]:
    payload = _as_dict(output)
    novel_id = str(payload.get("novel_id") or "").strip()
    chunk_id = str(payload.get("chunk_id") or "").strip()
    if not novel_id:
        raise ValueError("novel_id is required.")
    if not chunk_id:
        raise ValueError("chunk_id is required.")

    now = _utc_now_iso()
    output_id = str(payload.get("output_id") or f"{chunk_id}:{now}").strip()
    path = self._translation_runtime_dir() / "outputs.json"
    records = _read_mapping(self, path)
    run_scope, chapter_scope = _runtime_scope(payload)
    key = _runtime_record_key(novel_id, payload, chunk_id, output_id)
    record = {
        **payload,
        "schema_version": SCHEMA_VERSION,
        "output_id": output_id,
        "chunk_id": chunk_id,
        "novel_id": novel_id,
        "chapter_ids": _list_strings(payload.get("chapter_ids") or payload.get("chapter_id")),
        "chapter_scope": chapter_scope,
        "translation_run_id": run_scope,
        "runtime_key": key,
        "paragraph_ids": _list_strings(payload.get("paragraph_ids")),
        "translated_text": str(payload.get("translated_text") or ""),
        "structured_paragraph_map": payload.get("structured_paragraph_map") or [],
        "qa_warnings": _list_strings(payload.get("qa_warnings")),
        "qa_errors": _list_strings(payload.get("qa_errors")),
        "output_hash": payload.get("output_hash") or _hash_text(str(payload.get("translated_text") or "")),
        "created_at": str(payload.get("created_at") or now),
        "updated_at": now,
    }
    records[key] = record
    _write_mapping(self, path, records)
    return dict(record)


def read_translation_output(
    self: Any,
    novel_id: str,
    *,
    output_id: str | None = None,
    chunk_id: str | None = None,
    translation_run_id: str | None = None,
    chapter_id: str | None = None,
    chapter_ids: list[str] | tuple[str, ...] | str | None = None,
    chapter_scope: str | None = None,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    path = self._translation_runtime_dir() / "outputs.json"
    records = _read_mapping(self, path)
    items = [
        dict(record)
        for record in records.values()
        if isinstance(record, dict) and record.get("novel_id") == novel_id
    ]
    scope_payload = {
        "translation_run_id": translation_run_id,
        "chapter_id": chapter_id,
        "chapter_ids": chapter_ids,
        "chapter_scope": chapter_scope,
    }
    if any(value for value in scope_payload.values()):
        items = [item for item in items if _matches_runtime_scope(item, scope_payload)]
    if isinstance(output_id, str) and output_id.strip():
        for item in items:
            if item.get("output_id") == output_id:
                return item
        return None
    if isinstance(chunk_id, str) and chunk_id.strip():
        items = [item for item in items if item.get("chunk_id") == chunk_id]
    return items


def save_provider_request_record(self: Any, record: dict[str, Any] | Any) -> dict[str, Any]:
    payload = _redact_sensitive(_as_dict(record))
    if not isinstance(payload, dict):
        payload = {}
    path = self._runtime_dir() / "provider_requests.json"
    records = _read_json_file(self, path, [])
    if not isinstance(records, list):
        records = []
    now = _utc_now_iso()
    request_id = str(payload.get("request_id") or f"provider_request_{len(records) + 1:06d}")
    stored = {
        **payload,
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "timestamp": str(payload.get("timestamp") or now),
    }
    records.append(stored)
    self._write_text(path, json.dumps(records, ensure_ascii=False, indent=2))
    return dict(stored)


def list_provider_request_records(
    self: Any,
    *,
    novel_id: str | None = None,
    chunk_id: str | None = None,
    provider_key: str | None = None,
    success: bool | None = None,
) -> list[dict[str, Any]]:
    path = self._runtime_dir() / "provider_requests.json"
    records = _read_json_file(self, path, [])
    if not isinstance(records, list):
        return []
    items = [dict(item) for item in records if isinstance(item, dict)]
    for key, value in (("novel_id", novel_id), ("chunk_id", chunk_id), ("provider_key", provider_key)):
        if isinstance(value, str) and value.strip():
            items = [item for item in items if item.get(key) == value]
    if success is not None:
        items = [item for item in items if bool(item.get("success")) is success]
    return items


def cleanup_expired_runtime_data(self: Any, *, max_age_days: int | None = None) -> int:
    """Remove runtime translation data older than *max_age_days*.

    Scans chunks.json, chunk_attempts.json, bundles.json, outputs.json,
    and provider_requests.json -- purging entries whose ``updated_at`` /
    ``created_at`` / ``timestamp`` exceeds the threshold.  Returns the
    total count of purged entries.

    This is the main lifecycle-hardening entry-point called by the
    admin maintenance route or a periodic scheduler.
    """
    max_age_days = max_age_days or RUNTIME_DATA_MAX_AGE_DAYS
    cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
    total = 0

    # --- Mapping-based files (chunks, chunk_attempts, bundles, outputs) ---
    for filename in ("chunks.json", "chunk_attempts.json", "bundles.json", "outputs.json"):
        path = self._translation_runtime_dir() / filename
        records = _read_mapping(self, path)
        if not records:
            continue
        kept: dict[str, Any] = {}
        for key, record in records.items():
            if not isinstance(record, dict):
                continue
            updated = _parse_timestamp(record.get("updated_at") or record.get("created_at"))
            if updated is not None and updated < cutoff:
                total += 1
                continue
            kept[key] = record
        if len(kept) != len(records):
            _write_mapping(self, path, kept)

    # --- List-based file (provider_requests) ---
    req_path = self._runtime_dir() / "provider_requests.json"
    req_records = _read_json_file(self, req_path, [])
    if isinstance(req_records, list) and req_records:
        kept_reqs = [
            item for item in req_records
            if isinstance(item, dict)
            and (
                (ts := _parse_timestamp(item.get("timestamp"))) is None
                or ts >= cutoff
            )
        ]
        if len(kept_reqs) != len(req_records):
            total += len(req_records) - len(kept_reqs)
            self._write_text(req_path, json.dumps(kept_reqs, ensure_ascii=False, indent=2))

    if total > 0:
        logger.info("Cleanup: purged %d expired runtime records (max_age=%dd).", total, max_age_days)
    return total


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                parsed = datetime.strptime(text.rstrip("Z"), fmt)
                return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed
            except ValueError:
                continue
        return None
    except (ValueError, TypeError, OverflowError):
        return None


def save_fetch_cache_entry(self: Any, entry: dict[str, Any] | Any) -> dict[str, Any]:
    payload = _as_dict(entry)
    url = str(payload.get("url") or payload.get("requested_url") or "").strip()
    source_key = str(payload.get("source_key") or "").strip()
    if not url:
        raise ValueError("url is required.")
    if not source_key:
        raise ValueError("source_key is required.")

    body_text = payload.get("body_text")
    if body_text is None:
        body_text = payload.get("text")
    body_hash = payload.get("body_hash")
    if not isinstance(body_hash, str) or not body_hash.strip():
        body_hash = _hash_text(body_text) if isinstance(body_text, str) else None

    headers = payload.get("headers")
    headers_payload = {str(key).lower(): str(value) for key, value in headers.items()} if isinstance(headers, dict) else {}
    path = self._fetch_cache_dir() / "index.json"
    records = _read_mapping(self, path)
    record = {
        **payload,
        "schema_version": SCHEMA_VERSION,
        "url": url,
        "canonical_url": str(payload.get("canonical_url") or payload.get("final_url") or url),
        "source_key": source_key,
        "status_code": int(payload.get("status_code") or 0),
        "headers": headers_payload,
        "etag": payload.get("etag") or headers_payload.get("etag"),
        "last_modified": payload.get("last_modified") or headers_payload.get("last-modified"),
        "fetched_at": str(payload.get("fetched_at") or _utc_now_iso()),
        "body_hash": body_hash,
        "body_text": body_text,
        "from_cache": bool(payload.get("from_cache", False)),
    }
    records[_record_key(source_key, url)] = record
    _write_mapping(self, path, records)
    return dict(record)


def read_fetch_cache_entry(self: Any, source_key: str, url: str) -> dict[str, Any] | None:
    path = self._fetch_cache_dir() / "index.json"
    record = _read_mapping(self, path).get(_record_key(source_key, url))
    return dict(record) if isinstance(record, dict) else None


def fetch_cache_conditional_headers(self: Any, source_key: str, url: str) -> dict[str, str]:
    entry = self.read_fetch_cache_entry(source_key, url)
    if entry is None:
        return {}
    headers: dict[str, str] = {}
    etag = entry.get("etag")
    if isinstance(etag, str) and etag.strip():
        headers["If-None-Match"] = etag
    last_modified = entry.get("last_modified")
    if isinstance(last_modified, str) and last_modified.strip():
        headers["If-Modified-Since"] = last_modified
    return headers
