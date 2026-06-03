"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, RotateCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import {
  activityPhaseKey,
  activityPhaseLabel,
  activityStatus,
  activityTitle,
  activityUpdatedAtValue,
  splitActivityByPhase,
  type ActivityPhaseKey
} from "@/lib/activity";
import { api } from "@/lib/api";
import type { ActivityRecord } from "@/lib/api";
import { cn, formatDate } from "@/lib/utils";

const PHASE_ORDER: ActivityPhaseKey[] = ["preliminary", "scraping", "translating", "other"];

function metadataText(activity: ActivityRecord | undefined, key: string) {
  const value = activity?.metadata?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function displayToken(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function activityPhase(activity: ActivityRecord) {
  return metadataText(activity, "activity_phase") || activity.kind || activityPhaseLabel(activityPhaseKey(activity));
}

async function loadActivity(activityId: string) {
  const byNovel = await api.activity({ novel_id: activityId, limit: 200 });
  if (byNovel.activity.length > 0) {
    return { novelId: activityId, activity: byNovel.activity };
  }

  const activityItem = await api.activityItem(activityId);
  const siblings = await api.activity({ novel_id: activityItem.novel_id, limit: 200 });
  return { novelId: activityItem.novel_id, activity: siblings.activity.length ? siblings.activity : [activityItem] };
}

export default function ActivityDetailPage() {
  const params = useParams<{ activityId: string }>();
  const activityId = decodeURIComponent(params.activityId);
  const [selectedPhase, setSelectedPhase] = React.useState<ActivityPhaseKey>("preliminary");
  const activity = useQuery({
    queryKey: ["activity", activityId],
    queryFn: () => loadActivity(activityId),
    refetchInterval: 5000
  });

  const activityRows = React.useMemo(() => {
    return [...(activity.data?.activity ?? [])].sort((left, right) => {
      return (Date.parse(activityUpdatedAtValue(right)) || 0) - (Date.parse(activityUpdatedAtValue(left)) || 0);
    });
  }, [activity.data?.activity]);
  const splitActivity = React.useMemo(() => splitActivityByPhase(activityRows), [activityRows]);
  const visiblePhases = PHASE_ORDER.filter((phase) => splitActivity[phase].length > 0);
  const activePhase = visiblePhases.includes(selectedPhase) ? selectedPhase : visiblePhases[0] ?? "other";
  const activeActivity = splitActivity[activePhase] ?? [];
  const firstActivity = activityRows[0];
  const title = firstActivity ? activityTitle(firstActivity) : activity.data?.novelId ?? activityId;
  const status = activityStatus(activityRows);

  return (
    <>
      <div className="mb-4">
        <Link className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground" href="/admin/activity">
          <ArrowLeft className="h-4 w-4" />
          Activity Log
        </Link>
      </div>
      <PageHeading title="Activity Detail" description={activity.data?.novelId ?? activityId} />

      <div className="grid gap-5 lg:grid-cols-[360px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>Novel Activity</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Status</span>
              <StatusBadge status={activity.isLoading ? "loading" : status} />
            </div>
            <Button className="w-full" variant="outline" onClick={() => void activity.refetch()} disabled={activity.isFetching}>
              <RotateCw className="h-4 w-4" />
              Refresh
            </Button>
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-muted-foreground">Novel</dt>
                <dd className="break-words font-medium">{title}</dd>
                {activity.data?.novelId ? <dd className="mt-1 font-mono text-xs text-muted-foreground">{activity.data.novelId}</dd> : null}
              </div>
              <div>
                <dt className="text-muted-foreground">Activities</dt>
                <dd className="font-medium">{activityRows.length}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Latest update</dt>
                <dd className="font-medium">{formatDate(firstActivity ? activityUpdatedAtValue(firstActivity) : undefined)}</dd>
              </div>
            </dl>
          </PanelBody>
        </Panel>

        <Panel className="min-h-0">
          <PanelHeader>
            <PanelTitle>Activity Payload</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-4 p-0">
            <div className="flex flex-wrap gap-2 border-b p-4">
              {visiblePhases.length === 0 ? (
                <span className="text-sm text-muted-foreground">No activity records found.</span>
              ) : (
                visiblePhases.map((phase) => (
                  <Button
                    key={phase}
                    size="sm"
                    variant={activePhase === phase ? "default" : "outline"}
                    onClick={() => setSelectedPhase(phase)}
                  >
                    {activityPhaseLabel(phase)}
                    <span className={cn("ml-1 text-xs", activePhase === phase ? "text-primary-foreground/75" : "text-muted-foreground")}>
                      {splitActivity[phase].length}
                    </span>
                  </Button>
                ))
              )}
            </div>

            <div className="seamless-scrollbar max-h-[620px] overflow-auto px-4 pb-4">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 z-[1] border-b bg-card text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-3">Phase</th>
                    <th className="px-3 py-3">Scope</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3">Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {activeActivity.map((activityItem) => (
                    <tr key={activityItem.id} className="border-b last:border-0">
                      <td className="px-3 py-3">
                        <div className="font-medium">{displayToken(activityPhase(activityItem))}</div>
                        <div className="mt-1 font-mono text-xs text-muted-foreground">{activityItem.id}</div>
                      </td>
                      <td className="px-3 py-3">{activityItem.chapters || "-"}</td>
                      <td className="px-3 py-3">
                        <StatusBadge status={activityItem.status} />
                      </td>
                      <td className="px-3 py-3 text-muted-foreground">{formatDate(activityUpdatedAtValue(activityItem))}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-4 space-y-4">
                {activeActivity.map((activityItem) => (
                  <div key={`${activityItem.id}-payload`} className="rounded-md border">
                    <div className="border-b px-3 py-2 text-xs uppercase text-muted-foreground">{displayToken(activityPhase(activityItem))}</div>
                    {activityItem.error ? (
                      <div className="border-b border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{activityItem.error}</div>
                    ) : null}
                    <pre className="seamless-scrollbar max-h-80 overflow-auto bg-muted/35 p-3 text-xs leading-5">
                      {JSON.stringify(activityItem, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
