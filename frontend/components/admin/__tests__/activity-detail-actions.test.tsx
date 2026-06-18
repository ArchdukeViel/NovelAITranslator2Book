import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ActivityDetailPage from "@/app/(admin)/admin/activity/[activityId]/page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ activityId: "novel-1" }),
}));

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function activityRecord(id: string, status: string) {
  return {
    id,
    type: "crawl",
    kind: "chapters",
    novel_id: "novel-1",
    source_key: "syosetu_ncode",
    chapters: "all",
    status,
    retry_count: status === "failed" ? 1 : 0,
    created_at: "2026-06-01T00:00:00Z",
    metadata: { activity_subtype: "scraping", activity_phase: "chapter_scrape" },
  };
}

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("activity detail actions", () => {
  it("runs pending activity through the run endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/csrf")) {
        return Promise.resolve(jsonResponse({ csrf_token: "admin-csrf" }));
      }
      if (url.includes("/api/admin/activity/activity-pending/run") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ ...activityRecord("activity-pending", "completed"), finished_at: "2026-06-01T00:01:00Z" }));
      }
      return Promise.resolve(jsonResponse({ activity: [activityRecord("activity-pending", "pending")] }));
    });

    renderWithQuery(<ActivityDetailPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Run" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/activity/activity-pending/run",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("retries failed activity through the retry endpoint", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/csrf")) {
        return Promise.resolve(jsonResponse({ csrf_token: "admin-csrf" }));
      }
      if (url.includes("/api/admin/activity/activity-failed/retry") && init?.method === "POST") {
        return Promise.resolve(jsonResponse(activityRecord("activity-failed", "pending")));
      }
      return Promise.resolve(jsonResponse({ activity: [activityRecord("activity-failed", "failed")] }));
    });

    renderWithQuery(<ActivityDetailPage />);

    await userEvent.click(await screen.findByRole("button", { name: "Retry" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/admin/activity/activity-failed/retry",
        expect.objectContaining({ method: "POST" }),
      );
    });
  });

  it("shows retry for cancelled activity and no mutation action for completed activity", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        activity: [
          activityRecord("activity-cancelled", "cancelled"),
          activityRecord("activity-completed", "completed"),
        ],
      }),
    );

    renderWithQuery(<ActivityDetailPage />);

    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run" })).not.toBeInTheDocument();
  });
});
