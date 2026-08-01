"use client";

import { Search } from "lucide-react";

import { useSearchOverlay } from "@/lib/search-overlay";

/**
 * Desktop header search field. Per DESIGN.md — Search contract, the header
 * search field opens the one shared search overlay instead of submitting a
 * separate search box. The overlay is mounted once in PublicShell.
 */
export function SearchEntry() {
  const open = useSearchOverlay((state) => state.open);

  return (
    <button
      type="button"
      onClick={open}
      className="flex h-9 w-full items-center gap-2 rounded-md border border-border/70 bg-card/70 px-3 text-left text-sm text-muted-foreground transition-colors hover:border-border hover:bg-card md:max-w-md"
      aria-label="Search novels"
    >
      <Search className="h-4 w-4 shrink-0" aria-hidden="true" />
      <span className="flex-1 truncate">Search novels…</span>
      <kbd className="hidden rounded border border-border/70 bg-muted/50 px-1.5 py-0.5 text-[0.65rem] font-medium text-muted-foreground sm:inline-block">
        /
      </kbd>
    </button>
  );
}
