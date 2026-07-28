"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { DialogShell } from "@/components/admin/dialog-shell";
import { adminApi } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import type { AuditEventDetail, AuditEventListFilters } from "@/lib/api-types";

const ACTION_LABELS: Record<string, string> = {
  "user.enabled": "User enabled",
  "user.disabled": "User disabled",
  "user.role_changed": "User role changed",
  "user.sessions_revoked": "User sessions revoked",
  "user.delete": "User deleted",
  "takedown.reviewed": "Takedown reviewed",
  "credential.create": "Credential created",
  "credential.update": "Credential updated",
  "credential.delete": "Credential deleted",
  "export.run": "Export run",
  "settings.update": "Settings updated",
};

const TARGET_TYPE_LABELS: Record<string, string> = {
  user: "User",
  credential: "Credential",
  takedown_request: "Takedown request",
  export: "Export",
  settings: "Settings",
};

const STATUS_LABELS: Record<string, string> = {
  succeeded: "Succeeded",
  failed: "Failed",
  denied: "Denied",
  partial: "Partial",
  unknown: "Unknown",
};

const SEVERITY_LABELS: Record<string, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical",
  unknown: "Unknown",
};

function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action;
}

function targetTypeLabel(targetType: string | null | undefined): string {
  if (!targetType) return "—";
  return TARGET_TYPE_LABELS[targetType] ?? targetType;
}

function statusBadge(status: string | null | undefined): React.ReactElement {
  const normalized = (status ?? "unknown").toLowerCase();
  const label = STATUS_LABELS[normalized] ?? normalized;
  const tone =
    normalized === "succeeded"
      ? "green"
      : normalized === "failed" || normalized === "denied"
        ? "red"
        : normalized === "partial"
          ? "amber"
          : "neutral";
  return <Badge tone={tone}>{label}</Badge>;
}

function severityBadge(severity: string | null | undefined): React.ReactElement {
  const normalized = (severity ?? "unknown").toLowerCase();
  const label = SEVERITY_LABELS[normalized] ?? normalized;
  const tone =
    normalized === "critical"
      ? "red"
      : normalized === "warning"
        ? "amber"
        : normalized === "info"
          ? "blue"
          : "neutral";
  return <Badge tone={tone}>{label}</Badge>;
}

function formatDateForInput(value?: string | null): string {
  if (!value) return "";
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    // Return YYYY-MM-DD for date input, or YYYY-MM-DDTHH:mm for datetime-local
    return date.toISOString().slice(0, 16);
  } catch {
    return "";
  }
}

function parseDateFromInput(value: string): string | undefined {
  if (!value.trim()) return undefined;
  // Input from datetime-local is YYYY-MM-DD or YYYY-MM-DDTHH:mm.
  // Append seconds and Z for deterministic UTC — avoids local-timezone shift.
  const normalized = value.includes("T") ? `${value}:00.000Z` : `${value}T00:00:00.000Z`;
  // Validate the resulting ISO string is parseable
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return undefined;
  return normalized;
}

function JsonPreview({ value }: { value: unknown }): React.ReactElement {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  try {
    const str = JSON.stringify(value, null, 2);
    return (
      <pre className="max-h-64 overflow-auto rounded bg-muted p-2 text-xs font-mono whitespace-pre-wrap break-all">
        {str}
      </pre>
    );
  } catch {
    return <span className="text-destructive">[Unserializable]</span>;
  }
}

