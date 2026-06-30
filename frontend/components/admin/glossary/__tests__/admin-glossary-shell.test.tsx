import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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
const mockNovel = vi.hoisted(() => vi.fn());
const mockCreateGlossaryEntry = vi.hoisted(() => vi.fn());
const mockUpdateGlossaryEntry = vi.hoisted(() => vi.fn());
const mockChangeGlossaryEntryStatus = vi.hoisted(() => vi.fn());
const mockListGlossaryAliases = vi.hoisted(() => vi.fn());
const mockListGlossaryProvenanceForEntry = vi.hoisted(() => vi.fn());
const mockListGlossaryDecisionEvents = vi.hoisted(() => vi.fn());
const mockListGlossaryQaFindings = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    get api() {
      return {
        ...actual.api,
        novel: (...args: unknown[]) => mockNovel(...args),
      };
    },
    get adminApi() {
      return {
        ...actual.adminApi,
        listGlossaryEntries: (...args: unknown[]) => mockListGlossaryEntries(...args),
        createGlossaryEntry: (...args: unknown[]) => mockCreateGlossaryEntry(...args),
        updateGlossaryEntry: (...args: unknown[]) => mockUpdateGlossaryEntry(...args),
        changeGlossaryEntryStatus: (...args: unknown[]) => mockChangeGlossaryEntryStatus(...args),
        listGlossaryAliases: (...args: unknown[]) => mockListGlossaryAliases(...args),
        listGlossaryProvenanceForEntry: (...args: unknown[]) => mockListGlossaryProvenanceForEntry(...args),
        listGlossaryDecisionEvents: (...args: unknown[]) => mockListGlossaryDecisionEvents(...args),
        listGlossaryQaFindings: (...args: unknown[]) => mockListGlossaryQaFindings(...args),
      };
    },
  };
});

