"""Repeatable local Phase 6 acceptance fixture and HTTP workload.

The fixture is deliberately namespaced with ``phase6-load-`` and the cleanup
command removes only rows and storage objects in that namespace. Run fixture
commands inside the backend container so they use the same database and
storage configuration as the running services. Run the workload from the
host or another client so its timings include the proxy and network boundary.

Examples::

    python run_phase6_acceptance.py fixture status
    python run_phase6_acceptance.py workload --novel-slug phase6-load-large
    python run_phase6_acceptance.py fixture cleanup

The workload never prints cookies, CSRF tokens, response bodies, prompts, or
provider data. Optional authenticated translation traffic reads credentials
only from the environment variables named by ``--session-cookie-env`` and
``--csrf-token-env``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

FIXTURE_PREFIX = "phase6-load-"
LARGE_FIXTURE_SLUG = f"{FIXTURE_PREFIX}large"
FIXTURE_SOURCE_KEY = "phase6-load"
FIXTURE_LARGE_CHAPTERS = 300
FIXTURE_SMALL_NOVELS = 48
FIXTURE_SMALL_CHAPTERS = 24


@dataclass(frozen=True, slots=True)
class RequestResult:
    route: str
    method: str
    status: str
    latency_ms: float
    response_bytes: int
    error_type: str | None = None


def _percentile(values: Iterable[float], percentile: float) -> float | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))
    return round(ordered[index], 3)


def _fixture_slugs() -> list[str]:
    return [LARGE_FIXTURE_SLUG, *[f"{FIXTURE_PREFIX}{index:03d}" for index in range(1, FIXTURE_SMALL_NOVELS)]]


def _rowcount(result: Any) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


def _fixture_cleanup() -> dict[str, int]:
    """Delete only Phase 6 fixture rows and namespaced storage objects."""
    from sqlalchemy import delete, select

    from novelai.activity.database import ActivityRecord
    from novelai.db.engine import session_scope
    from novelai.db.models.analytics_event import AnalyticsEvent
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel
    from novelai.storage.service import StorageService

    slugs = _fixture_slugs()
    storage = StorageService()
    for slug in slugs:
        storage.delete_novel(slug)

    with session_scope() as db:
        novel_ids = list(db.scalars(select(Novel.id).where(Novel.slug.in_(slugs))))
        deleted_events = _rowcount(db.execute(delete(AnalyticsEvent).where(AnalyticsEvent.novel_id.in_(slugs))))
        deleted_activities = _rowcount(db.execute(delete(ActivityRecord).where(ActivityRecord.novel_id.in_(slugs))))
        deleted_chapters = (
            _rowcount(db.execute(delete(Chapter).where(Chapter.novel_id.in_(novel_ids)))) if novel_ids else 0
        )
        deleted_novels = _rowcount(db.execute(delete(Novel).where(Novel.id.in_(novel_ids)))) if novel_ids else 0

    return {
        "novels": int(deleted_novels),
        "chapters": int(deleted_chapters),
        "analytics_events": int(deleted_events),
        "activities": int(deleted_activities),
    }


def _fixture_status() -> dict[str, int]:
    from sqlalchemy import func, select

    from novelai.db.engine import session_scope
    from novelai.db.models.analytics_event import AnalyticsEvent
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel

    slugs = _fixture_slugs()
    with session_scope() as db:
        novel_ids = list(db.scalars(select(Novel.id).where(Novel.slug.in_(slugs))))
        return {
            "novels": len(novel_ids),
            "chapters": int(db.scalar(select(func.count(Chapter.id)).where(Chapter.novel_id.in_(novel_ids))) or 0)
            if novel_ids
            else 0,
            "analytics_events": int(
                db.scalar(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.novel_id.in_(slugs))) or 0
            ),
        }


def _fixture_seed() -> dict[str, int | str]:
    """Seed a realistic projection/storage workload for local acceptance."""
    from novelai.core.chapter_state import TranslationState
    from novelai.db.engine import session_scope
    from novelai.db.models.analytics_event import AnalyticsEvent
    from novelai.db.models.chapter import Chapter
    from novelai.db.models.novel import Novel
    from novelai.storage.service import StorageService

    _fixture_cleanup()
    storage = StorageService()
    now = datetime.now(UTC)
    total_chapters = 0
    with session_scope() as db:
        for novel_index, slug in enumerate(_fixture_slugs()):
            chapter_count = FIXTURE_LARGE_CHAPTERS if novel_index == 0 else FIXTURE_SMALL_CHAPTERS
            title = (
                "Phase 6 Large Acceptance Novel" if novel_index == 0 else f"Phase 6 Acceptance Novel {novel_index:03d}"
            )
            chapters: list[dict[str, Any]] = []
            novel = Novel(
                slug=slug,
                public_slug=slug,
                title=title,
                original_title=title,
                author="Phase 6 Fixture",
                source_site=FIXTURE_SOURCE_KEY,
                source_url=f"https://phase6.invalid/{slug}",
                language="en",
                publication_status="published",
                chapter_count=chapter_count,
                translated_count=chapter_count,
                latest_chapter_id=str(chapter_count),
                latest_chapter_number=chapter_count,
                latest_chapter_title=f"Chapter {chapter_count}",
                latest_chapter_updated_at=now,
                synopsis="Synthetic local acceptance fixture; not production content.",
                is_published=True,
                glossary_status="glossary_skipped",
            )
            db.add(novel)
            db.flush()

            for chapter_number in range(1, chapter_count + 1):
                chapter_id = str(chapter_number)
                chapter_title = f"Chapter {chapter_number}"
                text = (
                    f"Phase 6 fixture paragraph for {slug}, chapter {chapter_number}.\n\n"
                    "This synthetic text exists only to exercise the public projection and chapter path."
                )
                storage.save_chapter(
                    slug,
                    chapter_id,
                    text,
                    title=chapter_title,
                    source_key=FIXTURE_SOURCE_KEY,
                    source_url=f"https://phase6.invalid/{slug}/{chapter_id}",
                )
                storage.save_translated_chapter(
                    slug,
                    chapter_id,
                    text,
                    provider_key="phase6-fixture",
                    provider_model="phase6-fixture-model",
                    source_language="en",
                    target_language="English",
                )
                db.add(
                    Chapter(
                        novel_id=novel.id,
                        chapter_number=chapter_number,
                        logical_chapter_id=chapter_id,
                        source_episode_id=chapter_id,
                        sequence_number=chapter_number,
                        title=chapter_title,
                        source_url=f"https://phase6.invalid/{slug}/{chapter_id}",
                        raw_storage_key=f"novels/{slug}/chapters/{chapter_id}.json",
                        translated_storage_key=f"novels/{slug}/translations/{chapter_id}.json",
                        raw_status="completed",
                        translation_status="completed",
                        translation_state=TranslationState.COMPLETE.value,
                        word_count=len(text.split()),
                    )
                )
                chapters.append(
                    {
                        "id": chapter_id,
                        "title": chapter_title,
                        "number": chapter_number,
                        "url": f"https://phase6.invalid/{slug}/{chapter_id}",
                        "translated_at": now.isoformat(),
                    }
                )

            storage.save_metadata(
                slug,
                {
                    "novel_id": slug,
                    "source_novel_id": slug,
                    "source_key": FIXTURE_SOURCE_KEY,
                    "source_url": f"https://phase6.invalid/{slug}",
                    "title": title,
                    "translated_title": title,
                    "author": "Phase 6 Fixture",
                    "synopsis": "Synthetic local acceptance fixture.",
                    "chapters": chapters,
                    "publication_status": "published",
                    "is_published": True,
                },
            )

            # Seed both authenticated and anonymous distinct viewers across
            # daily, weekly, and monthly windows without storing IP addresses.
            for viewer in range(1, 13):
                db.add(
                    AnalyticsEvent(
                        event_name="public_novel.view",
                        user_id=700000 + viewer,
                        novel_id=slug,
                        created_at=now - timedelta(hours=viewer),
                    )
                )
                db.add(
                    AnalyticsEvent(
                        event_name="public_novel.view",
                        session_id=f"phase6-anon-{novel_index}-{viewer}",
                        novel_id=slug,
                        created_at=now - timedelta(days=viewer % 7, hours=viewer),
                    )
                )
            db.add(
                AnalyticsEvent(
                    event_name="public_novel.view",
                    user_id=800000 + novel_index,
                    novel_id=slug,
                    created_at=now - timedelta(days=20),
                )
            )
            total_chapters += chapter_count

    return {
        "fixture_prefix": FIXTURE_PREFIX,
        "novels": len(_fixture_slugs()),
        "chapters": total_chapters,
        "analytics_events": len(_fixture_slugs()) * 25,
    }


async def _request(
    client: httpx.AsyncClient,
    *,
    route: str,
    method: str,
    path: str,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
) -> RequestResult:
    started = time.perf_counter()
    try:
        response = await client.request(method, path, headers=headers, json=json_body)
        return RequestResult(
            route=route,
            method=method,
            status=str(response.status_code),
            latency_ms=(time.perf_counter() - started) * 1000,
            response_bytes=len(response.content),
        )
    except httpx.TimeoutException:
        return RequestResult(
            route=route,
            method=method,
            status="timeout",
            latency_ms=(time.perf_counter() - started) * 1000,
            response_bytes=0,
            error_type="timeout",
        )
    except Exception as exc:  # pragma: no cover - exercised by live environments
        return RequestResult(
            route=route,
            method=method,
            status="error",
            latency_ms=(time.perf_counter() - started) * 1000,
            response_bytes=0,
            error_type=type(exc).__name__,
        )


async def _workload_route(
    client: httpx.AsyncClient,
    *,
    route: str,
    method: str,
    path: str,
    samples: int,
    concurrency: int,
    headers: dict[str, str],
    json_body: dict[str, Any] | None = None,
    header_factory: Callable[[int], dict[str, str]] | None = None,
) -> list[RequestResult]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def one(index: int) -> RequestResult:
        async with semaphore:
            request_headers = header_factory(index) if header_factory is not None else dict(headers)
            return await _request(
                client,
                route=route,
                method=method,
                path=path,
                headers=request_headers,
                json_body=json_body,
            )

    # One warmup request establishes the cold-to-warm transition without
    # contaminating the reported sample distribution.
    warmup_headers = header_factory(-1) if header_factory is not None else dict(headers)
    await _request(
        client,
        route=f"{route}:warmup",
        method=method,
        path=path,
        headers=warmup_headers,
        json_body=json_body,
    )
    return list(await asyncio.gather(*(one(index) for index in range(samples))))


def _summarize(results: list[RequestResult]) -> dict[str, Any]:
    latencies = [result.latency_ms for result in results]
    statuses = Counter(result.status for result in results)
    errors = Counter(result.error_type for result in results if result.error_type is not None)
    return {
        "samples": len(results),
        "p50_ms": _percentile(latencies, 0.50),
        "p95_ms": _percentile(latencies, 0.95),
        "p99_ms": _percentile(latencies, 0.99),
        "min_ms": round(min(latencies), 3) if latencies else None,
        "max_ms": round(max(latencies), 3) if latencies else None,
        "average_response_bytes": round(statistics.mean(result.response_bytes for result in results), 1)
        if results
        else 0,
        "statuses": dict(statuses),
        "timeouts": int(statuses.get("timeout", 0)),
        "errors": dict(errors),
    }


async def _read_metrics(client: httpx.AsyncClient) -> dict[str, Any]:
    try:
        response = await client.get("/metrics")
    except Exception as exc:  # pragma: no cover - live environment only
        return {"status": "error", "error_type": type(exc).__name__}
    if response.status_code != 200:
        return {"status": str(response.status_code), "response_bytes": len(response.content)}
    selected: dict[str, float] = {}
    prefixes = (
        "novelai_activity_",
        "novelai_analytics_writer_",
        "novelai_provider_",
        "novelai_public_",
        "novelai_readiness_",
    )
    for line in response.text.splitlines():
        if not line or line.startswith("#") or "{" in line:
            continue
        name, _, value = line.partition(" ")
        if name.startswith(prefixes):
            try:
                selected[name] = float(value)
            except ValueError:
                continue
    return {"status": "200", "response_bytes": len(response.content), "selected": selected}


async def _run_workload(args: argparse.Namespace) -> dict[str, Any]:
    base_url = args.base_url.rstrip("/")
    slug = args.novel_slug
    encoded_slug = quote(slug, safe="")
    chapter_path = f"/api/public/novels/{encoded_slug}/chapters/{quote(args.chapter_id, safe='')}"
    public_headers = {"User-Agent": "novelai-phase6-acceptance/1"}
    if args.host_header:
        public_headers["Host"] = args.host_header
    cookie = os.environ.get(args.session_cookie_env, "").strip() if args.session_cookie_env else ""
    csrf = os.environ.get(args.csrf_token_env, "").strip() if args.csrf_token_env else ""
    authenticated_headers = dict(public_headers)
    if cookie:
        authenticated_headers["Cookie"] = cookie

    run_id = uuid.uuid4().hex[:12]
    route_specs: list[tuple[str, str, str, dict[str, str], dict[str, Any] | None]] = [
        ("health_live", "GET", "/health/live", public_headers, None),
        ("health_ready", "GET", "/health/ready", public_headers, None),
        ("catalog", "GET", "/api/public/catalog?page=1&page_size=24", public_headers, None),
        ("detail", "GET", f"/api/public/novels/{encoded_slug}", public_headers, None),
        ("chapter", "GET", chapter_path, public_headers, None),
        ("search", "GET", "/api/public/catalog?q=Phase%206&page=1&page_size=24", public_headers, None),
        ("ranking_daily", "GET", "/api/public/rankings?period=daily&limit=10", public_headers, None),
        ("ranking_weekly", "GET", "/api/public/rankings?period=weekly&limit=10", public_headers, None),
        ("ranking_monthly", "GET", "/api/public/rankings?period=monthly&limit=10", public_headers, None),
        ("home", "GET", "/home", public_headers, None),
    ]
    if cookie:
        route_specs.extend(
            [
                ("detail_authenticated", "GET", f"/api/public/novels/{encoded_slug}", authenticated_headers, None),
                ("chapter_authenticated", "GET", chapter_path, authenticated_headers, None),
            ]
        )

    results_by_route: dict[str, dict[str, Any]] = {}
    async with httpx.AsyncClient(
        base_url=base_url,
        follow_redirects=True,
        timeout=httpx.Timeout(args.timeout_seconds),
        verify=not args.insecure,
    ) as client:
        for route, method, path, headers, body in route_specs:
            results = await _workload_route(
                client,
                route=route,
                method=method,
                path=path,
                samples=args.samples,
                concurrency=args.concurrency,
                headers=headers,
                json_body=body,
            )
            results_by_route[route] = _summarize(results)

        translation_status: dict[str, Any]
        if cookie and csrf:
            translation_headers = dict(authenticated_headers)
            translation_headers["X-CSRF-Token"] = csrf

            def translation_headers_for(index: int) -> dict[str, str]:
                headers = dict(translation_headers)
                headers["Idempotency-Key"] = f"phase6-{run_id}-{index}"
                return headers

            translation_results = await _workload_route(
                client,
                route="translation_enqueue",
                method="POST",
                path=f"/api/admin/novels/{encoded_slug}/translate",
                samples=args.translation_samples,
                concurrency=min(args.concurrency, args.translation_concurrency),
                headers=translation_headers,
                json_body={
                    "source_key": FIXTURE_SOURCE_KEY,
                    "chapters": "1",
                    "target_language": "English",
                    "skip_glossary_gate": True,
                },
                header_factory=translation_headers_for,
            )
            translation_status = _summarize(translation_results)
        else:
            translation_status = {
                "skipped": True,
                "reason": "session cookie and CSRF token environment variables were not both supplied",
            }
        metrics = await _read_metrics(client)

    result = {
        "run_id": run_id,
        "started_at_utc": datetime.now(UTC).isoformat(),
        "base_url": base_url,
        "fixture_slug": slug,
        "samples_per_route": args.samples,
        "concurrency": args.concurrency,
        "routes": results_by_route,
        "translation_enqueue": translation_status,
        "metrics": metrics,
        "authenticated_public_session": bool(cookie),
        "provider_or_storage_fault_injection": "not injected by this client workload",
    }
    return result


def _print_workload(result: dict[str, Any]) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))
    print("\nPhase 6 route summary:")
    for route, summary in result["routes"].items():
        print(
            f"  {route}: p50={summary['p50_ms']} ms p95={summary['p95_ms']} ms "
            f"p99={summary['p99_ms']} ms statuses={summary['statuses']}"
        )
    print(f"  translation_enqueue: {result['translation_enqueue']}")
    print(f"  metrics: {result['metrics']}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Phase 6 acceptance fixture or workload.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fixture = subparsers.add_parser("fixture", help="Seed, inspect, or clean the namespaced local fixture.")
    fixture.add_argument("action", choices=("seed", "status", "cleanup"))

    workload = subparsers.add_parser("workload", help="Run concurrent public and optional authenticated HTTP traffic.")
    workload.add_argument("--base-url", default="http://localhost")
    workload.add_argument("--novel-slug", default=LARGE_FIXTURE_SLUG)
    workload.add_argument("--chapter-id", default="1")
    workload.add_argument("--samples", type=int, default=20)
    workload.add_argument("--concurrency", type=int, default=8)
    workload.add_argument("--translation-samples", type=int, default=8)
    workload.add_argument("--translation-concurrency", type=int, default=2)
    workload.add_argument("--timeout-seconds", type=float, default=10.0)
    workload.add_argument(
        "--host-header",
        default=None,
        help="Optional Host header for internal proxy targets such as http://caddy.",
    )
    workload.add_argument("--insecure", action="store_true")
    workload.add_argument("--session-cookie-env", default=None)
    workload.add_argument("--csrf-token-env", default=None)
    workload.add_argument("--json-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.command == "fixture":
        if args.action == "seed":
            result = _fixture_seed()
        elif args.action == "cleanup":
            result = _fixture_cleanup()
        else:
            result = _fixture_status()
        print(json.dumps(result, sort_keys=True))
        return 0

    result = asyncio.run(_run_workload(args))
    _print_workload(result)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
