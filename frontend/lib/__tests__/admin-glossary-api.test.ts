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

  it("previews glossary candidate import through the encoded backend route with CSRF and max_candidates", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "preview", candidates: [] }));
    const { adminApi } = await loadApi();

    await adminApi.previewGlossaryCandidateImport("novel/one", { max_candidates: 25 });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/csrf");
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/admin/novels/novel%2Fone/glossary/candidates/import/preview",
    );
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({ max_candidates: 25 });
    expect(body).not.toHaveProperty("provider");
    expect(body).not.toHaveProperty("provider_key");
    expect(body).not.toHaveProperty("provider_model");
    expect(body).not.toHaveProperty("rewrite_chapters");
    expect(body).not.toHaveProperty("repair_chapters");
  });

  it("applies glossary candidate import through the encoded backend route with CSRF and max_candidates", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "apply", candidates: [] }));
    const { adminApi } = await loadApi();

    await adminApi.applyGlossaryCandidateImport("novel one", { max_candidates: 10 });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/csrf");
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/admin/novels/novel%20one/glossary/candidates/import/apply",
    );
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({ max_candidates: 10 });
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("provider");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("repair");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("rewrite");
  });

  it("previews provider-assisted glossary candidates through the provider route with CSRF and full payload", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "preview", candidates: [] }));
    const { adminApi } = await loadApi();

    await adminApi.previewGlossaryProviderCandidates("novel/one", {
      max_candidates: 5,
      max_chapters: 1,
      max_chars: 4000,
      chapter_scope: "range",
      chapter_start: 10,
      chapter_end: 12,
      provider: "gemini",
      provider_model: "model-one",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/csrf");
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/admin/novels/novel%2Fone/glossary/candidates/provider/preview",
    );
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({
      max_candidates: 5,
      max_chapters: 1,
      max_chars: 4000,
      chapter_scope: "range",
      chapter_start: 10,
      chapter_end: 12,
      provider: "gemini",
      provider_model: "model-one",
    });
    expect(body).not.toHaveProperty("prompt_injection");
    expect(body).not.toHaveProperty("rewrite_chapters");
    expect(body).not.toHaveProperty("repair_chapters");
    expect(body).not.toHaveProperty("approve_candidates");
  });

  it("applies provider-assisted glossary candidates through the provider route with encoded novel_id", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "apply", candidates: [] }));
    const { adminApi } = await loadApi();

    await adminApi.applyGlossaryProviderCandidates("novel one", {
      max_candidates: 3,
      max_chapters: 2,
      max_chars: 3000,
      provider: "other",
      provider_model: "model two",
    });

    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/csrf");
    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe(
      "/api/admin/novels/novel%20one/glossary/candidates/provider/apply",
    );
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({
      max_candidates: 3,
      max_chapters: 2,
      max_chars: 3000,
      provider: "other",
      provider_model: "model two",
    });
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("/import/");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("repair");
    expect(String(fetchMock.mock.calls[1][0])).not.toContain("rewrite");
  });

  it("keeps no-provider import routes separate from provider-assisted routes", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "preview", candidates: [] }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "apply", candidates: [] }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "preview", candidates: [] }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, mode: "apply", candidates: [] }));
    const { adminApi } = await loadApi();

    await adminApi.previewGlossaryCandidateImport(12, { max_candidates: 1 });
    await adminApi.applyGlossaryCandidateImport(12, { max_candidates: 1 });
    await adminApi.previewGlossaryProviderCandidates(12, { max_candidates: 1 });
    await adminApi.applyGlossaryProviderCandidates(12, { max_candidates: 1 });

    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/12/glossary/candidates/import/preview");
    expect(fetchMock.mock.calls[2][0]).toBe("/api/admin/novels/12/glossary/candidates/import/apply");
    expect(fetchMock.mock.calls[3][0]).toBe("/api/admin/novels/12/glossary/candidates/provider/preview");
    expect(fetchMock.mock.calls[4][0]).toBe("/api/admin/novels/12/glossary/candidates/provider/apply");
  });

  it("does not expose glossary candidate repair, rewrite, prompt injection, or auto-approval client methods", async () => {
    const { adminApi } = await loadApi();
    const methods = Object.keys(adminApi);

    expect(methods).toContain("previewGlossaryCandidateImport");
    expect(methods).toContain("applyGlossaryCandidateImport");
    expect(methods).toContain("previewGlossaryProviderCandidates");
    expect(methods).toContain("applyGlossaryProviderCandidates");
    expect(methods).not.toContain("repairGlossaryCandidateImport");
    expect(methods).not.toContain("rewriteGlossaryCandidateImport");
    expect(methods).not.toContain("repairGlossaryChapters");
    expect(methods).not.toContain("rewriteGlossaryChapters");
    expect(methods).not.toContain("injectGlossaryPrompt");
    expect(methods).not.toContain("previewGlossaryPromptInjection");
    expect(methods).not.toContain("applyGlossaryPromptInjection");
    expect(methods).not.toContain("approveGlossaryProviderCandidates");
    expect(methods).not.toContain("autoApproveGlossaryCandidates");
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

  it("transitions glossary readiness status through encoded owner route with CSRF", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({ novel_id: 12, glossary_status: "glossary_skipped", glossary_revision: 0 }));
    const { adminApi } = await loadApi();

    await adminApi.transitionGlossaryStatus("novel/one", {
      target_status: "glossary_skipped",
      rationale: "Owner chose to translate now.",
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/novel%2Fone/glossary-status");
    expect(mutationInit?.method).toBe("PATCH");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(mutationInit?.body).toBe(
      JSON.stringify({
        target_status: "glossary_skipped",
        rationale: "Owner chose to translate now.",
      }),
    );
  });

  it("batch approves onboarding candidates through encoded owner route with CSRF", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "admin-csrf" }))
      .mockResolvedValueOnce(jsonResponse({
        novel_id: 12,
        approved_count: 2,
        glossary_status: "glossary_ready",
        glossary_revision: 3,
      }));
    const { adminApi } = await loadApi();

    await adminApi.batchApproveGlossaryCandidates("novel one", {
      rationale: "Ready for first translation.",
    });

    const [, mutationInit] = fetchMock.mock.calls[1];
    const headers = new Headers(mutationInit?.headers);
    const body = JSON.parse(String(mutationInit?.body)) as Record<string, unknown>;
    expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/novels/novel%20one/glossary/batch-approve");
    expect(mutationInit?.method).toBe("POST");
    expect(headers.get("X-CSRF-Token")).toBe("admin-csrf");
    expect(body).toEqual({ rationale: "Ready for first translation." });
    expect(body).not.toHaveProperty("provider");
    expect(body).not.toHaveProperty("rewrite_chapters");
    expect(body).not.toHaveProperty("repair_chapters");
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
