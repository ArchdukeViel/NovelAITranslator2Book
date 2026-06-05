from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "password",
    "secret",
    "session",
    "token",
)
_HEADER_SECRET_RE = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie)\s*[:=]\s*([^\r\n;,]+)"
)
_KEY_VALUE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|apikey|secret|token|password|admin[_-]?token)\s*[:=]\s*([^\s,;&]+)"
)
_JSON_SECRET_RE = re.compile(
    r'(?i)("(?:api[_-]?key|apikey|authorization|cookie|secret|token|password|admin[_-]?token)"\s*:\s*")([^"]*)(")'
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


def redact_secret_text(text: Any) -> str:
    """Return text with common secret-bearing patterns redacted."""

    value = str(text)
    value = _JSON_SECRET_RE.sub(lambda match: f"{match.group(1)}{_REDACTED}{match.group(3)}", value)
    value = _HEADER_SECRET_RE.sub(lambda match: f"{match.group(1)}: {_REDACTED}", value)
    value = _KEY_VALUE_SECRET_RE.sub(lambda match: f"{match.group(1)}={_REDACTED}", value)
    return _BEARER_RE.sub(f"Bearer {_REDACTED}", value)


def redact_sensitive(value: Any) -> Any:
    """Recursively redact secret-like values from public payloads and logs."""

    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if any(part in lowered for part in _SENSITIVE_KEY_PARTS):
                sanitized[key_text] = _REDACTED
            else:
                sanitized[key_text] = redact_sensitive(item)
        return sanitized
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    if isinstance(value, str):
        return redact_secret_text(value)
    return value


def _fully_unquote(value: str) -> str:
    decoded = value
    for _ in range(3):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return decoded


def validate_storage_identifier(value: str, field_name: str = "identifier") -> str:
    """Reject path-like identifiers before they are used as file or folder names."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    candidate = _fully_unquote(value.strip())
    if not candidate:
        raise ValueError(f"{field_name} must not be empty.")
    normalized = candidate.replace("\\", "/")
    if "\x00" in candidate:
        raise ValueError(f"{field_name} must not contain null bytes.")
    if normalized.startswith("//") or candidate.startswith("\\\\"):
        raise ValueError(f"{field_name} must not be a UNC path.")
    if _WINDOWS_DRIVE_RE.match(candidate):
        raise ValueError(f"{field_name} must not be an absolute path.")
    if Path(candidate).is_absolute() or normalized.startswith("/"):
        raise ValueError(f"{field_name} must not be an absolute path.")
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValueError(f"{field_name} must not contain path traversal.")
    if len(parts) > 1:
        raise ValueError(f"{field_name} must not contain path separators.")
    return candidate


def safe_child_path(root: Path, relative_path: str | Path) -> Path:
    """Resolve a child path and ensure it remains within root."""

    root_resolved = root.resolve()
    raw = str(relative_path)
    decoded = _fully_unquote(raw.strip())
    if not decoded:
        raise ValueError("relative path must not be empty.")
    if "\x00" in decoded:
        raise ValueError("relative path must not contain null bytes.")
    if decoded.startswith("\\\\") or decoded.replace("\\", "/").startswith("//"):
        raise ValueError("relative path must not be a UNC path.")
    if _WINDOWS_DRIVE_RE.match(decoded) or Path(decoded).is_absolute():
        raise ValueError("relative path must not be absolute.")
    candidate = (root_resolved / Path(decoded)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("relative path escapes storage root.") from exc
    return candidate
