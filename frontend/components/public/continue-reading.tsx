"use client";

import { BookOpen } from "lucide-react";

interface ContinueReadingProps {
  slug: string;
}

/**
 * Disabled continue-reading affordance until public accounts are implemented.
 */
export function ContinueReading({ slug: _slug }: ContinueReadingProps) {
  return (
    <button
      className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium opacity-60"
      disabled
      type="button"
    >
      <BookOpen className="h-4 w-4" />
      Continue Reading Unavailable
    </button>
  );
}
