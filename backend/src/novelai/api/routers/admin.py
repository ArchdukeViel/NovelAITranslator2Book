from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse

from novelai.api.routers.dependencies import get_job_runner, verify_api_key
from novelai.jobs.runner import BackgroundJobRunner

router = APIRouter()

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
    button, input { font: inherit; min-height: 32px; }
    button { border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); background: ButtonFace; color: ButtonText; padding: 0 10px; }
    input { border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 22%, transparent); padding: 0 8px; }
    .toolbar { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
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
      <pre id="worker-status"></pre>
    </section>
    <section><h2>Jobs</h2><pre id="jobs"></pre></section>
    <section><h2>Requests</h2><pre id="requests"></pre></section>
    <section><h2>Sources</h2><pre id="sources"></pre></section>
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
    async function refresh() {
      const [worker, jobs, requests, sources] = await Promise.all([
        request("/novels/admin/worker"),
        request("/novels/jobs?limit=20"),
        request("/novels/requests?limit=20"),
        request("/novels/jobs/source-health"),
      ]);
      document.getElementById("worker-status").textContent = pretty(worker);
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
