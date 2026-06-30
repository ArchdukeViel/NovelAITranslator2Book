import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminGlossaryShell } from "@/components/admin/glossary/admin-glossary-shell";
import type { GlossaryAlias, GlossaryDecisionEvent, GlossaryEntry, GlossaryProvenance, GlossaryQaFinding } from "@/lib/api-types";

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
const mockListGlossaryAliases = vi.hoisted(() => vi.fn());
const mockAddGlossaryAlias = vi.hoisted(() => vi.fn());
const mockUpdateGlossaryAlias = vi.hoisted(() => vi.fn());
const mockDeprecateGlossaryAlias = vi.hoisted(() => vi.fn());
const mockListGlossaryProvenanceForEntry = vi.hoisted(() => vi.fn());
const mockAddGlossaryProvenance = vi.hoisted(() => vi.fn());
const mockListGlossaryDecisionEvents = vi.hoisted(() => vi.fn());
const mockListGlossaryQaFindings = vi.hoisted(() => vi.fn());
const mockUpdateGlossaryQaFindingStatus = vi.hoisted(() => vi.fn());

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
        listGlossaryAliases: (...args: unknown[]) => mockListGlossaryAliases(...args),
        addGlossaryAlias: (...args: unknown[]) => mockAddGlossaryAlias(...args),
        updateGlossaryAlias: (...args: unknown[]) => mockUpdateGlossaryAlias(...args),
        deprecateGlossaryAlias: (...args: unknown[]) => mockDeprecateGlossaryAlias(...args),
        listGlossaryProvenanceForEntry: (...args: unknown[]) => mockListGlossaryProvenanceForEntry(...args),
        addGlossaryProvenance: (...args: unknown[]) => mockAddGlossaryProvenance(...args),
        listGlossaryDecisionEvents: (...args: unknown[]) => mockListGlossaryDecisionEvents(...args),
        listGlossaryQaFindings: (...args: unknown[]) => mockListGlossaryQaFindings(...args),
        updateGlossaryQaFindingStatus: (...args: unknown[]) => mockUpdateGlossaryQaFindingStatus(...args),
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

const alias: GlossaryAlias = {
  id: 5,
  glossary_entry_id: 1,
  novel_id: 42,
  alias_text: "Alberto",
  alias_type: "banned",
  language: null,
  text_origin: null,
  applies_to: "translated_text",
  matching_policy: "exact_phrase",
  notes: "Wrong variant",
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-04T00:00:00Z",
};

const provenance: GlossaryProvenance = {
  id: 9,
  glossary_entry_id: 1,
  novel_id: 42,
  source_site: "kakuyomu",
  source_adapter: "kakuyomu",
  source_novel_id: "16817330655991571532",
  source_url: null,
  source_chapter_id: "ch-1",
  source_chapter_number: 1,
  chapter_id: null,
  raw_source_term: "Eren JP",
  observed_translated_term: "Ellen",
  evidence_ref: "seed doc",
  local_reference: "section 1",
  evidence_quality: "mojibake",
  confidence: 0.8,
  first_seen_at: null,
  last_seen_at: null,
  created_at: "2026-01-03T00:00:00Z",
  updated_at: "2026-01-04T00:00:00Z",
};

const decisionEvent: GlossaryDecisionEvent = {
  id: 20,
  novel_id: 42,
  glossary_entry_id: 1,
  alias_id: null,
  actor_user_id: 1,
  event_type: "approve",
  old_value_json: '{"status":"candidate"}',
  new_value_json: '{"status":"approved"}',
  rationale: null,
  decision_source: "owner",
  created_at: "2026-01-05T00:00:00Z",
};

const qaFinding: GlossaryQaFinding = {
  id: 30,
  novel_id: 42,
  chapter_id: 4,
  glossary_entry_id: 1,
  finding_type: "banned_alias",
  severity: "warning",
  matched_text: "Alberto",
  suggested_text: "Albert",
  context_ref: "p0001",
  status: "open",
  reviewer_user_id: null,
  reviewer_notes: null,
  created_at: "2026-01-06T00:00:00Z",
  resolved_at: null,
};

beforeEach(() => {
  mockListGlossaryDecisionEvents.mockResolvedValue([]);
  mockListGlossaryQaFindings.mockResolvedValue([]);
});

