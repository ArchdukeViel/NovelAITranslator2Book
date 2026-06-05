import { AlertCircle, Clock, Gauge, PauseCircle } from "lucide-react";

import { ProgressBar } from "@/components/admin/progress-bar";
import { Badge } from "@/components/ui/badge";
import { activityProgress } from "@/lib/api";
import type { ActivityRecord, JobProgress, ModelState } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

function cleanText(value: unknown) {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return null;
}

function displayToken(value: string | null | undefined) {
  if (!value) {
    return null;
  }
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

function errorMessage(error: unknown) {
  if (typeof error === "string" && error.trim()) {
    return error.trim();
  }
  if (error && typeof error === "object" && !Array.isArray(error)) {
    const payload = error as Record<string, unknown>;
    return cleanText(payload.message) || cleanText(payload.error_code) || cleanText(payload.code);
  }
  return null;
}

function modelBadgeTone(status: string | null | undefined) {
  const normalized = (status || "").toLowerCase();
  if (normalized === "available" || normalized === "completed") {
    return "green" as const;
  }
  if (normalized === "cooling_down" || normalized === "running") {
    return "blue" as const;
  }
  if (normalized === "daily_exhausted" || normalized === "failed" || normalized === "disabled") {
    return "red" as const;
  }
  return "neutral" as const;
}

function schedulerBadges(progress: JobProgress) {
  const badges: Array<{ label: string; tone: "green" | "blue" | "amber" | "red" | "neutral" }> = [];
  const status = progress.status.toLowerCase();
  if (status.includes("paused") || progress.paused_reason) {
    badges.push({ label: "paused", tone: "amber" });
  }
  if (progress.model_states?.some((model) => model.status === "cooling_down")) {
    badges.push({ label: "cooling down", tone: "blue" });
  }
  if (progress.model_states?.some((model) => model.status === "daily_exhausted")) {
    badges.push({ label: "quota exhausted", tone: "red" });
  }
  if (progress.model_states?.some((model) => model.status === "failed" || model.status === "disabled")) {
    badges.push({ label: "model failed", tone: "red" });
  }
  if (status === "completed") {
    badges.push({ label: "completed", tone: "green" });
  }
  return badges;
}

export function SchedulerBadges({ activity, className }: { activity: ActivityRecord; className?: string }) {
  const progress = activityProgress(activity);
  const badges = schedulerBadges(progress);
  if (badges.length === 0) {
    return null;
  }

  return (
    <div className={cn("mt-2 flex flex-wrap gap-1.5", className)}>
      {badges.map((badge) => (
        <Badge key={`${activity.id}-${badge.label}`} tone={badge.tone}>
          {badge.label}
        </Badge>
      ))}
    </div>
  );
}

export function hasSchedulerProgress(activity: ActivityRecord) {
  const progress = activityProgress(activity);
  return Boolean(
    progress.current_stage ||
      progress.current_label ||
      typeof progress.completed === "number" ||
      progress.paused_reason ||
      progress.resume_after ||
      progress.model_states?.length ||
      progress.errors?.length ||
      progress.warnings?.length
  );
}

function modelDetail(model: ModelState) {
  const detail = [
    model.cooldown_until ? `cooldown ${formatDateTime(model.cooldown_until)}` : null,
    model.exhausted_until ? `quota reset ${formatDateTime(model.exhausted_until)}` : null,
    typeof model.requests_this_minute === "number" ? `${model.requests_this_minute}/min` : null,
    typeof model.requests_today === "number" ? `${model.requests_today}/day` : null
  ].filter(Boolean);
  return detail.join(" | ");
}

export function SchedulerStatePanel({ activity }: { activity: ActivityRecord }) {
  const progress = activityProgress(activity);
  if (!hasSchedulerProgress(activity)) {
    return null;
  }

  const completed = typeof progress.completed === "number" ? progress.completed : null;
  const total = typeof progress.total === "number" && progress.total > 0 ? progress.total : null;
  const percentage = completed !== null && total !== null ? (completed / total) * 100 : 0;
  const provider = progress.provider_key && progress.provider_model ? `${progress.provider_key} / ${progress.provider_model}` : null;
  const selectionReason = displayToken(progress.selection_reason);
  const visibleErrors = (progress.errors ?? []).map(errorMessage).filter((item): item is string => Boolean(item));
  const visibleWarnings = (progress.warnings ?? []).map(errorMessage).filter((item): item is string => Boolean(item));

  return (
    <div className="space-y-4 rounded-md border bg-muted/15 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium">Scheduler Progress</div>
          <div className="mt-1 text-xs text-muted-foreground">
            {[progress.current_stage, progress.current_label, provider].filter(Boolean).join(" | ") || "Backend progress state"}
          </div>
          {selectionReason ? <div className="mt-1 text-xs text-muted-foreground">Selection: {selectionReason}</div> : null}
        </div>
        <SchedulerBadges activity={activity} className="mt-0" />
      </div>

      {completed !== null || total !== null ? (
        <ProgressBar
          value={percentage}
          label="Chunk progress"
          detail={completed !== null && total !== null ? `${completed}/${total}` : "in progress"}
        />
      ) : null}

      {progress.paused_reason || progress.resume_after ? (
        <div className="grid gap-3 rounded-md border bg-background/60 p-3 text-sm md:grid-cols-2">
          <div className="flex gap-2">
            <PauseCircle className="mt-0.5 h-4 w-4 text-amber-600" />
            <div>
              <div className="text-muted-foreground">Paused reason</div>
              <div className="font-medium">{displayToken(progress.paused_reason) || "Paused"}</div>
            </div>
          </div>
          <div className="flex gap-2">
            <Clock className="mt-0.5 h-4 w-4 text-muted-foreground" />
            <div>
              <div className="text-muted-foreground">Resume after</div>
              <div className="font-medium">{progress.resume_after ? formatDateTime(progress.resume_after) : "-"}</div>
            </div>
          </div>
        </div>
      ) : null}

      {progress.model_states?.length ? (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Gauge className="h-4 w-4" />
            Model states
          </div>
          <div className="grid gap-2">
            {progress.model_states.map((model) => (
              <div key={`${model.provider_key}:${model.provider_model}`} className="rounded-md border bg-background/60 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div className="font-medium">{model.provider_key} / {model.provider_model}</div>
                    {modelDetail(model) ? <div className="mt-1 text-xs text-muted-foreground">{modelDetail(model)}</div> : null}
                    {displayToken(model.selection_reason) ? (
                      <div className="mt-1 text-xs text-muted-foreground">Selection: {displayToken(model.selection_reason)}</div>
                    ) : null}
                  </div>
                  <Badge tone={modelBadgeTone(model.status)}>{model.status}</Badge>
                </div>
                {model.last_error_code || model.last_error_message ? (
                  <div className="mt-2 text-xs text-muted-foreground">
                    {[displayToken(model.last_error_code), model.last_error_message].filter(Boolean).join(": ")}
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {visibleErrors.length || visibleWarnings.length ? (
        <div className="space-y-2 text-sm">
          {visibleErrors.length ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-destructive">
              <div className="mb-1 flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" />
                Errors
              </div>
              <ul className="space-y-1">
                {visibleErrors.map((message, index) => (
                  <li key={`${activity.id}-error-${index}`}>{message}</li>
                ))}
              </ul>
            </div>
          ) : null}
          {visibleWarnings.length ? (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-amber-700">
              <div className="mb-1 font-medium">Warnings</div>
              <ul className="space-y-1">
                {visibleWarnings.map((message, index) => (
                  <li key={`${activity.id}-warning-${index}`}>{message}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
