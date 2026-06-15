import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import HistoryPage from "@/app/(public)/account/history/page";
import { ContinueReading } from "@/components/public/continue-reading";
import { SaveToLibrary } from "@/components/public/save-to-library";

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

describe("public reading-state UI", () => {
  it("shows sign-in prompt for guest library/progress controls without user API calls", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse(guest));

    renderWithQuery(
      <div>
        <SaveToLibrary slug="demo" />
        <ContinueReading slug="demo" />
      </div>
    );

    expect(
      await screen.findAllByText("User features will return in a later phase.")
    ).toHaveLength(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/me",
      expect.objectContaining({ credentials: "include" })
    );
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes("/api/user/"))
    ).toBe(false);
  });

  it("allows an authenticated user to add a novel to the library", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/library/demo" && !init?.method) {
        return Promise.resolve(
          jsonResponse({ detail: "Library item not found." }, 404)
        );
      }
      if (url === "/api/user/library/demo" && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            status: "reading",
            added_at: "2026-06-15T00:00:00Z",
          }, 201)
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<SaveToLibrary slug="demo" />);

    await userEvent.click(await screen.findByRole("button", { name: /save to library/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/user/library/demo",
        expect.objectContaining({ method: "POST" })
      );
    });
  });

  it("shows continue-reading link for authenticated saved progress", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/progress/demo") {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            chapter_id: "7",
            progress_percent: 0.25,
            updated_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<ContinueReading slug="demo" />);

    const link = await screen.findByRole("link", { name: /continue reading/i });
    expect(link).toHaveAttribute("href", "/novel/demo/chapter/7");
  });

  it("renders authenticated reading history entries", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/history?limit=50") {
        return Promise.resolve(
          jsonResponse({
            items: [
              {
                id: 10,
                slug: "demo",
                chapter_id: "7",
                read_at: "2026-06-15T00:00:00Z",
              },
            ],
            next_cursor: null,
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<HistoryPage />);

    expect(await screen.findByText("demo")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /demo/i })).toHaveAttribute(
      "href",
      "/novel/demo/chapter/7"
    );
  });
});
