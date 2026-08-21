import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  isPublicRequestAbortError,
  PUBLIC_REQUEST_TIMEOUT_MS,
  publicFetch,
} from "@/lib/public-api";

function installPendingFetch() {
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
}

describe("publicFetch request bounds", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    installPendingFetch();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("classifies a caller cancellation separately from a timeout", async () => {
    const controller = new AbortController();
    const request = publicFetch("/api/public/catalog", { signal: controller.signal });
    const settled = request.catch((value: unknown) => value);

    controller.abort();

    const error = await settled;
    expect(isPublicRequestAbortError(error)).toBe(true);
    if (isPublicRequestAbortError(error)) expect(error.reason).toBe("caller");
  });

  it("aborts a request at the shared timeout", async () => {
    const request = publicFetch("/api/public/catalog");
    const settled = request.catch((value: unknown) => value);

    await vi.advanceTimersByTimeAsync(PUBLIC_REQUEST_TIMEOUT_MS);

    const error = await settled;
    expect(isPublicRequestAbortError(error)).toBe(true);
    if (isPublicRequestAbortError(error)) expect(error.reason).toBe("timeout");
  });
});
