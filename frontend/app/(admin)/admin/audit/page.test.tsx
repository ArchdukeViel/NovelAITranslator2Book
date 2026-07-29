import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AuditPage from "@/app/(admin)/admin/audit/page";
import type { AuditEventDetail, AuditEventListResponse, AuditEventSummary } from "@/lib/api-types";

const listAuditEvents = vi.hoisted(() => vi.fn());
const getAuditEvent = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/api")>();
  return {
    ...actual,
    adminApi: {
      ...actual.adminApi,
      listAuditEvents: (...args: unknown[]) => listAuditEvents(...args),
      getAuditEvent: (...args: unknown[]) => getAuditEvent(...args),
    },
  };
});

function renderWithQuery(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

function auditEvent(overrides: Partial<AuditEventSummary> = {}): AuditEventSummary {
  return {
    id: 1,
    created_at: "2026-07-27T12:00:00+00:00",
    actor_user_id: 1,
    action: "user.enabled",
    target_type: "user",
    target_id: "42",
    status: "succeeded",
    severity: "info",
    request_id: "req-abc123",
    correlation_id: "corr-xyz789",
    summary: "User enabled by owner",
    ...overrides,
  };
}

function auditResponse(overrides: Partial<AuditEventListResponse> = {}): AuditEventListResponse {
  return {
    items: [auditEvent()],
    total: 1,
    page: 1,
    page_size: 50,
    ...overrides,
  };
}

afterEach(() => {
  vi.restoreAllMocks();
  cleanup();
});

describe("AuditPage list", () => {
  it("shows loading then populated list with known labels", async () => {
    let resolve!: (value: AuditEventListResponse) => void;
    listAuditEvents.mockReturnValue(new Promise<AuditEventListResponse>((done) => { resolve = done; }));
    renderWithQuery(<AuditPage />);

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    resolve(auditResponse({ items: [auditEvent({ action: "user.enabled", target_type: "user", status: "succeeded", severity: "info" })] }));

    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());
    expect(screen.getByText("User")).toBeInTheDocument();
    expect(screen.getByText("Succeeded")).toBeInTheDocument();
    expect(screen.getByText("Info")).toBeInTheDocument();
    expect(screen.getByText("req-abc123")).toBeInTheDocument();
    expect(screen.getByText("corr-xyz789")).toBeInTheDocument();
  });

  it("shows unknown action/target labels as raw values", async () => {
    listAuditEvents.mockResolvedValue(auditResponse({ items: [auditEvent({ action: "unknown.action", target_type: "unknown_type", status: "weird", severity: "strange" })] }));
    renderWithQuery(<AuditPage />);

    await waitFor(() => expect(screen.getByText("unknown.action")).toBeInTheDocument());
    expect(screen.getByText("unknown_type")).toBeInTheDocument();
    expect(screen.getByText("weird")).toBeInTheDocument();
    expect(screen.getByText("strange")).toBeInTheDocument();
  });

  it("shows empty state when no items", async () => {
    listAuditEvents.mockResolvedValue(auditResponse({ items: [], total: 0 }));
    renderWithQuery(<AuditPage />);

    await waitFor(() => expect(screen.getByText("No audit events match.")).toBeInTheDocument());
  });

  it("shows error state", async () => {
    listAuditEvents.mockRejectedValue(new Error("network down"));
    renderWithQuery(<AuditPage />);

    await waitFor(() => expect(screen.getByText(/network down/i)).toBeInTheDocument());
  });

  it("paginates: page 2 calls list API with page=2", async () => {
    listAuditEvents.mockResolvedValue(auditResponse({ page: 2, total: 100 }));
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 50 })));
  });

  it("applies all labeled filters and clears them", async () => {
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.type(screen.getByLabelText("Action"), "user.enabled");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ action: "user.enabled", page: 1 })));

    await user.type(screen.getByLabelText("Actor user ID"), "5");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ actor_user_id: 5, page: 1 })));

    await user.type(screen.getByLabelText("Target type"), "credential");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ target_type: "credential", page: 1 })));

    await user.type(screen.getByLabelText("Target ID"), "123");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ target_id: "123", page: 1 })));

    await user.type(screen.getByLabelText("Status"), "failed");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ status: "failed", page: 1 })));

    await user.type(screen.getByLabelText("Severity"), "critical");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ severity: "critical", page: 1 })));

    await user.type(screen.getByLabelText("Request ID"), "req-test");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ request_id: "req-test", page: 1 })));

    await user.type(screen.getByLabelText("Correlation ID"), "corr-test");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ correlation_id: "corr-test", page: 1 })));

    await user.type(screen.getByLabelText("Date from"), "2026-07-01T00:00");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ date_from: "2026-07-01T00:00:00.000Z", page: 1 })));

    await user.type(screen.getByLabelText("Date to"), "2026-07-31T23:59");
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ date_to: "2026-07-31T23:59:00.000Z", page: 1 })));

    await user.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(listAuditEvents).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, page_size: 50 })));
    expect(screen.getByLabelText("Action")).toHaveValue("");
    // Number input: empty string renders as null in testing-library
    expect(screen.getByLabelText("Actor user ID")).toHaveValue(null);
    expect(screen.getByLabelText("Target type")).toHaveValue("");
    expect(screen.getByLabelText("Target ID")).toHaveValue("");
    expect(screen.getByLabelText("Status")).toHaveValue("");
    expect(screen.getByLabelText("Severity")).toHaveValue("");
    expect(screen.getByLabelText("Request ID")).toHaveValue("");
    expect(screen.getByLabelText("Correlation ID")).toHaveValue("");
  });
});

