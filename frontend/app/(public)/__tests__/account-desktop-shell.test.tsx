/**
 * Account desktop shell and landing summary tests.
 *
 * Confirms that:
 * - Desktop sidebar renders with correct navigation items
 * - Disabled routes (Reviews, Support) are labeled "Unavailable"
 * - Landing summary shows honest counts from existing data hooks
 * - Mobile hub navigation is hidden on desktop (lg:hidden)
 * - Empty states are honest (no fake data)
 *
 * Feature: FE-09
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, cleanup, screen, within } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  isAuthenticated: true,
  authPending: false,
  usePublicAuthMock: vi.fn(),
  useLibraryMock: vi.fn(),
  useHistoryMock: vi.fn(),
  useUnreadCountMock: vi.fn(),
  useLogoutMock: vi.fn(),
  usePathnameMock: vi.fn(() => "/account"),
  useRouterMock: vi.fn(() => ({ replace: vi.fn() })),
}));

const defaultLibraryData: { slug: string; status: string; added_at: string }[] =
  [
    { slug: "novel-1", status: "reading", added_at: "2025-01-01T00:00:00Z" },
    { slug: "novel-2", status: "completed", added_at: "2025-01-02T00:00:00Z" },
    { slug: "novel-3", status: "paused", added_at: "2025-01-03T00:00:00Z" },
  ];

const defaultHistoryData = {
  items: [
    {
      id: 1,
      slug: "novel-1",
      chapter_id: "ch-1",
      chapter_number: 5,
      read_at: "2025-06-15T10:00:00Z",
    },
  ],
  next_cursor: null,
};

const defaultUnreadCount = 3;

vi.mock("@/hooks/public/use-auth", () => ({
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useLogout: () => mocks.useLogoutMock(),
}));

vi.mock("@/hooks/public/use-reading-state", () => ({
  useLibrary: () => mocks.useLibraryMock(),
  useHistory: (params?: { limit?: number }) => mocks.useHistoryMock(),
}));

vi.mock("@/hooks/public/use-notifications", () => ({
  useUnreadCount: () => mocks.useUnreadCountMock(),
}));

vi.mock("@/components/public/public-theme-toggle", () => ({
  PublicThemeToggle: () => <button data-testid="theme-toggle" />,
  PublicThemeSegmentedControl: () => (
    <div data-testid="theme-segmented-control" />
  ),
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("lucide-react", () => {
  const Svg = ({
    className,
    children,
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => <span className={className}>{children}</span>;
  return {
    AlertTriangle: Svg,
    ArrowRight: Svg,
    Bell: Svg,
    BookOpen: Svg,
    Clock: Svg,
    FileText: Svg,
    Heart: Svg,
    HeartHandshake: Svg,
    HelpCircle: Svg,
    History: Svg,
    Info: Svg,
    Library: Svg,
    LifeBuoy: Svg,
    Loader2: Svg,
    Lock: Svg,
    LogOut: Svg,
    Newspaper: Svg,
    Palette: Svg,
    Scale: Svg,
    Settings: Svg,
    Shield: Svg,
    Star: Svg,
    Trophy: Svg,
    User: Svg,
    Wrench: Svg,
  };
});

vi.mock("next/navigation", () => ({
  usePathname: () => mocks.usePathnameMock(),
  useRouter: () => mocks.useRouterMock(),
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isAuthenticated = true;
  mocks.authPending = false;
  mocks.usePublicAuthMock.mockReturnValue({
    data: { is_authenticated: true, role: "user" },
    isPending: false,
    isError: false,
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
    authState: {
      status: "authenticated",
      user: { is_authenticated: true, role: "user" },
    },
    user: { is_authenticated: true, role: "user" },
    isAuthenticated: true,
    isPublicUser: true,
    isOwner: false,
  });
  mocks.useLibraryMock.mockReturnValue({
    data: defaultLibraryData,
    isPending: false,
    isError: false,
  });
  mocks.useHistoryMock.mockReturnValue({
    data: defaultHistoryData,
    isPending: false,
    isError: false,
  });
  mocks.useUnreadCountMock.mockReturnValue({
    data: defaultUnreadCount,
    isPending: false,
    isError: false,
  });
  mocks.useLogoutMock.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  });
});

afterEach(() => {
  cleanup();
});

function renderWithProviders(ui: React.ReactNode) {
  const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("Account desktop shell", () => {
  it("renders sidebar with all navigation items on desktop", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    const nav = screen.getByRole("navigation", { name: "Account navigation" });
    expect(nav).toBeInTheDocument();

    const links = [
      "/account/library",
      "/account/history",
      "/account/notifications",
      "/account/request-novels",
      "/account/reviews",
      "/account/contributions",
      "/account/settings",
    ];

    for (const href of links) {
      // Hyphens in the href (e.g. request-novels) match the spaced label (Request Novels)
      const namePattern = (href.split("/").pop() || "").replace(/-/g, "[ -]");
      const link = within(nav).getByRole("link", {
        name: new RegExp(namePattern, "i"),
      });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute("href", href);
    }

    // Unavailable items render as plain text, not links
    expect(
      within(nav).queryByRole("link", { name: /support/i }),
    ).not.toBeInTheDocument();
    expect(within(nav).getByText(/support/i)).toBeInTheDocument();
  });

  it("labels unavailable routes (Support) as Unavailable (non-links)", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    const desktopNav = screen.getByRole("navigation", {
      name: "Account navigation",
    });

    const supportText = within(desktopNav).getByText(/support/i);

    // Should be plain text containers, not links
    expect(supportText).not.toHaveAttribute("href");
    expect(supportText.closest("a")).not.toBeInTheDocument();

    // Only Support should show "Unavailable" label
    expect(within(desktopNav).getAllByText("Unavailable")).toHaveLength(1);
  });

  it("highlights active route in sidebar", async () => {
    mocks.usePathnameMock.mockReturnValue("/account/library");
    mocks.useRouterMock.mockReturnValue({ replace: vi.fn() });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    const desktopNav = screen.getByRole("navigation", {
      name: "Account navigation",
    });
    const libraryLink = within(desktopNav).getByRole("link", {
      name: /library/i,
    });
    expect(libraryLink).toHaveAttribute("aria-current", "page");
  });
});

describe("Account landing summary", () => {
  it("shows reading count from library data", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Currently Reading")).toBeInTheDocument();
    expect(screen.getByTestId("reading-count")).toHaveTextContent("1"); // 1 reading from defaultLibraryData
    expect(screen.getByText("3 total in library")).toBeInTheDocument();
  });

  it("shows history count and recent activity", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Reading History")).toBeInTheDocument();
    expect(screen.getByTestId("history-count")).toHaveTextContent("1"); // 1 history entry
    expect(screen.getByText("Most Recent Activity")).toBeInTheDocument();
    expect(screen.getByText("novel-1")).toBeInTheDocument();
    expect(screen.getByText("Ch. 5")).toBeInTheDocument();
  });

  it("shows unread notification count", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Unread Notifications")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument(); // defaultUnreadCount = 3
    expect(screen.getByText("Tap to view")).toBeInTheDocument();
  });

  it("shows honest empty state when library is empty", async () => {
    mocks.useLibraryMock.mockReturnValue({
      data: [],
      isPending: false,
      isError: false,
    });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Currently Reading")).toBeInTheDocument();
    expect(screen.getByTestId("reading-count")).toHaveTextContent("0");
    expect(screen.getByText("0 total in library")).toBeInTheDocument();
  });

  it("shows honest empty state when history is empty", async () => {
    mocks.useHistoryMock.mockReturnValue({
      data: { items: [], next_cursor: null },
      isPending: false,
      isError: false,
    });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Reading History")).toBeInTheDocument();
    expect(screen.getByTestId("history-count")).toHaveTextContent("0");
    expect(screen.getByText("No history yet")).toBeInTheDocument();
    expect(screen.queryByText("Most Recent Activity")).not.toBeInTheDocument();
  });

  it("shows honest empty state when no unread notifications", async () => {
    mocks.useUnreadCountMock.mockReturnValue({
      data: 0,
      isPending: false,
      isError: false,
    });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Unread Notifications")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
    expect(screen.getByText("All caught up")).toBeInTheDocument();
  });
});

describe("Mobile hub hidden on desktop", () => {
  it("renders mobile navigation inside lg:hidden container, not in desktop nav", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    const desktopNav = screen.getByRole("navigation", {
      name: "Account navigation",
    });

    const mobileNavHeading = screen.getByRole("heading", {
      name: /your account/i,
    });
    const mobileMoreHeading = screen.getByRole("heading", { name: /more/i });

    expect(mobileNavHeading).toBeInTheDocument();
    expect(mobileMoreHeading).toBeInTheDocument();

    for (const heading of [mobileNavHeading, mobileMoreHeading]) {
      expect(heading.closest("[class*='lg:hidden']")).not.toBeNull();
      expect(desktopNav).not.toContainElement(heading);
    }
  });
});

describe("Loading and auth states", () => {
  it("shows loading spinner while auth pending", async () => {
    mocks.usePublicAuthMock.mockReturnValue({
      data: undefined,
      isPending: true,
      isError: false,
      isLoading: true,
      isFetching: true,
      refetch: vi.fn(),
      authState: null,
      user: null,
      isAuthenticated: false,
      isPublicUser: false,
      isOwner: false,
    });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(screen.getByText("Checking session")).toBeInTheDocument();
  });

  it("redirects to login when not authenticated", async () => {
    const replaceMock = vi.fn();
    mocks.usePathnameMock.mockReturnValue("/account");
    mocks.useRouterMock.mockReturnValue({ replace: replaceMock });

    mocks.usePublicAuthMock.mockReturnValue({
      data: { is_authenticated: false, role: "guest" },
      isPending: false,
      isError: false,
      isLoading: false,
      isFetching: false,
      refetch: vi.fn(),
      authState: {
        status: "guest",
        user: { is_authenticated: false, role: "guest" },
      },
      user: { is_authenticated: false, role: "guest" },
      isAuthenticated: false,
      isPublicUser: false,
      isOwner: false,
    });

    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    expect(replaceMock).toHaveBeenCalledWith(
      "/login?mode=signin&callbackUrl=%2Faccount",
    );
  });

  it("redirects to login preserving deep account pathname", async () => {
    const replaceMock = vi.fn();
    mocks.usePathnameMock.mockReturnValue("/account/settings");
    mocks.useRouterMock.mockReturnValue({ replace: replaceMock });

    mocks.usePublicAuthMock.mockReturnValue({
      data: { is_authenticated: false, role: "guest" },
      isPending: false,
      isError: false,
      isLoading: false,
      isFetching: false,
      refetch: vi.fn(),
      authState: {
        status: "guest",
        user: { is_authenticated: false, role: "guest" },
      },
      user: { is_authenticated: false, role: "guest" },
      isAuthenticated: false,
      isPublicUser: false,
      isOwner: false,
    });

    const { default: Layout } = await import("../account/layout");

    renderWithProviders(
      <Layout>
        <div />
      </Layout>,
    );

    expect(replaceMock).toHaveBeenCalledWith(
      "/login?mode=signin&callbackUrl=%2Faccount%2Fsettings",
    );
  });
});

describe("Main landmark", () => {
  it("renders only one main landmark when child page renders its own main", async () => {
    const { default: Layout } = await import("../account/layout");
    const { default: Page } = await import("../account/settings/page");

    renderWithProviders(
      <Layout>
        <Page />
      </Layout>,
    );

    // Shell content wrapper is a non-landmark div; the child page owns the single main landmark
    expect(screen.getAllByRole("main")).toHaveLength(1);
  });
});
