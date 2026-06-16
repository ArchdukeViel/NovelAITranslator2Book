"use client";

import Link from "next/link";
import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SearchEntry } from "@/components/public/search-entry";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";

export function PublicHeader({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background">
      <div className="mx-auto flex h-14 items-center gap-4 px-4">
        {/* Mobile hamburger */}
        <div className="md:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label="Open navigation menu"
            onClick={onMenuClick}
          >
            <Menu className="h-5 w-5" />
          </Button>
        </div>

        {/* Brand link */}
        <Link
          href="/home"
          className="shrink-0 text-lg font-semibold tracking-tight font-literary"
        >
          Novel AI
        </Link>

        {/* Desktop search */}
        <div className="hidden flex-1 md:block">
          <SearchEntry />
        </div>

        <div className="ml-auto">
          <CurrentUserIndicator />
        </div>
      </div>

      {/* Mobile search */}
      <div className="border-t border-border px-4 py-2 md:hidden">
        <SearchEntry />
      </div>
    </header>
  );
}
