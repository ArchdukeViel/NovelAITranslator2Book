"use client";

import { useQuery } from "@tanstack/react-query";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

type RuntimeStateSummary = {
  status?: string;
  timestamp?: string;
  active_cooldowns?: number;
  active_failures?: number;
  exhausted_scopes?: number;
  stale_scopes?: number;
  runtime_states?: Array<Record<string, unknown>>;
};

type SchedulerHealthResponse = Record<string, unknown> & {
  runtime_state_summary?: RuntimeStateSummary;
};

function statusBadgeClass(status: string | undefined): string {
  switch ((status ?? "").toLowerCase()) {
    case "healthy":
      return "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300";
    case "degraded":
      return "bg-amber-500/15 text-amber-700 dark:text-amber-300";
    case "unhealthy":
      return "bg-red-500/15 text-red-700 dark:text-red-300";
    default:
      return "bg-muted text-muted-foreground";
  }
}

function formatNextEligible(value: unknown): string {
  if (typeof value !== "string") return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

/** Dashboard panel surfacing persisted scheduler runtime state (DEBT-052). */
export function SchedulerHealthCard() {
  const health = useQuery({
    queryKey: ["admin", "scheduler-health"],
    queryFn: async () => (await api.schedulerHealth()) as SchedulerHealthResponse,
    refetchInterval: 30_000,
  });

  const summary = health.data?.runtime_state_summary;
  const statusLabel = (summary?.status ?? "unknown").toUpperCase();
  const states = summary?.runtime_states ?? [];

  return (
    <Panel className="mt-5">
      <PanelHeader>
        <PanelTitle>Scheduler health</PanelTitle>
      </PanelHeader>
      <PanelBody className="space-y-3">
        <ErrorBanner
          error={health.isError ? health.error : undefined}
          fallback="Could not load scheduler health."
        />
        {!summary ? null : (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className={`rounded px-2 py-0.5 text-xs font-semibold ${statusBadgeClass(summary.status)}`}>
              {statusLabel}
            </span>
            <span className="text-muted-foreground">
              cooldowns: <strong>{summary.active_cooldowns ?? 0}</strong>
            </span>
            <span className="text-muted-foreground">
              failures: <strong>{summary.active_failures ?? 0}</strong>
            </span>
            <span className="text-muted-foreground">
              exhausted: <strong>{summary.exhausted_scopes ?? 0}</strong>
            </span>
            <span className="text-muted-foreground">
              stale: <strong>{summary.stale_scopes ?? 0}</strong>
            </span>
          </div>
        )}

        {health.isLoading ? (
          <table className="w-full table-auto text-sm">
            <tbody>
              <LoadingRows colSpan={5} label="Loading scheduler health..." />
            </tbody>
          </table>
        ) : states.length === 0 ? (
          <EmptyState
            title="No persisted scheduler scopes"
            description="Scopes are recorded when the scheduler first contacts a provider or source. Active state appears here as soon as the scheduler runs."
          />
        ) : (
          <table className="w-full table-auto text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                <th className="px-3 py-2">Scope</th>
                <th className="px-3 py-2">State</th>
                <th className="px-3 py-2">Reason</th>
                <th className="px-3 py-2">Next eligible</th>
                <th className="px-3 py-2">Failures</th>
              </tr>
            </thead>
            <tbody>
              {states.map((entry, index) => {
                const scope = `${String(entry.scope_type ?? "?")}/${String(entry.scope_key ?? "?")}`;
                return (
                  <tr key={`${scope}-${index}`} className="border-b last:border-b-0">
                    <td className="px-3 py-2 font-mono text-xs">{scope}</td>
                    <td className="px-3 py-2 text-xs">{String(entry.state ?? "—")}</td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {String(entry.reason ?? entry.error_category ?? "—")}
                    </td>
                    <td className="px-3 py-2 text-xs">{formatNextEligible(entry.next_eligible_at)}</td>
                    <td className="px-3 py-2 text-xs">{Number(entry.consecutive_failures ?? 0)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </PanelBody>
    </Panel>
  );
}
