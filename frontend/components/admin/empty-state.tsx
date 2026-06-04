import * as React from "react";

import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  className,
  colSpan
}: {
  title: string;
  description?: string;
  className?: string;
  colSpan?: number;
}) {
  const content = (
    <div className={cn("px-4 py-8 text-sm text-muted-foreground", className)}>
      <div className="font-medium text-foreground">{title}</div>
      {description ? <div className="mt-1">{description}</div> : null}
    </div>
  );

  if (typeof colSpan === "number") {
    return (
      <tr>
        <td colSpan={colSpan}>{content}</td>
      </tr>
    );
  }

  return content;
}
