import * as React from "react";

import { formatAdminError } from "@/lib/admin-errors";
import { cn } from "@/lib/utils";

export function ErrorBanner({
  error,
  fallback = "Something went wrong.",
  className
}: {
  error: unknown;
  fallback?: string;
  className?: string;
}) {
  if (!error) {
    return null;
  }

  const { message, trace_id } = formatAdminError(error, fallback);

  return (
    <div className={cn("border-t border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive", className)}>
      {message}
      {trace_id && <span className="ml-2 opacity-70">Trace: {trace_id}</span>}
    </div>
  );
}
