"use client";

import Link from "next/link";
import { LogIn } from "lucide-react";

/**
 * Inline login prompt shown to guests in place of authenticated features.
 * Shows benefit summary and routes sign-in to the dedicated login page.
 */
export function LoginPrompt() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border bg-muted/50 px-3 py-2 text-sm text-muted-foreground">
      <LogIn className="h-4 w-4 shrink-0" />
      <span>
        Sign in to save novels, continue reading, and leave reviews.
      </span>
      <Link
        href="/login?mode=signin"
        className="ml-auto inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
      >
        Sign in
      </Link>
    </div>
  );
}
