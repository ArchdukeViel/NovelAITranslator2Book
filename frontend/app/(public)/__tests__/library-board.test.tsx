/**
 * Library page board/list tests.
 *
 * jsdom applies no responsive CSS, so the page decides its presentation from
 * window.matchMedia("(min-width: 768px)"), initialized after mount, plus an
 * explicit Board/List override. Exactly one presentation tree renders per
 * group, so slug queries must match once, not twice.
 *
 * Confirms that:
 * - Five named group regions render: Reading, Plan to read, Completed, Dropped,
 *   Unknown. groupKey() maps reading/completed/paused to named groups and every
 *   other status (e.g. plan, odd) to Unknown; Plan to read has no status
 *   producer and always renders as an empty region.
 * - Search by slug filters items before grouping
 * - Sort control changes slug order within a group
 * - Mobile default is list, desktop default is board; Board/List toggles switch
 *   the rendered presentation and aria-pressed; one DOM tree only
 * - Empty library shows CTA to /browse-novels
 * - Remove action calls useRemoveFromLibrary mutate
 */

import { afterAll, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { LibraryItem } from "@/lib/public-types";

const mocks = vi.hoisted(() => ({
  usePublicAuthMock: vi.fn(),
  useLibraryMock: vi.fn(),
  useRemoveFromLibraryMock: vi.fn(),
  removeMutations: new Map<string, { isPending: boolean; mutate: ReturnType<typeof vi.fn> }>(),
  desktop: { matches: false },
  changeListeners: new Set<() => void>(),
}));

vi.mock("@/hooks/public/use-auth", () => ({
  usePublicAuth: () => mocks.usePublicAuthMock(),
}));

vi.mock("@/hooks/public/use-reading-state", () => ({
  useLibrary: () => mocks.useLibraryMock(),
  useRemoveFromLibrary: (slug: string) => {
    if (!mocks.removeMutations.has(slug)) {
      mocks.removeMutations.set(slug, { isPending: false, mutate: vi.fn() });
    }
    return mocks.removeMutations.get(slug);
  },
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("lucide-react", () => {
  const Svg = ({ className, children }: { className?: string; children?: React.ReactNode }) => (
    <span className={className}>{children}</span>
  );
  return {
    Bookmark: Svg,
    BookOpen: Svg,
    LayoutGrid: Svg,
    List: Svg,
    Loader2: Svg,
    LogIn: Svg,
  };
});

// Statuses outside the runtime contract (plan / odd) exist only via cast;
// groupKey() routes both to Unknown.
const defaultLibraryData: LibraryItem[] = [
  { slug: "zeta-novel", status: "reading", added_at: "2025-01-01T00:00:00Z" },
  { slug: "alpha-novel", status: "reading", added_at: "2025-01-03T00:00:00Z" },
  { slug: "plan-novel", status: "plan" as LibraryItem["status"], added_at: "2025-01-04T00:00:00Z" },
  { slug: "beta-novel", status: "completed", added_at: "2025-01-02T00:00:00Z" },
  { slug: "gamma-novel", status: "paused", added_at: "2025-01-05T00:00:00Z" },
  { slug: "odd-novel", status: "odd" as LibraryItem["status"], added_at: "2025-01-06T00:00:00Z" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.removeMutations.clear();
  mocks.desktop.matches = false;
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      get matches() {
        return mocks.desktop.matches;
      },
      media: query,
      onchange: null,
      addEventListener: (_type: string, callback: () => void) => mocks.changeListeners.add(callback),
      removeEventListener: (_type: string, callback: () => void) => mocks.changeListeners.delete(callback),
      dispatchEvent: vi.fn(),
    })),
  });
  mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: true, isPending: false });
  mocks.useLibraryMock.mockReturnValue({ data: defaultLibraryData, isPending: false, isError: false });
});

// Restore jsdom baseline (matchMedia is undefined in jsdom) so the mock
// does not leak into other test files under singleFork.
afterAll(() => {
  delete (window as unknown as { matchMedia?: unknown }).matchMedia;
});

async function renderPage() {
  const { default: Page } = await import("../account/library/page");
  render(<Page />);
}

