"use client";

import { RotateCw } from "lucide-react";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { SourceHealth } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export type SourceHealthPanelProps = {
  sources: SourceHealth[];
  loading: boolean;
  fetching: boolean;
  error: unknown;
  onRefresh: () => void;
};

export function SourceHealthPanel({ sources, loading, fetching, error, onRefresh }: SourceHealthPanelProps) {
  return (
    <Panel className="flex h-full min-h-0 flex-col">
      <PanelHeader className="flex flex-row items-center justify-between">
        <PanelTitle>Source Health</PanelTitle>
        <Button
          variant="outline"
          size="sm"
          className="min-h-11 rounded-lg focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
          onClick={onRefresh}
          disabled={fetching}
        >
          <RotateCw className="h-4 w-4" />
          Refresh
        </Button>
      </PanelHeader>
      <ErrorBanner error={error} fallback="Failed to load source health." />
      <PanelBody className="min-h-0 flex-1 p-0">
        <div className="seamless-scrollbar h-full overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-muted/55 text-xs uppercase tracking-wider font-metadata text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Health</th>
                <th className="px-4 py-3">Success</th>
                <th className="px-4 py-3">Failure</th>
                <th className="px-4 py-3">Last Seen</th>
                <th className="px-4 py-3">Last Error</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <LoadingRows colSpan={6} label="Loading source health..." />
              ) : error ? (
                <EmptyState title="Failed to load source health." colSpan={6} />
              ) : sources.length ? (
                sources.map((source) => (
                  <tr key={source.source_key} className="border-b border-border/50 last:border-0 hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium font-metadata">{source.source_key}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={source.failure_count > 0 ? "failed" : "ok"} />
                    </td>
                    <td className="px-4 py-3 tabular-nums font-mono">{source.success_count}</td>
                    <td className="px-4 py-3 tabular-nums font-mono">{source.failure_count}</td>
                    <td className="px-4 py-3 text-muted-foreground tabular-nums text-xs">
                      {formatDateTime(source.last_success_at || source.last_failure_at)}
                    </td>
                    <td className="max-w-[280px] truncate px-4 py-3 text-muted-foreground text-xs">{source.last_error || "-"}</td>
                  </tr>
                ))
              ) : (
                <EmptyState title="No source health data yet." colSpan={6} />
              )}
            </tbody>
          </table>
        </div>
      </PanelBody>
    </Panel>
  );
}
