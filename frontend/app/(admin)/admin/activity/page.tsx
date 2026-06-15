"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RotateCw, Trash2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { SchedulerBadges } from "@/components/admin/scheduler-state";
import { SortableHeader } from "@/components/admin/sortable-header";
import { StatusBadge } from "@/components/admin/status-badge";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";
import { activityPhaseSummary, groupActivityByNovel, type ActivityGroup } from "@/lib/activity";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const statusOptions = ["", "pending", "running", "paused", "paused_until_cooldown", "paused_until_quota_reset", "completed", "failed", "cancelled"];
type ActivitySortKey = "novel" | "phases" | "status" | "updated";

function activitySortValue(group: ActivityGroup, key: ActivitySortKey) {
  if (key === "novel") {
    return `${group.title} ${group.novelId}`.toLowerCase();
  }
  if (key === "phases") {
    return activityPhaseSummary(group.phases).toLowerCase();
  }
  if (key === "status") {
    return group.status;
  }
  return Date.parse(group.updatedAt) || 0;
}

export default function ActivityPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = React.useState("");
  const [novelId, setNovelId] = React.useState("");
  const [selectedActivityIds, setSelectedActivityIds] = React.useState<Set<string>>(new Set());
  const [deleteDialogOpen, setDeleteDialogOpen] = React.useState(false);
  const { sortKey, sortDirection, handleSort } = useSortableTable<ActivitySortKey>("updated", "desc");
  const activity = useQuery({
    queryKey: ["activity", status, novelId],
    queryFn: () =>
      api.activity({
        status: status || undefined,
        novel_id: novelId || undefined,
        limit: 100
    }),
    refetchInterval: 5000
  });
  const novels = useQuery({ queryKey: ["novels"], queryFn: () => api.novels() });
  const rows = activity.data?.activity ?? [];
  const groups = React.useMemo(() => groupActivityByNovel(rows, novels.data ?? []), [novels.data, rows]);
  const sortedGroups = React.useMemo(() => {
    return [...groups].sort((left, right) => {
      const leftValue = activitySortValue(left, sortKey);
      const rightValue = activitySortValue(right, sortKey);
      return compareSortableValues(leftValue, rightValue, sortDirection);
    });
  }, [groups, sortDirection, sortKey]);
  const allRowsSelected = groups.length > 0 && groups.every((group) => selectedActivityIds.has(group.id));

  const deleteActivities = useMutation({
    mutationFn: async (activityIds: string[]) => {
      const selectedGroups = groups.filter((group) => activityIds.includes(group.id));
      for (const group of selectedGroups) {
        for (const activityItem of group.activity) {
          await api.deleteActivity(activityItem.id);
        }
      }
    },
    onSuccess: () => {
      setSelectedActivityIds(new Set());
      setDeleteDialogOpen(false);
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    }
  });

  const toggleAllRows = () => {
    setSelectedActivityIds(allRowsSelected ? new Set() : new Set(groups.map((group) => group.id)));
  };

  const toggleActivity = (activityId: string) => {
    setSelectedActivityIds((current) => {
      const next = new Set(current);
      if (next.has(activityId)) {
        next.delete(activityId);
      } else {
        next.add(activityId);
      }
      return next;
    });
  };

  return (
    <>
      <PageHeading title="Activity Log" description="Track crawler and translation activity started from Add Novel and Library." />

      <div className="space-y-5">
        <Panel>
          <PanelHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <PanelTitle>Filters</PanelTitle>
              <p className="mt-1 text-sm text-muted-foreground">
                {selectedActivityIds.size ? `${selectedActivityIds.size} selected` : `${groups.length} novel activity item(s)`}
              </p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                variant="destructive"
                size="sm"
                onClick={() => setDeleteDialogOpen(true)}
                disabled={selectedActivityIds.size === 0 || deleteActivities.isPending}
              >
                <Trash2 className="h-4 w-4" />
                Delete selected
              </Button>
              <Button variant="outline" size="sm" onClick={() => void activity.refetch()} disabled={activity.isFetching}>
                <RotateCw className="h-4 w-4" />
                Refresh activity
              </Button>
            </div>
          </PanelHeader>
          <PanelBody className="bg-muted/10">
            <div className="grid gap-3 md:grid-cols-2">
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
              <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
            </div>
          </PanelBody>
          <ErrorBanner error={activity.error} fallback="Failed to load activity." />
          <ErrorBanner error={deleteActivities.error} fallback="Failed to delete selected activity." />
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Activity Log</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <div className="seamless-scrollbar max-h-[560px] overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-[1] border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="w-12 px-4 py-3">
                      <TableCheckbox checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all activity" />
                    </th>
                    <SortableHeader label="Novel" sortKey="novel" activeKey={sortKey} direction={sortDirection} onSort={handleSort} />
                    <SortableHeader label="Activity" sortKey="phases" activeKey={sortKey} direction={sortDirection} onSort={handleSort} />
                    <SortableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={handleSort} />
                    <SortableHeader label="Updated" sortKey="updated" activeKey={sortKey} direction={sortDirection} onSort={(key) => handleSort(key, "desc")} />
                    <th className="w-16 px-4 py-3" aria-label="Open activity" />
                  </tr>
                </thead>
                <tbody>
                  {activity.isLoading || novels.isLoading ? (
                    <LoadingRows colSpan={6} label="Loading activity..." />
                  ) : activity.error || novels.error ? (
                    <EmptyState title="Failed to load activity." colSpan={6} />
                  ) : sortedGroups.length === 0 ? (
                    <EmptyState title="No activity recorded yet." colSpan={6} />
                  ) : (
                    sortedGroups.map((group) => (
                      <tr className="border-b last:border-0" key={group.id}>
                        <td className="px-4 py-3">
                          <TableCheckbox
                            checked={selectedActivityIds.has(group.id)}
                            onChange={() => toggleActivity(group.id)}
                            aria-label={`Select activity ${group.novelId}`}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{group.title}</div>
                          <div className="mt-1 font-mono text-xs text-muted-foreground">{group.novelId}</div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{activityPhaseSummary(group.phases)}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={group.status} />
                          {group.activity.map((activityItem) => (
                            <SchedulerBadges key={activityItem.id} activity={activityItem} />
                          ))}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{formatDateTime(group.updatedAt)}</td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            href={`/admin/activity/${encodeURIComponent(group.novelId)}`}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-muted"
                            aria-label={`Open activity ${group.novelId}`}
                            title="Open activity"
                          >
                            <ExternalLink className="h-4 w-4" />
                          </Link>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </PanelBody>
        </Panel>
      </div>

      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete selected activity"
        description={`Delete ${selectedActivityIds.size} selected activity item(s)?`}
        confirmLabel="Delete"
        destructive
        pending={deleteActivities.isPending}
        onConfirm={() => deleteActivities.mutate(Array.from(selectedActivityIds))}
        onCancel={() => setDeleteDialogOpen(false)}
        auditNotice="This action is recorded in the audit log."
      />
    </>
  );
}