const approvedEntry: GlossaryEntry = {
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

const reviewingEntry: GlossaryEntry = {
  ...approvedEntry,
  id: 2,
  canonical_term: "Pocott",
  approved_translation: "Pocott Village",
  term_type: "place",
  status: "recommended",
  owner_locked: false,
};

beforeEach(() => {
  mockNovel.mockResolvedValue({ novel_id: "42", title: "Test Novel", translated_title: "Test Novel" });
  mockListGlossaryAliases.mockResolvedValue([]);
  mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
  mockListGlossaryDecisionEvents.mockResolvedValue([]);
  mockListGlossaryQaFindings.mockResolvedValue([]);
});

afterEach(() => {
  mockNovel.mockReset();
  mockListGlossaryEntries.mockReset();
  mockCreateGlossaryEntry.mockReset();
  mockUpdateGlossaryEntry.mockReset();
  mockChangeGlossaryEntryStatus.mockReset();
  mockListGlossaryAliases.mockReset();
  mockListGlossaryProvenanceForEntry.mockReset();
  mockListGlossaryDecisionEvents.mockReset();
  mockListGlossaryQaFindings.mockReset();
  vi.restoreAllMocks();
  cleanup();
});

describe("AdminGlossaryShell", () => {
  it("renders the simplified owner table and hides cluttered table controls", async () => {
    mockListGlossaryEntries.mockResolvedValue([approvedEntry, reviewingEntry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    expect(screen.getByText("Loading glossary entries...")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Pocott")).toBeInTheDocument());

    expect(screen.getByRole("columnheader", { name: "Term" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Translation" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Actions" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Updated" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Locked" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Term type" })).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Change status for Ellen")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Select" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Lock" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deprecate" })).not.toBeInTheDocument();
  });

  it("shows owner-facing statuses and table actions only", async () => {
    mockListGlossaryEntries.mockResolvedValue([approvedEntry, reviewingEntry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("Pocott")).toBeInTheDocument());
    expect(screen.getAllByText("Approved").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reviewing").length).toBeGreaterThan(0);
    expect(screen.queryByText("candidate")).not.toBeInTheDocument();
    expect(screen.queryByText("recommended")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approved" })).toBeDisabled();
  });

  it("uses novelId route scoping and owner help copy", async () => {
    mockListGlossaryEntries.mockResolvedValue([]);
    mockNovel.mockResolvedValue({ novel_id: "novel/with space", title: "Raw Title", translated_title: "Friendly Novel" });

    renderWithQuery(<AdminGlossaryShell novelId="novel/with space" />);

    await waitFor(() => expect(mockListGlossaryEntries).toHaveBeenCalledWith("novel/with space"));
    expect(await screen.findByRole("heading", { name: "Friendly Novel" })).toBeInTheDocument();
    expect(screen.getByText("Glossary - Novel: novel/with space")).toBeInTheDocument();
    expect(screen.getByText("Source IDs are evidence only. No global replace from this page. Saved chapter repair is a later explicit step.")).toBeInTheDocument();
    expect(screen.getByText("More review candidates can be imported from saved raw/translated chapters in a later step.")).toBeInTheDocument();
  });

  it("does not show the advanced bottom detail tabs by default", async () => {
    mockListGlossaryEntries.mockResolvedValue([approvedEntry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getAllByText("Ellen").length).toBeGreaterThan(0));
    expect(screen.queryByText("Entry details")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Aliases" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Evidence" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "History" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "QA findings" })).not.toBeInTheDocument();
    expect(mockListGlossaryAliases).not.toHaveBeenCalled();
    expect(mockListGlossaryProvenanceForEntry).not.toHaveBeenCalled();
    expect(mockListGlossaryDecisionEvents).not.toHaveBeenCalled();
    expect(mockListGlossaryQaFindings).not.toHaveBeenCalled();
  });

  it("selects a row by clicking the row without loading advanced data", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([reviewingEntry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("Pocott")).toBeInTheDocument());
    await user.click(screen.getByText("Pocott"));
    expect(mockListGlossaryAliases).not.toHaveBeenCalled();
    expect(mockListGlossaryProvenanceForEntry).not.toHaveBeenCalled();
  });

  it("approves a reviewing row through the scoped status endpoint", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([reviewingEntry]);
    mockChangeGlossaryEntryStatus.mockResolvedValue({ ...reviewingEntry, status: "approved" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() => {
      expect(mockChangeGlossaryEntryStatus).toHaveBeenCalledWith("42", 2, { status: "approved" });
    });
  });

  it("creates entries with only Reviewing and Approved owner status options", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockCreateGlossaryEntry.mockResolvedValue({ ...reviewingEntry, canonical_term: "Lydia" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await user.click(screen.getByRole("button", { name: "Create entry" }));
    const dialog = screen.getByRole("dialog", { name: "Create glossary entry" });
    const status = within(dialog).getByLabelText("Status");
    expect(within(status).getByRole("option", { name: "Reviewing" })).toBeInTheDocument();
    expect(within(status).getByRole("option", { name: "Approved" })).toBeInTheDocument();
    expect(within(status).queryByRole("option", { name: "recommended" })).not.toBeInTheDocument();
    expect(within(status).queryByRole("option", { name: "deprecated" })).not.toBeInTheDocument();

    await user.type(within(dialog).getByLabelText("Term"), "Lydia");
    await user.type(within(dialog).getByLabelText("Translation"), "Lydia");
    await user.selectOptions(status, "candidate");
    await user.click(screen.getAllByRole("button", { name: "Create entry" }).at(-1)!);

    await waitFor(() => {
      expect(mockCreateGlossaryEntry).toHaveBeenCalledWith("42", expect.objectContaining({
        canonical_term: "Lydia",
        approved_translation: "Lydia",
        status: "candidate",
      }));
    });
  });

  it("changes status from the edit dialog while keeping the table dropdown removed", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([reviewingEntry]);
    mockUpdateGlossaryEntry.mockResolvedValue(reviewingEntry);
    mockChangeGlossaryEntryStatus.mockResolvedValue({ ...reviewingEntry, status: "approved" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument());
    expect(screen.queryByLabelText("Change status for Pocott")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = screen.getByRole("dialog", { name: "Edit glossary entry" });
    await user.selectOptions(within(dialog).getByLabelText("Status"), "approved");
    await user.click(screen.getByRole("button", { name: "Save entry" }));

    await waitFor(() => {
      expect(mockUpdateGlossaryEntry).toHaveBeenCalledWith("42", 2, expect.objectContaining({
        canonical_term: "Pocott",
      }));
      expect(mockChangeGlossaryEntryStatus).toHaveBeenCalledWith("42", 2, { status: "approved" });
    });
  });

  it("preserves search by translation and type filtering", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([approvedEntry, reviewingEntry]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("Pocott")).toBeInTheDocument());
    await user.type(screen.getByLabelText("Search term or translation"), "Village");
    expect(screen.getByText("Pocott")).toBeInTheDocument();
    expect(screen.queryByText("Ellen")).not.toBeInTheDocument();

    await user.clear(screen.getByLabelText("Search term or translation"));
    await user.selectOptions(screen.getByLabelText("Type"), "character");
    expect(screen.getAllByText("Ellen").length).toBeGreaterThan(0);
    expect(screen.queryByText("Pocott")).not.toBeInTheDocument();
  });

  it("keeps non-goal global replace, repair, prompt injection, and QA engine controls absent", async () => {
    mockListGlossaryEntries.mockResolvedValue([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("No glossary entries yet.")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /scan/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /prompt injection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /replace/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /repair/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /import/i })).not.toBeInTheDocument();
  });

  it("renders API error state", async () => {
    mockListGlossaryEntries.mockRejectedValue(new Error("Network failure"));

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => {
      expect(screen.getAllByText("Failed to load glossary entries.").length).toBeGreaterThan(0);
    });
  });
});
