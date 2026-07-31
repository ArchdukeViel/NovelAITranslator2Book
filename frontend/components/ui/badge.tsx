import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeTone = "neutral" | "green" | "amber" | "red" | "blue" | "violet";

const tones: Record<BadgeTone, string> = {
  neutral: "border-border bg-muted text-muted-foreground",
  green: "border-success bg-success/20 text-success-text",
  amber: "border-warning bg-warning/20 text-warning-text",
  red: "border-destructive bg-destructive/20 text-destructive-text",
  blue: "border-info bg-info/20 text-info-text",
  violet: "border-violet-200 bg-violet-50 text-violet-700 dark:border-violet-900 dark:bg-violet-950 dark:text-violet-300"
};

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
