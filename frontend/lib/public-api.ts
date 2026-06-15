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
  HistoryEntry,
  LibraryMembership,
  NovelRequest,
  NovelRequestInput,
  PublicCatalogResponse,
  PublicChapterDetail,
  PublicChapterSummary,
  PublicNovelSummary,
  ReadingProgress,
  ReviewInput,
  ReviewResult,
} from "@/lib/public-types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

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
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) {
    throw await responseError(response);
  }
  return response;
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

async function publicPut<T>(path: string, body?: unknown): Promise<T> {
  const response = await publicFetch(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

async function publicDelete<T>(path: string): Promise<T> {
  const response = await publicFetch(path, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Public API client — /api/public/*
// ---------------------------------------------------------------------------

export const publicApi = {
  catalog(params: CatalogParams): Promise<PublicCatalogResponse> {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.status) search.set("status", params.status);
    if (params.language) search.set("language", params.language);
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
};

// ---------------------------------------------------------------------------
// Auth API client — /api/auth/*
// ---------------------------------------------------------------------------

export const authApi = {
  me(): Promise<AuthUser> {
    return publicGet<AuthUser>("/api/auth/me");
  },

  logout(): Promise<void> {
    return publicPost<void>("/api/auth/logout");
  },
};

// ---------------------------------------------------------------------------
// User API client — /api/user/*
// ---------------------------------------------------------------------------

export const userApi = {
  getLibraryItem(slug: string): Promise<LibraryMembership> {
    return publicGet<LibraryMembership>(
      `/api/user/library/${encodeURIComponent(slug)}`
    );
  },

  addToLibrary(slug: string): Promise<LibraryMembership> {
    return publicPost<LibraryMembership>(
      `/api/user/library/${encodeURIComponent(slug)}`
    );
  },

  removeFromLibrary(slug: string): Promise<void> {
    return publicDelete<void>(
      `/api/user/library/${encodeURIComponent(slug)}`
    );
  },

  getProgress(slug: string): Promise<ReadingProgress> {
    return publicGet<ReadingProgress>(
      `/api/user/progress/${encodeURIComponent(slug)}`
    );
  },

  putProgress(slug: string, chapterId: string): Promise<ReadingProgress> {
    return publicPut<ReadingProgress>(
      `/api/user/progress/${encodeURIComponent(slug)}`,
      { chapter_id: chapterId }
    );
  },

  recordHistory(slug: string, chapterId: string): Promise<void> {
    return publicPost<void>("/api/user/history", {
      slug,
      chapter_id: chapterId,
    });
  },

  listHistory(): Promise<HistoryEntry[]> {
    return publicGet<HistoryEntry[]>("/api/user/history");
  },

  postReview(slug: string, review: ReviewInput): Promise<ReviewResult> {
    return publicPost<ReviewResult>(
      `/api/user/reviews/${encodeURIComponent(slug)}`,
      review
    );
  },

  listRequests(): Promise<NovelRequest[]> {
    return publicGet<NovelRequest[]>("/api/user/requests");
  },

  createRequest(input: NovelRequestInput): Promise<NovelRequest> {
    return publicPost<NovelRequest>("/api/user/requests", input);
  },

};
