import { useUiStore } from "@/lib/store";
import type {
  ActivityRecord,
  ApiErrorPayload,
  ApproveTranslationChangeRequest,
  ApproveTranslationChangeResponse,
  ChapterDetail,
  ChapterSummary,
  CreateTranslationActivityPayload,
  GlossaryAlias,
  GlossaryAliasCreatePayload,
  GlossaryAliasUpdatePayload,
  GlossaryCandidateImportRequest,
  GlossaryCandidateImportResult,
  GlossaryProviderCandidateRequest,
  GlossaryProviderCandidateResult,
  GlossaryDecisionEvent,
  GlossaryDecisionPayload,
  GlossaryEntry,
  GlossaryEntryCreatePayload,
  GlossaryEntryListFilters,
  GlossaryEntryStatusPayload,
  GlossaryEntryUpdatePayload,
  GlossaryProvenance,
  GlossaryProvenanceCreatePayload,
  GlossaryQAResponse,
  GlossaryOverride,
  GlossaryQAResult,
  GlossaryQaFinding,
  GlossaryQaFindingCreatePayload,
  GlossaryQaFindingListFilters,
  GlossaryQaFindingStatusPayload,
  GlossaryBatchApproveResult,
  GlossaryStatusTransitionPayload,
  GlossaryStatusTransitionResult,
  AdminReviewRecord,
  JobProgress,
  ModelState,
  MaintenanceStatusResponse,
  NovelMetadata,
  NovelPublicationSummary,
  NovelRequestRecord,
  NovelSummary,
  NovelTaxonomyRequest,
  NovelTaxonomyResponse,
  PreliminaryCrawlResult,
  ProviderApiKeyStatus,
  ProviderApiKeyValidationPayload,
  ProviderCredential,
  RuntimeStateItem,
  SchedulerHealthResponse,
  SchedulerSummary,
  SourceHealth,
  TranslatedChapter,
  TranslationEditHistory,
  TranslationVersion,
  WorkerStatus,
} from "@/lib/api-types";

export type * from "@/lib/api-types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "/api";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
let csrfTokenPromise: Promise<string> | null = null;

