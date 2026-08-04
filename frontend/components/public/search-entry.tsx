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
      className="flex h-9 w-9 items-center justify-center gap-2.5 rounded-full bg-muted/40 p-0 text-left text-xs text-muted-foreground transition-all hover:bg-muted sm:w-full sm:max-w-[180px] sm:px-3.5 md:max-w-md md:text-sm"
      aria-label="Search novels"
    >
      <Search className="h-4 w-4 shrink-0 opacity-70" aria-hidden="true" />
      <span className="hidden flex-1 truncate sm:inline">Search novels…</span>
      <kbd className="hidden rounded bg-muted/60 px-1.5 py-0.5 text-[0.65rem] font-medium text-muted-foreground lg:inline-block">
        /
      </kbd>
    </button>
  );
}
