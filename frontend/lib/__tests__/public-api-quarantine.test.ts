import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("public API quarantine", () => {
  it("keeps guest reader API methods available", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");

    expect(publicApi).toContain("catalog(params");
    expect(publicApi).toContain("novel(slug");
    expect(publicApi).toContain("chapters(slug");
    expect(publicApi).toContain("chapter(slug");
    expect(publicApi).toContain("/api/public/catalog");
    expect(publicApi).toContain("/api/public/novels/");
  });

  it("exposes only reading-state and B5 engagement public user API methods", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");

    expect(publicApi).toContain("userReadingApi");
    expect(publicApi).toContain("userEngagementApi");
    expect(publicApi).toContain("/api/user/library");
    expect(publicApi).toContain("/api/user/progress/");
    expect(publicApi).toContain("/api/user/history");
    expect(publicApi).toContain("/api/user/reviews");
    expect(publicApi).toContain("/api/user/requests");
    expect(publicApi).not.toContain("userApi");
    expect(publicApi).not.toContain("/api/user/contributions");
    expect(publicApi).not.toContain("submitContribution");
  });

  it("exports only safe reading-state and engagement hooks from the hook barrel", () => {
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicHooks).toContain("useCatalog");
    expect(publicHooks).toContain("useNovel");
    expect(publicHooks).toContain("useChapters");
    expect(publicHooks).toContain("useChapter");
    expect(publicHooks).toContain("useLibrary");
    expect(publicHooks).toContain("useProgress");
    expect(publicHooks).toContain("useHistory");
    expect(publicHooks).toContain("useRecordHistory");
    expect(publicHooks).toContain("useRequests");
    expect(publicHooks).toContain("useCreateRequest");
    expect(publicHooks).toContain("useUpsertReview");
    expect(publicHooks).toContain("useDeleteReview");
    expect(publicHooks).not.toContain("useContribution");
  });
});
