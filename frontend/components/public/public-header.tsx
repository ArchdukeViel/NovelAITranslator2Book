"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SearchEntry } from "@/components/public/search-entry";
import { BrowseNav } from "@/components/public/browse-nav";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { usePublicAuth } from "@/hooks/public/use-auth";

/** Account navigation links — visible only when authenticated. */
function AccountNav({ onNavigate }: { onNavigate?: () => void }) {
  const { isAuthenticated } = usePublicAuth();

  if (!isAuthenticated) return null;

  return (
    <div className="flex items-center gap-3">
      <Link
        href="/account/history"
        onClick={onNavigate}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        History
      </Link>
      <Link
        href="/account/requests"
        onClick={onNavigate}
        className="text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        Requests
      </Link>
    </div>
  );
}

export function PublicHeader() {
  const [mobileOpen, setMobileOpen] = useState(false);

  function closeMobile() {
    setMobileOpen(false);
  }

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
          <AccountNav />
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
            <AccountNav onNavigate={closeMobile} />
            <CurrentUserIndicator onNavigate={closeMobile} />
          </div>
        </div>
      )}
    </header>
  );
}
