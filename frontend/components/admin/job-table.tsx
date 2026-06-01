"use client";

import { StatusBadge } from "@/components/admin/status-badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { JobRecord } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export function JobTable({ jobs }: { jobs: JobRecord[] }) {
  return (
    <Panel>
      <PanelHeader>
        <PanelTitle>Recent Jobs</PanelTitle>
      </PanelHeader>
      <PanelBody className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Novel</th>
                <th className="px-4 py-3">Scope</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Updated</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-muted-foreground" colSpan={5}>
                    No queued jobs yet.
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr className="border-b last:border-0" key={job.id}>
                    <td className="px-4 py-3">
                      <div className="font-medium">{job.type}</div>
                      <div className="text-xs text-muted-foreground">{job.kind}</div>
                    </td>
                    <td className="px-4 py-3">{job.novel_id}</td>
                    <td className="px-4 py-3">{job.chapters || "-"}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={job.status} />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(job.finished_at || job.started_at || job.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </PanelBody>
    </Panel>
  );
}
