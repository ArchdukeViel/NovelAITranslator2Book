import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";

import { NotificationIndicator } from "@/components/public/notification-indicator";
import { NotificationList } from "@/components/public/notification-list";
import { NotificationPreferences } from "@/components/public/notification-preferences";

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

const user = {
  user_id: 1,
  email: "reader@example.com",
  role: "user",
  is_authenticated: true,
  is_owner: false,
};

const mockNotifications = [
  {
    id: 1,
    event_type: "translation.completed" as const,
    title: "Translation Complete",
    body: "Your translation job finished successfully.",
    severity: "success" as const,
    status: "unread" as const,
    action_url: "/account/library/demo",
    created_at: "2026-01-15T10:30:00Z",
    read_at: null,
  },
  {
    id: 2,
    event_type: "translation.failed" as const,
    title: "Translation Failed",
    body: "Translation job encountered an error.",
    severity: "error" as const,
    status: "read" as const,
    action_url: "/account/request-novels",
    created_at: "2026-01-14T08:00:00Z",
    read_at: "2026-01-14T09:00:00Z",
  },
  {
    id: 3,
    event_type: "translation.requires_review" as const,
    title: "Review Needed",
    body: "Please review the translated chapter.",
    severity: "warning" as const,
    status: "unread" as const,
    action_url: "//external.example.com/bad",
    created_at: "2026-01-13T12:00:00Z",
    read_at: null,
  },
  {
    id: 4,
    event_type: "translation.completed" as const,
    title: "Another Complete",
    body: "Second translation done.",
    severity: "info" as const,
    status: "archived" as const,
    action_url: null,
    created_at: "2026-01-12T06:00:00Z",
    read_at: "2026-01-12T07:00:00Z",
  },
];

const mockPreferences = [
  { event_type: "translation.completed" as const, channel: "in_app" as const, enabled: true },
  { event_type: "translation.completed" as const, channel: "email" as const, enabled: false },
  { event_type: "translation.failed" as const, channel: "in_app" as const, enabled: true },
  { event_type: "translation.failed" as const, channel: "email" as const, enabled: true },
  { event_type: "translation.requires_review" as const, channel: "in_app" as const, enabled: false },
  { event_type: "translation.requires_review" as const, channel: "email" as const, enabled: false },
];

let fetchMock: MockInstance<typeof fetch>;

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("NotificationIndicator", () => {
  beforeEach(() => {
    fetchMock = vi.spyOn(globalThis, "fetch");
  });

  it("renders nothing for guest and makes no notification API call", async () => {
    fetchMock.mockResolvedValue(jsonResponse(guest));

    renderWithQuery(<NotificationIndicator />);

    expect(screen.queryByRole("link", { name: /notification/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /notification/i })).not.toBeInTheDocument();

    // Should only call /api/auth/me, not notification endpoints
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/auth/me",
        expect.objectContaining({ credentials: "include" })
      );
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/notifications"))).toBe(false);
  });

  it("renders nothing while auth is pending (isPending true)", async () => {
    // authApi.me() never resolves, keeping isPending true
    fetchMock.mockImplementation(() => new Promise(() => {}));

    renderWithQuery(<NotificationIndicator />);

    expect(screen.queryByRole("link", { name: /notification/i })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/notifications"))).toBe(false);
  });

  it("shows bell icon with no badge for authenticated user with zero unread", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user)) // /api/auth/me
      .mockResolvedValueOnce(jsonResponse({ unread_count: 0 })); // /api/user/notifications/unread-count

    renderWithQuery(<NotificationIndicator />);

    const link = await screen.findByRole("link", { name: "No unread notifications" });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/account/notifications");
    // Badge should not exist (no role="status" element for unread)
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows badge with positive count for authenticated user", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse({ unread_count: 5 }));

    renderWithQuery(<NotificationIndicator />);

    const link = await screen.findByRole("link", { name: "5 unread notifications" });
    expect(link).toBeInTheDocument();
    // Badge is a span with aria-live="polite" and aria-atomic="true"
    const badge = screen.getByText("5");
    expect(badge).toBeInTheDocument();
    expect(badge.closest('[aria-live="polite"]')).toBeInTheDocument();
  });

  it("caps badge at 99+ for high unread count", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse({ unread_count: 150 }));

    renderWithQuery(<NotificationIndicator />);

    const link = await screen.findByRole("link", { name: "150 unread notifications" });
    expect(link).toBeInTheDocument();
    const badge = screen.getByText("99+");
    expect(badge).toBeInTheDocument();
    expect(badge.closest('[aria-live="polite"]')).toBeInTheDocument();
  });

  it("shows loader while unread count is loading (no badge yet)", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockImplementationOnce(() => new Promise(() => {})); // hanging unread-count

    renderWithQuery(<NotificationIndicator />);

    const link = await screen.findByRole("link");
    expect(link).toBeInTheDocument();
    // Loader has aria-hidden="true" and class animate-spin
    const loader = screen.getByTestId("unread-count-loader");
    expect(loader).toBeInTheDocument();
    expect(loader).toHaveClass("animate-spin");
  });
});

