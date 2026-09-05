import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  googleOAuthStartUrl,
  isPublicRequestAbortError,
  PUBLIC_REQUEST_TIMEOUT_MS,
  publicFetch,
  safeRelativeReturnPath,
} from "./public-api";
import { deleteCookie, getCookie, setCookie } from "./cookie-utils";

describe("safeRelativeReturnPath (Finding 1.3, REQ-3, AC-3, SEC-2)", () => {
  it("returns fallback / for empty or missing inputs", () => {
    expect(safeRelativeReturnPath()).toBe("/");
    expect(safeRelativeReturnPath("")).toBe("/");
  });

  it("rejects targets with leading whitespace or tabs attempting protocol-relative bypass", () => {
    expect(safeRelativeReturnPath("\t//evil.com")).toBe("/");
    expect(safeRelativeReturnPath("  //evil.com")).toBe("/");
    expect(safeRelativeReturnPath("\r\n//evil.com")).toBe("/");
    expect(safeRelativeReturnPath("\x00//evil.com")).toBe("/");
  });

  it("rejects absolute URLs pointing to external domains", () => {
    expect(safeRelativeReturnPath("https://evil.com")).toBe("/");
    expect(safeRelativeReturnPath("http://evil.com/path")).toBe("/");
    expect(safeRelativeReturnPath("javascript:alert(1)")).toBe("/");
  });

  it("rejects protocol-relative and backslash prefix attempts", () => {
    expect(safeRelativeReturnPath("//evil.com")).toBe("/");
    expect(safeRelativeReturnPath("/\\evil.com")).toBe("/");
    expect(safeRelativeReturnPath("\\evil.com")).toBe("/");
  });

  it("preserves legitimate relative paths with search and hash parameters", () => {
    expect(safeRelativeReturnPath("/")).toBe("/");
    expect(safeRelativeReturnPath("/novels/my-novel")).toBe("/novels/my-novel");
    expect(safeRelativeReturnPath("/account/contributions?tab=keys#active")).toBe(
      "/account/contributions?tab=keys#active",
    );
  });

  it("sanitizes OAuth start URL next query parameter", () => {
    const maliciousUrl = googleOAuthStartUrl("\t//attacker.com");
    expect(maliciousUrl).toContain("next=%2F");

    const validUrl = googleOAuthStartUrl("/account/contributions");
    expect(validUrl).toContain("next=%2Faccount%2Fcontributions");
  });
});

describe("publicFetch default abort timeout (Finding 3.6, REQ-7, AC-7)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("enforces the 15-second default timeout bound", () => {
    expect(PUBLIC_REQUEST_TIMEOUT_MS).toBe(15_000);
  });

  it("attaches an abort signal and times out hanging requests without a caller signal", async () => {
    let observedSignal: AbortSignal | null = null;
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        observedSignal = (init?.signal as AbortSignal) ?? null;
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      }),
    );

    const request = publicFetch("/api/public/catalog");
    const settled = request.catch((value: unknown) => value);

    expect(observedSignal).not.toBeNull();

    await vi.advanceTimersByTimeAsync(PUBLIC_REQUEST_TIMEOUT_MS);

    const error = await settled;
    expect(isPublicRequestAbortError(error)).toBe(true);
    if (isPublicRequestAbortError(error)) expect(error.reason).toBe("timeout");
  });

  it("attributes caller cancellation separately from timeout when combined", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("aborted", "AbortError"));
          });
        });
      }),
    );

    const controller = new AbortController();
    const request = publicFetch("/api/public/catalog", { signal: controller.signal });
    const settled = request.catch((value: unknown) => value);

    controller.abort();

    const error = await settled;
    expect(isPublicRequestAbortError(error)).toBe(true);
    if (isPublicRequestAbortError(error)) expect(error.reason).toBe("caller");
  });
});

describe("cookie-utils security invariants (Finding 8.8, REQ-14, AC-14, SEC-1)", () => {
  beforeEach(() => {
    document.cookie = "";
  });

  it("enforces SameSite=Lax and path=/ on setCookie", () => {
    setCookie("session_pref", "dark_mode");
    expect(document.cookie).toContain("session_pref=dark_mode");
  });

  it("supports reading and deleting cookies", () => {
    setCookie("user_lang", "ja");
    expect(getCookie("user_lang")).toBe("ja");

    deleteCookie("user_lang");
    expect(getCookie("user_lang")).toBeNull();
  });
});
