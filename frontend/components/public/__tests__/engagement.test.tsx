import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RequestsPage from "@/app/(public)/account/requests/page";
import { RatingReview } from "@/components/public/rating-review";
import { RequestControl } from "@/components/public/request-control";

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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("public engagement UI", () => {
  it("shows sign-in prompts for guest review/request controls", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(guest));

    renderWithQuery(
      <div>
        <RatingReview slug="demo" />
        <RequestControl slug="demo" />
      </div>
    );

    expect(
      await screen.findAllByText("Sign in to save novels, continue reading, and leave reviews.")
    ).toHaveLength(2);
  });

  it("submits and deletes an authenticated review", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/auth/csrf") {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-test" }));
      }
      if (url === "/api/user/reviews/demo" && init?.method === "PUT") {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            rating: 5,
            body: "Great",
            status: "pending",
            updated_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      if (url === "/api/user/reviews/demo" && init?.method === "DELETE") {
        return Promise.resolve(new Response(null, { status: 204 }));
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<RatingReview slug="demo" />);

    await userEvent.click(await screen.findByLabelText("Rate 5 stars"));
    await userEvent.type(screen.getByPlaceholderText("Write your review (optional)"), "Great");
    await userEvent.click(screen.getByRole("button", { name: /submit review/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user/reviews/demo",
        expect.objectContaining({ method: "PUT" })
      );
    });
    const reviewMutation = fetchMock.mock.calls.find(
      ([url, init]) => String(url) === "/api/user/reviews/demo" && init?.method === "PUT"
    );
    expect(new Headers(reviewMutation?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-test");

    // Success confirmation
    expect(await screen.findByText(/review submitted/i)).toBeInTheDocument();

    // Delete button now visible (only after saved review)
    expect(screen.getByRole("button", { name: /remove review/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /remove review/i }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user/reviews/demo",
        expect.objectContaining({ method: "DELETE" })
      );
    });
  });

  it("blocks invalid review ratings client-side", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(user));

    renderWithQuery(<RatingReview slug="demo" />);

    await userEvent.click(await screen.findByRole("button", { name: /submit review/i }));

    expect(await screen.findByText("Choose a rating from 1 to 5.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/reviews"))
    ).toBe(false);
  });

  it("hides delete button until a review is saved", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(user));

    renderWithQuery(<RatingReview slug="demo" />);

    // Delete button should not be visible initially
    expect(screen.queryByRole("button", { name: /remove review/i })).not.toBeInTheDocument();

    // After selecting a rating (but not submitting), still no delete button
    await userEvent.click(await screen.findByLabelText("Rate 5 stars"));
    expect(screen.queryByRole("button", { name: /remove review/i })).not.toBeInTheDocument();
  });

  it("creates an authenticated novel request and shows success confirmation", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/auth/csrf") {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-test" }));
      }
      if (url === "/api/user/requests" && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            id: 5,
            request_type: "novel",
            status: "pending",
            source_url: "https://example.com/novel",
            slug: null,
            chapter_id: null,
            created_at: "2026-06-15T00:00:00Z",
          }, 201)
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<RequestControl />);

    await userEvent.type(
      await screen.findByPlaceholderText("https://example.com/novel"),
      "https://example.com/novel"
    );
    await userEvent.click(screen.getByRole("button", { name: /submit request/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user/requests",
        expect.objectContaining({ method: "POST" })
      );
    });
    const requestMutation = fetchMock.mock.calls.find(
      ([url, init]) => String(url) === "/api/user/requests" && init?.method === "POST"
    );
    expect(new Headers(requestMutation?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-test");

    // Success confirmation
    expect(await screen.findByText(/request submitted/i)).toBeInTheDocument();
  });

  it("blocks invalid request input client-side", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(user));

    renderWithQuery(<RequestControl />);

    await userEvent.click(await screen.findByRole("button", { name: /submit request/i }));

    expect(
      await screen.findByText("Source URL is required for novel requests.")
    ).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/requests"))
    ).toBe(false);
  });

  it("lists authenticated requests on the account page with novel links", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/requests?limit=50") {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: 7,
                request_type: "novel",
                status: "pending",
                source_url: "https://example.com/novel",
                slug: null,
                chapter_id: null,
                created_at: "2026-06-15T00:00:00Z",
              },
              {
                id: 8,
                request_type: "chapter",
                status: "completed",
                source_url: null,
                slug: "demo",
                chapter_id: "3",
                created_at: "2026-06-16T00:00:00Z",
              },
            ],
            next_cursor: null,
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<RequestsPage />);

    // Page header (appears after auth resolves)
    expect(await screen.findByText("My Requests")).toBeInTheDocument();
    expect(await screen.findByText("Novel and chapter translation requests you have submitted.")).toBeInTheDocument();

    // Novel request entry (source URL shown)
    expect(await screen.findByText("https://example.com/novel")).toBeInTheDocument();

    // Chapter request entry (slug linked)
    const novelLink = await screen.findByRole("link", { name: /demo/i });
    expect(novelLink).toHaveAttribute("href", "/novel/demo");

    // Status badges
    expect(await screen.findByText("Pending")).toBeInTheDocument();
    expect(await screen.findByText("Completed")).toBeInTheDocument();
  });

  it("shows empty requests state with browse link", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/requests?limit=50") {
        return Promise.resolve(jsonResponse({ items: [], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<RequestsPage />);

    expect(await screen.findByText("No requests yet.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /browse novels/i })).toBeInTheDocument();
  });
});