function auditEventDetail(overrides: Partial<AuditEventDetail> = {}): AuditEventDetail {
  return {
    ...auditEvent(),
    metadata: {},
    changes: null,
    ...overrides,
  };
}

describe("AuditPage detail dialog", () => {
  it("clicking Details button calls getAuditEvent with event ID", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail());
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    await waitFor(() => expect(getAuditEvent).toHaveBeenCalledWith(1));
  });

  it("shows loading state while detail loads", async () => {
    let resolve!: (value: AuditEventDetail) => void;
    getAuditEvent.mockReturnValue(new Promise<AuditEventDetail>((done) => { resolve = done; }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    expect(await screen.findByText("Loading detail…")).toBeInTheDocument();
  });

  it("shows error state when detail query fails", async () => {
    getAuditEvent.mockRejectedValue(new Error("event not found"));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    expect(await screen.findByText(/event not found/i)).toBeInTheDocument();
  });

  it("shows full detail content on success with known labels", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail({
      created_at: "2026-07-27T12:00:00+00:00",
      actor_user_id: 5,
      action: "user.enabled",
      target_type: "user",
      target_id: "42",
      status: "succeeded",
      severity: "info",
      request_id: "req-abc123",
      correlation_id: "corr-xyz789",
      summary: "User enabled by owner",
    }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog", { name: /Audit event 1/ });
    expect(dialog).toBeInTheDocument();

    // Timestamp (locale-sensitive format)
    expect(dialog).toHaveTextContent(/2026/);
    expect(dialog).toHaveTextContent(/Jul/i);

    // Actor
    expect(dialog).toHaveTextContent("5");

    // Action with known label
    expect(dialog).toHaveTextContent("User enabled");

    // Target type
    expect(dialog).toHaveTextContent("User");
    expect(dialog).toHaveTextContent("42");

    // Status and severity
    expect(dialog).toHaveTextContent("Succeeded");
    expect(dialog).toHaveTextContent("Info");

    // Request / correlation IDs
    expect(dialog).toHaveTextContent("req-abc123");
    expect(dialog).toHaveTextContent("corr-xyz789");

    // Summary
    expect(dialog).toHaveTextContent("User enabled by owner");
  });

  it("shows unknown action/target in detail dialog as raw values", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail({
      action: "strange.action",
      target_type: "odd_type",
      status: "weird",
      severity: "bizarre",
    }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog", { name: /Audit event 1/ });
    expect(dialog).toHaveTextContent("strange.action");
    expect(dialog).toHaveTextContent("odd_type");
    expect(dialog).toHaveTextContent("weird");
    expect(dialog).toHaveTextContent("bizarre");
  });

  it("displays metadata with redacted sentinel text and nested objects/arrays", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail({
      metadata: {
        ip_address: "***REDACTED***",
        headers: { "user-agent": "Mozilla/5.0" },
        tags: ["admin", "test"],
      },
    }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog", { name: /Audit event 1/ });

    // Redacted sentinel renders as escaped text
    expect(dialog).toHaveTextContent("***REDACTED***");

    // Nested object: MetadataSection uses String(value) which gives [object Object]
    expect(dialog).toHaveTextContent(/\[object Object\]/);

    // Array joined by commas: String(["admin", "test"]) => "admin,test"
    expect(dialog).toHaveTextContent("admin,test");
  });

  it("displays changes before/after in detail dialog", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail({
      changes: {
        before: { email: "old@example.com" },
        after: { email: "new@example.com" },
      },
    }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog", { name: /Audit event 1/ });

    // Field name
    expect(dialog).toHaveTextContent("email");
    // Before/after values
    expect(dialog).toHaveTextContent("old@example.com");
    expect(dialog).toHaveTextContent("new@example.com");
  });

  it("shows no-changes fallback when changes is null", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail({ changes: null }));
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog", { name: /Audit event 1/ });
    expect(dialog).toHaveTextContent("No changes recorded.");
  });

  it("has accessible dialog name, close button, and labeled filter controls", async () => {
    getAuditEvent.mockResolvedValue(auditEventDetail());
    listAuditEvents.mockResolvedValue(auditResponse());
    const user = userEvent.setup();
    renderWithQuery(<AuditPage />);
    await waitFor(() => expect(screen.getByText("User enabled")).toBeInTheDocument());

    // Labeled filter inputs
    expect(screen.getByLabelText("Action")).toBeInTheDocument();
    expect(screen.getByLabelText("Actor user ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Target type")).toBeInTheDocument();
    expect(screen.getByLabelText("Target ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
    expect(screen.getByLabelText("Severity")).toBeInTheDocument();
    expect(screen.getByLabelText("Request ID")).toBeInTheDocument();
    expect(screen.getByLabelText("Correlation ID")).toBeInTheDocument();

    // Open dialog
    await user.click(screen.getByRole("button", { name: /View details for audit event 1/ }));

    const dialog = await screen.findByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "Audit event 1");

    // Close button in dialog footer
    expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
  });
});
