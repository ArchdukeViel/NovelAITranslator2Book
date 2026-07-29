import Link from "next/link";
import { BookOpen } from "lucide-react";

import { NotFoundState } from "@/components/ui/page-state";

/**
 * Public route-group not-found boundary.
 * Renders when notFound() is called within public routes.
 */
export default function PublicNotFoundPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-16">
      <NotFoundState
        description="The page you are looking for does not exist."
        action={
          <div className="flex flex-wrap items-center gap-3">
            <Link
              href="/home"
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Return home
            </Link>
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
