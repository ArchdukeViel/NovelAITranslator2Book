import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SchedulerHealthCard } from "@/components/admin/scheduler-health-card";
import { api } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  api: {
    schedulerHealth: vi.fn(),
  },
}));

function renderWithClient(ui: React.ReactElement) {
  const testQueryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  });
  return render(
    <QueryClientProvider client={testQueryClient}>{ui}</QueryClientProvider>
  );
}

describe("SchedulerHealthCard component", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading state inside valid table DOM", async () => {
    vi.mocked(api.schedulerHealth).mockImplementation(
      () => new Promise(() => {})
    );
    const { container } = renderWithClient(<SchedulerHealthCard />);
    expect(screen.getByText("Scheduler health")).toBeTruthy();
    expect(screen.getByText("Loading scheduler health...")).toBeTruthy();

    // Ensure table structure is valid
    const table = container.querySelector("table");
    expect(table).not.toBeNull();
    expect(table?.querySelector("tbody")).not.toBeNull();
  });

  it("renders empty state when no runtime states exist", async () => {
    vi.mocked(api.schedulerHealth).mockResolvedValue({
      runtime_state_summary: {
        status: "healthy",
        active_cooldowns: 0,
        active_failures: 0,
        exhausted_scopes: 0,
        stale_scopes: 0,
        runtime_states: [],
      },
    } as unknown as Awaited<ReturnType<typeof api.schedulerHealth>>);

    renderWithClient(<SchedulerHealthCard />);

    await waitFor(() => {
      expect(screen.getByText("HEALTHY")).toBeTruthy();
      expect(screen.getByText("No persisted scheduler scopes")).toBeTruthy();
    });
  });

  it("renders table with runtime state rows when data present", async () => {
    vi.mocked(api.schedulerHealth).mockResolvedValue({
      runtime_state_summary: {
        status: "degraded",
        active_cooldowns: 1,
        active_failures: 1,
        exhausted_scopes: 0,
        stale_scopes: 0,
        runtime_states: [
          {
            scope_type: "provider",
            scope_key: "gemini",
            state: "cooling_down",
            reason: "rate_limit",
            next_eligible_at: "2026-08-12T12:00:00Z",
            consecutive_failures: 2,
          },
        ],
      },
    } as unknown as Awaited<ReturnType<typeof api.schedulerHealth>>);

    renderWithClient(<SchedulerHealthCard />);

    await waitFor(() => {
      expect(screen.getByText("DEGRADED")).toBeTruthy();
      expect(screen.getByText("provider/gemini")).toBeTruthy();
      expect(screen.getByText("cooling_down")).toBeTruthy();
      expect(screen.getByText("rate_limit")).toBeTruthy();
    });
  });
});
