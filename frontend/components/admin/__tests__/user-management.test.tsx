import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useParams } from "next/navigation";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn(), back: vi.fn(), forward: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
  useParams: vi.fn(() => ({})),
}));

import AdminUsersPage from "@/app/(admin)/admin/users/page";
import AdminUserDetailPage from "@/app/(admin)/admin/users/[userId]/page";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

afterEach(() => {
  cleanup();
});

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockUsers = {
  items: [
    {
      id: 1,
      email: "alice@example.com",
      display_name: "Alice",
      role: "user",
      is_active: true,
      auth_provider: null,
      has_password: true,
      email_verified: true,
      created_at: "2026-01-01T00:00:00Z",
      last_login_at: "2026-06-15T00:00:00Z",
    },
    {
      id: 2,
      email: "bob@test.com",
      display_name: "Bob",
      role: "guest",
      is_active: false,
      auth_provider: "google",
      has_password: false,
      email_verified: true,
      created_at: "2026-02-01T00:00:00Z",
      last_login_at: null,
    },
    {
      id: 3,
      email: "carol@example.com",
      display_name: null,
      role: "owner",
      is_active: true,
      auth_provider: null,
      has_password: true,
      email_verified: false,
      created_at: "2026-01-15T00:00:00Z",
      last_login_at: "2026-06-10T00:00:00Z",
    },
  ],
  total: 3,
  page: 1,
  page_size: 50,
};

const mockUserDetail = {
  ...mockUsers.items[0],
  auth_provider_subject: null,
  disabled_at: null,
  disabled_reason: null,
  disabled_by_user_id: null,
  session_revoked_at: null,
};

const mockDisabledDetail = {
  ...mockUsers.items[1],
  auth_provider_subject: "google-abc123",
  disabled_at: "2026-06-01T00:00:00Z",
  disabled_reason: "Terms of service violation",
  disabled_by_user_id: 1,
  session_revoked_at: "2026-06-01T00:00:01Z",
};

const mockOwnerDetail = {
  ...mockUsers.items[2],
  auth_provider_subject: null,
  disabled_at: null,
  disabled_reason: null,
  disabled_by_user_id: null,
  session_revoked_at: null,
};

function mockUser(userId: string) {
  vi.mocked(useParams).mockReturnValue({ userId });
}

// ---------------------------------------------------------------------------
// User list page tests
// ---------------------------------------------------------------------------

