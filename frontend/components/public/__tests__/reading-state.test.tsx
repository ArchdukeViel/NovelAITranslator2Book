import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import HistoryPage from "@/app/(public)/account/history/page";
import LibraryPage from "@/app/(public)/account/library/page";
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
  cleanup();
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
      await screen.findAllByText("Sign in to save novels, continue reading, and leave reviews.")
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
      if (url === "/api/auth/csrf") {
        return Promise.resolve(jsonResponse({ csrf_token: "csrf-test" }));
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
        expect.objectContaining({
          method: "POST",
          headers: expect.objectContaining({}),
        })
      );
    });
    const mutation = fetchMock.mock.calls.find(
      ([url, init]) => String(url) === "/api/user/library/demo" && init?.method === "POST"
    );
    expect(new Headers(mutation?.[1]?.headers).get("X-CSRF-Token")).toBe("csrf-test");
  });

  it("shows continue-reading link with chapter info for authenticated saved progress", async () => {
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
            chapter_number: 7,
            progress_percent: 0,
            updated_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<ContinueReading slug="demo" />);

    const link = await screen.findByRole("link", { name: /continue from ch/i });
    expect(link).toHaveAttribute("href", "/novel/demo/chapter/7");
  });

  it("shows start-reading link when no saved progress (404) but firstChapterId exists", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/progress/demo") {
        // No saved progress — 404 is "no progress", not an error
        return Promise.resolve(
          jsonResponse({ detail: "Progress not found." }, 404)
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<ContinueReading slug="demo" firstChapterId="1" />);

    const link = await screen.findByRole("link", { name: /start reading/i });
    expect(link).toHaveAttribute("href", "/novel/demo/chapter/1");
  });

  it("shows 'Chapter' fallback when chapter_number is null/undefined in progress", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/progress/demo") {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            chapter_id: "99",
            chapter_number: null,
            progress_percent: 0.5,
            updated_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<ContinueReading slug="demo" />);

    const link = await screen.findByRole("link", { name: /continue from chapter/i });
    expect(link).toBeInTheDocument();
    // Link href still uses chapter_id
    expect(link).toHaveAttribute("href", "/novel/demo/chapter/99");
    // Raw numeric ID not shown in label
    expect(link?.textContent).not.toContain("Ch. 99");
  });

  it("continue-reading label uses chapter_number over chapter_id", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/progress/demo") {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            chapter_id: "42",
            chapter_number: 7,
            progress_percent: 0.5,
            updated_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<ContinueReading slug="demo" />);

    const link = await screen.findByRole("link", { name: /continue from ch/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/novel/demo/chapter/42");
    // Label shows chapter_number=7, not chapter_id=42
    expect(link?.textContent).toContain("Ch. 7");
    expect(link?.textContent).not.toContain("Ch. 42");
  });

  it("renders authenticated reading history entries with links", async () => {
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
                chapter_number: 7,
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

    // History entry shows slug + chapter reference as a link
    const entryLink = await screen.findByRole("link", { name: /demo — ch\. 7/i });
    expect(entryLink).toHaveAttribute("href", "/novel/demo/chapter/7");

    // "Open" action link to the chapter
    const openLink = screen.getByRole("link", { name: /^open$/i });
    expect(openLink).toHaveAttribute("href", "/novel/demo/chapter/7");

    // "View My Library" cross-link appears
    expect(screen.getByRole("link", { name: /view my library/i })).toBeInTheDocument();
  });

  it("renders authenticated library entries with links and remove button", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      if (url === "/api/user/library") {
        return Promise.resolve(
          jsonResponse([
            {
              slug: "demo",
              status: "reading",
              added_at: "2026-06-15T00:00:00Z",
            },
          ])
        );
      }
      if (url === "/api/user/history?limit=50") {
        return Promise.resolve(jsonResponse({ items: [], next_cursor: null }));
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<LibraryPage />);

    // Library entry shows slug as a link to the novel
    const novelLink = await screen.findByRole("link", { name: /demo/ });
    expect(novelLink).toHaveAttribute("href", "/novel/demo");

    // Status badge
    expect(screen.getByText("Reading")).toBeInTheDocument();

    // Remove button exists
    expect(screen.getByRole("button", { name: /remove/i })).toBeInTheDocument();

    expect(screen.getByRole("heading", { name: /currently reading/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /reading history/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /dropped/i })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /updates/i })).toBeInTheDocument();
  });

  it("shows saved state with view-library link for an already-saved novel", async () => {
    // Simulate: library item already exists (already saved)
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method;
      if (url === "/api/auth/me") {
        return Promise.resolve(jsonResponse(user));
      }
      // GET /api/user/library/demo — item exists (saved)
      if (url === "/api/user/library/demo" && !method) {
        return Promise.resolve(
          jsonResponse({
            slug: "demo",
            status: "reading",
            added_at: "2026-06-15T00:00:00Z",
          })
        );
      }
      return Promise.resolve(jsonResponse({ detail: "unexpected" }, 500));
    });

    renderWithQuery(<SaveToLibrary slug="demo" />);

    // Already saved — shows "Saved" button
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /saved/i })).toBeInTheDocument();
    });

    // View Library link
    expect(screen.getByRole("link", { name: /view library/i })).toBeInTheDocument();
  });
});
