/**
 * Account Reviews page tests.
 *
 * Confirms that /account/reviews:
 * - Shows a login prompt for guests
 * - Lists the signed-in reader's own reviews with novel links and ratings
 * - Renders an honest empty state (no fake data)
 * - Removes a review through the delete mutation
 *
 * Feature: FE-10
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, cleanup, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  isAuthenticated: true,
  authPending: false,
  usePublicAuthMock: vi.fn(),
  useMyReviewsMock: vi.fn(),
  useDeleteReviewMock: vi.fn(),
}));

vi.mock("@/hooks/public", () => ({
  usePublicAuth: () => mocks.usePublicAuthMock(),
  useMyReviews: () => mocks.useMyReviewsMock(),
  useDeleteReview: (slug: string) => mocks.useDeleteReviewMock(slug),
}));

vi.mock("@/components/public/login-prompt", () => ({
  LoginPrompt: () => <div data-testid="login-prompt" />,
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
    <button {...props}>{children}</button>
  ),
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
    Loader2: Svg,
    Star: Svg,
    Trash2: Svg,
  };
});

const defaultReviews = [
  {
    slug: "novel-a",
    title: "Novel A",
    rating: 5,
    body: "Loved it.",
    status: "pending",
    created_at: "2025-01-01T00:00:00Z",
    updated_at: "2025-01-01T00:00:00Z",
  },
  {
    slug: "novel-b",
    title: "Novel B",
    rating: 3,
    body: null,
    status: "pending",
    created_at: "2025-01-02T00:00:00Z",
    updated_at: "2025-01-02T00:00:00Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mocks.isAuthenticated = true;
  mocks.authPending = false;
  mocks.usePublicAuthMock.mockReturnValue({
    isAuthenticated: mocks.isAuthenticated,
    isPending: mocks.authPending,
  });
  mocks.useMyReviewsMock.mockReturnValue({
    data: defaultReviews,
    isPending: false,
    isError: false,
  });
  mocks.useDeleteReviewMock.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  });
});

afterEach(() => {
  cleanup();
});

async function renderPage() {
  const { default: Page } = await import("../page");
  return render(<Page />);
}

describe("Account reviews page", () => {
  it("shows a login prompt for guests", async () => {
    mocks.usePublicAuthMock.mockReturnValue({ isAuthenticated: false, isPending: false });
    await renderPage();
    expect(screen.getByTestId("login-prompt")).toBeInTheDocument();
  });

  it("lists the reader's own reviews with novel links, ratings, status badges, and delete buttons", async () => {
    await renderPage();

    const novelLink = screen.getByRole("link", { name: /Novel A/i });
    expect(novelLink).toHaveAttribute("href", "/novels/novel-a?tab=reviews");

    expect(screen.getByText("Novel B")).toBeInTheDocument();
    expect(screen.getByText("Loved it.")).toBeInTheDocument();
    expect(screen.getByText(/No written review — rating only\./i)).toBeInTheDocument();
    expect(screen.getAllByText(/Pending review/i).length).toBeGreaterThanOrEqual(2);
    expect(screen.getByLabelText(/Delete review for Novel A/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Delete review for Novel B/i)).toBeInTheDocument();
  });

  it("renders an honest empty state with a browse CTA", async () => {
    mocks.useMyReviewsMock.mockReturnValue({ data: [], isPending: false, isError: false });
    await renderPage();
    expect(screen.getByText(/No reviews yet\./i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /browse novels/i })).toHaveAttribute("href", "/browse-novels");
  });

  it("shows loading and error states", async () => {
    mocks.useMyReviewsMock.mockReturnValue({ data: undefined, isPending: true, isError: false });
    await renderPage();
    expect(screen.getByText(/Loading reviews/i)).toBeInTheDocument();

    cleanup();
    mocks.useMyReviewsMock.mockReturnValue({ data: undefined, isPending: false, isError: true });
    await renderPage();
    expect(screen.getByText(/Could not load your reviews\./i)).toBeInTheDocument();
  });

  it("deletes a review via the delete mutation", async () => {
    const deleteMutate = vi.fn();
    mocks.useDeleteReviewMock.mockReturnValue({ mutate: deleteMutate, isPending: false });
    await renderPage();

    fireEvent.click(screen.getByLabelText(/Delete review for Novel A/i));
    expect(mocks.useDeleteReviewMock).toHaveBeenCalledWith("novel-a");
    expect(deleteMutate).toHaveBeenCalledTimes(1);
  });
});
