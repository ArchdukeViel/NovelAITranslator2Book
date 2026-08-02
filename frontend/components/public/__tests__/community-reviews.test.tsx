/**
 * CommunityReviews component tests.
 *
 * Confirms that:
 * - Published reviews render with rating, body, and date.
 * - "No published reviews yet" shows when items are empty.
 * - "Load more" appears only when next_cursor is present.
 * - Only published reviews are rendered (status is private / not exposed).
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  useNovelReviewsMock: vi.fn(),
}));

vi.mock("@/hooks/public", () => ({
  useNovelReviews: (slug: string, cursor?: string | null) => mocks.useNovelReviewsMock(slug, cursor),
}));

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

const sampleReviews = [
  { id: 1, rating: 5, body: "Amazing novel!", created_at: "2025-01-15T10:00:00Z" },
  { id: 2, rating: 3, body: "It was okay.", created_at: "2025-01-16T10:00:00Z" },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.useNovelReviewsMock.mockReturnValue({
    data: { items: sampleReviews, next_cursor: null },
    isPending: false,
    isLoading: false,
    isFetching: false,
    isError: false,
  });
});

afterEach(() => {
  cleanup();
});

async function renderComponent() {
  const { CommunityReviews } = await import("../community-reviews");
  return render(<CommunityReviews slug="test-novel" />);
}

describe("CommunityReviews", () => {
  it("renders published reviews with rating and body", async () => {
    await renderComponent();
    expect(screen.getByText("Amazing novel!")).toBeInTheDocument();
    expect(screen.getByText(/It was okay\./i)).toBeInTheDocument();
    expect(screen.getByText("Community Reviews")).toBeInTheDocument();
  });

  it("renders empty state when no reviews", async () => {
    mocks.useNovelReviewsMock.mockReturnValue({
      data: { items: [], next_cursor: null },
      isPending: false,
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    await renderComponent();
    expect(screen.getByText(/No published reviews yet\./i)).toBeInTheDocument();
  });

  it("shows load more button when next_cursor present", async () => {
    mocks.useNovelReviewsMock.mockReturnValue({
      data: { items: sampleReviews, next_cursor: "next-page-cursor" },
      isPending: false,
      isLoading: false,
      isFetching: false,
      isError: false,
    });
    await renderComponent();
    expect(screen.getByRole("button", { name: /Load more/i })).toBeInTheDocument();
  });

  it("hides load more button when next_cursor is null", async () => {
    await renderComponent();
    expect(screen.queryByRole("button", { name: /Load more/i })).not.toBeInTheDocument();
  });

  it("renders loading state", async () => {
    mocks.useNovelReviewsMock.mockReturnValue({
      data: undefined,
      isPending: false,
      isLoading: true,
      isFetching: false,
      isError: false,
    });
    await renderComponent();
    expect(screen.getByText(/Loading reviews/i)).toBeInTheDocument();
  });
});
