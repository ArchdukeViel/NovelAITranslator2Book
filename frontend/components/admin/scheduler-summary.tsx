"use client";

import { AlertCircle, CheckCircle2, Gauge, MemoryStick, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { SchedulerSummary } from "@/lib/api-types";
import { cn } from "@/lib/utils";

function displayToken(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

export function SchedulerSummaryPanel({ summary, className }: { summary: SchedulerSummary; className?: string }) {
  if (!summary || summary.chapters_with_decisions === 0) {
    return null;
  }

  const warnings: string[] = [];
  if (summary.fallback_count > 0) warnings.push(`${summary.fallback_count} fallback(s)`);
  if (summary.no_capacity_count > 0) warnings.push(`${summary.no_capacity_count} no-capacity`);
  if (summary.checkpoint_blocked_count > 0) warnings.push(`${summary.checkpoint_blocked_count} checkpoint blocked`);
  if (summary.memory_pressure_count > 0) warnings.push(`${summary.memory_pressure_count} memory pressure`);

  return (
    <div className={cn("space-y-3 rounded-md border bg-muted/15 p-4 text-sm", className)}>
      <div className="flex items-center gap-2 font-medium">
        <Gauge className="h-4 w-4" />
        Scheduler Summary
      </div>

      {warnings.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {warnings.map((w) => (
            <Badge key={w} tone="amber">
              {w}
            </Badge>
          ))}
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3.5 w-3.5 text-green-600" />
          No scheduler issues
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Chapters" value={summary.chapters_with_decisions} />
        <MetricCard label="Fallback" value={summary.fallback_count} highlight={summary.fallback_count > 0} />
        <MetricCard label="No Capacity" value={summary.no_capacity_count} highlight={summary.no_capacity_count > 0} />
        <MetricCard label="Checkpoint Blocked" value={summary.checkpoint_blocked_count} highlight={summary.checkpoint_blocked_count > 0} />
      </div>

      {Object.keys(summary.skip_reason_counts).length > 0 ? (
        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">Skip Reasons</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(summary.skip_reason_counts).map(([reason, count]) => (
              <Badge key={reason} tone={count > 5 ? "amber" : "neutral"}>
                {displayToken(reason)}: {count}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {Object.keys(summary.selected_provider_model_counts).length > 0 ? (
        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">Selected Models</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(summary.selected_provider_model_counts).map(([key, count]) => (
              <Badge key={key} tone="green">
                {key}: {count}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {Object.keys(summary.provider_key_counts).length > 0 ? (
        <div>
          <div className="mb-1 text-xs font-medium text-muted-foreground">By Provider</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(summary.provider_key_counts).map(([provider, count]) => (
              <Badge key={provider} tone="blue">
                {provider}: {count}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {summary.memory_pressure_count > 0 || summary.peak_exact_memory_bytes > 0 ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <MemoryStick className="h-3.5 w-3.5" />
          {summary.peak_exact_memory_bytes > 0
            ? `Peak: ${(summary.peak_exact_memory_bytes / 1024 / 1024).toFixed(1)} MB`
            : null}
          {summary.memory_pressure_count > 0
            ? ` · ${summary.memory_pressure_count} pressure event(s)`
            : null}
        </div>
      ) : null}
    </div>
  );
}

function MetricCard({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className="rounded-md border bg-background/60 p-2.5 text-center">
      <div className={cn("text-lg font-bold", highlight ? "text-amber-600" : "text-foreground")}>{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
