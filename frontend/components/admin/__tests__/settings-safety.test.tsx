import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import SettingsPage from "@/app/(admin)/admin/settings/page";

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

describe("admin settings safety", () => {
  it("requires confirmation before clearing runtime state", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/runtime-state") && !init?.method) {
        return Promise.resolve(jsonResponse({
          items: [
            { key: "test_state", label: "Test State", size_bytes: 1024, updated_at: "2026-06-15T00:00:00Z" }
          ]
        }));
      }
      if (url.includes("/admin/runtime-state/test_state") && init?.method === "DELETE") {
        return Promise.resolve(jsonResponse({}));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<SettingsPage />);

    const clearButton = await screen.findByRole("button", { name: /clear test_state/i });
    await userEvent.click(clearButton);

    expect(await screen.findByRole("heading", { name: /clear runtime state/i })).toBeInTheDocument();
    
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent(/test_state/i);

    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/admin/runtime-state/test_state"),
      expect.objectContaining({ method: "DELETE" })
    );

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(fetchMock).not.toHaveBeenCalledWith(
      expect.stringContaining("/admin/runtime-state/test_state"),
      expect.objectContaining({ method: "DELETE" })
    );
  });

  it("calls clear API when confirmation is accepted", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/runtime-state") && !init?.method) {
        return Promise.resolve(jsonResponse({
          items: [
            { key: "test_state", label: "Test State", size_bytes: 1024, updated_at: "2026-06-15T00:00:00Z" }
          ]
        }));
      }
      if (url.includes("/admin/runtime-state/test_state") && init?.method === "DELETE") {
        return Promise.resolve(jsonResponse({}));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<SettingsPage />);

    const clearButton = await screen.findByRole("button", { name: /clear test_state/i });
    await userEvent.click(clearButton);

    const confirmButton = await screen.findByRole("button", { name: /clear state/i });
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/runtime-state/test_state"),
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("displays error banner when runtime state query fails", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(owner));
      }
      if (url.includes("/admin/runtime-state")) {
        return Promise.reject(new Error("Runtime state fetch failed"));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<SettingsPage />);

    expect(await screen.findByText(/runtime state fetch failed/i)).toBeInTheDocument();
  });
});
