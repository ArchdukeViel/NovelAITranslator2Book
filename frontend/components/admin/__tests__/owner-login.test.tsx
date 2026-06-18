import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";
import { LogoutControl } from "@/components/admin/logout-control";
import { OwnerLoginView } from "@/components/admin/owner-login-view";

const mockRefresh = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mockRefresh }),
}));

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

const guest = {
  user_id: null,
  email: null,
  role: "guest",
  is_authenticated: false,
  is_owner: false,
};

const owner = {
  user_id: 1,
  email: "owner@local",
  role: "owner",
  is_authenticated: true,
  is_owner: true,
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  mockRefresh.mockReset();
});

describe("admin owner login", () => {
  it("shows the owner login panel for unauthenticated admin access", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(guest));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(
      <AdminAuthGuard>
        <div>Admin dashboard content</div>
      </AdminAuthGuard>
    );

    expect(
      await screen.findByRole("heading", { name: /admin sign in/i })
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/owner login secret/i)).toBeInTheDocument();
    expect(screen.queryByText("Admin dashboard content")).not.toBeInTheDocument();
  });

  it("submits owner bootstrap login to /api/auth/login", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/login")) {
        return Promise.resolve(jsonResponse(owner));
      }
      return Promise.resolve(jsonResponse({}));
    });
    const onSuccess = vi.fn();

    render(<OwnerLoginView onSuccess={onSuccess} />);

    await user.type(screen.getByLabelText(/owner login secret/i), "owner-secret-value");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/login"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ secret: "owner-secret-value" }),
        })
      );
      expect(onSuccess).toHaveBeenCalled();
    });
  });

  it("shows a safe error when owner bootstrap login fails", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/login")) {
        return Promise.resolve(jsonResponse({ detail: "Invalid credentials." }, 401));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(<OwnerLoginView onSuccess={vi.fn()} />);

    await user.type(screen.getByLabelText(/owner login secret/i), "wrong-secret");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Invalid login secret. Please try again.");
    expect(alert).not.toHaveTextContent("wrong-secret");
    expect(alert).not.toHaveTextContent("Invalid credentials.");
  });

  it("shows admin content after successful owner login", async () => {
    const user = userEvent.setup();
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/me")) {
        return Promise.resolve(jsonResponse(guest));
      }
      if (url.includes("/api/auth/login")) {
        return Promise.resolve(jsonResponse(owner));
      }
      return Promise.resolve(jsonResponse({}));
    });

    render(
      <AdminAuthGuard>
        <div>Admin dashboard content</div>
      </AdminAuthGuard>
    );

    await screen.findByRole("heading", { name: /admin sign in/i });
    await user.type(screen.getByLabelText(/owner login secret/i), "owner-secret-value");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(await screen.findByText("Admin dashboard content")).toBeInTheDocument();
    expect(mockRefresh).toHaveBeenCalled();
  });

  it("posts logout and refreshes the admin route", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/auth/logout")) {
        return Promise.resolve(jsonResponse({ status: "logged_out" }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<LogoutControl />);

    await user.click(screen.getByRole("button", { name: /sign out/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/auth/logout"),
        expect.objectContaining({ method: "POST" })
      );
      expect(mockRefresh).toHaveBeenCalled();
    });
  });
});
