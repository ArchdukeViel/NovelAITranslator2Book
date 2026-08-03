"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BookOpen, FileText, Library } from "lucide-react";

import { NotificationIndicator } from "@/components/public/notification-indicator";
import { SearchEntry } from "@/components/public/search-entry";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { PublicBrand } from "@/components/public/public-brand";
import { PublicSidebar } from "@/components/public/public-sidebar";
import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { cn } from "@/lib/utils";

// Ranking and Contribute are excluded from the primary header nav per the
// DESIGN.md honesty principle — they have no live data yet. They remain
// reachable from the Account/More hub (mobile) and the footer (desktop).
// Add them to the header when they ship real data or a real action.
const desktopNavItems = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse", icon: BookOpen },
  { href: "/request-novel", label: "Request", icon: FileText },
  { href: "/account/library", label: "Library", icon: Library },
];

export function PublicHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-30 border-b border-border/80 bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <PublicSidebar />
        <PublicBrand className="shrink-0" />

        <nav
          aria-label="Primary"
          className="hidden flex-1 items-center gap-1 md:flex"
        >
          {desktopNavItems.map((item) => {
            const isActive =
              pathname === item.href ||
              (item.href !== "/home" && pathname.startsWith(item.href));
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1.5 text-sm font-medium transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:bg-card/70 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="hidden flex-1 justify-center md:flex">
          <SearchEntry />
        </div>

        <div className="ml-auto flex items-center gap-1 sm:gap-2">
          <div className="hidden md:block">
            <PublicThemeToggle />
          </div>
          <NotificationIndicator />
          <CurrentUserIndicator />
        </div>
      </div>
    </header>
  );
}
