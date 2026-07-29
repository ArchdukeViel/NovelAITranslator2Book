"use client";

import { useQuery } from "@tanstack/react-query";

import { ErrorBanner } from "@/components/admin/error-banner";
import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/ui/page-state";
import { Panel, PanelBody } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

function label(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export default function MaintenancePage() {
  const status = useQuery({
    queryKey: ["maintenance-status"],
    queryFn: () => api.maintenanceStatus(),
    refetchInterval: 30000,
  });

  return (
    <>
      <PageHeading
        title="Maintenance"
        description="Durable schedule and runtime status for registered cleanup tasks."
      />
      <ErrorBanner error={status.error} fallback="Failed to load maintenance status." className="mb-4 rounded-md border" />
      {status.isLoading ? (
        <LoadingState label="Loading maintenance status..." />
      ) : status.data ? (
        <Panel>
          <PanelBody className="p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Task</th>
                  <th className="px-4 py-3">Schedule</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Last completed</th>
                  <th className="px-4 py-3">Next eligible</th>
                  <th className="px-4 py-3">Result</th>
                </tr>
              </thead>
              <tbody>
                {status.data.tasks.map((task) => (
                  <tr className="border-b last:border-0" key={task.task_key}>
                    <td className="px-4 py-3 font-medium">{label(task.task_key)}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      <div>{task.schedule}</div><div className="text-xs">{task.timezone}</div>
                    </td>
                    <td className="px-4 py-3"><Badge tone={task.state === "failed" ? "red" : "neutral"}>{label(task.state)}</Badge></td>
                    <td className="px-4 py-3 text-muted-foreground">{task.last_finished_at ? formatDateTime(task.last_finished_at) : "Never"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{task.next_eligible_at ? formatDateTime(task.next_eligible_at) : "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{task.failure_summary ?? (task.result ? label(task.result) : "—")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </PanelBody>
        </Panel>
      ) : null}
    </>
  );
}
