from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from novelai.config.settings import settings
import logging
from novelai.runtime.container import container
from novelai.services.job_queue_service import JobQueueService
from novelai.services.job_runner_service import BackgroundJobRunner
from novelai.services.job_worker_service import JobWorkerService
from novelai.services.novel_request_service import NovelRequestService
from novelai.services.novel_orchestration_service import NovelOrchestrationService
from novelai.services.storage_service import StorageService
from novelai.inputs.registry import available_input_adapters
from novelai.sources.registry import available_sources, detect_source
from novelai.utils.rate_limiter import get_default_rate_limiter

router = APIRouter()

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Reject requests when WEB_API_KEY is set and no valid token is provided."""
    expected = settings.WEB_API_KEY
    if expected is None:
        return  # auth disabled
    # Support multiple API keys separated by commas in the configured secret.
    expected_value = expected.get_secret_value()
    allowed = [v.strip() for v in expected_value.split(",") if v.strip()]
    supplied = credentials.credentials if credentials is not None else None
    if supplied is None or supplied not in allowed:
        client_ip = None
        try:
            # request not available here; best-effort to log from credentials
            client_ip = "unknown"
        except Exception:
            client_ip = "unknown"
        logging.getLogger(__name__).warning(
            "Failed web API auth attempt from %s", client_ip
        )
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Simple in-process rate limiter (per-client IP, per-endpoint)
# ---------------------------------------------------------------------------

_RATE_WINDOW = 60  # seconds (used to initialize default limiter)
_RATE_LIMITS: dict[str, int] = {
    "scrape": 5,
    "translate": 5,
    "export": 10,
    "edit": 20,
    "delete": 10,
}


_hits: dict[str, list[float]] = defaultdict(list)


# default in-process limiter (backend selected from settings)
# pass the module-level `_hits` so tests can patch it with `unittest.mock.patch`
_DEFAULT_LIMITER = get_default_rate_limiter(
    backend=settings.WEB_RATE_LIMITER_BACKEND,
    limits=_RATE_LIMITS,
    window_seconds=_RATE_WINDOW,
    hits_storage=_hits,
)


def _rate_limit(request: Request, action: str) -> None:
    limiter = _DEFAULT_LIMITER
    try:
        client = request.client.host if request.client else "unknown"
    except Exception:
        client = "unknown"
    allowed = limiter.hit(client, action)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def get_storage() -> StorageService:
    """FastAPI dependency for storage service (uses container singleton)."""
    return container.storage


def get_orchestrator() -> NovelOrchestrationService:
    return container.orchestrator


def get_jobs() -> JobQueueService:
    return container.jobs


def get_job_worker() -> JobWorkerService:
    return container.job_worker


def get_job_runner() -> BackgroundJobRunner:
    return container.job_runner


def get_requests() -> NovelRequestService:
    return container.requests


def _metadata_chapters(meta: dict[str, Any]) -> list[dict[str, Any]]:
    chapters = meta.get("chapters")
    return [chapter for chapter in chapters if isinstance(chapter, dict)] if isinstance(chapters, list) else []


def _reader_title(meta: dict[str, Any]) -> str | None:
    title = meta.get("translated_title") or meta.get("title")
    return title if isinstance(title, str) else None


def _reader_author(meta: dict[str, Any]) -> str | None:
    author = meta.get("translated_author") or meta.get("author")
    return author if isinstance(author, str) else None


_ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Novel AI Admin</title>
  <style>
    :root { color-scheme: light dark; font-family: Inter, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: Canvas; color: CanvasText; }
    header { display: flex; gap: 12px; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid color-mix(in srgb, CanvasText 16%, transparent); }
    main { display: grid; gap: 16px; padding: 16px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
    section { border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 8px; padding: 12px; min-width: 0; }
    h1 { font-size: 18px; margin: 0; }
    h2 { font-size: 15px; margin: 0 0 10px; }
    button, input { font: inherit; }
    button { min-height: 34px; border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); background: ButtonFace; color: ButtonText; padding: 0 10px; }
    input { min-height: 32px; border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); padding: 0 8px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .toolbar input { width: min(320px, 100%); }
    .status { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
    .metric { border: 1px solid color-mix(in srgb, CanvasText 12%, transparent); border-radius: 6px; padding: 8px; }
    .metric strong { display: block; font-size: 12px; opacity: .75; }
    pre { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0; max-height: 360px; overflow: auto; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <h1>Novel AI Admin</h1>
    <div class="toolbar">
      <input id="token" type="password" placeholder="API token">
      <button id="save-token">Save</button>
      <button id="refresh">Refresh</button>
    </div>
  </header>
  <main>
    <section>
      <h2>Worker</h2>
      <div class="toolbar">
        <button id="start">Start</button>
        <button id="stop">Stop</button>
        <button id="run-once">Run Once</button>
      </div>
      <div class="status" id="worker-status"></div>
    </section>
    <section>
      <h2>Jobs</h2>
      <pre id="jobs"></pre>
    </section>
    <section>
      <h2>Requests</h2>
      <pre id="requests"></pre>
    </section>
    <section>
      <h2>Sources</h2>
      <pre id="sources"></pre>
    </section>
  </main>
  <script>
    const tokenInput = document.getElementById("token");
    tokenInput.value = sessionStorage.getItem("novelai.token") || "";
    document.getElementById("save-token").onclick = () => sessionStorage.setItem("novelai.token", tokenInput.value);
    const headers = () => tokenInput.value ? {"Authorization": `Bearer ${tokenInput.value}`} : {};
    async function request(path, options = {}) {
      const response = await fetch(path, {...options, headers: {...headers(), ...(options.headers || {})}});
      if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
      return response.json();
    }
    const pretty = value => JSON.stringify(value, null, 2);
    function drawWorker(status) {
      document.getElementById("worker-status").innerHTML = [
        ["Running", status.running],
        ["Processed", status.jobs_processed],
        ["Idle", status.idle_ticks],
        ["Last job", status.last_job_id || "-"],
        ["Last error", status.last_error || "-"],
        ["Poll", `${status.poll_seconds}s`],
      ].map(([k, v]) => `<div class="metric"><strong>${k}</strong>${v}</div>`).join("");
    }
    async function refresh() {
      const [worker, jobs, requests, sources] = await Promise.all([
        request("/novels/admin/worker"),
        request("/novels/jobs?limit=20"),
        request("/novels/requests?limit=20"),
        request("/novels/jobs/source-health"),
      ]);
      drawWorker(worker);
      document.getElementById("jobs").textContent = pretty(jobs.jobs);
      document.getElementById("requests").textContent = pretty(requests.requests);
      document.getElementById("sources").textContent = pretty(sources.sources);
    }
    document.getElementById("refresh").onclick = () => refresh().catch(alert);
    document.getElementById("start").onclick = () => request("/novels/admin/worker/start", {method: "POST"}).then(refresh).catch(alert);
    document.getElementById("stop").onclick = () => request("/novels/admin/worker/stop", {method: "POST"}).then(refresh).catch(alert);
    document.getElementById("run-once").onclick = () => request("/novels/admin/worker/run-once", {method: "POST"}).then(refresh).catch(alert);
    refresh().catch(console.error);
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class NovelSummary(BaseModel):
    novel_id: str
    title: str | None = None
    author: str | None = None
    chapter_count: int = 0


class ChapterSummary(BaseModel):
    id: str
    title: str | None = None
    translated: bool = False


class ScrapeRequest(BaseModel):
    source_key: str | None = None
    url: str
    chapters: str = "all"
    mode: str = "update"
    max_chapter: int | None = None


class TranslateRequest(BaseModel):
    source_key: str
    chapters: str = "all"
    provider_key: str | None = None
    provider_model: str | None = None
    force: bool = False


class TranslationEditRequest(BaseModel):
    text: str
    editor: str | None = None
    note: str | None = None


class TranslationRollbackRequest(BaseModel):
    version_id: str
    editor: str | None = None
    note: str | None = None


class ExportRequest(BaseModel):
    format: str = "epub"
    chapters: str | None = None


class ImportRequest(BaseModel):
    adapter_key: str
    source: str
    max_units: int | None = None


class CrawlJobRequest(BaseModel):
    novel_id: str
    source_key: str
    kind: str = "chapters"
    chapters: str | None = "all"
    source_url: str | None = None
    metadata: dict[str, Any] | None = None


class TranslationJobRequest(BaseModel):
    novel_id: str
    source_key: str | None = None
    kind: str = "translate"
    chapters: str = "all"
    provider: str | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None


class JobStatusUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    metadata: dict[str, Any] | None = None


class NovelRequestCreateRequest(BaseModel):
    title: str
    source_key: str | None = None
    source_url: str | None = None
    requested_by: str | None = None
    notes: str | None = None


class NovelRequestVoteRequest(BaseModel):
    voter: str | None = None


class NovelRequestStatusRequest(BaseModel):
    status: str
    reviewed_by: str | None = None
    notes: str | None = None


class SourceCandidateCreateRequest(BaseModel):
    source_key: str | None = None
    source_url: str | None = None
    submitted_by: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Sources (must come before /{novel_id} to avoid route collision)
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=list[str])
async def list_sources(_auth: None = Depends(verify_api_key)) -> list[str]:
    return available_sources()


@router.get("/input-adapters", response_model=list[str])
async def list_input_adapters(_auth: None = Depends(verify_api_key)) -> list[str]:
    return available_input_adapters()


# ---------------------------------------------------------------------------
# Jobs (must come before /{novel_id} to avoid route collision)
# ---------------------------------------------------------------------------

@router.get("/jobs")
async def list_jobs(
    status: str | None = None,
    job_type: str | None = None,
    novel_id: str | None = None,
    limit: int | None = None,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        items = jobs.list_jobs(status=status, job_type=job_type, novel_id=novel_id, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"jobs": items}


@router.get("/jobs/source-health")
async def list_source_health(
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return {"sources": jobs.list_source_health()}


@router.get("/jobs/source-health/{source_key}")
async def get_source_health(
    source_key: str,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    source = jobs.get_source_health(source_key)
    if source is None:
        raise HTTPException(status_code=404, detail="Source health not found")
    return source


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    job = jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/crawl")
async def create_crawl_job(
    body: CrawlJobRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return jobs.create_crawl_job(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            source_url=body.source_url,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/translation")
async def create_translation_job(
    body: TranslationJobRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return jobs.create_translation_job(
            novel_id=body.novel_id,
            source_key=body.source_key,
            kind=body.kind,
            chapters=body.chapters,
            provider=body.provider,
            model=body.model,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/jobs/run-next")
async def run_next_job(
    job_type: str | None = None,
    worker: JobWorkerService = Depends(get_job_worker),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = await worker.run_next(job_type=job_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="No pending job found")
    return job


@router.post("/jobs/{job_id}/run")
async def run_job(
    job_id: str,
    worker: JobWorkerService = Depends(get_job_worker),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = await worker.run_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/jobs/{job_id}")
async def update_job_status(
    job_id: str,
    body: JobStatusUpdateRequest,
    jobs: JobQueueService = Depends(get_jobs),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        job = jobs.update_job_status(job_id, body.status, error=body.error, metadata=body.metadata)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ---------------------------------------------------------------------------
# Novel Requests (must come before /{novel_id} to avoid route collision)
# ---------------------------------------------------------------------------

@router.get("/requests")
async def list_novel_requests(
    status: str | None = None,
    limit: int | None = None,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        items = requests.list_requests(status=status, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"requests": items}


@router.post("/requests")
async def create_novel_request(
    body: NovelRequestCreateRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        return requests.create_request(
            title=body.title,
            source_key=body.source_key,
            source_url=body.source_url,
            requested_by=body.requested_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/requests/{request_id}")
async def get_novel_request(
    request_id: str,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    item = requests.get_request(request_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return item


@router.post("/requests/{request_id}/vote")
async def vote_novel_request(
    request_id: str,
    body: NovelRequestVoteRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    item = requests.vote_request(request_id, voter=body.voter)
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return item


@router.patch("/requests/{request_id}")
async def update_novel_request_status(
    request_id: str,
    body: NovelRequestStatusRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        item = requests.update_request_status(
            request_id,
            body.status,
            reviewed_by=body.reviewed_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return item


@router.post("/requests/{request_id}/source-candidates")
async def add_source_candidate(
    request_id: str,
    body: SourceCandidateCreateRequest,
    requests: NovelRequestService = Depends(get_requests),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    try:
        item = requests.add_source_candidate(
            request_id,
            source_key=body.source_key,
            source_url=body.source_url,
            submitted_by=body.submitted_by,
            notes=body.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Novel request not found")
    return item


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(_auth: None = Depends(verify_api_key)) -> HTMLResponse:
    return HTMLResponse(_ADMIN_HTML)


@router.get("/admin/worker")
async def get_worker_status(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return runner.status()


@router.post("/admin/worker/start")
async def start_worker(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.start()


@router.post("/admin/worker/stop")
async def stop_worker(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    return await runner.stop()


@router.post("/admin/worker/run-once")
async def run_worker_once(
    runner: BackgroundJobRunner = Depends(get_job_runner),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    job = await runner.run_once()
    return {
        "job": job,
        "worker": runner.status(),
    }


# ---------------------------------------------------------------------------
# List / Detail
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[NovelSummary])
async def list_novels(
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> list[NovelSummary]:
    summaries: list[NovelSummary] = []
    for novel_id in storage.list_novels():
        meta = storage.load_metadata(novel_id) or {}
        summaries.append(
            NovelSummary(
                novel_id=novel_id,
                title=meta.get("title"),
                author=meta.get("author"),
                chapter_count=len(meta.get("chapters", [])),
            )
        )
    return summaries


@router.get("/{novel_id}")
async def get_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    return meta


@router.delete("/{novel_id}", status_code=204)
async def delete_novel(
    novel_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> None:
    _rate_limit(request, "delete")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    storage.delete_novel(novel_id)


# ---------------------------------------------------------------------------
# Chapters
# ---------------------------------------------------------------------------

@router.get("/{novel_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> list[ChapterSummary]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    translated_ids = set(storage.list_translated_chapters(novel_id))
    return [
        ChapterSummary(
            id=str(c.get("id")),
            title=c.get("title") or c.get("translated_title"),
            translated=str(c.get("id")) in translated_ids,
        )
        for c in meta.get("chapters", [])
        if isinstance(c, dict)
    ]


@router.get("/{novel_id}/chapters/{chapter_id}")
async def get_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    chapter = storage.load_chapter(novel_id, chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")
    text = chapter.get("text")
    if not isinstance(text, str):
        raise HTTPException(status_code=500, detail="Stored chapter is malformed")
    return {"novel_id": novel_id, "chapter_id": chapter_id, "text": text}


@router.get("/{novel_id}/chapters/{chapter_id}/translated")
async def get_translated_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {"novel_id": novel_id, "chapter_id": chapter_id, **translated}


@router.get("/{novel_id}/reader")
async def get_reader_novel(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    translated_ids = set(storage.list_translated_chapters(novel_id))
    chapters = []
    for chapter in _metadata_chapters(meta):
        chapter_id = str(chapter.get("id"))
        chapters.append(
            {
                "id": chapter_id,
                "num": chapter.get("num"),
                "title": chapter.get("translated_title") or chapter.get("title"),
                "source_title": chapter.get("title"),
                "translated": chapter_id in translated_ids,
            }
        )

    return {
        "novel_id": novel_id,
        "title": _reader_title(meta),
        "source_title": meta.get("title"),
        "author": _reader_author(meta),
        "source_author": meta.get("author"),
        "source": meta.get("source"),
        "source_url": meta.get("source_url"),
        "chapter_count": len(chapters),
        "translated_count": len(translated_ids),
        "chapters": chapters,
    }


@router.get("/{novel_id}/reader/chapters/{chapter_id}")
async def get_reader_chapter(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    chapters = _metadata_chapters(meta)
    chapter_ids = [str(chapter.get("id")) for chapter in chapters]
    if chapter_id not in chapter_ids:
        raise HTTPException(status_code=404, detail="Chapter not found")

    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None or not isinstance(translated.get("text"), str):
        raise HTTPException(status_code=404, detail="Translated chapter not found")

    index = chapter_ids.index(chapter_id)
    chapter = chapters[index]
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "novel_title": _reader_title(meta),
        "title": chapter.get("translated_title") or chapter.get("title"),
        "source_title": chapter.get("title"),
        "text": translated.get("text"),
        "version_id": translated.get("version_id"),
        "version_kind": translated.get("version_kind"),
        "previous_chapter_id": chapter_ids[index - 1] if index > 0 else None,
        "next_chapter_id": chapter_ids[index + 1] if index + 1 < len(chapter_ids) else None,
    }


@router.get("/{novel_id}/chapters/{chapter_id}/translated/versions")
async def list_translated_chapter_versions(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    versions = storage.list_translated_chapter_versions(novel_id, chapter_id)
    if not versions:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {"novel_id": novel_id, "chapter_id": chapter_id, "versions": versions}


@router.get("/{novel_id}/chapters/{chapter_id}/translated/edit-history")
async def get_translation_edit_history(
    novel_id: str,
    chapter_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if storage.load_translated_chapter(novel_id, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Translated chapter not found")
    return {
        "novel_id": novel_id,
        "chapter_id": chapter_id,
        "history": storage.load_translation_edit_history(novel_id, chapter_id),
    }


@router.put("/{novel_id}/chapters/{chapter_id}/translated")
async def update_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationEditRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if storage.load_chapter(novel_id, chapter_id) is None and storage.load_translated_chapter(novel_id, chapter_id) is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Translated text cannot be empty")

    storage.save_edited_translation(
        novel_id,
        chapter_id,
        text,
        editor=body.editor,
        note=body.note,
    )
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Edited translation could not be loaded")
    return {"novel_id": novel_id, "chapter_id": chapter_id, **translated}


@router.post("/{novel_id}/chapters/{chapter_id}/translated/rollback")
async def rollback_translated_chapter(
    novel_id: str,
    chapter_id: str,
    body: TranslationRollbackRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "edit")
    if storage.load_metadata(novel_id) is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    if not storage.activate_translated_chapter_version(
        novel_id,
        chapter_id,
        body.version_id,
        editor=body.editor,
        note=body.note,
    ):
        raise HTTPException(status_code=404, detail="Translation version not found")
    translated = storage.load_translated_chapter(novel_id, chapter_id)
    if translated is None:
        raise HTTPException(status_code=500, detail="Rolled back translation could not be loaded")
    return {"novel_id": novel_id, "chapter_id": chapter_id, **translated}


# ---------------------------------------------------------------------------
# Scrape / Translate / Export  (long-running — kept simple for now)
# ---------------------------------------------------------------------------

@router.post("/{novel_id}/scrape")
async def scrape_novel(
    novel_id: str,
    body: ScrapeRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    source_key = body.source_key or detect_source(body.url) or "generic"
    timeout = settings.WEB_REQUEST_TIMEOUT_SECONDS
    try:
        meta = await asyncio.wait_for(
            orchestrator.scrape_metadata(
                source_key, novel_id, mode=body.mode, max_chapter=body.max_chapter,
            ),
            timeout=timeout,
        )
        await asyncio.wait_for(
            orchestrator.scrape_chapters(
                source_key, novel_id, body.chapters, mode=body.mode,
            ),
            timeout=timeout,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {"novel_id": novel_id, "source_key": source_key, "chapters": len(meta.get("chapters", []))}


@router.post("/{novel_id}/import")
async def import_document(
    novel_id: str,
    body: ImportRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    _rate_limit(request, "scrape")
    try:
        metadata = await asyncio.wait_for(
            orchestrator.import_document(
                body.adapter_key,
                novel_id,
                body.source,
                max_units=body.max_units,
            ),
            timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {
        "novel_id": novel_id,
        "adapter_key": body.adapter_key,
        "chapters": len(metadata.get("chapters", [])),
        "document_type": metadata.get("document_type"),
    }


@router.post("/{novel_id}/translate")
async def translate_novel(
    novel_id: str,
    body: TranslateRequest,
    request: Request,
    orchestrator: NovelOrchestrationService = Depends(get_orchestrator),
    _auth: None = Depends(verify_api_key),
) -> dict[str, str]:
    _rate_limit(request, "translate")
    try:
        await asyncio.wait_for(
            orchestrator.translate_chapters(
                body.source_key,
                novel_id,
                body.chapters,
                provider_key=body.provider_key,
                provider_model=body.provider_model,
                force=body.force,
            ),
            timeout=settings.WEB_REQUEST_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Operation timed out") from None
    return {"novel_id": novel_id, "status": "ok"}


@router.post("/{novel_id}/export")
async def export_novel(
    novel_id: str,
    body: ExportRequest,
    request: Request,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> FileResponse:
    _rate_limit(request, "export")
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")

    chapters: list[dict[str, Any]] = []
    for chap in meta.get("chapters", []):
        chap_id = str(chap.get("id"))
        translated = storage.load_translated_chapter(novel_id, chap_id)
        if not translated:
            continue
        chapters.append(
            {
                "title": chap.get("title"),
                "text": translated.get("text"),
                "images": storage.load_chapter_export_images(novel_id, chap_id),
            }
        )

    if not chapters:
        raise HTTPException(status_code=400, detail="No translated chapters available for export")

    output_path = str(storage.build_export_path(novel_id, body.format))
    container.export.export(
        body.format,
        novel_id=novel_id,
        chapters=chapters,
        output_path=output_path,
    )
    return FileResponse(
        output_path,
        media_type="application/epub+zip" if body.format == "epub" else "application/octet-stream",
        filename=f"{novel_id}.{body.format}",
    )


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------

@router.get("/{novel_id}/progress")
async def get_progress(
    novel_id: str,
    storage: StorageService = Depends(get_storage),
    _auth: None = Depends(verify_api_key),
) -> dict[str, Any]:
    meta = storage.load_metadata(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    total = len(meta.get("chapters", []))
    scraped = storage.count_stored_chapters(novel_id)
    translated = storage.count_translated_chapters(novel_id)
    return {"novel_id": novel_id, "total": total, "scraped": scraped, "translated": translated}
