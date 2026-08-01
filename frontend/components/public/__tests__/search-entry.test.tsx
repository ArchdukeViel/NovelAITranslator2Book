/**
 * SearchEntry tests.
 *
 * The desktop header search field is now a button that opens the one shared
 * search overlay (DESIGN.md — Search contract); it no longer submits a form
 * or routes to /browse-novels itself.
 *
 * Feature: PUBLIC-SEARCH-1, DEBT-FE-04
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";

import { SearchEntry } from "@/components/public/search-entry";
import { useSearchOverlay } from "@/lib/search-overlay";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  openFn: vi.fn(),
}));

vi.mock("@/lib/search-overlay", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/search-overlay")>();
  return {
    ...actual,
    useSearchOverlay: (selector?: unknown) =>
      typeof selector === "function"
        ? selector({ open: mocks.openFn, isOpen: false, close: vi.fn() })
        : { open: mocks.openFn, isOpen: false, close: vi.fn() },
  };
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SearchEntry overlay trigger", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders as a search-lookalike button", () => {
    render(<SearchEntry />);
    const button = screen.getByRole("button", { name: /search novels/i });
    expect(button.tagName).toBe("BUTTON");
  });

  it("opens the shared search overlay on click", () => {
    render(<SearchEntry />);
    fireEvent.click(screen.getByRole("button", { name: /search novels/i }));
    expect(mocks.openFn).toHaveBeenCalledTimes(1);
  });

  it("does not push a route or render a form", () => {
    render(<SearchEntry />);
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument();
    expect(document.querySelector("form")).toBeNull();
  });
});