afterEach(() => {
  mockListGlossaryEntries.mockReset();
  mockCreateGlossaryEntry.mockReset();
  mockUpdateGlossaryEntry.mockReset();
  mockChangeGlossaryEntryStatus.mockReset();
  mockLockGlossaryEntry.mockReset();
  mockUnlockGlossaryEntry.mockReset();
  mockDeprecateGlossaryEntry.mockReset();
  mockListGlossaryAliases.mockReset();
  mockAddGlossaryAlias.mockReset();
  mockUpdateGlossaryAlias.mockReset();
  mockDeprecateGlossaryAlias.mockReset();
  mockListGlossaryProvenanceForEntry.mockReset();
  mockAddGlossaryProvenance.mockReset();
  mockListGlossaryDecisionEvents.mockReset();
  mockListGlossaryQaFindings.mockReset();
  mockUpdateGlossaryQaFindingStatus.mockReset();
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
    expect(screen.queryByRole("button", { name: /scan/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /prompt injection/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /replace/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /repair/i })).not.toBeInTheDocument();
  });

  it("selecting an entry loads aliases and provenance with novelId and entryId", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([alias]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([provenance]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));

    await waitFor(() => {
      expect(mockListGlossaryAliases).toHaveBeenCalledWith("42", 1);
      expect(mockListGlossaryProvenanceForEntry).toHaveBeenCalledWith("42", 1);
    });
    expect(screen.getByText("Alberto")).toBeInTheDocument();
    expect(screen.getByText("kakuyomu / kakuyomu")).toBeInTheDocument();
    expect(screen.getByText("Source metadata is evidence only. Glossary ownership remains per novel.")).toBeInTheDocument();
  });

  it("loads selected-entry decision history without mutating glossary data", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockListGlossaryDecisionEvents.mockResolvedValue([decisionEvent]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));

    await waitFor(() => {
      expect(mockListGlossaryDecisionEvents).toHaveBeenCalledWith("42", 1);
    });
    expect(screen.getByText("approve")).toBeInTheDocument();
    expect(screen.getByText("No rationale recorded.")).toBeInTheDocument();
    expect(screen.getByText('Previous: {"status":"candidate"}')).toBeInTheDocument();
    expect(screen.getByText('New: {"status":"approved"}')).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /decision/i })).not.toBeInTheDocument();
  });

  it("shows decision history empty and error states", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockListGlossaryDecisionEvents.mockResolvedValueOnce([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getByText("No decision events yet.")).toBeInTheDocument());

    cleanup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockListGlossaryDecisionEvents.mockRejectedValue(new Error("Decision failure"));
    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getAllByText("Failed to load decision history.").length).toBeGreaterThan(0));
  });

  it("lists QA findings and updates only finding status", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockListGlossaryQaFindings.mockResolvedValue([qaFinding]);
    mockUpdateGlossaryQaFindingStatus.mockResolvedValue({ ...qaFinding, status: "dismissed" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("banned alias")).toBeInTheDocument());
    expect(screen.getByText("Matched: Alberto")).toBeInTheDocument();
    expect(screen.getByText("Suggested: Albert")).toBeInTheDocument();
    expect(screen.getByText("Context: p0001")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Update QA finding 30 status"), "dismissed");

    await waitFor(() => {
      expect(mockUpdateGlossaryQaFindingStatus).toHaveBeenCalledWith("42", 30, { status: "dismissed" });
    });
    expect(screen.queryByRole("button", { name: /scan/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /repair/i })).not.toBeInTheDocument();
  });

  it("filters QA findings by status and chapter id", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockListGlossaryQaFindings.mockResolvedValue([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("No QA findings yet.")).toBeInTheDocument());
    await user.selectOptions(screen.getByLabelText("Filter QA findings by status"), "open");
    await user.type(screen.getByLabelText("Filter QA findings by chapter id"), "4");

    await waitFor(() => {
      expect(mockListGlossaryQaFindings).toHaveBeenCalledWith("42", { status: "open", chapter_id: 4 });
    });
  });

  it("shows QA findings empty and error states", async () => {
    mockListGlossaryEntries.mockResolvedValue([]);
    mockListGlossaryQaFindings.mockResolvedValueOnce([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByText("No QA findings yet.")).toBeInTheDocument());

    cleanup();
    mockListGlossaryEntries.mockResolvedValue([]);
    mockListGlossaryQaFindings.mockRejectedValue(new Error("QA failure"));
    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getAllByText("Failed to load QA findings.").length).toBeGreaterThan(0));
  });

  it("adds an alias with selected entry scope", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockAddGlossaryAlias.mockResolvedValue(alias);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Add alias" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Add alias" }));
    await user.type(screen.getByLabelText("Alias text"), "Auri");
    await user.selectOptions(screen.getByLabelText("Alias type"), "banned");
    await user.selectOptions(screen.getByLabelText("Applies to"), "translated_text");
    await user.selectOptions(screen.getByLabelText("Matching policy override"), "exact_phrase");
    await user.type(screen.getByLabelText("Notes"), "Bad output variant");
    await user.click(screen.getAllByRole("button", { name: "Add alias" }).at(-1)!);

    await waitFor(() => {
      expect(mockAddGlossaryAlias).toHaveBeenCalledWith("42", 1, expect.objectContaining({
        alias_text: "Auri",
        alias_type: "banned",
        applies_to: "translated_text",
        matching_policy: "exact_phrase",
        notes: "Bad output variant",
      }));
    });
  });

  it("blocks blank alias text before submit", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Add alias" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Add alias" }));
    await user.click(screen.getAllByRole("button", { name: "Add alias" }).at(-1)!);

    expect(screen.getByText("Alias text is required.")).toBeInTheDocument();
    expect(mockAddGlossaryAlias).not.toHaveBeenCalled();
  });

  it("updates and deprecates aliases with the actual client signatures", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([alias]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockUpdateGlossaryAlias.mockResolvedValue({ ...alias, alias_text: "Albertox" });
    mockDeprecateGlossaryAlias.mockResolvedValue({ ...alias, alias_type: "deprecated" });

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getByText("Alberto")).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Edit alias" }));
    const aliasInput = screen.getByLabelText("Alias text");
    await user.clear(aliasInput);
    await user.type(aliasInput, "Albertox");
    await user.click(screen.getByRole("button", { name: "Save alias" }));

    await waitFor(() => {
      expect(mockUpdateGlossaryAlias).toHaveBeenCalledWith("42", 5, expect.objectContaining({ alias_text: "Albertox" }));
    });

    await user.click(screen.getByRole("button", { name: "Deprecate alias" }));
    await user.click(within(screen.getByRole("dialog", { name: "Deprecate alias" })).getByRole("button", { name: "Deprecate alias" }));

    await waitFor(() => {
      expect(mockDeprecateGlossaryAlias).toHaveBeenCalledWith("42", 5);
    });
  });

  it("adds provenance evidence with selected entry scope", async () => {
    const user = userEvent.setup();
    mockListGlossaryEntries.mockResolvedValue([entry]);
    mockListGlossaryAliases.mockResolvedValue([]);
    mockListGlossaryProvenanceForEntry.mockResolvedValue([]);
    mockAddGlossaryProvenance.mockResolvedValue(provenance);

    renderWithQuery(<AdminGlossaryShell novelId="42" />);

    await waitFor(() => expect(screen.getByRole("button", { name: "Select" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Select" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Add provenance" })).toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Add provenance" }));
    await user.type(screen.getByLabelText("Source site"), "kakuyomu");
    await user.type(screen.getByLabelText("Source adapter"), "kakuyomu");
    await user.type(screen.getByLabelText("Source novel ID"), "16817330655991571532");
    await user.type(screen.getByLabelText("Source chapter number"), "1");
    await user.type(screen.getByLabelText("Raw source term"), "Eren JP");
    await user.type(screen.getByLabelText("Observed translated term"), "Ellen");
    await user.selectOptions(screen.getByLabelText("Evidence quality"), "mojibake");
    await user.type(screen.getByLabelText("Confidence"), "0.8");
    await user.click(screen.getAllByRole("button", { name: "Add provenance" }).at(-1)!);

    await waitFor(() => {
      expect(mockAddGlossaryProvenance).toHaveBeenCalledWith("42", 1, expect.objectContaining({
        source_site: "kakuyomu",
        source_adapter: "kakuyomu",
        source_novel_id: "16817330655991571532",
        source_chapter_number: 1,
        raw_source_term: "Eren JP",
        observed_translated_term: "Ellen",
        evidence_quality: "mojibake",
        confidence: 0.8,
      }));
    });
  });
});
