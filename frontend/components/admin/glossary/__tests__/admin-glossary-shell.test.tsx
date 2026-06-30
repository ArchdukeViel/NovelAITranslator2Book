import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
const mockCreateGlossaryEntry = vi.hoisted(() => vi.fn());
const mockUpdateGlossaryEntry = vi.hoisted(() => vi.fn());
const mockChangeGlossaryEntryStatus = vi.hoisted(() => vi.fn());
const mockLockGlossaryEntry = vi.hoisted(() => vi.fn());
const mockUnlockGlossaryEntry = vi.hoisted(() => vi.fn());
const mockDeprecateGlossaryEntry = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get adminApi() {
      return {
        ...actual.adminApi,
        listGlossaryEntries: (...args: unknown[]) => mockListGlossaryEntries(...args),
        createGlossaryEntry: (...args: unknown[]) => mockCreateGlossaryEntry(...args),
        updateGlossaryEntry: (...args: unknown[]) => mockUpdateGlossaryEntry(...args),
        changeGlossaryEntryStatus: (...args: unknown[]) => mockChangeGlossaryEntryStatus(...args),
        lockGlossaryEntry: (...args: unknown[]) => mockLockGlossaryEntry(...args),
        unlockGlossaryEntry: (...args: unknown[]) => mockUnlockGlossaryEntry(...args),
        deprecateGlossaryEntry: (...args: unknown[]) => mockDeprecateGlossaryEntry(...args),
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
  mockCreateGlossaryEntry.mockReset();
  mockUpdateGlossaryEntry.mockReset();
  mockChangeGlossaryEntryStatus.mockReset();
  mockLockGlossaryEntry.mockReset();
  mockUnlockGlossaryEntry.mockReset();
  mockDeprecateGlossaryEntry.mockReset();
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

  it("creates an entry with novelId scope and form payload", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockCreateGlossaryEntry.mockResolvedValue({ ...entry, id: 2, canonical_term: "Lydia" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await user.click(screen.getByRole("button", { name: "Create entry" }));
    await user.type(screen.getByLabelText("Canonical term"), "Lydia");
    await user.type(screen.getByLabelText("Approved translation"), "Lydia");
    await user.selectOptions(screen.getByLabelText("Term type"), "character");
    await user.selectOptions(screen.getByLabelText("Status"), "recommended");
    await user.selectOptions(screen.getByLabelText("Enforcement level"), "warning");
    await user.click(screen.getAllByRole("button", { name: "Create entry" }).at(-1)!);

    await waitFor(() => {
      expect(mockCreateGlossaryEntry).toHaveBeenCalledWith("42", expect.objectContaining({
        canonical_term: "Lydia",
        approved_translation: "Lydia",
        term_type: "character",
        status: "recommended",
        enforcement_level: "warning",
      }));
    });
  });

  it("submits edit payload for an existing entry", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockUpdateGlossaryEntry.mockResolvedValue({ ...entry, canonical_term: "Ellenora" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getAllByText("Ellen").length).toBeGreaterThan(0);
    });
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const canonical = screen.getByLabelText("Canonical term");
    await user.clear(canonical);
    await user.type(canonical, "Ellenora");
    await user.click(screen.getByRole("button", { name: "Save entry" }));

    await waitFor(() => {
      expect(mockUpdateGlossaryEntry).toHaveBeenCalledWith("42", 1, expect.objectContaining({
        canonical_term: "Ellenora",
      }));
    });
  });

  it("changes status through the scoped client function", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockChangeGlossaryEntryStatus.mockResolvedValue({ ...entry, status: "recommended" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getByLabelText("Change status for Ellen")).toBeInTheDocument();
    });
    await user.selectOptions(screen.getByLabelText("Change status for Ellen"), "recommended");

    await waitFor(() => {
      expect(mockChangeGlossaryEntryStatus).toHaveBeenCalledWith("42", 1, { status: "recommended" });
    });
  });

  it("locks, unlocks, and deprecates through scoped client functions", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([{ ...entry, owner_locked: false }]);
    mockLockGlossaryEntry.mockResolvedValue({ ...entry, owner_locked: true });
    mockUnlockGlossaryEntry.mockResolvedValue({ ...entry, owner_locked: false });
    mockDeprecateGlossaryEntry.mockResolvedValue({ ...entry, status: "deprecated" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Lock" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Lock" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(mockLockGlossaryEntry).toHaveBeenCalledWith("42", 1));

    cleanup();
    mockListGlossaryEntries.mockResolvedValue([{ ...entry, owner_locked: true }]);
    renderWithQuery(<AdminGlossaryShell novelId="42" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Unlock" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Unlock" }));
    await user.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(mockUnlockGlossaryEntry).toHaveBeenCalledWith("42", 1));

    cleanup();
    mockListGlossaryEntries.mockResolvedValue([{ ...entry, status: "approved" }]);
    renderWithQuery(<AdminGlossaryShell novelId="42" />);
    await waitFor(() => expect(screen.getByRole("button", { name: "Deprecate" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Deprecate" }));
    await user.click(within(screen.getByRole("dialog", { name: "Deprecate glossary entry" })).getByRole("button", { name: "Deprecate" }));
    await waitFor(() => expect(mockDeprecateGlossaryEntry).toHaveBeenCalledWith("42", 1));
  });

  it("displays duplicate/API error and keeps non-goal controls absent", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockCreateGlossaryEntry.mockRejectedValue(new Error("Duplicate canonical term"));

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await user.click(screen.getByRole("button", { name: "Create entry" }));
    await user.type(screen.getByLabelText("Canonical term"), "Ellen");
    await user.click(screen.getAllByRole("button", { name: "Create entry" }).at(-1)!);

    await waitFor(() => {
      expect(screen.getByText("Duplicate canonical term")).toBeInTheDocument();
    });
    expect(screen.getByText("Glossary terms are owned by this novel. Source IDs are provenance only.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /alias/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /provenance/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /qa/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /replace/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /repair/i })).not.toBeInTheDocument();
  });
});