// ===========================================
// Shared low-level request helper (Task 3.1)
// Uses credentials: "include" to send HTTP-only Session_Cookie
// Does NOT read apiToken from store, does NOT set Authorization header
// ===========================================
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (!SAFE_METHODS.has(method) && path !== "/auth/csrf" && !headers.has(CSRF_HEADER_NAME)) {
    headers.set(CSRF_HEADER_NAME, await getCsrfToken());
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include", // Send HTTP-only Session_Cookie
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

async function getCsrfToken(): Promise<string> {
  csrfTokenPromise ??= request<{ csrf_token: string }>("/auth/csrf")
    .then((payload) => payload.csrf_token)
    .catch((error) => {
      csrfTokenPromise = null;
      throw error;
    });
  return csrfTokenPromise;
}

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

type RouteId = string | number;

function routeId(value: RouteId): string {
  return encodeURIComponent(String(value));
}

function metadataProgress(activity: ActivityRecord): Record<string, unknown> {
  const progress = activity.metadata?.progress;
  return progress && typeof progress === "object" && !Array.isArray(progress) ? (progress as Record<string, unknown>) : {};
}

export function activityProgress(activity: ActivityRecord): JobProgress {
  const progress = metadataProgress(activity);
  const metadata = activity.metadata ?? {};
  const progressErrors = Array.isArray(progress.errors) ? progress.errors : [];
  const metadataErrors = Array.isArray(metadata.errors) ? metadata.errors : [];
  const providerError = metadata.provider_error ? [metadata.provider_error] : [];
  const progressWarnings = Array.isArray(progress.warnings) ? progress.warnings : [];
  const metadataWarnings = Array.isArray(metadata.warnings) ? metadata.warnings : [];
  const progressModelStates = Array.isArray(progress.model_states) ? (progress.model_states as ModelState[]) : [];
  const metadataModelStates = Array.isArray(metadata.model_states) ? (metadata.model_states as ModelState[]) : [];
  return {
    status: activity.status,
    provider_key: activity.provider_key ?? payloadText(progress.provider_key) ?? payloadText(metadata.provider_key),
    provider_model: activity.provider_model ?? payloadText(progress.provider_model) ?? payloadText(metadata.provider_model),
    current_stage: activity.current_stage ?? payloadText(progress.current_stage) ?? payloadText(metadata.current_stage),
    current_label: activity.current_label ?? payloadText(progress.current_label) ?? payloadText(metadata.current_label),
    completed: activity.completed ?? progressNumber(progress.completed) ?? progressNumber(metadata.completed),
    total: activity.total ?? progressNumber(progress.total) ?? progressNumber(metadata.total),
    paused_reason: activity.paused_reason ?? payloadText(progress.paused_reason) ?? payloadText(metadata.paused_reason),
    resume_after: activity.resume_after ?? payloadText(progress.resume_after) ?? payloadText(metadata.resume_after),
    selection_reason: payloadText(progress.selection_reason) ?? payloadText(metadata.selection_reason),
    errors: activity.errors ?? (progressErrors.length ? progressErrors : [...metadataErrors, ...providerError]),
    warnings: activity.warnings ?? (progressWarnings.length ? progressWarnings : metadataWarnings),
    model_states: activity.model_states ?? (progressModelStates.length ? progressModelStates : metadataModelStates)
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

// Legacy fetch wrapper - now uses session cookie via request()
// Previously used Bearer token from store (apiToken), which is now decommissioned
// All endpoints now use credentials: "include" to send HTTP-only Session_Cookie
async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  return request<T>(path, { ...init, cache: init.cache ?? "no-store" });
}

export const api = {
  inputAdapters: () => apiFetch<string[]>("/admin/input-adapters"),
  novels: () => apiFetch<NovelSummary[]>("/admin/novels"),
  novel: (novelId: string) => apiFetch<NovelMetadata>(`/admin/novels/${encodeURIComponent(novelId)}`),
  deleteNovel: (novelId: string) =>
    apiFetch<void>(`/admin/novels/${encodeURIComponent(novelId)}`, {
      method: "DELETE"
    }),
  publishNovel: (novelId: string) =>
    apiFetch<NovelPublicationSummary>(`/admin/novels/${encodeURIComponent(novelId)}/publish`, {
      method: "POST"
    }),
  unpublishNovel: (novelId: string) =>
    apiFetch<NovelPublicationSummary>(`/admin/novels/${encodeURIComponent(novelId)}/unpublish`, {
      method: "POST"
    }),
  chapters: (novelId: string) => apiFetch<ChapterSummary[]>(`/admin/novels/${encodeURIComponent(novelId)}/chapters`),
  chapter: (novelId: string, chapterId: string) =>
    apiFetch<ChapterDetail>(`/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}`),
  translatedChapter: (novelId: string, chapterId: string) =>
    apiFetch<TranslatedChapter>(`/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated`),
  translationVersions: (novelId: string, chapterId: string) =>
    apiFetch<{ novel_id: string; chapter_id: string; versions: TranslationVersion[] }>(
      `/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/versions`
    ),
  translationEditHistory: (novelId: string, chapterId: string) =>
    apiFetch<{ novel_id: string; chapter_id: string; history: TranslationEditHistory[] }>(
      `/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/edit-history`
    ),
  updateTranslatedChapter: (
    novelId: string,
    chapterId: string,
    payload: {
      text: string;
      editor?: string;
      note?: string;
      lint?: boolean;
      source_text?: string;
      glossary_override?: GlossaryOverride;
    }
  ) =>
    apiFetch<TranslatedChapter & { glossary_qa?: GlossaryQAResult }>(
      `/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated`,
      {
        method: "PUT",
        body: JSON.stringify(payload)
      }
    ),
  lintTranslatedChapter: (
    novelId: string,
    chapterId: string,
    payload: { text: string; source_text?: string; max_terms?: number }
  ) =>
    apiFetch<GlossaryQAResponse>(
      `/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/lint`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  approveTranslationChange: (
    novelId: string,
    entryId: number,
    payload: ApproveTranslationChangeRequest
  ) =>
    apiFetch<ApproveTranslationChangeResponse>(
      `/admin/novels/${encodeURIComponent(novelId)}/glossary/entries/${entryId}/approve-translation-change`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  rollbackTranslatedChapter: (
    novelId: string,
    chapterId: string,
    payload: { version_id: string; editor?: string; note?: string }
  ) =>
    apiFetch<TranslatedChapter>(
      `/admin/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/translated/rollback`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  activity: (params: { status?: string; activity_type?: string; novel_id?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.activity_type) search.set("activity_type", params.activity_type);
    if (params.novel_id) search.set("novel_id", params.novel_id);
    search.set("limit", String(params.limit ?? 50));
    return apiFetch<{ activity: ActivityRecord[] }>(`/admin/activity?${search.toString()}`);
  },
  activityItem: (activityId: string) => apiFetch<ActivityRecord>(`/admin/activity/${encodeURIComponent(activityId)}`),
  deleteActivity: (activityId: string) =>
    apiFetch<void>(`/admin/activity/${encodeURIComponent(activityId)}`, {
      method: "DELETE"
    }),
  runActivity: (activityId: string) =>
    apiFetch<ActivityRecord>(`/admin/activity/${encodeURIComponent(activityId)}/run`, {
      method: "POST"
    }),
  retryActivity: (activityId: string) =>
    apiFetch<ActivityRecord>(`/admin/activity/${encodeURIComponent(activityId)}/retry`, {
      method: "POST"
    }),
  sourceHealth: () => apiFetch<{ sources: SourceHealth[] }>("/admin/activity/source-health"),
  providerApiKeyStatus: (provider = "gemini") =>
    apiFetch<ProviderApiKeyStatus>(`/admin/provider-api-key/${encodeURIComponent(provider)}`),
  setProviderApiKey: (payload: ProviderApiKeyValidationPayload & { api_key: string; apply_globally?: boolean; validate_connection?: boolean }) =>
    apiFetch<ProviderApiKeyStatus>("/admin/provider-api-key", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  runtimeState: () => apiFetch<{ items: RuntimeStateItem[] }>("/admin/runtime-state"),
  clearRuntimeState: (key: string) =>
    apiFetch<RuntimeStateItem>(`/admin/runtime-state/${encodeURIComponent(key)}`, {
      method: "DELETE"
    }),
  workerStatus: () => apiFetch<WorkerStatus>("/admin/worker"),
  workerStart: () => apiFetch<WorkerStatus>("/admin/worker/start", { method: "POST" }),
  workerStop: () => apiFetch<WorkerStatus>("/admin/worker/stop", { method: "POST" }),
  workerRunOnce: () => apiFetch<{ activity: ActivityRecord | null; worker: WorkerStatus }>("/admin/worker/run-once", { method: "POST" }),
  schedulerHealth: () => apiFetch<SchedulerHealthResponse>("/admin/translation/scheduler-health"),
  maintenanceStatus: () => apiFetch<MaintenanceStatusResponse>("/admin/maintenance/status"),
  requests: () => apiFetch<{ requests: NovelRequestRecord[] }>("/admin/requests?limit=50"),
  adminReviews: (params?: { status?: string; page?: number; page_size?: number }) => {
    const search = new URLSearchParams();
    if (params?.status) search.set("status", params.status);
    if (params?.page !== undefined) search.set("page", String(params.page));
    if (params?.page_size !== undefined) search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return apiFetch<{ items: AdminReviewRecord[]; total: number; page: number; page_size: number }>(
      `/admin/reviews${qs ? `?${qs}` : ""}`
    );
  },
  moderateReview: (reviewId: number, payload: { status: string; reviewer_notes?: string }) =>
    apiFetch<{ status: string }>(`/admin/reviews/${reviewId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateRequestStatus: (requestId: string, payload: { status: string; reviewed_by?: string; notes?: string }) =>
    apiFetch<NovelRequestRecord>(`/admin/requests/${encodeURIComponent(requestId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  createCrawlActivity: (payload: { novel_id: string; source_key: string; kind: string; chapters?: string; source_url?: string; metadata?: Record<string, unknown> }) =>
    apiFetch<ActivityRecord>("/admin/activity/crawl", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  createTranslationActivity: (payload: CreateTranslationActivityPayload) =>
    apiFetch<ActivityRecord>("/admin/activity/translation", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  preliminaryCrawl: (
    novelId: string,
    payload: { source_key?: string; identifier: string; mode?: string; max_chapter?: number | null }
  ) =>
    apiFetch<PreliminaryCrawlResult>(`/admin/novels/${encodeURIComponent(novelId)}/preliminary-crawl`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  importNow: (novelId: string, payload: { adapter_key: string; source: string; max_units?: number | null }) =>
    apiFetch<{ novel_id: string; adapter_key: string; chapters: number; document_type?: string | null }>(
      `/admin/novels/${encodeURIComponent(novelId)}/import`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  retranslateStale: (
    novelId: string,
    payload: {
      chapter_ids?: string[];
      provider_key?: string | null;
      provider_model?: string | null;
    }
  ) =>
    apiFetch<{
      novel_id: string;
      stale_chapter_count: number;
      scheduled_chapter_count: number;
      activity_id: string | null;
    }>(`/admin/novels/${encodeURIComponent(novelId)}/retranslate-stale`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  getTaxonomy: (novelId: string) =>
    apiFetch<NovelTaxonomyResponse>(`/admin/novels/${encodeURIComponent(novelId)}/taxonomy`),
  setTaxonomy: (novelId: string, payload: NovelTaxonomyRequest) =>
    apiFetch<NovelTaxonomyResponse>(`/admin/novels/${encodeURIComponent(novelId)}/taxonomy`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
};
// ===========================================
// Admin Auth namespace (Task 3.2)
// Uses the shared request() helper with session cookie
// ===========================================
export const adminAuth = {
  me: () => request<import("./api-types").AuthUser>("/auth/me"),
  ownerBootstrapLogin: (secret: string) =>
    request<import("./api-types").AuthUser>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ secret })
    }),
  logout: () => request<{ status: string }>("/auth/logout", { method: "POST" })
};

function appendQuery(path: string, search: URLSearchParams): string {
  const query = search.toString();
  return query ? `${path}?${query}` : path;
}

function glossaryEntryPath(novelId: RouteId, entryId: RouteId): string {
  return `/admin/novels/${routeId(novelId)}/glossary/entries/${routeId(entryId)}`;
}

// ===========================================
// Admin API namespace (Task 3.3)
// All admin endpoints targeting /api/admin/*
// Sends session cookie, never a bearer key
// ===========================================
type AdminApi = {
  listTakedowns: (status?: string) => Promise<import("./api-types").TakedownListResponse>;
  reviewTakedown: (requestId: number, payload: { status: string; reviewer_notes?: string }) => Promise<{ status: string }>;
  // ── Admin User Management ────────────────────────────────────────────
  listUsers: (filters?: import("./api-types").UserListFilters) => Promise<import("./api-types").UserListResponse>;
  getUser: (userId: number) => Promise<import("./api-types").UserDetail>;
  updateUserActive: (userId: number, payload: import("./api-types").ActiveUpdatePayload) => Promise<import("./api-types").UserDetail>;
  updateUserRole: (userId: number, payload: import("./api-types").RoleUpdatePayload) => Promise<import("./api-types").UserDetail>;
  revokeUserSessions: (userId: number, payload: import("./api-types").RevokeSessionsPayload) => Promise<import("./api-types").UserDetail>;
  // ── Glossary ─────────────────────────────────────────────────────────
  listGlossaryEntries: (novelId: RouteId, filters?: GlossaryEntryListFilters) => Promise<GlossaryEntry[]>;
  createGlossaryEntry: (novelId: RouteId, payload: GlossaryEntryCreatePayload) => Promise<GlossaryEntry>;
  previewGlossaryCandidateImport: (novelId: RouteId, payload?: GlossaryCandidateImportRequest) => Promise<GlossaryCandidateImportResult>;
  applyGlossaryCandidateImport: (novelId: RouteId, payload?: GlossaryCandidateImportRequest) => Promise<GlossaryCandidateImportResult>;
  previewGlossaryProviderCandidates: (novelId: RouteId, payload?: GlossaryProviderCandidateRequest) => Promise<GlossaryProviderCandidateResult>;
  applyGlossaryProviderCandidates: (novelId: RouteId, payload?: GlossaryProviderCandidateRequest) => Promise<GlossaryProviderCandidateResult>;
  getGlossaryEntry: (novelId: RouteId, entryId: RouteId) => Promise<GlossaryEntry>;
  updateGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload: GlossaryEntryUpdatePayload) => Promise<GlossaryEntry>;
  changeGlossaryEntryStatus: (novelId: RouteId, entryId: RouteId, payload: GlossaryEntryStatusPayload) => Promise<GlossaryEntry>;
  lockGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload?: GlossaryDecisionPayload) => Promise<GlossaryEntry>;
  unlockGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload?: GlossaryDecisionPayload) => Promise<GlossaryEntry>;
  deprecateGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload?: GlossaryDecisionPayload) => Promise<GlossaryEntry>;
  listGlossaryAliases: (novelId: RouteId, entryId: RouteId) => Promise<GlossaryAlias[]>;
  addGlossaryAlias: (novelId: RouteId, entryId: RouteId, payload: GlossaryAliasCreatePayload) => Promise<GlossaryAlias>;
  updateGlossaryAlias: (novelId: RouteId, aliasId: RouteId, payload: GlossaryAliasUpdatePayload) => Promise<GlossaryAlias>;
  deprecateGlossaryAlias: (novelId: RouteId, aliasId: RouteId, payload?: GlossaryDecisionPayload) => Promise<GlossaryAlias>;
  listGlossaryProvenanceForEntry: (novelId: RouteId, entryId: RouteId) => Promise<GlossaryProvenance[]>;
  listGlossaryProvenanceForNovel: (novelId: RouteId) => Promise<GlossaryProvenance[]>;
  addGlossaryProvenance: (novelId: RouteId, entryId: RouteId, payload: GlossaryProvenanceCreatePayload) => Promise<GlossaryProvenance>;
  listGlossaryDecisionEvents: (novelId: RouteId, entryId?: RouteId) => Promise<GlossaryDecisionEvent[]>;
  listGlossaryQaFindings: (novelId: RouteId, filters?: GlossaryQaFindingListFilters) => Promise<GlossaryQaFinding[]>;
  createGlossaryQaFinding: (novelId: RouteId, payload: GlossaryQaFindingCreatePayload) => Promise<GlossaryQaFinding>;
  updateGlossaryQaFindingStatus: (novelId: RouteId, findingId: RouteId, payload: GlossaryQaFindingStatusPayload) => Promise<GlossaryQaFinding>;
  transitionGlossaryStatus: (novelId: RouteId, payload: GlossaryStatusTransitionPayload) => Promise<GlossaryStatusTransitionResult>;
  batchApproveGlossaryCandidates: (novelId: RouteId, payload?: GlossaryDecisionPayload) => Promise<GlossaryBatchApproveResult>;
  providerCredential: (provider?: string) => Promise<ProviderCredential>;
  resumeOnboarding: (novelId: string, chapters?: string) => Promise<{ novel_id: string; onboarding_status: string; activity_id: string | null }>;
  cancelOnboarding: (novelId: string) => Promise<{ novel_id: string; onboarding_status: string }>;
  librarySummary: (params?: { refresh?: boolean }) => Promise<import("./api-types").LibrarySummaryResponse>;
  analyticsSummary: (params: {
    window: import("./api-types").AnalyticsWindow;
    timezone: import("./api-types").AnalyticsTimezone;
  }) => Promise<import("./api-types").AnalyticsSummary>;
  listAuditEvents: (
    filters?: import("./api-types").AuditEventListFilters,
  ) => Promise<import("./api-types").AuditEventListResponse>;
  getAuditEvent: (auditId: number) => Promise<import("./api-types").AuditEventDetail>;
  listProviderCredentialRows: () => Promise<import("./api-types").ProviderCredentialListResponse>;
  createProviderCredential: (
    payload: import("./api-types").ProviderCredentialCreatePayload,
  ) => Promise<import("./api-types").ProviderCredentialRow>;
  updateProviderCredential: (
    credentialId: string,
    payload: import("./api-types").ProviderCredentialUpdatePayload,
  ) => Promise<import("./api-types").ProviderCredentialRow>;
  deleteProviderCredential: (credentialId: string) => Promise<{ deleted: boolean }>;
  testProviderCredential: (
    credentialId: string,
    payload?: { api_key?: string; provider_model?: string | null },
  ) => Promise<import("./api-types").ProviderCredentialValidationResult>;
};

export const adminApi: AdminApi = {
  listTakedowns: (status) =>
    request<import("./api-types").TakedownListResponse>(
      `/admin/takedowns${status ? `?status=${encodeURIComponent(status)}` : ""}`,
    ),
  reviewTakedown: (requestId, payload) =>
    request<{ status: string }>(`/admin/takedowns/${requestId}/review`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // ── Admin User Management ────────────────────────────────────────────
  listUsers: (filters: import("./api-types").UserListFilters = {}) => {
    const search = new URLSearchParams();
    if (filters.role) search.set("role", filters.role);
    if (typeof filters.is_active === "boolean") search.set("is_active", String(filters.is_active));
    if (filters.search) search.set("search", filters.search);
    if (typeof filters.page === "number") search.set("page", String(filters.page));
    if (typeof filters.page_size === "number") search.set("page_size", String(filters.page_size));
    return request<import("./api-types").UserListResponse>(
      appendQuery("/admin/users", search)
    );
  },
  getUser: (userId: number) =>
    request<import("./api-types").UserDetail>(`/admin/users/${userId}`),
  updateUserActive: (userId: number, payload: import("./api-types").ActiveUpdatePayload) =>
    request<import("./api-types").UserDetail>(`/admin/users/${userId}/active`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  updateUserRole: (userId: number, payload: import("./api-types").RoleUpdatePayload) =>
    request<import("./api-types").UserDetail>(`/admin/users/${userId}/role`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  revokeUserSessions: (userId: number, payload: import("./api-types").RevokeSessionsPayload) =>
    request<import("./api-types").UserDetail>(`/admin/users/${userId}/revoke-sessions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  // ── Glossary ─────────────────────────────────────────────────────────
  listGlossaryEntries: (novelId: RouteId, filters: GlossaryEntryListFilters = {}) => {
    const search = new URLSearchParams();
    if (filters.status) search.set("status", filters.status);
    if (filters.term_type) search.set("term_type", filters.term_type);
    if (typeof filters.public_visible === "boolean") search.set("public_visible", String(filters.public_visible));
    return request<GlossaryEntry[]>(appendQuery(`/admin/novels/${routeId(novelId)}/glossary`, search));
  },
  createGlossaryEntry: (novelId: RouteId, payload: GlossaryEntryCreatePayload) =>
    request<GlossaryEntry>(`/admin/novels/${routeId(novelId)}/glossary`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  previewGlossaryCandidateImport: (novelId: RouteId, payload: GlossaryCandidateImportRequest = {}) =>
    request<GlossaryCandidateImportResult>(
      `/admin/novels/${routeId(novelId)}/glossary/candidates/import/preview`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  applyGlossaryCandidateImport: (novelId: RouteId, payload: GlossaryCandidateImportRequest = {}) =>
    request<GlossaryCandidateImportResult>(
      `/admin/novels/${routeId(novelId)}/glossary/candidates/import/apply`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  previewGlossaryProviderCandidates: (novelId: RouteId, payload: GlossaryProviderCandidateRequest = {}) =>
    request<GlossaryProviderCandidateResult>(
      `/admin/novels/${routeId(novelId)}/glossary/candidates/provider/preview`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  applyGlossaryProviderCandidates: (novelId: RouteId, payload: GlossaryProviderCandidateRequest = {}) =>
    request<GlossaryProviderCandidateResult>(
      `/admin/novels/${routeId(novelId)}/glossary/candidates/provider/apply`,
      {
        method: "POST",
        body: JSON.stringify(payload)
      }
    ),
  getGlossaryEntry: (novelId: RouteId, entryId: RouteId) =>
    request<GlossaryEntry>(glossaryEntryPath(novelId, entryId)),
  updateGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload: GlossaryEntryUpdatePayload) =>
    request<GlossaryEntry>(glossaryEntryPath(novelId, entryId), {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  changeGlossaryEntryStatus: (novelId: RouteId, entryId: RouteId, payload: GlossaryEntryStatusPayload) =>
    request<GlossaryEntry>(`${glossaryEntryPath(novelId, entryId)}/status`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  lockGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload: GlossaryDecisionPayload = {}) =>
    request<GlossaryEntry>(`${glossaryEntryPath(novelId, entryId)}/lock`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  unlockGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload: GlossaryDecisionPayload = {}) =>
    request<GlossaryEntry>(`${glossaryEntryPath(novelId, entryId)}/unlock`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  deprecateGlossaryEntry: (novelId: RouteId, entryId: RouteId, payload: GlossaryDecisionPayload = {}) =>
    request<GlossaryEntry>(`${glossaryEntryPath(novelId, entryId)}/deprecate`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listGlossaryAliases: (novelId: RouteId, entryId: RouteId) =>
    request<GlossaryAlias[]>(`${glossaryEntryPath(novelId, entryId)}/aliases`),
  addGlossaryAlias: (novelId: RouteId, entryId: RouteId, payload: GlossaryAliasCreatePayload) =>
    request<GlossaryAlias>(`${glossaryEntryPath(novelId, entryId)}/aliases`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateGlossaryAlias: (novelId: RouteId, aliasId: RouteId, payload: GlossaryAliasUpdatePayload) =>
    request<GlossaryAlias>(`/admin/novels/${routeId(novelId)}/glossary/aliases/${routeId(aliasId)}`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  deprecateGlossaryAlias: (novelId: RouteId, aliasId: RouteId, payload: GlossaryDecisionPayload = {}) =>
    request<GlossaryAlias>(`/admin/novels/${routeId(novelId)}/glossary/aliases/${routeId(aliasId)}/deprecate`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listGlossaryProvenanceForEntry: (novelId: RouteId, entryId: RouteId) =>
    request<GlossaryProvenance[]>(`${glossaryEntryPath(novelId, entryId)}/provenance`),
  listGlossaryProvenanceForNovel: (novelId: RouteId) =>
    request<GlossaryProvenance[]>(`/admin/novels/${routeId(novelId)}/glossary/provenance`),
  addGlossaryProvenance: (novelId: RouteId, entryId: RouteId, payload: GlossaryProvenanceCreatePayload) =>
    request<GlossaryProvenance>(`${glossaryEntryPath(novelId, entryId)}/provenance`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  listGlossaryDecisionEvents: (novelId: RouteId, entryId?: RouteId) =>
    request<GlossaryDecisionEvent[]>(
      entryId === undefined
        ? `/admin/novels/${routeId(novelId)}/glossary/events`
        : `${glossaryEntryPath(novelId, entryId)}/events`
    ),
  listGlossaryQaFindings: (novelId: RouteId, filters: GlossaryQaFindingListFilters = {}) => {
    const search = new URLSearchParams();
    if (typeof filters.chapter_id === "number") search.set("chapter_id", String(filters.chapter_id));
    if (filters.status) search.set("status", filters.status);
    return request<GlossaryQaFinding[]>(appendQuery(`/admin/novels/${routeId(novelId)}/glossary/qa-findings`, search));
  },
  createGlossaryQaFinding: (novelId: RouteId, payload: GlossaryQaFindingCreatePayload) =>
    request<GlossaryQaFinding>(`/admin/novels/${routeId(novelId)}/glossary/qa-findings`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  updateGlossaryQaFindingStatus: (novelId: RouteId, findingId: RouteId, payload: GlossaryQaFindingStatusPayload) =>
    request<GlossaryQaFinding>(`/admin/novels/${routeId(novelId)}/glossary/qa-findings/${routeId(findingId)}/status`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  transitionGlossaryStatus: (novelId: RouteId, payload: GlossaryStatusTransitionPayload) =>
    request<GlossaryStatusTransitionResult>(`/admin/novels/${routeId(novelId)}/glossary-status`, {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  batchApproveGlossaryCandidates: (novelId: RouteId, payload: GlossaryDecisionPayload = {}) =>
    request<GlossaryBatchApproveResult>(`/admin/novels/${routeId(novelId)}/glossary/batch-approve`, {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  // Active provider credential status used by the admin shell.
  providerCredential: (provider?: string) =>
    request<import("./api-types").ProviderCredential>(`/admin/providers/${provider ?? "gemini"}`),
  resumeOnboarding: (novelId: string, chapters = "all") =>
    request<{ novel_id: string; onboarding_status: string; activity_id: string | null }>(
      `/novels/${encodeURIComponent(novelId)}/onboarding/resume`,
      { method: "POST", body: JSON.stringify({ chapters }) }
    ),
  cancelOnboarding: (novelId: string) =>
    request<{ novel_id: string; onboarding_status: string }>(
      `/novels/${encodeURIComponent(novelId)}/onboarding/cancel`,
      { method: "POST", body: JSON.stringify({}) }
    ),
  librarySummary: (params?: { refresh?: boolean }) => {
    const search = new URLSearchParams();
    if (params?.refresh) search.set("refresh", "true");
    return request<import("./api-types").LibrarySummaryResponse>(
      appendQuery("/admin/library/summary", search)
    );
  },
  analyticsSummary: ({ window, timezone }) => {
    const search = new URLSearchParams({ window, timezone });
    return request<import("./api-types").AnalyticsSummary>(
      appendQuery("/admin/analytics/summary", search)
    );
  },
  // Audit log viewer (DEBT-054)
  listAuditEvents: (filters: import("./api-types").AuditEventListFilters = {}) => {
    const search = new URLSearchParams();
    if (filters.action) search.set("action", filters.action);
    if (typeof filters.actor_user_id === "number") search.set("actor_user_id", String(filters.actor_user_id));
    if (filters.target_type) search.set("target_type", filters.target_type);
    if (filters.target_id) search.set("target_id", filters.target_id);
    if (filters.status) search.set("status", filters.status);
    if (filters.severity) search.set("severity", filters.severity);
    if (filters.request_id) search.set("request_id", filters.request_id);
    if (filters.correlation_id) search.set("correlation_id", filters.correlation_id);
    if (filters.date_from) search.set("date_from", filters.date_from);
    if (filters.date_to) search.set("date_to", filters.date_to);
    if (typeof filters.page === "number") search.set("page", String(filters.page));
    if (typeof filters.page_size === "number") search.set("page_size", String(filters.page_size));
    return request<import("./api-types").AuditEventListResponse>(
      appendQuery("/admin/audit", search)
    );
  },
  getAuditEvent: (auditId: number) =>
    request<import("./api-types").AuditEventDetail>(
      `/admin/audit/${auditId}`
    ),
  // DEBT-023: Provider credential CRUD (owner-only).
  listProviderCredentialRows: () =>
    request<import("./api-types").ProviderCredentialListResponse>(
      "/admin/providers/credentials"
    ),
  createProviderCredential: (payload) =>
    request<import("./api-types").ProviderCredentialRow>(
      "/admin/providers/credentials",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  updateProviderCredential: (credentialId, payload) =>
    request<import("./api-types").ProviderCredentialRow>(
      `/admin/providers/credentials/${encodeURIComponent(credentialId)}`,
      { method: "PATCH", body: JSON.stringify(payload) }
    ),
  deleteProviderCredential: (credentialId) =>
    request<{ deleted: boolean }>(
      `/admin/providers/credentials/${encodeURIComponent(credentialId)}`,
      { method: "DELETE" }
    ),
  testProviderCredential: (credentialId, payload) =>
    request<import("./api-types").ProviderCredentialValidationResult>(
      `/admin/providers/credentials/${encodeURIComponent(credentialId)}/test`,
      {
        method: "POST",
        body: JSON.stringify(payload ?? {})
      }
    ),
};
