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
});
