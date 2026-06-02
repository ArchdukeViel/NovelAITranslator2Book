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

export type NovelMetadata = Record<string, unknown> & {
  novel_id?: string;
  title?: string | null;
  translated_title?: string | null;
  author?: string | null;
  translated_author?: string | null;
  chapters?: Array<Record<string, unknown>>;
};

export type ChapterDetail = {
  novel_id: string;
  chapter_id: string;
  text: string;
};

export type TranslatedChapter = {
  novel_id: string;
  chapter_id: string;
  id?: string;
  version_id?: string | null;
  version_kind?: string | null;
  provider?: string | null;
  model?: string | null;
  translated_at?: string | null;
  created_at?: string | null;
  text: string;
  editor?: string | null;
  note?: string | null;
  confidence_score?: number | null;
  polish_needed?: boolean | null;
};

export type TranslationVersion = Record<string, unknown> & {
  id?: string;
  version_id?: string;
  version_kind?: string;
  kind?: string;
  text?: string;
  active?: boolean;
  provider?: string | null;
  model?: string | null;
  created_at?: string | null;
  translated_at?: string | null;
};

export type TranslationEditHistory = Record<string, unknown> & {
  id?: string;
  action?: string;
  version_id?: string;
  previous_version_id?: string | null;
  created_at?: string | null;
  editor?: string | null;
  note?: string | null;
};

export type NovelProgress = {
  novel_id: string;
  total: number;
  scraped: number;
  translated: number;
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

export type PreliminaryCrawlResult = {
  novel_id: string;
  source_key: string;
  source_url?: string | null;
  title?: string | null;
  translated_title?: string | null;
  author?: string | null;
  translated_author?: string | null;
  synopsis?: string | null;
  translated_synopsis?: string | null;
  detected_at?: string | null;
  chapters: number;
  chapter_list: Array<{
    id?: string | number | null;
    num?: number | null;
    title?: string | null;
    translated_title?: string | null;
    date_added?: string | null;
    published_at?: string | null;
    updated_at?: string | null;
    volume?: string | number | null;
    part?: string | number | null;
    arc?: string | number | null;
    section?: string | number | null;
    group?: string | number | null;
    url?: string | null;
  } & Record<string, unknown>>;
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

async function apiDownload(path: string, body: unknown): Promise<Blob> {
  const token = useUiStore.getState().apiToken;
  const headers = new Headers();
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.blob();
}

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),
  sources: () => apiFetch<string[]>("/novels/sources"),
  inputAdapters: () => apiFetch<string[]>("/novels/input-adapters"),
  novels: () => apiFetch<NovelSummary[]>("/novels/"),
  novel: (novelId: string) => apiFetch<NovelMetadata>(`/novels/${encodeURIComponent(novelId)}`),
  chapters: (novelId: string) => apiFetch<ChapterSummary[]>(`/novels/${encodeURIComponent(novelId)}/chapters`),
  chapter: (novelId: string, chapterId: string) =>
    apiFetch<ChapterDetail>(`/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}`),
  translatedChapter: (novelId: string, chapterId: string) =>
    apiFetch<TranslatedChapter>(`/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated`),
  translationVersions: (novelId: string, chapterId: string) =>
    apiFetch<{ novel_id: string; chapter_id: string; versions: TranslationVersion[] }>(
      `/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/versions`
    ),
  translationEditHistory: (novelId: string, chapterId: string) =>
    apiFetch<{ novel_id: string; chapter_id: string; history: TranslationEditHistory[] }>(
      `/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/edit-history`
    ),
  updateTranslatedChapter: (
    novelId: string,
    chapterId: string,
    payload: { text: string; editor?: string; note?: string }
  ) =>
    apiFetch<TranslatedChapter>(`/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  rollbackTranslatedChapter: (
    novelId: string,
    chapterId: string,
    payload: { version_id: string; editor?: string; note?: string }
  ) =>
    apiFetch<TranslatedChapter>(
      `/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/rollback`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  progress: (novelId: string) => apiFetch<NovelProgress>(`/novels/${encodeURIComponent(novelId)}/progress`),
  readerNovel: (novelId: string) => apiFetch<ReaderNovel>(`/novels/${encodeURIComponent(novelId)}/reader`),
  readerChapter: (novelId: string, chapterId: string) =>
    apiFetch<ReaderChapter>(`/novels/${encodeURIComponent(novelId)}/reader/chapters/${encodeURIComponent(chapterId)}`),
  jobs: (params: { status?: string; job_type?: string; novel_id?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.job_type) search.set("job_type", params.job_type);
    if (params.novel_id) search.set("novel_id", params.novel_id);
    search.set("limit", String(params.limit ?? 50));
    return apiFetch<{ jobs: JobRecord[] }>(`/novels/jobs?${search.toString()}`);
  },
  job: (jobId: string) => apiFetch<JobRecord>(`/novels/jobs/${encodeURIComponent(jobId)}`),
  runJob: (jobId: string) =>
    apiFetch<JobRecord>(`/novels/jobs/${encodeURIComponent(jobId)}/run`, {
      method: "POST"
    }),
  runNextJob: (jobType?: string) => {
    const suffix = jobType ? `?job_type=${encodeURIComponent(jobType)}` : "";
    return apiFetch<JobRecord>(`/novels/jobs/run-next${suffix}`, { method: "POST" });
  },
  updateJobStatus: (jobId: string, payload: { status: string; error?: string; metadata?: Record<string, unknown> }) =>
    apiFetch<JobRecord>(`/novels/jobs/${encodeURIComponent(jobId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  sourceHealth: () => apiFetch<{ sources: SourceHealth[] }>("/novels/jobs/source-health"),
  sourceHealthDetail: (sourceKey: string) => apiFetch<SourceHealth>(`/novels/jobs/source-health/${encodeURIComponent(sourceKey)}`),
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
  createCrawlJob: (payload: { novel_id: string; source_key: string; kind: string; chapters?: string; source_url?: string; metadata?: Record<string, unknown> }) =>
    apiFetch<JobRecord>("/novels/jobs/crawl", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTranslationJob: (payload: {
    novel_id: string;
    source_key?: string;
    kind: string;
    chapters: string;
    provider?: string;
    model?: string;
    metadata?: Record<string, unknown>;
  }) =>
    apiFetch<JobRecord>("/novels/jobs/translation", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  scrapeNow: (
    novelId: string,
    payload: { source_key?: string; url: string; chapters?: string; mode?: string; max_chapter?: number | null }
  ) =>
    apiFetch<{ novel_id: string; source_key: string; chapters: number }>(`/novels/${encodeURIComponent(novelId)}/scrape`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  preliminaryCrawl: (
    novelId: string,
    payload: { source_key?: string; identifier: string; mode?: string; max_chapter?: number | null }
  ) =>
    apiFetch<PreliminaryCrawlResult>(`/novels/${encodeURIComponent(novelId)}/preliminary-crawl`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  importNow: (novelId: string, payload: { adapter_key: string; source: string; max_units?: number | null }) =>
    apiFetch<{ novel_id: string; adapter_key: string; chapters: number; document_type?: string | null }>(
      `/novels/${encodeURIComponent(novelId)}/import`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  translateNow: (
    novelId: string,
    payload: { source_key: string; chapters?: string; provider_key?: string; provider_model?: string; force?: boolean }
  ) =>
    apiFetch<{ novel_id: string; status: string }>(`/novels/${encodeURIComponent(novelId)}/translate`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportNovel: (novelId: string, payload: { format: string; chapters?: string | null }) =>
    apiDownload(`/novels/${encodeURIComponent(novelId)}/export`, payload)
};
