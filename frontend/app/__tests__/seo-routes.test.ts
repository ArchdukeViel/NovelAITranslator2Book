import { describe, it, expect, beforeEach, vi } from "vitest";
import robots from "@/app/robots";
import { default as sitemap } from "@/app/sitemap";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  process.env.NEXT_PUBLIC_SITE_URL = "https://dokushodo.example.com";
  process.env.NEXT_PUBLIC_API_URL = "https://api.example.com";
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// robots.txt
// ---------------------------------------------------------------------------

describe("robots.txt", () => {
  it("returns rules with allow and disallow", () => {
    const result = robots();
    expect(result.rules).toBeDefined();
    expect(Array.isArray(result.rules)).toBe(true);
  });

  it("allows root and disallows admin, api, login, auth, account", () => {
    const result = robots();
    const rule = Array.isArray(result.rules) ? result.rules[0] : result.rules;
    expect(rule.userAgent).toBe("*");
    expect(rule.allow).toBe("/");

    const disallow = rule.disallow ?? [];
    expect(disallow).toContain("/admin/");
    expect(disallow).toContain("/api/");
    expect(disallow).toContain("/login");
    expect(disallow).toContain("/auth/");
    expect(disallow).toContain("/account/");
  });

  it("includes sitemap URL", () => {
    const result = robots();
    expect(result.sitemap).toBe(
      "https://dokushodo.example.com/sitemap.xml",
    );
  });

  it("uses localhost fallback when SITE_URL is unset", () => {
    delete process.env.NEXT_PUBLIC_SITE_URL;
    const result = robots();
    expect(result.sitemap).toBe("http://localhost:3000/sitemap.xml");
  });
});

// ---------------------------------------------------------------------------
// sitemap.xml
// ---------------------------------------------------------------------------

describe("sitemap.xml", () => {
  it("includes static pages when API unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new Error("Network error"),
    );

    const result = await sitemap();

    expect(result.length).toBeGreaterThanOrEqual(7);
    const urls = result.map((e) => e.url);
    expect(urls).toContain(
      "https://dokushodo.example.com/home",
    );
    expect(urls).toContain(
      "https://dokushodo.example.com/browse-novels",
    );
    expect(urls).toContain(
      "https://dokushodo.example.com/about",
    );
  });

  it("includes novel entries from API response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          novels: [
            { slug: "my-novel", added_at: "2026-01-15T00:00:00Z" },
            { slug: "another-story", added_at: "2026-06-01T00:00:00Z" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await sitemap();

    const urls = result.map((e) => e.url);
    expect(urls).toContain(
      "https://dokushodo.example.com/novels/my-novel",
    );
    expect(urls).toContain(
      "https://dokushodo.example.com/novels/another-story",
    );
  });

  it("includes lastmod when available", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          novels: [
            {
              slug: "dated-novel",
              latest_chapter_updated_at: "2026-07-10T12:00:00Z",
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await sitemap();

    const novel = result.find((e) =>
      e.url.includes("dated-novel"),
    );
    expect(novel).toBeDefined();
    expect(novel!.lastModified).toBeDefined();
  });

  it("omits lastmod when no dates available", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          novels: [{ slug: "no-date-novel" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await sitemap();

    const novel = result.find((e) =>
      e.url.includes("no-date-novel"),
    );
    expect(novel).toBeDefined();
    expect(novel!.lastModified).toBeUndefined();
  });

  it("skips novels without a slug", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          novels: [
            { slug: "" },
            { slug: "valid-slug" },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await sitemap();

    const urls = result.map((e) => e.url);
    expect(urls).not.toContain("https://dokushodo.example.com/novels/");
    expect(urls).toContain(
      "https://dokushodo.example.com/novels/valid-slug",
    );
  });

  it("encodes special characters in slugs", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          novels: [{ slug: "my novel" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    const result = await sitemap();

    const novel = result.find((e) => e.url.includes("/novels/"));
    expect(novel!.url).toBe(
      "https://dokushodo.example.com/novels/my%20novel",
    );
  });
});
