"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RotateCw, Trash2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { activityPhaseSummary, groupActivityByNovel, type ActivityGroup } from "@/lib/activity";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

const statusOptions = ["", "pending", "running", "completed", "failed", "cancelled"];
type ActivitySortKey = "novel" | "phases" | "status" | "updated";
type SortDirection = "asc" | "desc";

function sortPointer(key: ActivitySortKey, activeKey: ActivitySortKey, direction: SortDirection) {
  if (key !== activeKey) {
    return "";
  }
  return direction === "asc" ? " \u25B2" : " \u25BC";
}

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
  const [sortKey, setSortKey] = React.useState<ActivitySortKey>("updated");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc");
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
      const direction = sortDirection === "asc" ? 1 : -1;
      if (typeof leftValue === "number" && typeof rightValue === "number") {
        return (leftValue - rightValue) * direction;
      }
      return String(leftValue).localeCompare(String(rightValue)) * direction;
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

  const handleSort = (key: ActivitySortKey) => {
    if (sortKey === key) {
      setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "updated" ? "desc" : "asc");
  };

  const header = (label: string, key: ActivitySortKey) => (
    <th className="px-4 py-3">
      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => handleSort(key)}>
        {label}
        {sortPointer(key, sortKey, sortDirection)}
      </button>
    </th>
  );

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
                onClick={() => deleteActivities.mutate(Array.from(selectedActivityIds))}
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
                      <input className="table-checkbox" type="checkbox" checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all activity" />
                    </th>
                    {header("Novel", "novel")}
                    {header("Activity", "phases")}
                    {header("Status", "status")}
                    {header("Updated", "updated")}
                    <th className="w-16 px-4 py-3" aria-label="Open activity" />
                  </tr>
                </thead>
                <tbody>
                  {sortedGroups.length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-muted-foreground" colSpan={6}>
                        No activity recorded yet.
                      </td>
                    </tr>
                  ) : (
                    sortedGroups.map((group) => (
                      <tr className="border-b last:border-0" key={group.id}>
                        <td className="px-4 py-3">
                          <input
                            className="table-checkbox"
                            type="checkbox"
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
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{formatDate(group.updatedAt)}</td>
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
    </>
  );
}
