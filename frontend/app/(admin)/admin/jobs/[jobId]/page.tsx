"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, Play, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function JobDetailPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = decodeURIComponent(params.jobId);
  const queryClient = useQueryClient();
  const job = useQuery({ queryKey: ["job", jobId], queryFn: () => api.job(jobId), refetchInterval: 5000 });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
  };

  const run = useMutation({ mutationFn: () => api.runJob(jobId), onSuccess: invalidate });
  const cancel = useMutation({
    mutationFn: () => api.updateJobStatus(jobId, { status: "cancelled" }),
    onSuccess: invalidate
  });

  const data = job.data;

  return (
    <>
      <div className="mb-4">
        <Link className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground" href="/admin/jobs">
          <ArrowLeft className="h-4 w-4" />
          Jobs
        </Link>
      </div>
      <PageHeading title="Job Detail" description={jobId} />

      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>State</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              <StatusBadge status={data?.status ?? "loading"} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Button onClick={() => run.mutate()} disabled={!data || run.isPending || ["running", "completed", "cancelled"].includes(data.status)}>
                <Play className="h-4 w-4" />
                Run
              </Button>
              <Button variant="outline" onClick={() => void job.refetch()} disabled={job.isFetching}>
                <RotateCw className="h-4 w-4" />
                Refresh
              </Button>
              <Button
                className="col-span-2"
                variant="destructive"
                onClick={() => cancel.mutate()}
                disabled={!data || cancel.isPending || ["completed", "cancelled"].includes(data.status)}
              >
                <Ban className="h-4 w-4" />
                Cancel
              </Button>
            </div>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Novel</dt>
                <dd className="break-words font-medium">{data?.novel_id ?? "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Type</dt>
                <dd className="font-medium">{data ? `${data.type} / ${data.kind}` : "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Scope</dt>
                <dd className="font-medium">{data?.chapters || "-"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Created</dt>
                <dd className="font-medium">{formatDate(data?.created_at)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Finished</dt>
                <dd className="font-medium">{formatDate(data?.finished_at)}</dd>
              </div>
            </dl>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Log Payload</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4">
            {data?.error ? (
              <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                {data.error}
              </div>
            ) : null}
            <pre className="max-h-[560px] overflow-auto rounded-md bg-muted p-4 text-xs leading-5">
              {JSON.stringify(data ?? {}, null, 2)}
            </pre>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