/** Fire the "change" handler the page registered on matchMedia. */
function emitMatchMediaChange(matches: boolean) {
  mocks.desktop.matches = matches;
  act(() => {
    for (const listener of mocks.changeListeners) {
      listener();
    }
  });
}

/** The <section> whose <h2> matches the given group title. */
function groupSection(name: string): HTMLElement {
  const heading = screen.getByRole("heading", { name });
  const section = heading.closest("section");
  if (!section) {
    throw new Error(`No <section> ancestor for group heading "${name}"`);
  }
  return section;
}

/** Ordered list of novel slugs shown in a group (single rendered presentation). */
function listPresentationOrder(section: HTMLElement): string[] {
  const links = section.querySelectorAll<HTMLAnchorElement>('a[href*="/novels/"]');
  return [...links]
    .map((link) => link.textContent?.trim() ?? "")
    .filter((text) => text !== "View");
}

describe("Library page groups", () => {
  it("renders five named group regions and routes each item to the right one", async () => {
    await renderPage();

    for (const title of ["Reading", "Plan to read", "Completed", "Dropped", "Unknown"]) {
      expect(groupSection(title)).toBeInTheDocument();
    }

    // Plan to read has no status producer in groupKey(); it renders as an
    // empty region. Any unrecognized status (plan, odd) lands in Unknown.
    expect(within(groupSection("Plan to read")).getByText("No novels in this group yet.")).toBeInTheDocument();

    // Mobile default is list: each slug appears exactly once in its group.
    const reading = groupSection("Reading");
    expect(within(reading).getByText("alpha-novel")).toBeInTheDocument();
    expect(within(reading).getByText("zeta-novel")).toBeInTheDocument();
    expect(within(reading).queryAllByText("alpha-novel")).toHaveLength(1);
    expect(within(reading).queryAllByText("zeta-novel")).toHaveLength(1);
    expect(within(reading).queryByText("beta-novel")).not.toBeInTheDocument();

    expect(within(groupSection("Completed")).getByText("beta-novel")).toBeInTheDocument();
    expect(within(groupSection("Dropped")).getByText("gamma-novel")).toBeInTheDocument();
    const unknown = groupSection("Unknown");
    expect(within(unknown).getByText("odd-novel")).toBeInTheDocument();
    expect(within(unknown).getByText("plan-novel")).toBeInTheDocument();
    expect(within(unknown).queryAllByText("alpha-novel")).toHaveLength(0);
  });

  it("searches by slug and empties non-matching groups", async () => {
    const user = userEvent.setup();
    await renderPage();

    await user.type(screen.getByRole("searchbox", { name: "Search by slug" }), "alpha");

    const reading = groupSection("Reading");
    expect(within(reading).getByText("alpha-novel")).toBeInTheDocument();
    expect(within(reading).queryAllByText("zeta-novel")).toHaveLength(0);

    for (const title of ["Plan to read", "Completed", "Dropped", "Unknown"]) {
      expect(within(groupSection(title)).getByText("No novels in this group yet.")).toBeInTheDocument();
    }
    expect(screen.queryByText("beta-novel")).not.toBeInTheDocument();
  });

  it("changes item order within a group when sort changes", async () => {
    const user = userEvent.setup();
    await renderPage();

    await user.click(screen.getByRole("button", { name: "List view" }));
    const reading = groupSection("Reading");

    // Default sort added-desc: alpha (01-03) before zeta (01-01)
    expect(listPresentationOrder(reading)).toEqual(["alpha-novel", "zeta-novel"]);

    await user.selectOptions(screen.getByRole("combobox"), "slug-desc");
    expect(listPresentationOrder(reading)).toEqual(["zeta-novel", "alpha-novel"]);
  });

  it("defaults to list presentation on mobile", async () => {
    await renderPage();
    const reading = groupSection("Reading");
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Board view" })).toHaveAttribute("aria-pressed", "false");
    expect(reading.querySelector(".divide-y")).toBeInTheDocument();
    expect(reading.querySelector('div[class*="sm:grid-cols-2"]')).not.toBeInTheDocument();
    expect(within(reading).queryAllByText("alpha-novel")).toHaveLength(1);
  });

  it("defaults to board presentation on desktop via matchMedia", async () => {
    mocks.desktop.matches = true;
    await renderPage();
    const reading = groupSection("Reading");
    expect(screen.getByRole("button", { name: "Board view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "false");
    expect(reading.querySelector('div[class*="sm:grid-cols-2"]')).toBeInTheDocument();
    expect(reading.querySelector(".divide-y")).not.toBeInTheDocument();
    expect(within(reading).queryAllByText("alpha-novel")).toHaveLength(1);
  });

  it("toggles board/list view with aria-pressed and one rendered presentation", async () => {
    const user = userEvent.setup();
    await renderPage();

    const boardButton = screen.getByRole("button", { name: "Board view" });
    const listButton = screen.getByRole("button", { name: "List view" });
    const reading = groupSection("Reading");

    await user.click(boardButton);
    expect(boardButton).toHaveAttribute("aria-pressed", "true");
    expect(listButton).toHaveAttribute("aria-pressed", "false");
    expect(reading.querySelector('div[class*="sm:grid-cols-2"]')).toBeInTheDocument();
    expect(reading.querySelector(".divide-y")).not.toBeInTheDocument();
    expect(within(reading).queryAllByText("alpha-novel")).toHaveLength(1);

    await user.click(listButton);
    expect(listButton).toHaveAttribute("aria-pressed", "true");
    expect(boardButton).toHaveAttribute("aria-pressed", "false");
    expect(reading.querySelector(".divide-y")).toBeInTheDocument();
    expect(reading.querySelector('div[class*="sm:grid-cols-2"]')).not.toBeInTheDocument();
    expect(within(reading).queryAllByText("alpha-novel")).toHaveLength(1);
  });

  it("shows empty library CTA linking to /browse-novels", async () => {
    mocks.useLibraryMock.mockReturnValue({ data: [], isPending: false, isError: false });
    await renderPage();

    expect(screen.getByText("Your library is empty.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Browse novels" })).toHaveAttribute("href", "/browse-novels");
    expect(screen.getByRole("link", { name: "Back to Browse" })).toHaveAttribute("href", "/browse-novels");
  });

  it("calls useRemoveFromLibrary mutate when Remove clicked", async () => {
    const user = userEvent.setup();
    await renderPage();

    const reading = groupSection("Reading");
    await user.click(within(reading).getByRole("button", { name: "Remove zeta-novel from library" }));

    const mutation = mocks.removeMutations.get("zeta-novel");
    expect(mutation?.mutate).toHaveBeenCalledTimes(1);
  });

  it("shows session loading state while auth is pending", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false, isPending: true });
    await renderPage();

    expect(screen.getByText("Checking session")).toBeInTheDocument();
    expect(screen.queryByText(/Sign in to save novels/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Reading" })).not.toBeInTheDocument();
  });

  it("shows LoginPrompt when unauthenticated", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false, isPending: false });
    await renderPage();

    expect(screen.getByText("Sign in to save novels, continue reading, and leave reviews.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/login?mode=signin");
  });

  it("shows loading state while library is pending", async () => {
    mocks.useLibraryMock.mockReturnValue({ data: [], isPending: true, isError: false });
    await renderPage();

    expect(screen.getByText("Loading library")).toBeInTheDocument();
  });

  it("shows error state when library fails", async () => {
    mocks.useLibraryMock.mockReturnValue({ data: [], isPending: false, isError: true });
    await renderPage();

    expect(screen.getByText("Could not load your library.")).toBeInTheDocument();
    expect(screen.getByText("Try refreshing the page, or return to browse.")).toBeInTheDocument();
  });

  it("disables Remove button while its mutation is pending", async () => {
    mocks.removeMutations.set("zeta-novel", { isPending: true, mutate: vi.fn() });
    await renderPage();

    expect(
      within(groupSection("Reading")).getByRole("button", { name: "Remove zeta-novel from library" }),
    ).toBeDisabled();
  });

  it("updates default presentation on matchMedia change until user overrides", async () => {
    await renderPage();
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");

    emitMatchMediaChange(true);
    expect(screen.getByRole("button", { name: "Board view" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "false");

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "List view" }));
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");

    emitMatchMediaChange(false);
    expect(screen.getByRole("button", { name: "List view" })).toHaveAttribute("aria-pressed", "true");
  });
});
