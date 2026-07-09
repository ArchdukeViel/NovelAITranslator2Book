"use client";

import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Info,
  ShieldAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { GlossaryQAIssue, GlossaryQAResult } from "@/lib/api-types";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<
  GlossaryQAResult["status"],
  "green" | "amber" | "red" | "blue" | "neutral"
> = {
  passed: "green",
  advisory: "blue",
  warning: "amber",
  blocked: "red",
  overridden: "amber",
};

const STATUS_LABEL: Record<GlossaryQAResult["status"], string> = {
  passed: "Passed",
  advisory: "Advisory",
  warning: "Warning",
  blocked: "Blocked",
  overridden: "Overridden",
};

const SEVERITY_ICON: Record<GlossaryQAIssue["severity"], typeof AlertCircle> = {
  error: ShieldAlert,
  warning: AlertTriangle,
  advisory: Info,
};

const SEVERITY_TONE: Record<
  GlossaryQAIssue["severity"],
  "red" | "amber" | "blue"
> = {
  error: "red",
  warning: "amber",
  advisory: "blue",
};

export function GlossaryQAPanel({
  result,
  onApproveChange,
  onOverride,
  canApprove = false,
  canOverride = false,
  className,
}: {
  result?: GlossaryQAResult | null;
  onApproveChange?: (issue: GlossaryQAIssue) => void;
  onOverride?: (issues: GlossaryQAIssue[]) => void;
  canApprove?: boolean;
  canOverride?: boolean;
  className?: string;
}) {
  if (!result) return null;

  const tone = STATUS_TONE[result.status] ?? "neutral";
  const label = STATUS_LABEL[result.status] ?? result.status;
  const notes = result.notes ?? [];
  const issues = result.issues ?? [];

  return (
    <div className={cn("space-y-3 rounded-md border bg-muted/15 p-4 text-sm", className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 font-medium">
          {result.status === "passed" ? (
            <CheckCircle2 className="h-4 w-4 text-green-600" />
          ) : result.status === "blocked" ? (
            <ShieldAlert className="h-4 w-4 text-red-600" />
          ) : (
            <AlertCircle className="h-4 w-4 text-amber-600" />
          )}
          Glossary QA
        </div>

        <Badge tone={tone}>{label}</Badge>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground md:grid-cols-4">
        <div>
          <div className="font-medium text-foreground">{result.checked_terms}</div>
          <div>Checked terms</div>
        </div>

        <div>
          <div className="font-medium text-foreground">{result.issue_count}</div>
          <div>Issues</div>
        </div>

        <div>
          <div className="font-medium text-foreground">
            {result.glossary_revision ?? "-"}
          </div>
          <div>Revision</div>
        </div>

        <div>
          <div className="font-medium text-foreground">{result.source_context}</div>
          <div>Source context</div>
        </div>
      </div>

      {result.cap_reached ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-800">
          Term cap reached: checked first {result.cap_limit ?? 50} entries.
        </div>
      ) : null}

      {notes.length > 0 ? (
        <div className="space-y-1">
          {notes.map((note, idx) => (
            <div key={idx} className="text-xs text-muted-foreground">
              {note}
            </div>
          ))}
        </div>
      ) : null}

      {issues.length > 0 ? (
        <div className="space-y-2">
          {issues.map((issue) => {
            const Icon = SEVERITY_ICON[issue.severity] ?? AlertCircle;
            const issueTone = SEVERITY_TONE[issue.severity] ?? "amber";

            return (
              <div key={issue.issue_id} className="rounded-md border bg-background/60 p-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-2">
                    <Icon className="mt-0.5 h-4 w-4 shrink-0" />

                    <div className="space-y-0.5">
                      <div className="flex items-center gap-1.5">
                        <span className="font-medium">{issue.canonical_term}</span>
                        <Badge tone={issueTone}>{issue.severity}</Badge>
                        {issue.owner_locked ? <Badge tone="red">locked</Badge> : null}
                      </div>

                      {issue.approved_translation ? (
                        <div className="text-xs text-muted-foreground">
                          Expected:{" "}
                          <span className="font-medium">
                            {issue.approved_translation}
                          </span>
                        </div>
                      ) : null}

                      {issue.matched_variant ? (
                        <div className="text-xs text-muted-foreground">
                          Found:{" "}
                          <span className="font-medium">
                            {issue.matched_variant}
                          </span>
                        </div>
                      ) : null}

                      {issue.context_hint ? (
                        <div className="text-xs text-muted-foreground">
                          {issue.context_hint}
                        </div>
                      ) : null}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-col gap-1">
                    {canApprove && issue.entry_id != null ? (
                      <button
                        type="button"
                        className="rounded border px-2 py-0.5 text-xs hover:bg-muted"
                        onClick={() => onApproveChange?.(issue)}
                      >
                        Approve change
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}

      {result.status === "blocked" && canOverride ? (
        <div className="rounded-md border border-red-300 bg-red-50 p-2 text-xs text-red-800">
          Save is blocked. Fix the issues above or submit an override with a reason.

          <button
            type="button"
            className="ml-2 rounded border border-red-400 px-2 py-0.5 text-xs hover:bg-red-100"
            onClick={() => onOverride?.(issues)}
          >
            Override
          </button>
        </div>
      ) : null}
    </div>
  );
}