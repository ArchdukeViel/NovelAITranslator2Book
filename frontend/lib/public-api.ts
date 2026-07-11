/**
 * Public-scoped fetch client for the public reader surface.
 *
 * This module NEVER imports or reads `useUiStore().apiToken` from `lib/store.ts`
 * and NEVER sets an `Authorization` header. It uses `credentials: "include"` so
 * the HTTP-only session cookie is sent on all requests.
 *
 * Error parsing reuses the shared `ApiError` class from `lib/api.ts`.
 */

import { ApiError } from "@/lib/api";
import type { ApiErrorPayload } from "@/lib/api-types";
import type {
  AuthUser,
  CatalogParams,
  EmailPasswordAuthInput,
  HistoryListParams,
  HistoryListResponse,
  HistoryRecordInput,
  HistoryEntry,
  LibraryItem,
  ProgressInput,
  ProgressResponse,
  PublicRequestInput,
  PublicRequest,
  PublicCatalogResponse,
  PublicChapterDetail,
  PublicChapterSummary,
  PublicGenreResponse,
  PublicNovelSummary,
  PublicTagSearchResult,
  RegisterAuthInput,
  RequestListParams,
  RequestListResponse,
  ReviewInput,
  ReviewResponse,
  TagSearchParams,
} from "@/lib/public-types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";
const DEFAULT_PUBLIC_RETURN_TO = "/";
const CSRF_HEADER_NAME = "X-CSRF-Token";
let csrfTokenPromise: Promise<string> | null = null;

// ---------------------------------------------------------------------------
// Error parsing (mirrors lib/api.ts responseError logic, reuses ApiError class)
// ---------------------------------------------------------------------------

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
      message: response.statusText || `HTTP ${response.status}`,
    });
  }

  try {
    const payload = JSON.parse(body) as Record<string, unknown>;
    const detail = payload.detail;
    const nestedDetail =
      detail && typeof detail === "object" && !Array.isArray(detail)
        ? (detail as Record<string, unknown>)
        : null;
    const code =
      payloadText(payload.code) ||
      payloadText(payload.error) ||
      (nestedDetail
        ? payloadText(nestedDetail.code) || payloadText(nestedDetail.error)
        : null) ||
      `HTTP_${response.status}`;
    const message =
      payloadText(payload.message) ||
      payloadText(payload.detail) ||
      (nestedDetail
        ? payloadText(nestedDetail.message) || payloadText(nestedDetail.detail)
        : null) ||
      response.statusText ||
      `HTTP ${response.status}`;
    const explanation =
      payloadText(payload.explanation) ||
      (nestedDetail ? payloadText(nestedDetail.explanation) : null);
    const details =
      payload.details ?? (nestedDetail ? nestedDetail.details : undefined);
    const trace_id =
      payloadText(payload.trace_id) ||
      (nestedDetail ? payloadText(nestedDetail.trace_id) : null);
    return new ApiError({
      status: response.status,
      code,
      message,
      explanation,
      details,
      trace_id,
      raw: payload,
    } as ApiErrorPayload);
  } catch {
    return new ApiError({
      status: response.status,
      code: `HTTP_${response.status}`,
      message: body || response.statusText || `HTTP ${response.status}`,
      raw: body,
    } as ApiErrorPayload);
  }
}

// ---------------------------------------------------------------------------
// publicFetch — public-scoped fetch wrapper
// ---------------------------------------------------------------------------

