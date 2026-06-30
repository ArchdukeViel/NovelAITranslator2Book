import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AdminGlossaryShell } from "@/components/admin/glossary/admin-glossary-shell";
import type { GlossaryEntry } from "@/lib/api-types";

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockListGlossaryEntries = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get adminApi() {
      return {
        ...actual.adminApi,
        listGlossaryEntries: (...args: unknown[]) => mockListGlossaryEntries(...args),
      };
    },
  };
});

const entry: GlossaryEntry = {
  id: 1,
  novel_id: 42,
  canonical_term: "Ellen",
  term_type: "character",
  approved_translation: "Ellen",
  status: "approved",
  enforcement_level: "warning",
  owner_locked: true,
  public_visible: false,
  public_description: null,
  admin_notes: null,
  confidence: 0.9,
  replacement_policy: "preview_required",
  matching_policy: "exact_phrase",
  first_seen_chapter_id: 1,
  first_seen_chapter_number: 1,
  last_seen_chapter_id: 4,
  last_seen_chapter_number: 4,
  created_by_user_id: 1,
  updated_by_user_id: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
  deprecated_at: null,
};

afterEach(() => {
  mockListGlossaryEntries.mockReset();
  vi.restoreAllMocks();
  cleanup();
});

describe("AdminGlossaryShell", () => {
  it("renders loading then glossary entries", async () => {
    mockListGlossaryEntries.mockResolvedValue([entry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    expect(screen.getByText("Loading glossary entries...")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getAllByText("Ellen").length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText("approved").length).toBeGreaterThan(0);
    expect(screen.getByText("character")).toBeInTheDocument();
    expect(screen.getByText("warning")).toBeInTheDocument();
  });

  it("renders empty state", async () => {
    mockListGlossaryEntries.mockResolvedValue([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getByText("No glossary entries yet.")).toBeInTheDocument();
    });
  });

  it("renders API error state", async () => {
    mockListGlossaryEntries.mockRejectedValue(new Error("Network failure"));

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getAllByText("Failed to load glossary entries.").length).toBeGreaterThan(0);
    });
  });

  it("uses novelId route scoping and source-agnostic copy", async () => {
    mockListGlossaryEntries.mockResolvedValue([]);

    renderWithQuery(<AdminGlossaryShell novelId="novel/with space" />);

    await waitFor(() => {
      expect(mockListGlossaryEntries).toHaveBeenCalledWith("novel/with space");
    });
    expect(screen.getByText("Glossary terms are owned by this novel. Source IDs are provenance only.")).toBeInTheDocument();
  });

  it("does not render create or edit controls in the shell phase", async () => {
    mockListGlossaryEntries.mockResolvedValue([entry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getAllByText("Ellen").length).toBeGreaterThan(0);
    });
    expect(screen.queryByRole("button", { name: /create/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /create/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /edit/i })).not.toBeInTheDocument();
  });
});
