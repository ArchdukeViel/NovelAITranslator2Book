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

  it("does not expose active public user API methods", () => {
    const publicApi = readFileSync("lib/public-api.ts", "utf8");

    expect(publicApi).not.toContain("/api/user/");
    expect(publicApi).not.toContain("userApi");
    expect(publicApi).not.toContain("getLibraryItem");
    expect(publicApi).not.toContain("putProgress");
    expect(publicApi).not.toContain("recordHistory");
    expect(publicApi).not.toContain("postReview");
    expect(publicApi).not.toContain("createRequest");
  });

  it("does not export public user action hooks from the hook barrel", () => {
    const publicHooks = readFileSync("hooks/public/index.ts", "utf8");

    expect(publicHooks).toContain("useCatalog");
    expect(publicHooks).toContain("useNovel");
    expect(publicHooks).toContain("useChapters");
    expect(publicHooks).toContain("useChapter");
    expect(publicHooks).not.toContain("useLibrary");
    expect(publicHooks).not.toContain("useProgress");
    expect(publicHooks).not.toContain("useHistory");
    expect(publicHooks).not.toContain("useRequests");
    expect(publicHooks).not.toContain("usePostReview");
  });
});