export async function publicFetch(
  path: string,
  init?: RequestInit
): Promise<Response> {
  const method = (init?.method ?? "GET").toUpperCase();
  const unsafeMethod = !["GET", "HEAD", "OPTIONS"].includes(method);
  const headers = new Headers(init?.headers);
  if (unsafeMethod && path !== "/api/auth/csrf" && !headers.has(CSRF_HEADER_NAME)) {
    headers.set(CSRF_HEADER_NAME, await getCsrfToken());
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response;
}

async function getCsrfToken(): Promise<string> {
  csrfTokenPromise ??= publicGet<{ csrf_token: string }>("/api/auth/csrf")
    .then((payload) => payload.csrf_token)
    .catch((error) => {
      csrfTokenPromise = null;
      throw error;
    });
  return csrfTokenPromise;
}

// ---------------------------------------------------------------------------
// Internal typed helpers
// ---------------------------------------------------------------------------

async function publicGet<T>(path: string): Promise<T> {
  const response = await publicFetch(path);
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function publicPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await publicFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function publicPut<T>(path: string, body: unknown): Promise<T> {
  const response = await publicFetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function publicDelete(path: string): Promise<void> {
  await publicFetch(path, { method: "DELETE" });
}

async function publicHead(path: string): Promise<{ available: boolean }> {
  const response = await publicFetch(path, { method: "HEAD" });
  return { available: response.status !== 503 };
}

function safeRelativeReturnPath(returnTo?: string): string {
  if (!returnTo || !returnTo.startsWith("/") || returnTo.startsWith("//")) {
    return DEFAULT_PUBLIC_RETURN_TO;
  }
  try {
    const parsed = new URL(returnTo, "http://novelai.local");
    if (parsed.origin !== "http://novelai.local") {
      return DEFAULT_PUBLIC_RETURN_TO;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return DEFAULT_PUBLIC_RETURN_TO;
  }
}

export function googleOAuthStartUrl(returnTo?: string): string {
  const safeReturnTo = safeRelativeReturnPath(returnTo);
  const search = new URLSearchParams({ next: safeReturnTo });
  return `${API_BASE_URL}/api/auth/google/start?${search.toString()}`;
}

// ---------------------------------------------------------------------------
// Public API client — /api/public/*
// ---------------------------------------------------------------------------

export const publicApi = {
  catalog(params: CatalogParams): Promise<PublicCatalogResponse> {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.status) search.set("status", params.status);
    if (params.sort_by) search.set("sort_by", params.sort_by);
    if (params.order) search.set("order", params.order);
    if (params.min_chapters !== undefined)
      search.set("min_chapters", String(params.min_chapters));
    if (params.max_chapters !== undefined)
      search.set("max_chapters", String(params.max_chapters));
    if (params.genre_include) search.set("genre_include", params.genre_include);
    if (params.genre_exclude) search.set("genre_exclude", params.genre_exclude);
    if (params.tag_include) search.set("tag_include", params.tag_include);
    if (params.tag_exclude) search.set("tag_exclude", params.tag_exclude);
    if (params.page !== undefined) search.set("page", String(params.page));
    if (params.page_size !== undefined)
      search.set("page_size", String(params.page_size));
    const qs = search.toString();
    return publicGet<PublicCatalogResponse>(
      `/api/public/catalog${qs ? `?${qs}` : ""}`
    );
  },

  novel(slug: string): Promise<PublicNovelSummary> {
    return publicGet<PublicNovelSummary>(
      `/api/public/novels/${encodeURIComponent(slug)}`
    );
  },

  chapters(slug: string): Promise<PublicChapterSummary[]> {
    return publicGet<PublicChapterSummary[]>(
      `/api/public/novels/${encodeURIComponent(slug)}/chapters`
    );
  },

  chapter(slug: string, chapterId: string): Promise<PublicChapterDetail> {
    return publicGet<PublicChapterDetail>(
      `/api/public/novels/${encodeURIComponent(slug)}/chapters/${encodeURIComponent(chapterId)}`
    );
  },

  genres(params?: { include_adult?: boolean }): Promise<PublicGenreResponse[]> {
    const search = new URLSearchParams();
    if (params?.include_adult !== undefined)
      search.set("include_adult", String(params.include_adult));
    const qs = search.toString();
    return publicGet<PublicGenreResponse[]>(
      `/api/public/genres${qs ? `?${qs}` : ""}`
    );
  },

  searchTags(params: TagSearchParams): Promise<PublicTagSearchResult[]> {
    const search = new URLSearchParams();
    search.set("q", params.q);
    if (params.include_adult !== undefined)
      search.set("include_adult", String(params.include_adult));
    if (params.limit !== undefined)
      search.set("limit", String(params.limit));
    return publicGet<PublicTagSearchResult[]>(
      `/api/public/tags/search?${search.toString()}`
    );
  },
};

// ---------------------------------------------------------------------------
// Auth API client — /api/auth/*
// ---------------------------------------------------------------------------

export const authApi = {
  csrf(): Promise<{ csrf_token: string }> {
    return publicGet<{ csrf_token: string }>("/api/auth/csrf");
  },

  me(): Promise<AuthUser> {
    return publicGet<AuthUser>("/api/auth/me");
  },

  logout(): Promise<void> {
    return publicPost<void>("/api/auth/logout");
  },

  googleStart(returnTo?: string): string {
    return googleOAuthStartUrl(returnTo);
  },

  googleStartCheck(): Promise<{ available: boolean }> {
    return publicHead("/api/auth/google/start");
  },

  passwordLogin(input: EmailPasswordAuthInput): Promise<AuthUser> {
    return publicPost<AuthUser>("/api/auth/password/login", input);
  },

  register(input: RegisterAuthInput): Promise<AuthUser> {
    return publicPost<AuthUser>("/api/auth/register", input);
  },
};

// ---------------------------------------------------------------------------
// Reading-state API client - /api/user/library, /progress, /history only
// ---------------------------------------------------------------------------

export const userReadingApi = {
  getLibrary(): Promise<LibraryItem[]> {
    return publicGet<LibraryItem[]>("/api/user/library");
  },

  getLibraryItem(slug: string): Promise<LibraryItem> {
    return publicGet<LibraryItem>(
      `/api/user/library/${encodeURIComponent(slug)}`
    );
  },

  addToLibrary(slug: string): Promise<LibraryItem> {
    return publicPost<LibraryItem>(
      `/api/user/library/${encodeURIComponent(slug)}`
    );
  },

  removeFromLibrary(slug: string): Promise<void> {
    return publicDelete(`/api/user/library/${encodeURIComponent(slug)}`);
  },

  getProgress(slug: string): Promise<ProgressResponse> {
    return publicGet<ProgressResponse>(
      `/api/user/progress/${encodeURIComponent(slug)}`
    );
  },

  putProgress(slug: string, input: ProgressInput): Promise<ProgressResponse> {
    return publicPut<ProgressResponse>(
      `/api/user/progress/${encodeURIComponent(slug)}`,
      input
    );
  },

  listHistory(params: HistoryListParams = {}): Promise<HistoryListResponse> {
    const search = new URLSearchParams();
    if (params.limit !== undefined) {
      search.set("limit", String(params.limit));
    }
    const qs = search.toString();
    return publicGet<HistoryListResponse>(
      `/api/user/history${qs ? `?${qs}` : ""}`
    );
  },

  recordHistory(input: HistoryRecordInput): Promise<HistoryEntry> {
    return publicPost<HistoryEntry>("/api/user/history", input);
  },
};

// ---------------------------------------------------------------------------
// Engagement API client - reviews/ratings and public requests only
// ---------------------------------------------------------------------------

export const userEngagementApi = {
  putReview(slug: string, input: ReviewInput): Promise<ReviewResponse> {
    return publicPut<ReviewResponse>(
      `/api/user/reviews/${encodeURIComponent(slug)}`,
      input
    );
  },

  deleteReview(slug: string): Promise<void> {
    return publicDelete(`/api/user/reviews/${encodeURIComponent(slug)}`);
  },

  listRequests(params: RequestListParams = {}): Promise<RequestListResponse> {
    const search = new URLSearchParams();
    if (params.limit !== undefined) {
      search.set("limit", String(params.limit));
    }
    const qs = search.toString();
    return publicGet<RequestListResponse>(
      `/api/user/requests${qs ? `?${qs}` : ""}`
    );
  },

  createRequest(input: PublicRequestInput): Promise<PublicRequest> {
    return publicPost<PublicRequest>("/api/user/requests", input);
  },
};
