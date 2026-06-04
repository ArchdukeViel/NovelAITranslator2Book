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

  return (
    <div className={cn("border-t border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive", className)}>
      {formatAdminError(error, fallback)}
    </div>
  );
}
