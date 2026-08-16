import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { readFileSync } from "node:fs";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AnalyticsPage from "@/app/(admin)/admin/analytics/page";
import type { AnalyticsSummary } from "@/lib/api-types";

const analyticsSummary = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    adminApi: { ...actual.adminApi, analyticsSummary: (...args: unknown[]) => analyticsSummary(...args) },
  };
});

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function summary(overrides: Partial<AnalyticsSummary> = {}): AnalyticsSummary {
  return {
    enabled: true,
    window: "24h",
    timezone: "UTC",
    generated_at: "2026-07-27T12:00:00+00:00",
    cutoff_at: "2026-07-26T12:00:00+00:00",
    status: "ok",
    groups: {
      views: { "public_novel.view": 3, "public_chapter.view": 2 },
      search: { "search.performed": 4 },
      features: { "glossary_annotation.opened": 5 },
      top_novels: [],
    },
    failed_groups: [],
    ...overrides,
  };
}

afterEach(() => {
  vi.clearAllMocks();
  vi.restoreAllMocks();
  cleanup();
});

describe("AnalyticsPage", () => {
  it("shows loading then aggregate data and metadata", async () => {
    let resolve!: (value: AnalyticsSummary) => void;
    analyticsSummary.mockReturnValue(new Promise<AnalyticsSummary>((done) => { resolve = done; }));
    renderWithQuery(<AnalyticsPage />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading analytics");
    resolve(summary());

    expect(await screen.findByText("public novel view")).toBeInTheDocument();
    expect(screen.getByText(/Generated 2026-07-27T12:00:00\+00:00 · UTC · 24h · ok/)).toBeInTheDocument();
    expect(screen.getAllByText("5")).toHaveLength(3);
  });

  it("shows zero-data empty state", async () => {
    analyticsSummary.mockResolvedValue(summary({
      groups: { views: {}, search: {}, features: {}, top_novels: [] },
    }));
    renderWithQuery(<AnalyticsPage />);

    expect(await screen.findByText("No analytics events in this window.")).toBeInTheDocument();
  });

  it("shows unavailable partial group", async () => {
    analyticsSummary.mockResolvedValue(summary({ status: "partial", failed_groups: ["search"] }));
    renderWithQuery(<AnalyticsPage />);

    expect(await screen.findByText("Some groups are unavailable.")).toBeInTheDocument();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThanOrEqual(1);
  });

  it("shows safe error", async () => {
    analyticsSummary.mockRejectedValue(new Error("network down"));
    renderWithQuery(<AnalyticsPage />);

    expect(await screen.findByText(/network down/i)).toBeInTheDocument();
  });

  it("changes window and refetches", async () => {
    analyticsSummary.mockResolvedValue(summary());
    const user = userEvent.setup();
    renderWithQuery(<AnalyticsPage />);
    await screen.findByText("public novel view");

    await user.selectOptions(screen.getByLabelText("Window"), "1h");
    await waitFor(() => expect(analyticsSummary).toHaveBeenLastCalledWith({ window: "1h", timezone: "UTC" }));
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(analyticsSummary).toHaveBeenCalledTimes(3));
  });

  it("does not render user-level or sensitive fields", () => {
    const page = readFileSync("app/(admin)/admin/analytics/page.tsx", "utf8");
    expect(page).not.toContain("top_novels");
    expect(page).not.toContain("user_id");
    expect(page).not.toContain("session_id");
    expect(page).not.toContain("metadata");
  });
});
