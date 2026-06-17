/**
 * SearchEntry tests.
 *
 * Confirms header search routes to /browse-novels?q=<encoded> correctly,
 * handles empty/whitespace queries, and does not pass include_adult=true.
 *
 * Feature: PUBLIC-SEARCH-1
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";

import { SearchEntry } from "@/components/public/search-entry";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mocks = vi.hoisted(() => ({
  pushFn: vi.fn(),
  getQueryParam: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.pushFn }),
  useSearchParams: () => ({
    get: mocks.getQueryParam,
    [Symbol.iterator]: function* () {},
  }),
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

let queryClient: QueryClient;

beforeEach(() => {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  vi.clearAllMocks();
  mocks.getQueryParam.mockReturnValue(null);
});

afterEach(() => {
  cleanup();
});

function renderSearchEntry() {
  return render(
    <QueryClientProvider client={queryClient}>
      <SearchEntry />
    </QueryClientProvider>
  );
}

/**
 * Set input value and submit the form via fireEvent.
 * Uses act() wrapping to flush React 18 batched state updates.
 */
function setInputAndSubmit(text: string) {
  renderSearchEntry();

  const input = screen.getByRole("searchbox", { name: /search novels/i });

  // First set the value — React 18 batches this
  act(() => {
    fireEvent.change(input, { target: { value: text } });
  });

  // Now find form and submit it — submit reads from React query state
  const form = input.closest("form")!;
  act(() => {
    fireEvent.submit(form);
  });
}

/**
 * Set URL q param, render, then submit the form.
 * The input initializes from URL, then submit reads from state.
 */
function initFromUrlThenSubmit(urlQ: string | null) {
  if (urlQ !== null) {
    mocks.getQueryParam.mockImplementation((key: string) =>
      key === "q" ? urlQ : null
    );
  }
  renderSearchEntry();
  const form = screen.getByRole("searchbox", { name: /search novels/i }).closest("form")!;
  act(() => {
    fireEvent.submit(form);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SearchEntry routing", () => {
  it("routes non-empty query to /browse-novels?q=<encoded>", () => {
    initFromUrlThenSubmit("test");

    expect(mocks.pushFn).toHaveBeenCalledTimes(1);
    expect(mocks.pushFn.mock.calls[0][0]).toBe("/browse-novels?q=test");
  });

  it("encodes special characters in query", () => {
    initFromUrlThenSubmit("日本語");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels?q=%E6%97%A5%E6%9C%AC%E8%AA%9E");
    expect(url).not.toContain("日本語");
  });

  it("encodes spaces as %20", () => {
    initFromUrlThenSubmit("two words");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels?q=two%20words");
  });

  it("encodes special URL characters", () => {
    initFromUrlThenSubmit("a&b=c?d");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels?q=a%26b%3Dc%3Fd");
  });

  it("trims whitespace before routing", () => {
    initFromUrlThenSubmit("  trimmed  ");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels?q=trimmed");
  });

  it("routes empty query to /browse-novels without q param", () => {
    initFromUrlThenSubmit("");

    expect(mocks.pushFn).toHaveBeenCalledTimes(1);
    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels");
    expect(url).not.toContain("q=");
  });

  it("routes whitespace-only query to /browse-novels without q param", () => {
    initFromUrlThenSubmit("   ");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).toBe("/browse-novels");
    expect(url).not.toContain("q=");
  });

  it("initializes from URL q param when present", () => {
    mocks.getQueryParam.mockImplementation((key: string) =>
      key === "q" ? "initial" : null
    );

    renderSearchEntry();

    const input = screen.getByRole("searchbox", { name: /search novels/i }) as HTMLInputElement;
    expect(input.value).toBe("initial");
  });

  it("initializes empty when no q param in URL", () => {
    renderSearchEntry();

    const input = screen.getByRole("searchbox", { name: /search novels/i }) as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("does not pass include_adult=true in router push", () => {
    initFromUrlThenSubmit("test");

    const url = mocks.pushFn.mock.calls[0][0] as string;
    expect(url).not.toContain("include_adult");
  });
});
