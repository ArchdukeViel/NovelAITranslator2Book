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

describe("admin glossary API client", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists glossary entries under encoded novel_id scope with filters", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse([]));
    const { adminApi } = await loadApi();

    await adminApi.listGlossaryEntries("novel/one", {
      status: "approved",
      term_type: "character",
      public_visible: false,
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/admin/novels/novel%2Fone/glossary?status=approved&term_type=character&public_visible=false",
    );
    expect(new Headers(fetchMock.mock.calls[0][1]?.headers).has("X-CSRF-Token")).toBe(false);
  });

  it("creates glossary entries through the shared request path with CSRF and JSON body", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ id: 1, novel_id: 12 }));
    const { adminApi } = await loadApi();

    await adminApi.createGlossaryEntry(12, {
      canonical_term: "Ellen",
      term_type: "character",
      approved_translation: "Ellen",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/csrf");
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/12/glossary");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(mutationInit?.body).toBe(
      JSON.stringify({
        canonical_term: "Ellen",
        term_type: "character",
        approved_translation: "Ellen",
      }),
    );
  });

  it("uses backend alias routes scoped by novel_id, not source identifiers", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ id: 7, novel_id: 99 }));
    const { adminApi } = await loadApi();

    await adminApi.updateGlossaryAlias("novel 99", "alias/7", {
      alias_text: "Auri",
      alias_type: "banned",
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/novel%2099/glossary/aliases/alias%2F7");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("source_site");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("source_novel_id");
    expect(mutationInit?.method).toBe("PATCH");
  });

  it("supports novel-level and entry-level glossary decision event routes", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValueOnce(jsonResponse([])).mockResolvedValueOnce(jsonResponse([]));
    const { adminApi } = await loadApi();

    await adminApi.listGlossaryDecisionEvents(42);
    await adminApi.listGlossaryDecisionEvents(42, "entry/3");

    expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/novels/42/glossary/events");
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/42/glossary/entries/entry%2F3/events");
  });

  it("updates QA finding status with encoded IDs and JSON body", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ id: 5, novel_id: 10 }));
    const { adminApi } = await loadApi();

    await adminApi.updateGlossaryQaFindingStatus("novel/10", "finding/5", {
      status: "dismissed",
      reviewer_notes: "Owner reviewed.",
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/admin/novels/novel%2F10/glossary/qa-findings/finding%2F5/status",
    );
    expect(mutationInit?.method).toBe("PATCH");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(mutationInit?.body).toBe(
      JSON.stringify({
        status: "dismissed",
        reviewer_notes: "Owner reviewed.",
      }),
    );
  });
});