describe("NotificationList", () => {
  const defaultProps = {
    items: mockNotifications,
    onRead: vi.fn(),
    onArchive: vi.fn(),
    onReadAll: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders loading spinner when isLoading=true", () => {
    renderWithQuery(<NotificationList {...defaultProps} isLoading={true} />);

    expect(screen.getByText("Loading notifications...")).toBeInTheDocument();
    const spinner = screen.getByTestId("notification-list-loader");
    expect(spinner).toHaveClass("animate-spin");
  });

  it("renders empty message when items array is empty", () => {
    renderWithQuery(<NotificationList {...defaultProps} items={[]} />);

    expect(screen.getByText("No notifications yet.")).toBeInTheDocument();
  });

  it("renders custom emptyMessage when provided", () => {
    renderWithQuery(<NotificationList {...defaultProps} items={[]} emptyMessage="Custom empty" />);

    expect(screen.getByText("Custom empty")).toBeInTheDocument();
  });

  it("renders all notification items with correct data", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    // Mark all as read button visible (first item is unread)
    expect(screen.getByRole("button", { name: /mark all as read/i })).toBeInTheDocument();

    // Check first item (unread)
    expect(await screen.findByText("Translation Complete")).toBeInTheDocument();
    expect(screen.getByText("Your translation job finished successfully.")).toBeInTheDocument();
    expect(screen.getByText("success")).toBeInTheDocument();
    const statusBadges = screen.getAllByText("unread");
    expect(statusBadges.length).toBeGreaterThanOrEqual(1);
    // "Translation completed" appears for items 1 and 4 - check first occurrence
    const eventLabels = screen.getAllByText("Translation completed");
    expect(eventLabels.length).toBeGreaterThanOrEqual(1);

    // Check action URL rendered as link for safe internal URLs
    // Items 1 and 2 both have valid internal action_url; item 3 has protocol-relative "//external.example.com/bad"
    // (safeActionUrl returns null); item 4 has action_url null. Only items 1 and 2 render View links.
    const viewLinks = screen.getAllByRole("link", { name: "View" });
    expect(viewLinks).toHaveLength(2);
    expect(viewLinks.map((l) => l.getAttribute("href"))).toEqual([
      "/account/library/demo",
      "/account/request-novels",
    ]);

    // Check fourth item (archived) - no action_url, no View link
    expect(screen.getByText("Another Complete")).toBeInTheDocument();
    expect(screen.getByText("archived")).toBeInTheDocument();
  });

  it("calls onRead when Mark as read clicked from dropdown", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    // Open dropdown for first item
    const moreButton1 = screen.getAllByRole("button", { name: /more actions/i })[0];
    await userEvent.click(moreButton1);

    await userEvent.click(screen.getByRole("button", { name: /mark as read/i }));

    expect(defaultProps.onRead).toHaveBeenCalledWith(1);
  });

  it("calls onArchive when Archive clicked from dropdown", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    const moreButton1 = screen.getAllByRole("button", { name: /more actions/i })[0];
    await userEvent.click(moreButton1);

    await userEvent.click(screen.getByRole("button", { name: /archive/i }));

    expect(defaultProps.onArchive).toHaveBeenCalledWith(1);
  });

  it("calls onReadAll when Mark all as read clicked", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    await userEvent.click(screen.getByRole("button", { name: /mark all as read/i }));

    expect(defaultProps.onReadAll).toHaveBeenCalledTimes(1);
  });

  it("disables Mark all as read button when isReadingAll=true", async () => {
    renderWithQuery(<NotificationList {...defaultProps} isReadingAll={true} />);

    const readAllBtn = screen.getByRole("button", { name: /marking all as read/i });
    expect(readAllBtn).toBeDisabled();
    expect(screen.getByText("Marking all as read…")).toBeInTheDocument();
  });

  it("does not show Mark all as read when no unread items", () => {
    const readOnly = mockNotifications.filter((n) => n.status !== "unread");
    renderWithQuery(<NotificationList {...defaultProps} items={readOnly} />);

    expect(screen.queryByRole("button", { name: /mark all as read/i })).not.toBeInTheDocument();
  });

  it("renders external/protocol-relative URLs as safe fallback - no View link for bad URLs", () => {
    const itemsWithBadUrl = [
      {
        ...mockNotifications[0],
        action_url: "https://external.example.com/path",
      },
    ];
    renderWithQuery(<NotificationList {...defaultProps} items={itemsWithBadUrl} />);

    const viewLinks = screen.queryAllByRole("link", { name: "View" });
    expect(viewLinks).toHaveLength(0); // external URL not rendered
  });

  it("renders items with accessible labels", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    const articles = screen.getAllByRole("listitem");
    expect(articles).toHaveLength(4);

    // First article aria-label includes event type, status, date
    expect(articles[0]).toHaveAttribute("aria-label", expect.stringContaining("Translation completed"));
    expect(articles[0]).toHaveAttribute("aria-label", expect.stringContaining("unread"));
  });

  it("expands dropdown on More button click and closes on backdrop click", async () => {
    renderWithQuery(<NotificationList {...defaultProps} />);

    const moreButton = screen.getAllByRole("button", { name: /more actions/i })[0];
    await userEvent.click(moreButton);

    expect(screen.getByRole("button", { name: /mark as read/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /archive/i })).toBeInTheDocument();

    // Click backdrop (the fixed inset-0 div) to close
    const backdrop = document.querySelector(".fixed.inset-0.z-10");
    if (backdrop) {
      await userEvent.click(backdrop);
      expect(screen.queryByRole("button", { name: /mark as read/i })).not.toBeInTheDocument();
    }
  });
});

