"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminApi } from "@/lib/api";
import type { AnalyticsEventCounts, AnalyticsWindow } from "@/lib/api-types";

const WINDOWS: AnalyticsWindow[] = ["5m", "15m", "1h", "24h", "7d", "30d"];

const GROUPS: Array<{ key: "views" | "exports" | "search" | "features"; title: string }> = [
  { key: "views", title: "Views" },
  { key: "exports", title: "Exports" },
  { key: "search", title: "Searches" },
  { key: "features", title: "Feature interactions" },
];

function total(counts: AnalyticsEventCounts): number {
  return Object.values(counts).reduce((sum, count) => sum + count, 0);
}

function eventLabel(eventName: string): string {
  return eventName.replace(/[._]/g, " ");
}

export default function AnalyticsPage() {
  const [window, setWindow] = React.useState<AnalyticsWindow>("24h");
  const summary = useQuery({
    queryKey: ["analytics-summary", window, "UTC"],
    queryFn: () => adminApi.analyticsSummary({ window, timezone: "UTC" }),
  });

  const data = summary.data;
  const noEvents = data && GROUPS.every(({ key }) => total(data.groups[key]) === 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <PageHeading title="Analytics" description="Aggregate event counts only. No user-level activity." />
        <div className="flex items-end gap-2">
          <label className="grid gap-1 text-sm font-medium" htmlFor="analytics-window">
            Window
            <select
              id="analytics-window"
              className="h-9 rounded-md border bg-background px-3 text-sm"
              value={window}
              onChange={(event) => setWindow(event.target.value as AnalyticsWindow)}
            >
              {WINDOWS.map((value) => <option key={value} value={value}>{value}</option>)}
            </select>
          </label>
          <Button variant="outline" size="sm" onClick={() => void summary.refetch()} disabled={summary.isFetching}>
            Refresh
          </Button>
        </div>
      </div>

      {summary.isPending ? <p role="status" className="text-sm text-muted-foreground">Loading analytics…</p> : null}
      {summary.isError && !data ? <ErrorBanner error={summary.error} fallback="Analytics summary is unavailable." /> : null}

      {data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {GROUPS.map(({ key, title }) => {
              const unavailable = data.failed_groups.includes(key);
              return (
                <Panel key={key}>
                  <PanelHeader><PanelTitle>{title}</PanelTitle></PanelHeader>
                  <PanelBody>
                    <div className="text-2xl font-semibold">{unavailable ? "Unavailable" : total(data.groups[key])}</div>
                  </PanelBody>
                </Panel>
              );
            })}
          </div>

          <p className="text-sm text-muted-foreground">
            Generated {data.generated_at} · {data.timezone} · {data.window} · {data.status}
          </p>
          {data.status === "partial" ? <p role="status" className="text-sm text-amber-700">Some groups are unavailable.</p> : null}
          {summary.isRefetchError ? <ErrorBanner error={summary.error} fallback="Analytics refresh failed; showing prior data." /> : null}

          {noEvents ? <EmptyState title="No analytics events in this window." /> : null}

          {!noEvents ? GROUPS.map(({ key, title }) => (
            <Panel key={key}>
              <PanelHeader><PanelTitle>{title}</PanelTitle></PanelHeader>
              <PanelBody>
                {data.failed_groups.includes(key) ? <p className="text-sm text-muted-foreground">Unavailable.</p> : (
                  <table className="w-full text-sm">
                    <thead><tr className="border-b text-left"><th className="py-2 font-medium">Event</th><th className="py-2 text-right font-medium">Count</th></tr></thead>
                    <tbody>{Object.entries(data.groups[key]).map(([eventName, count]) => (
                      <tr className="border-b last:border-0" key={eventName}><td className="py-2 capitalize">{eventLabel(eventName)}</td><td className="py-2 text-right">{count}</td></tr>
                    ))}</tbody>
                  </table>
                )}
              </PanelBody>
            </Panel>
          )) : null}
        </>
      ) : null}
    </div>
  );
}
