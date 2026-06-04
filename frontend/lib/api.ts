import { useUiStore } from "@/lib/store";
import type {
  ActivityRecord,
  ApiErrorPayload,
  ChapterDetail,
  ChapterSummary,
  CreateTranslationActivityPayload,
  JobProgress,
  ModelState,
  NovelMetadata,
  NovelProgress,
  NovelRequestRecord,
  NovelSummary,
  PreliminaryCrawlResult,
  ProviderApiKeyStatus,
  ProviderApiKeyValidationPayload,
  ReaderChapter,
  ReaderNovel,
  RuntimeStateItem,
  SourceHealth,
  TranslatedChapter,
  TranslationEditHistory,
  TranslationVersion,
  WorkerStatus
} from "@/lib/api-types";

export type * from "@/lib/api-types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;
  code: string;
  explanation?: string | null;
  details?: unknown;
  trace_id?: string | null;
  raw?: unknown;

  constructor(payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = payload.status;
    this.code = payload.code;
    this.explanation = payload.explanation;
    this.details = payload.details;
    this.trace_id = payload.trace_id;
    this.raw = payload.raw;
  }
}

function payloadText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

async function responseError(response: Response): Promise<ApiError> {
  const body = await response.text();
  if (!body) {
    return new ApiError({
      status: response.status,
      code: `HTTP_${response.status}`,
      message: response.statusText || `HTTP ${response.status}`
    });
  }

  try {
    const payload = JSON.parse(body) as Record<string, unknown>;
    const detail = payload.detail;
    const nestedDetail = detail && typeof detail === "object" && !Array.isArray(detail) ? (detail as Record<string, unknown>) : null;
    const code =
      payloadText(payload.code) ||
      payloadText(payload.error) ||
      (nestedDetail ? payloadText(nestedDetail.code) || payloadText(nestedDetail.error) : null) ||
      `HTTP_${response.status}`;
    const message =
      payloadText(payload.message) ||
      payloadText(payload.detail) ||
      (nestedDetail ? payloadText(nestedDetail.message) || payloadText(nestedDetail.detail) : null) ||
      response.statusText ||
      `HTTP ${response.status}`;
    const explanation =
      payloadText(payload.explanation) ||
      (nestedDetail ? payloadText(nestedDetail.explanation) : null);
    const details = payload.details ?? (nestedDetail ? nestedDetail.details : undefined);
    const trace_id = payloadText(payload.trace_id) || (nestedDetail ? payloadText(nestedDetail.trace_id) : null);
    return new ApiError({
      status: response.status,
      code,
      message,
      explanation,
      details,
      trace_id,
      raw: payload
    });
  } catch {
    return new ApiError({
      status: response.status,
      code: `HTTP_${response.status}`,
      message: body || response.statusText || `HTTP ${response.status}`,
      raw: body
    });
  }
}

export function describeApiError(error: unknown) {
  if (error instanceof ApiError) {
    const prefix = `${error.status} ${error.code}`;
    return {
      title: `${prefix}: ${error.message}`,
      explanation:
        error.explanation ||
        "The backend returned an error without a detailed explanation. Check Activity Log for the operation payload.",
      details: error.trace_id ? { trace_id: error.trace_id, details: error.details } : error.details
    };
  }
  if (error instanceof Error) {
    return {
      title: error.message,
      explanation: "The browser received an application error while running this action.",
      details: undefined
    };
  }
  return {
    title: "Unknown error",
    explanation: "The browser received an unknown error while running this action.",
    details: error
  };
}

export function apiErrorKey(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.status}:${error.code}:${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  try {
    return JSON.stringify(error);
  } catch {
    return "unknown-error";
  }
}

