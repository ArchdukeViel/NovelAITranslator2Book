import { useUiStore } from "@/lib/store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export type NovelSummary = {
  novel_id: string;
  title?: string | null;
  author?: string | null;
  chapter_count: number;
};

export type ChapterSummary = {
  id: string;
  title?: string | null;
  translated: boolean;
};

export type JobRecord = {
  id: string;
  type: "crawl" | "translation";
  kind: string;
  novel_id: string;
  source_key?: string | null;
  chapters?: string | null;
  provider?: string | null;
  model?: string | null;
  status: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  retry_count: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
};

export type WorkerStatus = {
  running: boolean;
  poll_seconds: number;
  last_job_id?: string | null;
  last_error?: string | null;
  jobs_processed: number;
  idle_ticks: number;
  error_count: number;
};

export type SourceHealth = {
  source_key: string;
  success_count: number;
  failure_count: number;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  last_error?: string | null;
};

export type NovelRequestRecord = {
  id: string;
  title: string;
  status: string;
  requested_by?: string | null;
  vote_count: number;
  created_at?: string | null;
  source_candidates: Array<Record<string, unknown>>;
};

export type ReaderNovel = {
  novel_id: string;
  title?: string | null;
  source_title?: string | null;
  author?: string | null;
  source?: string | null;
  source_url?: string | null;
  chapter_count: number;
  translated_count: number;
  chapters: Array<{
    id: string;
    num?: number | null;
    title?: string | null;
    source_title?: string | null;
    translated: boolean;
  }>;
};

export type ReaderChapter = {
  novel_id: string;
  chapter_id: string;
  novel_title?: string | null;
  title?: string | null;
  source_title?: string | null;
  text: string;
  version_id?: string | null;
  version_kind?: string | null;
  previous_chapter_id?: string | null;
  next_chapter_id?: string | null;
};

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useUiStore.getState().apiToken;
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),
  novels: () => apiFetch<NovelSummary[]>("/novels/"),
  chapters: (novelId: string) => apiFetch<ChapterSummary[]>(`/novels/${encodeURIComponent(novelId)}/chapters`),
  readerNovel: (novelId: string) => apiFetch<ReaderNovel>(`/novels/${encodeURIComponent(novelId)}/reader`),
  readerChapter: (novelId: string, chapterId: string) =>
    apiFetch<ReaderChapter>(`/novels/${encodeURIComponent(novelId)}/reader/chapters/${encodeURIComponent(chapterId)}`),
  jobs: () => apiFetch<{ jobs: JobRecord[] }>("/novels/jobs?limit=50"),
  sourceHealth: () => apiFetch<{ sources: SourceHealth[] }>("/novels/jobs/source-health"),
  workerStatus: () => apiFetch<WorkerStatus>("/novels/admin/worker"),
  workerStart: () => apiFetch<WorkerStatus>("/novels/admin/worker/start", { method: "POST" }),
  workerStop: () => apiFetch<WorkerStatus>("/novels/admin/worker/stop", { method: "POST" }),
  workerRunOnce: () => apiFetch<{ job: JobRecord | null; worker: WorkerStatus }>("/novels/admin/worker/run-once", { method: "POST" }),
  requests: () => apiFetch<{ requests: NovelRequestRecord[] }>("/novels/requests?limit=50"),
  createRequest: (payload: { title: string; source_key?: string; source_url?: string; requested_by?: string; notes?: string }) =>
    apiFetch<NovelRequestRecord>("/novels/requests", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createCrawlJob: (payload: { novel_id: string; source_key: string; kind: string; chapters?: string; source_url?: string }) =>
    apiFetch<JobRecord>("/novels/jobs/crawl", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTranslationJob: (payload: { novel_id: string; source_key?: string; kind: string; chapters: string; provider?: string; model?: string }) =>
    apiFetch<JobRecord>("/novels/jobs/translation", {
      method: "POST",
      body: JSON.stringify(payload)
    })
};
