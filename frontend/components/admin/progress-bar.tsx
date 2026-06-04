import * as React from "react";

export function ProgressBar({
  value,
  label,
  detail
}: {
  value: number;
  label?: string;
  detail?: string;
}) {
  const normalized = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label || "Progress"}</span>
        <span>{detail || `${normalized}%`}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-300"
          style={{ width: `${normalized}%` }}
        />
      </div>
    </div>
  );
}
