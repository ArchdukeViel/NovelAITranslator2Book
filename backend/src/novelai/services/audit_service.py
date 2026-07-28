"""Audit log service for owner accountability (DEBT-054).

Writes immutable rows to ``audit_logs`` for sensitive owner actions. Reads
return redacted, paginated views. Public API responses never include raw
secrets, raw paths, or raw error stack traces.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from novelai.db.models.system import AuditLog

logger = logging.getLogger(__name__)

# Keys whose values are redacted recursively in metadata_json responses.
_REDACTED_KEYS = frozenset(
    {
        "api_key",
        "apiKey",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "client_secret",
        "authorization",
        "auth",
        "jwt",
        "session_token",
        "csrf_token",
        "private_key",
        "encryption_key",
        "db_url",
        "database_url",
        "smtp_password",
        "s3_secret",
        "s3_access_key",
        "r2_secret",
        "r2_access_key",
        "github_token",
        "github_pat",
        "signed_url",
        "presigned_url",
        "download_url",
        "upload_url",
        "prompt",
        "system_prompt",
        "user_prompt",
        "source_text",
        "translated_text",
        "chapter_text",
        "raw_text",
        "glossary_definition",
        "private_definition",
        "filesystem_path",
        "abs_path",
        "absolute_path",
        "storage_key_path",
    }
)

# Substring patterns whose value is replaced with "***REDACTED***".
_REDACTED_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[A-Za-z0-9_\-]{16,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[bpars]-[A-Za-z0-9\-]{10,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}", re.IGNORECASE),
    # Signed S3/R2 URLs
    re.compile(r"https?://[^\s]*\?[^\s]*(?:X-Amz-Signature|Signature=|X-Goog-Signature=)[^\s]+", re.IGNORECASE),
    # Provider-style prompts (rough heuristic for long system-prompt dumps)
    re.compile(r"(?ms)You are a translator[^\"]{0,500}"),
    # Absolute filesystem paths leaked into free-form strings
    re.compile(r"(?:/var/|/etc/|C:\\|/home/|/Users/)[A-Za-z0-9_./\\-]{8,}"),
)

# Canonical safe enumerations. Anything outside is normalised to "unknown" so
# the viewer never displays arbitrary attacker-controlled values verbatim.
_ALLOWED_STATUSES = frozenset({"succeeded", "failed", "denied", "partial"})
_ALLOWED_SEVERITIES = frozenset({"info", "warning", "critical"})

# Allowlisted metadata keys that may be promoted into canonical columns when
# not passed explicitly. No secrets, no payloads.
_METADATA_STATUS_KEYS = ("status", "audit_status", "outcome")
_METADATA_SEVERITY_KEYS = ("severity", "level")
_METADATA_REQUEST_ID_KEYS = ("request_id", "requestId", "x_request_id")
_METADATA_CORRELATION_ID_KEYS = ("correlation_id", "correlationId", "trace_id")


def _normalize_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if candidate in _ALLOWED_STATUSES:
        return candidate
    if candidate in {"success", "ok", "completed"}:
        return "succeeded"
    if candidate in {"error", "errored", "failure"}:
        return "failed"
    return "unknown"


def _normalize_severity(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if not candidate:
        return None
    if candidate in _ALLOWED_SEVERITIES:
        return candidate
    return "unknown"


def _coerce_id(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned[:128] if cleaned else None
    if isinstance(value, (int, float)):
        return str(value)[:128]
    return None


def _resolve_canonical(
    *,
    explicit: Any,
    metadata: dict[str, Any] | None,
    keys: tuple[str, ...],
    normaliser: Any,
) -> Any:
    if explicit is not None:
        return normaliser(explicit)
    if metadata:
        for key in keys:
            if key in metadata:
                value = normaliser(metadata.get(key))
                if value is not None:
                    return value
    return None


def _pop_metadata_keys(
    metadata: dict[str, Any] | None,
    keys: tuple[str, ...],
) -> None:
    """Remove allowlisted metadata keys once promoted to canonical columns."""
    if not metadata:
        return
    for key in keys:
        metadata.pop(key, None)


def _redact_value(key: str, value: Any) -> Any:
    if isinstance(key, str) and key.lower() in _REDACTED_KEYS:
        return "***REDACTED***"
    if isinstance(value, str):
        for pattern in _REDACTED_VALUE_PATTERNS:
            if pattern.search(value):
                return pattern.sub("***REDACTED***", value)
    return value


def _redact(obj: Any) -> Any:
    """Recursively redact known secret-shaped keys/values."""
    if isinstance(obj, dict):
        return {str(k): _redact_value(str(k), _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(item) for item in obj]
    return obj


def _parse_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        loaded = json.loads(metadata_json)
    except (TypeError, ValueError):
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(k): v for k, v in loaded.items()}


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    return str(value)


def _safe_before_after(metadata: dict[str, Any]) -> dict[str, Any] | None:
    """Return a safe {before, after} view derived from the canonical metadata
    storage. Already-redacted metadata passes through; we additionally scrub
    any remaining secret-shaped keys so the viewer can render a before/after
    diff without leaking credentials or private payloads."""
    if not isinstance(metadata, dict):
        return None
    before = metadata.get("before")
    after = metadata.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    return {
        "before": _redact(before),
        "after": _redact(after),
    }


class AuditService:
    """Service for writing and listing audit logs for owner accountability."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        action: str,
        actor_user_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        *,
        status: str | None = None,
        severity: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditLog:
        """Write an immutable audit log entry to the database.

        Optional canonical columns (``status``, ``severity``, ``request_id``,
        ``correlation_id``) fall back to allowlisted metadata keys so existing
        producers that pass these via ``metadata`` keep working. Values are
        normalised against safe enumerations; unknown values collapse to
        ``"unknown"`` rather than echoing arbitrary strings.
        """
        metadata_dict = dict(metadata) if metadata else None
        resolved_status = _resolve_canonical(
            explicit=status,
            metadata=metadata_dict,
            keys=_METADATA_STATUS_KEYS,
            normaliser=_normalize_status,
        )
        resolved_severity = _resolve_canonical(
            explicit=severity,
            metadata=metadata_dict,
            keys=_METADATA_SEVERITY_KEYS,
            normaliser=_normalize_severity,
        )
        resolved_request_id = _resolve_canonical(
            explicit=request_id,
            metadata=metadata_dict,
            keys=_METADATA_REQUEST_ID_KEYS,
            normaliser=_coerce_id,
        )
        resolved_correlation_id = _resolve_canonical(
            explicit=correlation_id,
            metadata=metadata_dict,
            keys=_METADATA_CORRELATION_ID_KEYS,
            normaliser=_coerce_id,
        )

        # Strip promoted keys so they are not duplicated in metadata_json.
        _pop_metadata_keys(metadata_dict, _METADATA_STATUS_KEYS)
        _pop_metadata_keys(metadata_dict, _METADATA_SEVERITY_KEYS)
        _pop_metadata_keys(metadata_dict, _METADATA_REQUEST_ID_KEYS)
        _pop_metadata_keys(metadata_dict, _METADATA_CORRELATION_ID_KEYS)

        safe_metadata = _redact(metadata_dict) if metadata_dict else None
        metadata_str = json.dumps(safe_metadata, ensure_ascii=False) if safe_metadata else None
        log_entry = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            status=resolved_status,
            severity=resolved_severity,
            request_id=resolved_request_id,
            correlation_id=resolved_correlation_id,
            metadata_json=metadata_str,
            created_at=datetime.now(UTC),
        )
        self.db.add(log_entry)
        self.db.flush()
        logger.info(
            "AUDIT LOG: action=%s actor=%s target=%s/%s status=%s severity=%s",
            action,
            actor_user_id,
            target_type,
            target_id,
            resolved_status,
            resolved_severity,
        )
        return log_entry

    def get_log(self, audit_id: int) -> AuditLog | None:
        return self.db.get(AuditLog, audit_id)

    def list_logs(
        self,
        *,
        action: str | None = None,
        actor_user_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        request_id: str | None = None,
        correlation_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """List audit logs with filtering and pagination."""
        q = self.db.query(AuditLog)
        if action:
            q = q.filter(AuditLog.action == action)
        if actor_user_id is not None:
            q = q.filter(AuditLog.actor_user_id == actor_user_id)
        if target_type:
            q = q.filter(AuditLog.target_type == target_type)
        if target_id:
            q = q.filter(AuditLog.target_id == str(target_id))
        normalized_status = _normalize_status(status) if status else None
        if normalized_status:
            q = q.filter(AuditLog.status == normalized_status)
        normalized_severity = _normalize_severity(severity) if severity else None
        if normalized_severity:
            q = q.filter(AuditLog.severity == normalized_severity)
        if request_id:
            q = q.filter(AuditLog.request_id == request_id)
        if correlation_id:
            q = q.filter(AuditLog.correlation_id == correlation_id)
        if date_from is not None:
            q = q.filter(AuditLog.created_at >= date_from)
        if date_to is not None:
            q = q.filter(AuditLog.created_at <= date_to)

        total = q.count()
        rows = q.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
        return list(rows), total

    def to_summary(self, log: AuditLog) -> dict[str, Any]:
        """Redacted, public-safe summary for list responses."""
        return {
            "id": log.id,
            "created_at": _iso(log.created_at),
            "actor_user_id": log.actor_user_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "status": log.status,
            "severity": log.severity,
            "request_id": log.request_id,
            "correlation_id": log.correlation_id,
            "summary": _summarize_metadata(_parse_metadata(log.metadata_json)),
        }

    def to_detail(self, log: AuditLog) -> dict[str, Any]:
        """Redacted, public-safe detail for the single-event endpoint."""
        metadata = _redact(_parse_metadata(log.metadata_json))
        changes = _safe_before_after(metadata)
        return {
            "id": log.id,
            "created_at": _iso(log.created_at),
            "actor_user_id": log.actor_user_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "status": log.status,
            "severity": log.severity,
            "request_id": log.request_id,
            "correlation_id": log.correlation_id,
            "metadata": metadata,
            "changes": changes,
        }


def _summarize_metadata(metadata: dict[str, Any]) -> str:
    """Build a single-line human-readable summary from the metadata dict."""
    if not metadata:
        return ""
    parts: list[str] = []
    for key, value in metadata.items():
        if key in {"actor", "actor_user_id", "user_id"}:
            continue
        if isinstance(value, (str, int, float, bool)):
            parts.append(f"{key}={value}")
        if len(parts) >= 3:
            break
    return "; ".join(parts)
