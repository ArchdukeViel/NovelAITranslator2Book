from __future__ import annotations

import re
from pathlib import Path


FRONTEND_DIR = Path("frontend")
API_CLIENT = FRONTEND_DIR / "lib" / "api.ts"
PUBLIC_API_CLIENT = FRONTEND_DIR / "lib" / "public-api.ts"
APPROVED_API_CLIENTS = {
    API_CLIENT,
    PUBLIC_API_CLIENT,
}
API_TYPES = FRONTEND_DIR / "lib" / "api-types.ts"


def test_frontend_fetch_calls_are_centralized_in_api_client() -> None:
    offenders: list[Path] = []
    for path in FRONTEND_DIR.rglob("*"):
        if any(part in {"node_modules", ".next"} for part in path.parts):
            continue
        if path.suffix not in {".ts", ".tsx"}:
            continue
        # Frontend intentionally has separate admin/shared and public-reader API clients.
        if path in APPROVED_API_CLIENTS:
            continue
        text = path.read_text(encoding="utf-8")
        if re.search(r"\bfetch\s*\(", text) or re.search(r"\baxios\s*\(", text):
            offenders.append(path)

    assert offenders == []


def test_frontend_api_client_exposes_error_and_progress_contracts() -> None:
    text = API_CLIENT.read_text(encoding="utf-8")
    types_text = API_TYPES.read_text(encoding="utf-8")

    assert 'export type * from "@/lib/api-types"' in text
    assert "export type ApiErrorPayload" in types_text
    assert "trace_id?: string | null" in text
    assert "trace_id?: string | null" in types_text
    assert "export function describeApiError" in text
    assert "export type JobProgress" in types_text
    assert "paused_reason?: string | null" in types_text
    assert "resume_after?: string | null" in types_text
    assert "model_states?: ModelState[]" in types_text
    assert "provider_key?: string" in types_text
    assert "provider_model?: string" in types_text
    assert "last_job_id?: string | null" in types_text
    assert "request_id?: string" in types_text
    assert "source_url?: string | null" in types_text
    assert "provider_key?: string | null" in types_text
    assert "provider_model?: string | null" in types_text
    assert "export function activityProgress" in text
    assert "export function activityProgressLabel" in text
    assert "/novels/activity" in text
    assert "/novels/admin/worker" in text


def test_provider_credential_routes_are_not_bolted_onto_frontend_without_auth_boundary() -> None:
    text = API_CLIENT.read_text(encoding="utf-8")

    assert "/api/me/provider-credentials" not in text
    assert "/provider-credentials" not in text
