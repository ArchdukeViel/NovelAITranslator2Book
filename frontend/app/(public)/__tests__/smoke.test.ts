/**
 * Smoke test — confirms the Vitest runner starts, the @/ path alias resolves,
 * and the jsdom environment is available. Does NOT test any admin behavior.
 *
 * Feature: public-reader-rework
 * Requirements: 16.5
 */
import { describe, it, expect } from "vitest";

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
});
