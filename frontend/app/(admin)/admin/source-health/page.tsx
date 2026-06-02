"use client";

import { useQuery } from "@tanstack/react-query";
import { RotateCw } from "lucide-react";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function SourceHealthPage() {
  const sourceHealth = useQuery({ queryKey: ["source-health"], queryFn: () => api.sourceHealth(), refetchInterval: 10000 });
  const rows = sourceHealth.data?.sources ?? [];

  return (
    <>
      <PageHeading title="Sources" description="Crawler adapter health, recent failures, and source reliability counters." />

      <Panel>
        <PanelHeader className="flex flex-row items-center justify-between">
          <PanelTitle>Source Health</PanelTitle>
          <Button variant="outline" size="sm" onClick={() => void sourceHealth.refetch()} disabled={sourceHealth.isFetching}>
            <RotateCw className="h-4 w-4" />
            Refresh
          </Button>
        </PanelHeader>
        <PanelBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Success</th>
                  <th className="px-4 py-3">Failure</th>
                  <th className="px-4 py-3">Last Success</th>
                  <th className="px-4 py-3">Last Failure</th>
                  <th className="px-4 py-3">Last Error</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((source) => (
                    <tr key={source.source_key} className="border-b last:border-0">
                      <td className="px-4 py-3 font-medium">{source.source_key}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={source.failure_count > 0 ? "failed" : "ok"} />
                      </td>
                      <td className="px-4 py-3">{source.success_count}</td>
                      <td className="px-4 py-3">{source.failure_count}</td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(source.last_success_at)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(source.last_failure_at)}</td>
                      <td className="max-w-[420px] truncate px-4 py-3 text-muted-foreground">{source.last_error || "-"}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-4 py-6 text-muted-foreground" colSpan={7}>
                      No source health records yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>
    </>
  );
}