function MetadataSection({ metadata }: { metadata: Record<string, unknown> | null | undefined }): React.ReactElement {
  if (!metadata || Object.keys(metadata).length === 0) {
    return <p className="text-sm text-muted-foreground">No metadata.</p>;
  }
  return (
    <dl className="grid gap-2 sm:grid-cols-2 text-sm">
      {Object.entries(metadata).map(([key, value]) => (
        <React.Fragment key={key}>
          <dt className="font-medium text-muted-foreground">{key}</dt>
          <dd className="font-mono break-all">{typeof value === "string" ? value : String(value)}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function ChangesSection({ changes }: { changes: { before: Record<string, unknown>; after: Record<string, unknown> } | null | undefined }): React.ReactElement {
  if (!changes) {
    return <p className="text-sm text-muted-foreground">No changes recorded.</p>;
  }
  const allKeys = new Set([...Object.keys(changes.before), ...Object.keys(changes.after)]);
  if (allKeys.size === 0) {
    return <p className="text-sm text-muted-foreground">No changes recorded.</p>;
  }
  return (
    <div className="space-y-4">
      <table className="w-full text-sm border rounded-md overflow-hidden">
        <thead>
          <tr className="bg-muted text-left text-xs uppercase text-muted-foreground">
            <th className="px-3 py-2 border-b w-1/3">Field</th>
            <th className="px-3 py-2 border-b">Before</th>
            <th className="px-3 py-2 border-b">After</th>
          </tr>
        </thead>
        <tbody>
          {Array.from(allKeys).map((key) => (
            <tr key={key} className="border-b last:border-b-0">
              <td className="px-3 py-2 font-medium text-muted-foreground font-mono">{key}</td>
              <td className="px-3 py-2 font-mono text-xs break-all">
                {key in changes.before ? String(changes.before[key]) : <span className="text-muted-foreground">—</span>}
              </td>
              <td className="px-3 py-2 font-mono text-xs break-all">
                {key in changes.after ? String(changes.after[key]) : <span className="text-muted-foreground">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function AuditPage() {
  const queryClient = useQueryClient();

  const [actionFilter, setActionFilter] = React.useState("");
  const [actorUserIdFilter, setActorUserIdFilter] = React.useState("");
  const [targetTypeFilter, setTargetTypeFilter] = React.useState("");
  const [targetIdFilter, setTargetIdFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [severityFilter, setSeverityFilter] = React.useState("");
  const [requestIdFilter, setRequestIdFilter] = React.useState("");
  const [correlationIdFilter, setCorrelationIdFilter] = React.useState("");
  const [dateFromFilter, setDateFromFilter] = React.useState("");
  const [dateToFilter, setDateToFilter] = React.useState("");
  const [page, setPage] = React.useState(1);
  const pageSize = 50;

  const [detailOpen, setDetailOpen] = React.useState(false);
  const [selectedEventId, setSelectedEventId] = React.useState<number | null>(null);

  const filters = React.useMemo((): AuditEventListFilters => {
    const f: AuditEventListFilters = {
      page,
      page_size: pageSize,
    };
    if (actionFilter.trim()) f.action = actionFilter.trim();
    if (actorUserIdFilter.trim()) f.actor_user_id = Number.parseInt(actorUserIdFilter.trim(), 10);
    if (targetTypeFilter.trim()) f.target_type = targetTypeFilter.trim();
    if (targetIdFilter.trim()) f.target_id = targetIdFilter.trim();
    if (statusFilter.trim()) f.status = statusFilter.trim();
    if (severityFilter.trim()) f.severity = severityFilter.trim();
    if (requestIdFilter.trim()) f.request_id = requestIdFilter.trim();
    if (correlationIdFilter.trim()) f.correlation_id = correlationIdFilter.trim();
    const df = parseDateFromInput(dateFromFilter);
    const dt = parseDateFromInput(dateToFilter);
    if (df) f.date_from = df;
    if (dt) f.date_to = dt;
    return f;
  }, [
    actionFilter,
    actorUserIdFilter,
    targetTypeFilter,
    targetIdFilter,
    statusFilter,
    severityFilter,
    requestIdFilter,
    correlationIdFilter,
    dateFromFilter,
    dateToFilter,
    page,
  ]);

  const events = useQuery({
    queryKey: ["admin-audit", filters],
    queryFn: () => adminApi.listAuditEvents(filters),
    placeholderData: (previousData) => previousData,
  });

  const detailQuery = useQuery({
    queryKey: ["admin-audit-detail", selectedEventId],
    queryFn: () => (selectedEventId ? adminApi.getAuditEvent(selectedEventId) : null),
    enabled: detailOpen && selectedEventId !== null,
  });

  const total = events.data?.total ?? 0;
  const items = events.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const clearFilters = () => {
    setActionFilter("");
    setActorUserIdFilter("");
    setTargetTypeFilter("");
    setTargetIdFilter("");
    setStatusFilter("");
    setSeverityFilter("");
    setRequestIdFilter("");
    setCorrelationIdFilter("");
    setDateFromFilter("");
    setDateToFilter("");
    setPage(1);
  };

  const openDetail = (eventId: number) => {
    setSelectedEventId(eventId);
    setDetailOpen(true);
  };

  const closeDetail = () => {
    setDetailOpen(false);
    setSelectedEventId(null);
    // Invalidate to refetch if reopened
    queryClient.invalidateQueries({ queryKey: ["admin-audit-detail", selectedEventId] });
  };

  return (
    <>
      <PageHeading
        title="Audit log"
        description="Immutable record of sensitive owner actions. Metadata is server-redacted before display."
      />

      {events.isError && (
        <ErrorBanner error={events.error} fallback="Could not load audit log." className="mb-4 rounded-md border" />
      )}

      <Panel className="mb-4">
        <PanelHeader>
          <PanelTitle>Filters</PanelTitle>
        </PanelHeader>
        <PanelBody className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-action">Action</label>
            <Input
              id="audit-action"
              value={actionFilter}
              onChange={(event) => { setActionFilter(event.target.value); setPage(1); }}
              placeholder="e.g. user.enabled"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-actor-user-id">Actor user ID</label>
            <Input
              id="audit-actor-user-id"
              type="number"
              min="1"
              value={actorUserIdFilter}
              onChange={(event) => { setActorUserIdFilter(event.target.value); setPage(1); }}
              placeholder="e.g. 1"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-target-type">Target type</label>
            <Input
              id="audit-target-type"
              value={targetTypeFilter}
              onChange={(event) => { setTargetTypeFilter(event.target.value); setPage(1); }}
              placeholder="e.g. user"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-target-id">Target ID</label>
            <Input
              id="audit-target-id"
              value={targetIdFilter}
              onChange={(event) => { setTargetIdFilter(event.target.value); setPage(1); }}
              placeholder="e.g. 42"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-status">Status</label>
            <Input
              id="audit-status"
              value={statusFilter}
              onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}
              placeholder="succeeded, failed, denied, partial"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-severity">Severity</label>
            <Input
              id="audit-severity"
              value={severityFilter}
              onChange={(event) => { setSeverityFilter(event.target.value); setPage(1); }}
              placeholder="info, warning, critical"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-request-id">Request ID</label>
            <Input
              id="audit-request-id"
              value={requestIdFilter}
              onChange={(event) => { setRequestIdFilter(event.target.value); setPage(1); }}
              placeholder="req-abc123"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-correlation-id">Correlation ID</label>
            <Input
              id="audit-correlation-id"
              value={correlationIdFilter}
              onChange={(event) => { setCorrelationIdFilter(event.target.value); setPage(1); }}
              placeholder="corr-xyz789"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-date-from">Date from</label>
            <Input
              id="audit-date-from"
              type="datetime-local"
              value={formatDateForInput(dateFromFilter)}
              onChange={(event) => { setDateFromFilter(event.target.value); setPage(1); }}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="audit-date-to">Date to</label>
            <Input
              id="audit-date-to"
              type="datetime-local"
              value={formatDateForInput(dateToFilter)}
              onChange={(event) => { setDateToFilter(event.target.value); setPage(1); }}
            />
          </div>
          <div className="flex items-end justify-end lg:col-span-5">
            <Button type="button" variant="outline" onClick={clearFilters}>Clear</Button>
          </div>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle>Events ({total})</PanelTitle>
        </PanelHeader>
        <PanelBody className="p-0">
          <table className="w-full table-auto text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                <th className="px-4 py-2">When</th>
                <th className="px-4 py-2">Action</th>
                <th className="px-4 py-2">Actor</th>
                <th className="px-4 py-2">Target</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Severity</th>
                <th className="px-4 py-2">Request ID</th>
                <th className="px-4 py-2">Correlation ID</th>
                <th className="px-4 py-2">Summary</th>
                <th className="px-4 py-2 w-20"></th>
              </tr>
            </thead>
            <tbody>
              {events.isLoading ? (
                <LoadingRows colSpan={10} />
              ) : items.length === 0 ? (
                <EmptyState
                  colSpan={10}
                  title="No audit events match."
                  description="Adjust the filters or wait for the first sensitive action to be recorded."
                />
              ) : items.map((event) => (
                <tr key={event.id} className="border-b last:border-b-0 hover:bg-muted/30">
                  <td className="px-4 py-2 align-top text-xs text-muted-foreground">
                    {event.created_at ? formatDateTime(event.created_at) : "—"}
                  </td>
                  <td className="px-4 py-2 align-top font-mono text-xs">
                    <span title={event.action}>{actionLabel(event.action)}</span>
                  </td>
                  <td className="px-4 py-2 align-top text-xs">
                    {event.actor_user_id ?? "—"}
                  </td>
                  <td className="px-4 py-2 align-top text-xs">
                    <span className="font-mono">{targetTypeLabel(event.target_type)}</span>
                    {event.target_id ? (
                      <span className="text-muted-foreground"> / {event.target_id}</span>
                    ) : null}
                  </td>
                  <td className="px-4 py-2 align-top">{statusBadge(event.status)}</td>
                  <td className="px-4 py-2 align-top">{severityBadge(event.severity)}</td>
                  <td className="px-4 py-2 align-top font-mono text-xs">{event.request_id || "—"}</td>
                  <td className="px-4 py-2 align-top font-mono text-xs">{event.correlation_id || "—"}</td>
                  <td className="px-4 py-2 align-top text-xs max-w-xs truncate" title={event.summary || ""}>
                    {event.summary || "—"}
                  </td>
                  <td className="px-4 py-2 align-top">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => openDetail(event.id)}
                      aria-label={`View details for audit event ${event.id}`}
                    >
                      Details
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </PanelBody>
      </Panel>

      <div className="mt-3 flex items-center justify-between text-sm">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setPage((current) => Math.max(1, current - 1))}
          disabled={page <= 1}
        >
          Previous
        </Button>
        <span className="text-xs text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>

      {/* Detail Dialog */}
      <DialogShell
        open={detailOpen}
        title={`Audit event ${selectedEventId ?? ""}`}
        description="Server-redacted detail for a single audit event."
        onClose={closeDetail}
        className="max-w-3xl"
        footer={
          <div className="flex justify-end">
            <Button variant="outline" onClick={closeDetail}>Close</Button>
          </div>
        }
      >
        {detailQuery.isLoading ? (
          <div className="p-4 text-center text-sm text-muted-foreground">Loading detail…</div>
        ) : detailQuery.isError ? (
          <ErrorBanner error={detailQuery.error} fallback="Could not load audit event detail." className="p-4" />
        ) : detailQuery.data ? (
          <div className="space-y-6 p-4">
            <dl className="grid gap-3 sm:grid-cols-2 text-sm border rounded-md p-4 bg-muted/30">
              <dt className="font-medium text-muted-foreground">Timestamp</dt>
              <dd className="font-mono">{detailQuery.data.created_at ? formatDateTime(detailQuery.data.created_at) : "—"}</dd>

              <dt className="font-medium text-muted-foreground">Actor</dt>
              <dd>{detailQuery.data.actor_user_id ?? "—"}</dd>

              <dt className="font-medium text-muted-foreground">Action</dt>
              <dd className="font-mono">{actionLabel(detailQuery.data.action)}</dd>

              <dt className="font-medium text-muted-foreground">Target</dt>
              <dd>
                <span className="font-mono">{targetTypeLabel(detailQuery.data.target_type)}</span>
                {detailQuery.data.target_id ? <span className="text-muted-foreground ml-1">/ {detailQuery.data.target_id}</span> : null}
              </dd>

              <dt className="font-medium text-muted-foreground">Status</dt>
              <dd>{statusBadge(detailQuery.data.status)}</dd>

              <dt className="font-medium text-muted-foreground">Severity</dt>
              <dd>{severityBadge(detailQuery.data.severity)}</dd>

              {detailQuery.data.request_id && (
                <>
                  <dt className="font-medium text-muted-foreground">Request ID</dt>
                  <dd className="font-mono text-xs break-all">{detailQuery.data.request_id}</dd>
                </>
              )}

              {detailQuery.data.correlation_id && (
                <>
                  <dt className="font-medium text-muted-foreground">Correlation ID</dt>
                  <dd className="font-mono text-xs break-all">{detailQuery.data.correlation_id}</dd>
                </>
              )}
            </dl>

            <section>
              <h3 className="mb-2 text-sm font-medium">Summary</h3>
              <p className="text-sm text-muted-foreground">{detailQuery.data.summary || "—"}</p>
            </section>

            <section>
              <h3 className="mb-2 text-sm font-medium">Metadata</h3>
              <MetadataSection metadata={detailQuery.data.metadata} />
            </section>

            <section>
              <h3 className="mb-2 text-sm font-medium">Changes</h3>
              <ChangesSection changes={detailQuery.data.changes} />
            </section>
          </div>
        ) : (
          <div className="p-4 text-center text-sm text-muted-foreground">No detail available.</div>
        )}
      </DialogShell>
    </>
  );
}