describe("NotificationPreferences", () => {
  beforeEach(() => {
    fetchMock = vi.spyOn(globalThis, "fetch");
    vi.clearAllMocks();
  });

  it("renders loading skeletons while isLoading=true", async () => {
    // Mock auth me then hang on preferences
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockImplementationOnce(() => new Promise(() => {}));

    renderWithQuery(<NotificationPreferences />);

    // Wait for skeletons to appear (auth resolves, then preferences starts loading)
    await waitFor(() => {
      const skeletons = document.querySelectorAll(".animate-pulse");
      expect(skeletons.length).toBeGreaterThanOrEqual(3);
    });
  });

  it("renders error message when isError=true", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse({ detail: "error" }, 500));

    renderWithQuery(<NotificationPreferences />);

    expect(await screen.findByText("Failed to load notification preferences.")).toBeInTheDocument();
  });

  it("renders empty state when no preferences returned", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse([]));

    renderWithQuery(<NotificationPreferences />);

    expect(await screen.findByText("No notification preferences available.")).toBeInTheDocument();
  });

  it("renders preference grid with event types and channels when data loads", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse(mockPreferences));

    renderWithQuery(<NotificationPreferences />);

    // Header row - text might be split, use flexible matching
    await waitFor(() => {
      expect(screen.getByText("Event")).toBeInTheDocument();
      expect(screen.getByText("In-app")).toBeInTheDocument();
      expect(screen.getByText("Email")).toBeInTheDocument();
    });

    // Event rows - eventTypeKey formats the event type
    expect(screen.getByText("Translation completed")).toBeInTheDocument();
    expect(screen.getByText("Translation failed")).toBeInTheDocument();
    expect(screen.getByText("Translation requires review")).toBeInTheDocument();

    // Checkboxes reflect enabled state
    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(6);

    // translation.completed in_app = true
    expect(checkboxes[0]).toBeChecked();
    // translation.completed email = false
    expect(checkboxes[1]).not.toBeChecked();
    // translation.failed in_app = true
    expect(checkboxes[2]).toBeChecked();
    // translation.failed email = true
    expect(checkboxes[3]).toBeChecked();
    // translation.requires_review in_app = false
    expect(checkboxes[4]).not.toBeChecked();
    // translation.requires_review email = false
    expect(checkboxes[5]).not.toBeChecked();
  });

  it("calls updatePreference with exact {event_type, channel, enabled} contract on toggle", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse(mockPreferences))
      .mockResolvedValueOnce(jsonResponse({ event_type: "translation.completed", channel: "email", enabled: true }));

    renderWithQuery(<NotificationPreferences />);

    // Wait for grid to render
    await waitFor(() => {
      expect(screen.getByText("Event")).toBeInTheDocument();
    });

    // Find the email checkbox for translation.completed (index 1, currently unchecked)
    const emailCheckbox = screen.getAllByRole("checkbox")[1];
    expect(emailCheckbox).not.toBeChecked();

    await userEvent.click(emailCheckbox);

    // Verify the mutation was called with correct payload
    await waitFor(() => {
      const mutationCall = fetchMock.mock.calls.find(
        ([url, init]) => {
          const rInit = init as RequestInit | undefined;
          return String(url).includes("/api/user/notifications/preferences") && rInit?.method === "PUT";
        }
      );
      expect(mutationCall).toBeDefined();
      const body = JSON.parse((mutationCall![1] as RequestInit)?.body as string);
      expect(body).toEqual({
        event_type: "translation.completed",
        channel: "email",
        enabled: true,
      });
    });
  });

  it("shows loading spinner on checkbox while saving and disables it", async () => {
    let resolveMutation: (value: Response) => void;
    const mutationPromise = new Promise<Response>((resolve) => {
      resolveMutation = resolve;
    });

    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse(mockPreferences))
      .mockImplementationOnce(() => mutationPromise);

    renderWithQuery(<NotificationPreferences />);

    // Wait for grid to render
    await waitFor(() => {
      expect(screen.getByText("Event")).toBeInTheDocument();
    });

    const emailCheckbox = screen.getAllByRole("checkbox")[1];
    await userEvent.click(emailCheckbox);

    // While saving, checkbox disabled and spinner shown
    expect(emailCheckbox).toBeDisabled();
    const spinner = screen.getByTestId("preference-save-spinner");
    expect(spinner).toHaveClass("animate-spin");

    resolveMutation!(jsonResponse({ event_type: "translation.completed", channel: "email", enabled: true }));

    await waitFor(() => {
      expect(emailCheckbox).not.toBeDisabled();
    });
  });

  it("reverts on mutation error and refetches", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse(mockPreferences))
      .mockResolvedValueOnce(jsonResponse({ detail: "server error" }, 500))
      .mockResolvedValueOnce(jsonResponse(mockPreferences)); // refetch after error

    renderWithQuery(<NotificationPreferences />);

    // Wait for grid to render
    await waitFor(() => {
      expect(screen.getByText("Event")).toBeInTheDocument();
    });

    const emailCheckbox = screen.getAllByRole("checkbox")[1];
    await userEvent.click(emailCheckbox);

    await waitFor(() => {
      expect(emailCheckbox).not.toBeChecked(); // reverted to false
    });

    // Verify refetch happened (4 calls: auth me, preferences, mutation error, refetch)
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("checkboxes have accessible aria-labels with channel and event type", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(user))
      .mockResolvedValueOnce(jsonResponse(mockPreferences));

    renderWithQuery(<NotificationPreferences />);

    // Wait for grid to render
    await waitFor(() => {
      expect(screen.getByText("Event")).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes[0]).toHaveAttribute("aria-label", "In-app notifications for Translation completed");
    expect(checkboxes[1]).toHaveAttribute("aria-label", "Email notifications for Translation completed");
    expect(checkboxes[2]).toHaveAttribute("aria-label", "In-app notifications for Translation failed");
    expect(checkboxes[3]).toHaveAttribute("aria-label", "Email notifications for Translation failed");
    expect(checkboxes[4]).toHaveAttribute("aria-label", "In-app notifications for Translation requires review");
    expect(checkboxes[5]).toHaveAttribute("aria-label", "Email notifications for Translation requires review");
  });
});
