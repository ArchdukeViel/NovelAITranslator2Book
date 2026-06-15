import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import DashboardPage from "@/app/(admin)/admin/dashboard/page";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

const owner = {
  user_id: 1,
  email: "admin@example.com",
  role: "owner",
  is_authenticated: true,
  is_owner: true,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("admin dashboard safety", () => {
  it("displays error banner when worker status query fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/worker")) {
        return Promise.reject(new Error("Worker fetch failed"));
      }
      return Promise.resolve(jsonResponse({ activity: [], requests: [], sources: [] }));
    });

    renderWithQuery(<DashboardPage />);
    expect(await screen.findByText(/worker fetch failed/i)).toBeInTheDocument();
  });

  it("shows 'Run Once' button with accessible explanation", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ activity: [], requests: [], worker: { running: false }, sources: [] })
    );

    renderWithQuery(<DashboardPage />);

    const runOnceButton = await screen.findByRole("button", { name: /run worker once to process a single pending batch/i });
    expect(runOnceButton).toBeInTheDocument();
    expect(runOnceButton).toHaveTextContent(/run once/i);
    expect(runOnceButton).toHaveAttribute("title", "Processes one pending batch/activity without starting the continuous worker.");
  });

  it("requires confirmation before stopping the worker", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/worker/stop") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ running: false }));
      }
      return Promise.resolve(jsonResponse({ activity: [], requests: [], worker: { running: true }, sources: [] }));
    });

    renderWithQuery(<DashboardPage />);

    const stopButton = await screen.findByRole("button", { name: /stop/i });
    await userEvent.click(stopButton);

    expect(await screen.findByRole("heading", { name: /stop worker/i })).toBeInTheDocument();
    
    // Check dialog contains the warning text (using getAllByText since it appears twice in dialog)
    const warningTexts = screen.getAllByText(/pause all pending translation and crawl jobs/i);
    expect(warningTexts.length).toBeGreaterThan(0);

    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/admin/worker/stop"),
      expect.objectContaining({ method: "POST" })
    );

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole("heading", { name: /stop worker/i })).not.toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/admin/worker/stop"),
      expect.objectContaining({ method: "POST" })
    );
  });

  it("calls stop API when confirmation is accepted", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/worker/stop") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ running: false }));
      }
      return Promise.resolve(jsonResponse({ activity: [], requests: [], worker: { running: true }, sources: [] }));
    });

    renderWithQuery(<DashboardPage />);

    const stopButton = await screen.findByRole("button", { name: /stop/i });
    await userEvent.click(stopButton);

    const confirmButton = await screen.findByRole("button", { name: /stop worker/i });
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/worker/stop"),
        expect.objectContaining({ method: "POST" })
      );
    });
  });
});
