"use client";

import { useEffect } from "react";
import Link from "next/link";
import { BookOpen } from "lucide-react";

import { ErrorState } from "@/components/ui/page-state";
import { errorToProps } from "@/lib/api-error";

/**
 * Public route-group error boundary.
 * Catches unhandled errors in public routes and renders a safe fallback
 * using the shared ErrorState component.
 */
export default function PublicErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    if (process.env.NODE_ENV === "development") {
      console.error("Public route error", { digest: error.digest ?? null });
    }
  }, [error]);

  const { title, description } = errorToProps(error);

  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <ErrorState
        title={title}
        description={description}
        action={
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => reset()}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Try again
            </button>
            <Link
              href="/browse-novels"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md border border-border bg-card px-5 text-sm font-medium transition-colors hover:bg-muted"
            >
              <BookOpen className="h-4 w-4" />
              Browse catalog
            </Link>
          </div>
        }
      />
    </main>
  );
}
