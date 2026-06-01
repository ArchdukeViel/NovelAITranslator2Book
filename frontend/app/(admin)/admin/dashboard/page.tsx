"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCw, Square } from "lucide-react";

import { JobTable } from "@/components/admin/job-table";
import { Metric } from "@/components/admin/metric";
import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const requests = useQuery({ queryKey: ["requests"], queryFn: () => api.requests() });
  const worker = useQuery({ queryKey: ["worker"], queryFn: () => api.workerStatus(), refetchInterval: 5000 });
  const sources = useQuery({ queryKey: ["source-health"], queryFn: () => api.sourceHealth() });

  const invalidate = () => {
    void queryClient.invalidateQueries();
  };
  const start = useMutation({ mutationFn: api.workerStart, onSuccess: invalidate });
  const stop = useMutation({ mutationFn: api.workerStop, onSuccess: invalidate });
  const runOnce = useMutation({ mutationFn: api.workerRunOnce, onSuccess: invalidate });

  const jobRows = jobs.data?.jobs ?? [];
  const requestRows = requests.data?.requests ?? [];
  const workerStatus = worker.data;
  const failedSources = (sources.data?.sources ?? []).filter((item) => item.failure_count > 0).length;

  return (
    <>
      <PageHeading
        title="Dashboard"
        description="Operational overview for crawler, translation jobs, source health, and reader request intake."
      />

      <div className="grid gap-4 md:grid-cols-4">
        <Metric label="Queued jobs" value={jobRows.filter((job) => job.status === "pending").length} />
        <Metric label="Running worker" value={workerStatus?.running ? "Yes" : "No"} accent="violet" />
        <Metric label="Open requests" value={requestRows.filter((item) => item.status === "pending").length} accent="amber" />
        <Metric label="Sources with failures" value={failedSources} accent={failedSources ? "red" : "primary"} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>Worker Control</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              <StatusBadge status={workerStatus?.running ? "running" : "stopped"} />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <Button onClick={() => start.mutate()} disabled={start.isPending}>
                <Play className="h-4 w-4" />
                Start
              </Button>
              <Button variant="outline" onClick={() => stop.mutate()} disabled={stop.isPending}>
                <Square className="h-4 w-4" />
                Stop
              </Button>
              <Button variant="secondary" onClick={() => runOnce.mutate()} disabled={runOnce.isPending}>
                <RotateCw className="h-4 w-4" />
                Once
              </Button>
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Processed</dt>
                <dd className="font-medium">{workerStatus?.jobs_processed ?? 0}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Idle ticks</dt>
                <dd className="font-medium">{workerStatus?.idle_ticks ?? 0}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted-foreground">Last error</dt>
                <dd className="break-words font-medium">{workerStatus?.last_error || "-"}</dd>
              </div>
            </dl>
          </PanelBody>
        </Panel>

        <JobTable jobs={jobRows.slice(0, 8)} />
      </div>
    </>
  );
}
