/**
 * Smoke test — confirms the Vitest runner starts, the @/ path alias resolves,
 * and the jsdom environment is available. Does NOT test any admin behavior.
 *
 * Feature: public-reader-rework
 * Requirements: 16.5
 */
import { describe, it, expect } from "vitest";
import { existsSync, readFileSync } from "node:fs";

// Verify the @/ alias resolves to the frontend root by importing a known module.
// lib/utils.ts is a pure utility with no heavy side-effects.
import { cn } from "@/lib/utils";

describe("PBT harness smoke test", () => {
  it("vitest runner is operational", () => {
    expect(true).toBe(true);
  });

  it("@/ path alias resolves correctly", () => {
    // If the import above resolved, the alias works. Verify we get the function.
    expect(cn).toBeDefined();
    expect(typeof cn).toBe("function");
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("jsdom environment is available", () => {
    expect(typeof document).toBe("object");
    expect(typeof window).toBe("object");
  });

  it("localStorage/sessionStorage shims are functional", () => {
    localStorage.setItem("test-key", "test-value");
    expect(localStorage.getItem("test-key")).toBe("test-value");
    localStorage.removeItem("test-key");
    expect(localStorage.getItem("test-key")).toBeNull();
  });

  it("keeps public novel pages on the plural /novels route only", () => {
    expect(existsSync("app/(public)/novels/[slug]/page.tsx")).toBe(true);
    expect(existsSync("app/(public)/novels/[slug]/chapter/[chapterId]/page.tsx")).toBe(true);
    expect(existsSync("app/(public)/novel/[slug]/page.tsx")).toBe(false);
    expect(existsSync("app/(public)/novel/[slug]/chapter/[chapterId]/page.tsx")).toBe(false);

    const nextConfig = readFileSync("next.config.mjs", "utf8");
    expect(nextConfig).not.toContain("/novel/:slug");
    expect(nextConfig).not.toContain("redirects()");
  });
});