export function apiErrorInlineMessage(error: unknown) {
  if (error instanceof ApiError) {
    return `${error.status} ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function progressNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function metadataProgress(activity: ActivityRecord): Record<string, unknown> {
  const progress = activity.metadata?.progress;
  return progress && typeof progress === "object" && !Array.isArray(progress) ? (progress as Record<string, unknown>) : {};
}

export function activityProgress(activity: ActivityRecord): JobProgress {
  const progress = metadataProgress(activity);
  return {
    status: activity.status,
    current_stage: activity.current_stage ?? payloadText(progress.current_stage),
    current_label: activity.current_label ?? payloadText(progress.current_label),
    completed: activity.completed ?? progressNumber(progress.completed),
    total: activity.total ?? progressNumber(progress.total),
    paused_reason: activity.paused_reason ?? payloadText(progress.paused_reason),
    resume_after: activity.resume_after ?? payloadText(progress.resume_after),
    errors: activity.errors ?? (Array.isArray(progress.errors) ? progress.errors : []),
    warnings: activity.warnings ?? (Array.isArray(progress.warnings) ? progress.warnings : []),
    model_states: activity.model_states ?? (Array.isArray(progress.model_states) ? (progress.model_states as ModelState[]) : [])
  };
}

export function activityProgressLabel(activity: ActivityRecord) {
  const progress = activityProgress(activity);
  const parts = [progress.current_label, progress.current_stage].filter(Boolean);
  if (typeof progress.completed === "number" && typeof progress.total === "number") {
    parts.push(`${progress.completed}/${progress.total}`);
  }
  return parts.join(" · ");
}

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
    throw await responseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
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
    throw await responseError(response);
  }
  return response.blob();
}

export const api = {
  health: () => apiFetch<{ status: string }>("/health"),
  sources: () => apiFetch<string[]>("/novels/sources"),
  inputAdapters: () => apiFetch<string[]>("/novels/input-adapters"),
  novels: () => apiFetch<NovelSummary[]>("/novels"),
  novel: (novelId: string) => apiFetch<NovelMetadata>(`/novels/${encodeURIComponent(novelId)}`),
  deleteNovel: (novelId: string) =>
    apiFetch<void>(`/novels/${encodeURIComponent(novelId)}`, {
      method: "DELETE"
    }),
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
  activity: (params: { status?: string; activity_type?: string; novel_id?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.activity_type) search.set("activity_type", params.activity_type);
    if (params.novel_id) search.set("novel_id", params.novel_id);
    search.set("limit", String(params.limit ?? 50));
    return apiFetch<{ activity: ActivityRecord[] }>(`/novels/activity?${search.toString()}`);
  },
  activityItem: (activityId: string) => apiFetch<ActivityRecord>(`/novels/activity/${encodeURIComponent(activityId)}`),
  deleteActivity: (activityId: string) =>
    apiFetch<void>(`/novels/activity/${encodeURIComponent(activityId)}`, {
      method: "DELETE"
    }),
  runActivity: (activityId: string) =>
    apiFetch<ActivityRecord>(`/novels/activity/${encodeURIComponent(activityId)}/run`, {
      method: "POST"
    }),
  runNextActivity: (activityType?: string) => {
    const suffix = activityType ? `?activity_type=${encodeURIComponent(activityType)}` : "";
    return apiFetch<ActivityRecord>(`/novels/activity/run-next${suffix}`, { method: "POST" });
  },
  updateActivityStatus: (activityId: string, payload: { status: string; error?: string; metadata?: Record<string, unknown> }) =>
    apiFetch<ActivityRecord>(`/novels/activity/${encodeURIComponent(activityId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  sourceHealth: () => apiFetch<{ sources: SourceHealth[] }>("/novels/activity/source-health"),
  sourceHealthDetail: (sourceKey: string) => apiFetch<SourceHealth>(`/novels/activity/source-health/${encodeURIComponent(sourceKey)}`),
  providerApiKeyStatus: (provider = "gemini") =>
    apiFetch<ProviderApiKeyStatus>(`/novels/admin/provider-api-key/${encodeURIComponent(provider)}`),
  setProviderApiKey: (payload: ProviderApiKeyValidationPayload & { api_key: string; apply_globally?: boolean; validate_connection?: boolean }) =>
    apiFetch<ProviderApiKeyStatus>("/novels/admin/provider-api-key", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  validateProviderApiKey: (payload: ProviderApiKeyValidationPayload) =>
    apiFetch<ProviderApiKeyStatus>("/novels/admin/provider-api-key/validate", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  clearProviderApiKey: (provider = "gemini") =>
    apiFetch<ProviderApiKeyStatus>(`/novels/admin/provider-api-key/${encodeURIComponent(provider)}`, {
      method: "DELETE"
    }),
  runtimeState: () => apiFetch<{ items: RuntimeStateItem[] }>("/novels/admin/runtime-state"),
  refreshRuntimeState: (key: string) =>
    apiFetch<RuntimeStateItem>(`/novels/admin/runtime-state/${encodeURIComponent(key)}/refresh`, {
      method: "POST"
    }),
  clearRuntimeState: (key: string) =>
    apiFetch<RuntimeStateItem>(`/novels/admin/runtime-state/${encodeURIComponent(key)}`, {
      method: "DELETE"
    }),
  workerStatus: () => apiFetch<WorkerStatus>("/novels/admin/worker"),
  workerStart: () => apiFetch<WorkerStatus>("/novels/admin/worker/start", { method: "POST" }),
  workerStop: () => apiFetch<WorkerStatus>("/novels/admin/worker/stop", { method: "POST" }),
  workerRunOnce: () => apiFetch<{ activity: ActivityRecord | null; worker: WorkerStatus }>("/novels/admin/worker/run-once", { method: "POST" }),
  requests: () => apiFetch<{ requests: NovelRequestRecord[] }>("/novels/requests?limit=50"),
  createRequest: (payload: { title: string; source_key?: string; source_url?: string; requested_by?: string; notes?: string }) =>
    apiFetch<NovelRequestRecord>("/novels/requests", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateRequestStatus: (requestId: string, payload: { status: string; reviewed_by?: string; notes?: string }) =>
    apiFetch<NovelRequestRecord>(`/novels/requests/${encodeURIComponent(requestId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  createCrawlActivity: (payload: { novel_id: string; source_key: string; kind: string; chapters?: string; source_url?: string; metadata?: Record<string, unknown> }) =>
    apiFetch<ActivityRecord>("/novels/activity/crawl", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTranslationActivity: (payload: CreateTranslationActivityPayload) =>
    apiFetch<ActivityRecord>("/novels/activity/translation", {
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
    payload: {
      source_key: string;
      chapters?: string;
      provider_key?: string;
      provider_model?: string;
      force?: boolean;
      source_language?: string;
      target_language?: string;
    }
  ) =>
    apiFetch<{ novel_id: string; status: string }>(`/novels/${encodeURIComponent(novelId)}/translate`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  exportNovel: (novelId: string, payload: { format: string; chapters?: string | null }) =>
    apiDownload(`/novels/${encodeURIComponent(novelId)}/export`, payload)
};
