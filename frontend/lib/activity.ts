import type { ActivityRecord, NovelSummary } from "@/lib/api";

export type ActivityPhaseKey = "preliminary" | "scraping" | "translating" | "other";

export type ActivityGroup = {
  id: string;
  novelId: string;
  title: string;
  activity: ActivityRecord[];
  status: string;
  updatedAt: string;
  phases: ActivityPhaseKey[];
};

const PHASE_LABELS: Record<ActivityPhaseKey, string> = {
  preliminary: "Preliminary Crawl",
  scraping: "Scraping",
  translating: "Translating",
  other: "Other"
};

function activityUpdatedAt(activity: ActivityRecord) {
  return activity.finished_at || activity.started_at || activity.created_at || "";
}

function metadataText(activity: ActivityRecord, key: string) {
  const value = activity.metadata?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function activityTitle(activity: ActivityRecord, novels: NovelSummary[] = []) {
  const novel = novels.find((item) => item.novel_id === activity.novel_id);
  return novel?.title || metadataText(activity, "translated_title") || metadataText(activity, "title") || activity.novel_id;
}

export function activityPhaseKey(activity: ActivityRecord): ActivityPhaseKey {
  const subtype = metadataText(activity, "activity_subtype");
  const phase = metadataText(activity, "activity_phase");
  if (activity.type === "translation" || subtype === "translating") {
    return "translating";
  }
  if (activity.kind === "metadata" || phase === "preliminary_crawl" || activity.metadata?.preliminary_crawl) {
    return "preliminary";
  }
  if (subtype === "scraping" || activity.type === "crawl") {
    return "scraping";
  }
  return "other";
}

export function activityPhaseLabel(phase: ActivityPhaseKey) {
  return PHASE_LABELS[phase];
}

export function activityPhaseSummary(phases: ActivityPhaseKey[]) {
  return phases.map(activityPhaseLabel).join(", ");
}

export function activityStatus(activities: ActivityRecord[]) {
  if (activities.some((activity) => activity.status === "running")) {
    return "running";
  }
  if (activities.some((activity) => activity.status === "failed")) {
    return "failed";
  }
  if (activities.some((activity) => activity.status === "pending")) {
    return "pending";
  }
  if (activities.length > 0 && activities.every((activity) => activity.status === "cancelled")) {
    return "cancelled";
  }
  if (activities.length > 0 && activities.every((activity) => activity.status === "completed" || activity.status === "cancelled")) {
    return "completed";
  }
  return activities[0]?.status || "unknown";
}

export function groupActivityByNovel(activities: ActivityRecord[], novels: NovelSummary[] = []) {
  const groups = new Map<string, ActivityRecord[]>();
  for (const activity of activities) {
    const existing = groups.get(activity.novel_id) ?? [];
    existing.push(activity);
    groups.set(activity.novel_id, existing);
  }

  return Array.from(groups.entries())
    .map(([novelId, groupedActivity]) => {
      const sortedActivity = [...groupedActivity].sort((left, right) => {
        return (Date.parse(activityUpdatedAt(right)) || 0) - (Date.parse(activityUpdatedAt(left)) || 0);
      });
      const phases = Array.from(new Set(sortedActivity.map(activityPhaseKey)));
      return {
        id: novelId,
        novelId,
        title: activityTitle(sortedActivity[0], novels),
        activity: sortedActivity,
        status: activityStatus(sortedActivity),
        updatedAt: activityUpdatedAt(sortedActivity[0]),
        phases
      } satisfies ActivityGroup;
    })
    .sort((left, right) => (Date.parse(right.updatedAt) || 0) - (Date.parse(left.updatedAt) || 0));
}

export function splitActivityByPhase(activities: ActivityRecord[]) {
  const split: Record<ActivityPhaseKey, ActivityRecord[]> = {
    preliminary: [],
    scraping: [],
    translating: [],
    other: []
  };
  for (const activity of activities) {
    split[activityPhaseKey(activity)].push(activity);
  }
  return split;
}

export function activityUpdatedAtValue(activity: ActivityRecord) {
  return activityUpdatedAt(activity);
}
