"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, RotateCw } from "lucide-react";
import * as React from "react";

import { JobTable } from "@/components/admin/job-table";
import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const statusOptions = ["", "pending", "running", "completed", "failed", "cancelled"];
const typeOptions = ["", "crawl", "translation"];

export default function JobsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = React.useState("");
  const [jobType, setJobType] = React.useState("");
  const [novelId, setNovelId] = React.useState("");
  const jobs = useQuery({
    queryKey: ["jobs", status, jobType, novelId],
    queryFn: () =>
      api.jobs({
        status: status || undefined,
        job_type: jobType || undefined,
        novel_id: novelId || undefined,
        limit: 100
      }),
    refetchInterval: 5000
  });
  const worker = useQuery({ queryKey: ["worker"], queryFn: () => api.workerStatus(), refetchInterval: 5000 });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["worker"] });
  };

  const runNext = useMutation({ mutationFn: () => api.runNextJob(jobType || undefined), onSuccess: invalidate });
  const runOnce = useMutation({ mutationFn: api.workerRunOnce, onSuccess: invalidate });

  return (
    <>
      <PageHeading title="Jobs" description="Queue inspection, worker ticks, and job execution history." />

      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>Queue Controls</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Worker</span>
              <StatusBadge status={worker.data?.running ? "running" : "stopped"} />
            </div>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Processed</dt>
                <dd className="font-medium">{worker.data?.jobs_processed ?? 0}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Last tick</dt>
                <dd className="font-medium">{formatDate(worker.data?.last_job_id ? worker.data.last_job_id : "")}</dd>
              </div>
            </dl>
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={() => runNext.mutate()} disabled={runNext.isPending}>
                <Play className="h-4 w-4" />
                Run next
              </Button>
              <Button variant="secondary" onClick={() => runOnce.mutate()} disabled={runOnce.isPending}>
                <RotateCw className="h-4 w-4" />
                Once
              </Button>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Filters</PanelTitle>
          </PanelHeader>
          <PanelBody>
            <div className="grid gap-3 md:grid-cols-3">
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={status}
                onChange={(event) => setStatus(event.target.value)}
              >
                {statusOptions.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "all statuses"}
                  </option>
                ))}
              </select>
              <select
                className="h-9 rounded-md border bg-background px-3 text-sm"
                value={jobType}
                onChange={(event) => setJobType(event.target.value)}
              >
                {typeOptions.map((option) => (
                  <option key={option || "all"} value={option}>
                    {option || "all types"}
                  </option>
                ))}
              </select>
              <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
            </div>
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-5">
        <JobTable jobs={jobs.data?.jobs ?? []} />
      </div>
    </>
  );
}
