"use client";

import { Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SearchEntry } from "@/components/public/search-entry";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { PublicBrand } from "@/components/public/public-brand";

export function PublicHeader({ onMenuClick }: { onMenuClick: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border/80 bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <Button
          variant="ghost"
          size="icon"
          aria-label="Open navigation menu"
          onClick={onMenuClick}
          className="h-8 w-8 shrink-0 rounded-sm"
        >
          <Menu className="h-4 w-4" />
        </Button>

        <PublicBrand className="shrink-0" />

        <div className="hidden flex-1 justify-center md:flex">
          <SearchEntry />
        </div>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <CurrentUserIndicator />
        </div>
      </div>

      <div className="border-t border-border/50 px-4 py-2 md:hidden">
        <SearchEntry />
      </div>
    </header>
  );
}
