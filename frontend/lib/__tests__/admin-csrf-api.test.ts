import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

async function loadApi() {
  vi.resetModules();
  return import("../api");
}

describe("admin API CSRF wiring", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends X-CSRF-Token on representative admin POST mutations", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ configured: true }));
    const { api } = await loadApi();

    await api.setProviderApiKey({
      provider_key: "gemini",
      api_key: "AIza-test-key",
      validate_connection: false,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      "/api/auth/csrf",
      expect.objectContaining({ credentials: "include" }),
    );
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/provider-api-key");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
  });

  it("sends X-CSRF-Token on DELETE admin mutations", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const { api } = await loadApi();

    await api.deleteNovel("test-novel");

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/test-novel");
    expect(mutationInit?.method).toBe("DELETE");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
  });

  it("sends X-CSRF-Token on publish and unpublish mutations", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({
        novel_id: "test-novel",
        title: "Test Novel",
        is_published: true,
        chapter_count: 2,
        translated_count: 1,
        publication_status: "ongoing",
        visibility_warnings: [],
      }))
      .mockResolvedValueOnce(jsonResponse({
        novel_id: "test-novel",
        title: "Test Novel",
        is_published: false,
        chapter_count: 2,
        translated_count: 1,
        publication_status: "ongoing",
        visibility_warnings: [],
      }));
    const { api } = await loadApi();

    await api.publishNovel("test-novel");
    await api.unpublishNovel("test-novel");

    const [, publishInit] = fetchMock.mock.calls[1];
    const publishHeaders = new Headers(publishInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/test-novel/publish");
    expect(publishInit?.method).toBe("POST");
    expect(publishHeaders.get("X-CSRF-Token")).toBe("admin-csrf");

    const [, unpublishInit] = fetchMock.mock.calls[2];
    const unpublishHeaders = new Headers(unpublishInit?.headers);
    expect(fetchMock.mock.calls[2][0]).toBe("/api/admin/novels/test-novel/unpublish");
    expect(unpublishInit?.method).toBe("POST");
    expect(unpublishHeaders.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("does not fetch CSRF for safe admin GET calls", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse({ configured: false }));
    const { api } = await loadApi();

    await api.providerApiKeyStatus("gemini");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/provider-api-key/gemini");
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("sends X-CSRF-Token on admin downloads", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(new Response("book", { status: 200 }));
    const { api } = await loadApi();

    await api.exportNovel("test-novel", { format: "epub" });

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/test-novel/export");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
  });

  it("keeps runActivity on the pending-only run endpoint", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ id: "activity-1", type: "crawl", kind: "chapters", novel_id: "novel-1", status: "completed", retry_count: 0 }));
    const { api } = await loadApi();

    await api.runActivity("activity-1");

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/activity/activity-1/run");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
  });

  it("sends X-CSRF-Token on explicit activity retry", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ id: "activity-1", type: "crawl", kind: "chapters", novel_id: "novel-1", status: "pending", retry_count: 2 }));
    const { api } = await loadApi();

    await api.retryActivity("activity-1");

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/activity/activity-1/retry");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
  });

  it("sends translation activity glossary gate override through the shared CSRF request path", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({
        id: "activity-translation",
        type: "translation",
        kind: "translation",
        novel_id: "novel-1",
        status: "pending",
        retry_count: 0,
      }));
    const { api } = await loadApi();

    await api.createTranslationActivity({
      novel_id: "novel-1",
      source_key: "kakuyomu",
      chapters: "1",
      skip_glossary_gate: true,
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/activity/translation");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({
      novel_id: "novel-1",
      source_key: "kakuyomu",
      chapters: "1",
      skip_glossary_gate: true,
    });
  });
});
