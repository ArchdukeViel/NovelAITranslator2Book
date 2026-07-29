import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import MaintenancePage from "./page";

const maintenanceStatus = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ api: { maintenanceStatus } }));

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MaintenancePage /></QueryClientProvider>);
}

describe("maintenance status page", () => {
  it("shows durable task status and redacted failure", async () => {
    maintenanceStatus.mockResolvedValue({
      status: "degraded",
      tasks: [{
        task_key: "fetch_cache_cleanup",
        schedule: "0 3 * * *",
        timezone: "UTC",
        enabled: true,
        state: "failed",
        last_started_at: "2026-07-29T02:59:00Z",
        last_finished_at: "2026-07-29T03:00:00Z",
        result: "failed",
        failure_summary: "Maintenance task failed; inspect redacted operator logs.",
        next_eligible_at: "2026-07-30T03:00:00Z",
      }],
    });

    renderPage();

    expect(screen.getByText("Loading maintenance status...")).toBeInTheDocument();
    expect(await screen.findByText("Fetch Cache Cleanup")).toBeInTheDocument();
    expect(screen.getByText("Maintenance task failed; inspect redacted operator logs.")).toBeInTheDocument();
    expect(screen.queryByText(/secret|private path/i)).not.toBeInTheDocument();
  });
});