describe("Admin Users List Page", () => {
  it("renders user list from API", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/admin/users")) {
        return Promise.resolve(jsonResponse(mockUsers));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<AdminUsersPage />);

    expect(await screen.findByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getByText("bob@test.com")).toBeInTheDocument();
    expect(screen.getByText("carol@example.com")).toBeInTheDocument();
  });

  it("shows display name in list", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUsers));

    renderWithQuery(<AdminUsersPage />);

    expect(await screen.findByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("shows loading state", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(
      () => new Promise(() => {}) // never resolves
    );

    renderWithQuery(<AdminUsersPage />);

    expect(screen.getByText("Loading users...")).toBeInTheDocument();
  });

  it("shows empty state when no users", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/admin/users")) {
        return Promise.resolve(jsonResponse({ items: [], total: 0, page: 1, page_size: 50 }));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<AdminUsersPage />);

    expect(await screen.findByText("No users found")).toBeInTheDocument();
  });

  it("shows error state on fetch failure", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/admin/users")) {
        return Promise.reject(new Error("Failed to fetch users"));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<AdminUsersPage />);

    expect(await screen.findByText(/failed to fetch users/i)).toBeInTheDocument();
  });

  it("filters by search term", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/admin/users") && url.includes("search=alice")) {
        return Promise.resolve(jsonResponse({
          items: [mockUsers.items[0]],
          total: 1,
          page: 1,
          page_size: 50,
        }));
      }
      if (url.includes("/admin/users")) {
        return Promise.resolve(jsonResponse(mockUsers));
      }
      return Promise.resolve(jsonResponse({}));
    });

    renderWithQuery(<AdminUsersPage />);

    await screen.findByText("alice@example.com");

    const searchInput = screen.getByPlaceholderText("Email or display name...");
    await userEvent.type(searchInput, "alice");

    const searchButton = screen.getByRole("button", { name: /search/i });
    await userEvent.click(searchButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("search=alice"),
        expect.anything()
      );
    });
  });

  it("shows role and status badges", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUsers));

    renderWithQuery(<AdminUsersPage />);

    await screen.findByText("alice@example.com");

    expect(screen.getAllByText("user").length).toBeGreaterThan(0);
    expect(screen.getAllByText("guest").length).toBeGreaterThan(0);
    expect(screen.getAllByText("owner").length).toBeGreaterThan(0);
    expect(screen.getAllByText("active").length).toBeGreaterThan(0);
    expect(screen.getByText("disabled")).toBeInTheDocument();
  });

  it("changes role filter triggers refetch", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUsers));

    renderWithQuery(<AdminUsersPage />);

    await screen.findByText("alice@example.com");

    const roleSelect = screen.getByLabelText("Role");
    await userEvent.selectOptions(roleSelect, "guest");

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("role=guest"),
        expect.anything()
      );
    });
  });

  it("links user email to detail page", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUsers));

    renderWithQuery(<AdminUsersPage />);

    await screen.findByText("alice@example.com");

    const link = screen.getByRole("link", { name: /alice@example\.com/i });
    expect(link).toHaveAttribute("href", "/admin/users/1");
  });

  it("shows pagination controls for large result sets", async () => {
    const manyItems = Array.from({ length: 60 }, (_, i) => ({
      id: i + 1,
      email: `user${i + 1}@example.com`,
      display_name: `User ${i + 1}`,
      role: "user",
      is_active: true,
      auth_provider: null,
      has_password: true,
      email_verified: false,
      created_at: "2026-01-01T00:00:00Z",
      last_login_at: null,
    }));

    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({
      items: manyItems.slice(0, 50),
      total: 60,
      page: 1,
      page_size: 50,
    }));

    renderWithQuery(<AdminUsersPage />);

    await screen.findByText("Showing 1–50 of 60");
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /next page/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// User detail page tests
// ---------------------------------------------------------------------------

describe("Admin User Detail Page", () => {
  beforeEach(() => {
    // Reset useParams mock before each test so mockUser() calls work fresh
    vi.mocked(useParams).mockReset();
    vi.mocked(useParams).mockReturnValue({});
  });

  it("renders user account summary", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    const alices = await screen.findAllByText("Alice");
    expect(alices.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    expect(screen.getAllByText("user").length).toBeGreaterThan(0);
    expect(screen.getByText("active")).toBeInTheDocument();
  });

  it("shows timestamps section", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    expect(await screen.findByText("Timestamps")).toBeInTheDocument();
    expect(screen.getAllByText(/2026/).length).toBeGreaterThanOrEqual(1);
  });

  it("shows disabled metadata for disabled users", async () => {
    mockUser("2");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockDisabledDetail));

    renderWithQuery(<AdminUserDetailPage />);

    expect(await screen.findByText("Disabled Metadata")).toBeInTheDocument();
    expect(screen.getByText("Terms of service violation")).toBeInTheDocument();
  });

  it("shows session_revoked_at timestamp", async () => {
    mockUser("2");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockDisabledDetail));

    renderWithQuery(<AdminUserDetailPage />);

    expect(await screen.findByText("Session Revoked")).toBeInTheDocument();
  });

  it("renders action buttons for non-owner users", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    expect(await screen.findByText("Actions")).toBeInTheDocument();
    const disableButtons = screen.getAllByRole("button", { name: /disable account/i });
    expect(disableButtons.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: /change role/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /revoke sessions/i })).toBeInTheDocument();
  });

  it("does not show mutation controls for owner users", async () => {
    mockUser("3");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockOwnerDetail));

    renderWithQuery(<AdminUserDetailPage />);

    expect(await screen.findByText(/owner accounts cannot be modified/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /disable account/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /change role/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /revoke sessions/i })).not.toBeInTheDocument();
  });

  it("opens disable confirmation dialog with reason field", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /disable account/i });
    await userEvent.click(actionButtons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByLabelText(/reason/i)).toBeInTheDocument();

    const reasonInput = screen.getByLabelText(/reason/i);
    // Confirm should be disabled initially (no reason)
    const confirmButtons = screen.getAllByRole("button", { name: /^disable account$/i });
    expect(confirmButtons).toHaveLength(2);

    await userEvent.type(reasonInput, "Violated community guidelines");

    // After typing reason, confirm should be enabled
    const enabledButtons = screen.getAllByRole("button", { name: /^disable account$/i });
    expect(enabledButtons).toHaveLength(2);
  });

  it("calls disable API when confirmed with reason", async () => {
    mockUser("1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/1/active") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ ...mockUserDetail, is_active: false }));
      }
      return Promise.resolve(jsonResponse(mockUserDetail));
    });

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /disable account/i });
    await userEvent.click(actionButtons[0]);

    const reasonInput = screen.getByLabelText(/reason/i);
    await userEvent.type(reasonInput, "Violated community guidelines");

    const confirmButtons = screen.getAllByRole("button", { name: /^disable account$/i });
    await userEvent.click(confirmButtons[1]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/users/1/active"),
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("Violated community guidelines"),
        })
      );
    });
  });

  it("calls enable API when confirmed with reason", async () => {
    mockUser("2");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/2/active") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ ...mockDisabledDetail, is_active: true }));
      }
      return Promise.resolve(jsonResponse(mockDisabledDetail));
    });

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /enable account/i });
    await userEvent.click(actionButtons[0]);

    const reasonInput = screen.getByLabelText(/reason/i);
    await userEvent.type(reasonInput, "Appeal approved");

    const confirmButtons = screen.getAllByRole("button", { name: /enable account/i });
    await userEvent.click(confirmButtons[1]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/users/2/active"),
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("is_active"),
        })
      );
    });
  });

  it("calls revoke sessions API when confirmed with reason", async () => {
    mockUser("1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/1/revoke-sessions") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({
          ...mockUserDetail,
          session_revoked_at: "2026-07-26T12:00:00Z",
        }));
      }
      return Promise.resolve(jsonResponse(mockUserDetail));
    });

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /revoke sessions/i });
    await userEvent.click(actionButtons[0]);

    const reasonInput = screen.getByLabelText(/reason/i);
    await userEvent.type(reasonInput, "Account compromise detected");

    const confirmButtons = screen.getAllByRole("button", { name: /revoke sessions/i });
    await userEvent.click(confirmButtons[1]);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/users/1/revoke-sessions"),
        expect.objectContaining({
          method: "POST",
          body: expect.stringContaining("Account compromise detected"),
        })
      );
    });
  });

  it("calls role change API when confirmed with reason", async () => {
    mockUser("1");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/1/role") && init?.method === "PATCH") {
        return Promise.resolve(jsonResponse({ ...mockUserDetail, role: "guest" }));
      }
      return Promise.resolve(jsonResponse(mockUserDetail));
    });

    renderWithQuery(<AdminUserDetailPage />);

    await screen.findByRole("button", { name: /change role/i });
    const roleButton = screen.getByRole("button", { name: /change role/i });
    await userEvent.click(roleButton);

    const reasonInput = screen.getByLabelText(/reason/i);
    await userEvent.type(reasonInput, "Account type downgraded");

    const confirmButton = screen.getByRole("button", { name: /change to/i });
    await userEvent.click(confirmButton);

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/admin/users/1/role"),
        expect.objectContaining({
          method: "PATCH",
          body: expect.stringContaining("Account type downgraded"),
        })
      );
    });
  });

  it("shows error from failed mutation", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/admin/users/1/active") && init?.method === "PATCH") {
        return Promise.reject(new Error("Cannot disable the last admin"));
      }
      return Promise.resolve(jsonResponse(mockUserDetail));
    });

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /disable account/i });
    await userEvent.click(actionButtons[0]);

    const reasonInput = screen.getByLabelText(/reason/i);
    await userEvent.type(reasonInput, "Testing");

    const confirmButtons = screen.getAllByRole("button", { name: /^disable account$/i });
    await userEvent.click(confirmButtons[1]);

    expect(await screen.findByText(/cannot disable the last admin/i)).toBeInTheDocument();
  });

  it("has link to audit events for the user", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    await screen.findByText(/User ID: 1/);

    const auditLink = screen.getByRole("link", { name: /view audit events/i });
    expect(auditLink).toHaveAttribute("href", "/admin/audit?target_type=user&target_id=1");
  });

  it("resets dialog state on cancel", async () => {
    mockUser("1");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(mockUserDetail));

    renderWithQuery(<AdminUserDetailPage />);

    const actionButtons = await screen.findAllByRole("button", { name: /disable account/i });
    await userEvent.click(actionButtons[0]);

    expect(screen.getByRole("dialog")).toBeInTheDocument();

    const cancelButton = screen.getByRole("button", { name: /cancel/i });
    await userEvent.click(cancelButton);

    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });
});
