import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReviewsPage from "../page";
import type { AdminReviewRecord } from "@/lib/api-types";

const { adminReviewsMock, moderateReviewMock } = vi.hoisted(() => ({
  adminReviewsMock: vi.fn(),
  moderateReviewMock: vi.fn(),
}));

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return { ...actual, api: { ...actual.api, adminReviews: adminReviewsMock, moderateReview: moderateReviewMock } };
});

vi.mock("@/components/admin/confirm-dialog", () => ({
  ConfirmDialog: () => null,
}));

const sampleReview: AdminReviewRecord = {
  id: 1,
  user_id: 10,
  slug: "test-novel",
  title: "Test Novel",
  rating: 5,
  body: "Great",
  status: "pending",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  moderated_at: null,
  reviewer_notes: null,
  reviewed_by_user_id: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  adminReviewsMock.mockResolvedValue({
    items: [sampleReview],
    total: 1,
    page: 1,
    page_size: 20,
  });
});

afterEach(() => {
  cleanup();
});

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("Admin Reviews page", () => {
  it("renders page heading and review data after load", async () => {
    renderWithQuery(<ReviewsPage />);
    expect(await screen.findByText("Test Novel")).toBeInTheDocument();
    expect(screen.getByText(/by user #10/i)).toBeInTheDocument();
  });

  it("shows error state on load failure", async () => {
    adminReviewsMock.mockRejectedValue(new Error("Failed"));
    renderWithQuery(<ReviewsPage />);
    expect(await screen.findByText(/Failed to load reviews/i)).toBeInTheDocument();
  });

  it("shows empty state when no reviews", async () => {
    adminReviewsMock.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20 });
    renderWithQuery(<ReviewsPage />);
    expect(await screen.findByText(/No reader reviews yet\./i)).toBeInTheDocument();
  });
});
