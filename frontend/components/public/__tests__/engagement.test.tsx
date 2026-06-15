import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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
  vi.restoreAllMocks();
});

describe("public engagement UI", () => {
  it("shows sign-in prompts for guest review/request controls without user API calls", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(guest));

    renderWithQuery(
      <div>
        <RatingReview slug="demo" />
        <RequestControl slug="demo" />
      </div>
    );

    expect(
      await screen.findAllByText("User features will return in a later phase.")
    ).toHaveLength(2);
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/"))
    ).toBe(false);
  });

  it("submits and deletes an authenticated review", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
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
    await userEvent.type(screen.getByPlaceholderText("Optional review"), "Great");
    await userEvent.click(screen.getByRole("button", { name: /submit review/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user/reviews/demo",
        expect.objectContaining({ method: "PUT" })
      );
    });
    expect(await screen.findByText("Review saved with status: pending")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /delete review/i }));
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

  it("creates an authenticated novel request and handles duplicate-pending response", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
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
    expect(await screen.findByText("Request #5 is pending.")).toBeInTheDocument();
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

  it("lists authenticated public requests on the account page", async () => {
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
            ],
            next_cursor: null,
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<RequestsPage />);

    expect(await screen.findByText("Recent requests")).toBeInTheDocument();
    expect(await screen.findByText("novel")).toBeInTheDocument();
    expect(screen.getByText("pending")).toBeInTheDocument();
  });
});
