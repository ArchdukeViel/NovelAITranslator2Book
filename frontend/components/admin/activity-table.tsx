"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { StatusBadge } from "@/components/admin/status-badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import type { ActivityRecord } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

type ActivitySortKey = "novel" | "scope" | "status" | "updated";
type SortDirection = "asc" | "desc";

function activityUpdatedAt(activity: ActivityRecord) {
  return activity.finished_at || activity.started_at || activity.created_at || "";
}

function activitySortValue(activity: ActivityRecord, key: ActivitySortKey) {
  if (key === "novel") {
    return activity.novel_id;
  }
  if (key === "scope") {
    return activity.chapters || "";
  }
  if (key === "status") {
    return activity.status;
  }
  return Date.parse(activityUpdatedAt(activity)) || 0;
}

function sortPointer(key: ActivitySortKey, activeKey: ActivitySortKey, direction: SortDirection) {
  if (key !== activeKey) {
    return "";
  }
  return direction === "asc" ? " \u25B2" : " \u25BC";
}

export type ActivityTableProps = {
  activity: ActivityRecord[];
  title?: string;
  emptyText?: string;
  selectable?: boolean;
  selectedActivityIds?: Set<string>;
  allSelected?: boolean;
  onToggleAll?: () => void;
  onToggleActivity?: (activityId: string) => void;
  className?: string;
  bodyClassName?: string;
  tableContainerClassName?: string;
};

export function ActivityTable({
  activity,
  title = "Recent Activity",
  emptyText = "No activity yet.",
  selectable = false,
  selectedActivityIds,
  allSelected = false,
  onToggleAll,
  onToggleActivity,
  className,
  bodyClassName,
  tableContainerClassName
}: ActivityTableProps) {
  const [sortKey, setSortKey] = React.useState<ActivitySortKey>("updated");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc");

  const sortedActivity = React.useMemo(() => {
    return [...activity].sort((left, right) => {
      const leftValue = activitySortValue(left, sortKey);
      const rightValue = activitySortValue(right, sortKey);
      const direction = sortDirection === "asc" ? 1 : -1;
      if (typeof leftValue === "number" && typeof rightValue === "number") {
        return (leftValue - rightValue) * direction;
      }
      return String(leftValue).localeCompare(String(rightValue)) * direction;
    });
  }, [activity, sortDirection, sortKey]);

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
    <Panel className={className}>
      <PanelHeader>
        <PanelTitle>{title}</PanelTitle>
      </PanelHeader>
      <PanelBody className={cn("p-0", bodyClassName)}>
        <div className={cn("overflow-x-auto", tableContainerClassName)}>
          <table className="w-full text-left text-sm">
            <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
              <tr>
                {selectable ? (
                  <th className="w-12 px-4 py-3">
                    <input className="table-checkbox" type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Select all activity" />
                  </th>
                ) : null}
                {header("Novel", "novel")}
                {header("Scope", "scope")}
                {header("Status", "status")}
                {header("Updated", "updated")}
                <th className="px-4 py-3" aria-label="Open activity" />
              </tr>
            </thead>
            <tbody>
              {sortedActivity.length === 0 ? (
                <tr>
                  <td className="px-4 py-6 text-muted-foreground" colSpan={selectable ? 6 : 5}>
                    {emptyText}
                  </td>
                </tr>
              ) : (
                sortedActivity.map((activityItem) => (
                  <tr className="border-b last:border-0" key={activityItem.id}>
                    {selectable ? (
                      <td className="px-4 py-3">
                        <input
                          className="table-checkbox"
                          type="checkbox"
                          checked={selectedActivityIds?.has(activityItem.id) ?? false}
                          onChange={() => onToggleActivity?.(activityItem.id)}
                          aria-label={`Select activity ${activityItem.id}`}
                        />
                      </td>
                    ) : null}
                    <td className="px-4 py-3 font-medium">{activityItem.novel_id}</td>
                    <td className="px-4 py-3">{activityItem.chapters || "-"}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={activityItem.status} />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(activityUpdatedAt(activityItem))}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        href={`/admin/activity/${encodeURIComponent(activityItem.id)}`}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md border hover:bg-muted"
                        aria-label={`Open activity ${activityItem.id}`}
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
  );
}
