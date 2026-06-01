from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from novelai.config.settings import settings
from novelai.core.platform import NovelRequestStatus
from novelai.utils import atomic_write


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class NovelRequestService:
    """Durable request/vote/source-candidate store for the reader platform."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = (base_dir or settings.DATA_DIR).resolve()
        self.requests_dir = self.base_dir / "requests"
        self.requests_dir.mkdir(parents=True, exist_ok=True)
        self.requests_file = self.requests_dir / "novel_requests.json"

    def _load_requests(self) -> list[dict[str, Any]]:
        if not self.requests_file.exists():
            return []
        try:
            data = json.loads(self.requests_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
        if not isinstance(data, list):
            return []
        return [dict(item) for item in data if isinstance(item, dict)]

    def _persist_requests(self, requests: list[dict[str, Any]]) -> None:
        atomic_write(self.requests_file, json.dumps(requests, ensure_ascii=False, indent=2))

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    @staticmethod
    def _normalize_status(status: str | NovelRequestStatus | None) -> str | None:
        if isinstance(status, NovelRequestStatus):
            return status.value
        if isinstance(status, str) and status in {item.value for item in NovelRequestStatus}:
            return status
        return None

    @staticmethod
    def _candidate(
        *,
        source_key: str | None,
        url: str | None,
        submitted_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_url = url.strip() if isinstance(url, str) and url.strip() else None
        normalized_source = source_key.strip() if isinstance(source_key, str) and source_key.strip() else None
        if normalized_url is None and normalized_source is None:
            return None
        return {
            "id": f"src_{uuid4().hex}",
            "source_key": normalized_source,
            "url": normalized_url,
            "submitted_by": submitted_by.strip() if isinstance(submitted_by, str) and submitted_by.strip() else None,
            "status": NovelRequestStatus.PENDING.value,
            "created_at": _utc_now_iso(),
            "reviewed_at": None,
            "reviewed_by": None,
            "notes": notes.strip() if isinstance(notes, str) and notes.strip() else None,
        }

    def create_request(
        self,
        *,
        title: str,
        source_key: str | None = None,
        source_url: str | None = None,
        requested_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        normalized_title = title.strip() if isinstance(title, str) else ""
        if not normalized_title:
            raise ValueError("title is required.")

        candidate = self._candidate(
            source_key=source_key,
            url=source_url,
            submitted_by=requested_by,
            notes=notes,
        )
        request: dict[str, Any] = {
            "id": self._new_id("req"),
            "title": normalized_title,
            "requested_by": requested_by.strip() if isinstance(requested_by, str) and requested_by.strip() else None,
            "status": NovelRequestStatus.PENDING.value,
            "created_at": _utc_now_iso(),
            "reviewed_at": None,
            "reviewed_by": None,
            "vote_count": 0,
            "voters": [],
            "notes": notes.strip() if isinstance(notes, str) and notes.strip() else None,
            "source_candidates": [candidate] if candidate is not None else [],
        }
        requests = self._load_requests()
        requests.append(request)
        self._persist_requests(requests)
        return dict(request)

    def list_requests(
        self,
        *,
        status: str | NovelRequestStatus | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_status = self._normalize_status(status)
        if status is not None and normalized_status is None:
            raise ValueError(f"Unsupported request status: {status}")

        requests = self._load_requests()
        if normalized_status is not None:
            requests = [request for request in requests if request.get("status") == normalized_status]
        requests.sort(key=lambda item: (-int(item.get("vote_count", 0) or 0), str(item.get("created_at") or "")))
        if limit is not None:
            requests = requests[: max(0, int(limit))]
        return [dict(request) for request in requests]

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        for request in self._load_requests():
            if request.get("id") == request_id:
                return dict(request)
        return None

    def vote_request(self, request_id: str, *, voter: str | None = None) -> dict[str, Any] | None:
        requests = self._load_requests()
        for index, request in enumerate(requests):
            if request.get("id") != request_id:
                continue
            updated = dict(request)
            voters = [str(item) for item in updated.get("voters", []) if isinstance(item, str)]
            normalized_voter = voter.strip() if isinstance(voter, str) and voter.strip() else None
            if normalized_voter is not None:
                if normalized_voter not in voters:
                    voters.append(normalized_voter)
                    updated["vote_count"] = int(updated.get("vote_count", 0) or 0) + 1
            else:
                updated["vote_count"] = int(updated.get("vote_count", 0) or 0) + 1
            updated["voters"] = voters
            requests[index] = updated
            self._persist_requests(requests)
            return dict(updated)
        return None

    def update_request_status(
        self,
        request_id: str,
        status: str | NovelRequestStatus,
        *,
        reviewed_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        normalized_status = self._normalize_status(status)
        if normalized_status is None:
            raise ValueError(f"Unsupported request status: {status}")

        requests = self._load_requests()
        for index, request in enumerate(requests):
            if request.get("id") != request_id:
                continue
            updated = dict(request)
            updated["status"] = normalized_status
            updated["reviewed_at"] = _utc_now_iso()
            if isinstance(reviewed_by, str) and reviewed_by.strip():
                updated["reviewed_by"] = reviewed_by.strip()
            if isinstance(notes, str):
                updated["notes"] = notes.strip() or None
            requests[index] = updated
            self._persist_requests(requests)
            return dict(updated)
        return None

    def add_source_candidate(
        self,
        request_id: str,
        *,
        source_key: str | None,
        source_url: str | None,
        submitted_by: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any] | None:
        candidate = self._candidate(
            source_key=source_key,
            url=source_url,
            submitted_by=submitted_by,
            notes=notes,
        )
        if candidate is None:
            raise ValueError("source_key or source_url is required.")

        requests = self._load_requests()
        for index, request in enumerate(requests):
            if request.get("id") != request_id:
                continue
            updated = dict(request)
            candidates = [dict(item) for item in updated.get("source_candidates", []) if isinstance(item, dict)]
            candidates.append(candidate)
            updated["source_candidates"] = candidates
            requests[index] = updated
            self._persist_requests(requests)
            return dict(candidate)
        return None
