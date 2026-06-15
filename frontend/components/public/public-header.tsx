"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SearchEntry } from "@/components/public/search-entry";
import { BrowseNav } from "@/components/public/browse-nav";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";

export function PublicHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        {/* Brand link */}
        <Link
          href="/"
          className="shrink-0 text-lg font-semibold tracking-tight"
        >
          Novel AI
        </Link>

        {/* Desktop nav (hidden at ≤ 768px) */}
        <div className="hidden flex-1 items-center gap-4 md:flex">
          <SearchEntry />
          <BrowseNav />
          <div className="ml-auto">
            <CurrentUserIndicator />
          </div>
        </div>

        {/* Mobile hamburger (shown at ≤ 768px) */}
        <div className="ml-auto md:hidden">
          <Button
            variant="ghost"
            size="icon"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            onClick={() => setMobileOpen((prev) => !prev)}
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile disclosure menu */}
      {mobileOpen && (
        <div className="border-t border-border px-4 pb-4 pt-3 md:hidden">
          <div className="flex flex-col gap-3">
            <SearchEntry />
            <BrowseNav />
            <CurrentUserIndicator />
          </div>
        </div>
      )}
    </header>
  );
}
