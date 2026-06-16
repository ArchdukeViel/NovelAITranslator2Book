"use client";

import Link from "next/link";
import { Library, Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SearchEntry } from "@/components/public/search-entry";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { PublicBrand } from "@/components/public/public-brand";
import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { usePublicAuth } from "@/hooks/public/use-auth";

export function PublicHeader({ onMenuClick }: { onMenuClick: () => void }) {
  const { isAuthenticated } = usePublicAuth();

  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation menu"
          onClick={onMenuClick}
          className="shrink-0"
        >
          <Menu className="h-5 w-5" />
        </Button>

        <PublicBrand className="shrink-0" />

        <div className="hidden flex-1 justify-center md:flex">
          <SearchEntry />
        </div>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          {isAuthenticated && (
            <Link
              href="/account/library"
              className="hidden h-9 items-center gap-2 rounded-md px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground lg:inline-flex"
            >
              <Library className="h-4 w-4" />
              Library
            </Link>
          )}
          <PublicThemeToggle />
          <CurrentUserIndicator />
        </div>
      </div>

      <div className="border-t border-border/50 px-4 py-2 md:hidden">
        <SearchEntry />
      </div>
    </header>
  );
}
