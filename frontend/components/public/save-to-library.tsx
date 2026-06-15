"use client";

import { Bookmark } from "lucide-react";

interface SaveToLibraryProps {
  slug: string;
}

/**
 * Disabled save-to-library affordance until public accounts are implemented.
 */
export function SaveToLibrary({ slug: _slug }: SaveToLibraryProps) {
  return (
    <div className="flex flex-col gap-1">
      <button
        className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium opacity-60"
        disabled
        type="button"
      >
        <Bookmark className="h-4 w-4" />
        Save to Library Unavailable
      </button>
      <p className="text-xs text-muted-foreground">
        Public accounts are not available yet.
      </p>
    </div>
  );
}
