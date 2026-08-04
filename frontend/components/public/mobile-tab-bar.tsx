"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BookOpen, Search, Library, User } from "lucide-react";

import { usePublicAuth } from "@/hooks/public/use-auth";
import { useSearchOverlay } from "@/lib/search-overlay";
import { cn } from "@/lib/utils";

// Search is rendered as a button that opens the shared search overlay
// (DESIGN.md — Search contract: "tap the search tab … a centered overlay
// opens"), not as a link to a separate search page.
const tabs = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse", icon: BookOpen },
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account", label: "Account", icon: User },
];

export function MobileTabBar() {
  const pathname = usePathname();
  const { isAuthenticated } = usePublicAuth();
  const openSearch = useSearchOverlay((state) => state.open);

  function resolveHref(href: string): string {
    if (!isAuthenticated) {
      if (href === "/account/library") {
        return "/login?mode=signin&callbackUrl=%2Faccount%2Flibrary";
      }
      if (href === "/account") {
        return "/login?mode=signin&callbackUrl=%2Faccount";
      }
    }
    return href;
  }

  return (
    <nav
      aria-label="Primary"
      className={cn(
        "fixed inset-x-0 bottom-0 z-40 border-t border-border/80 bg-background/95 backdrop-blur",
        "md:hidden",
      )}
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <ul className="mx-auto flex h-14 max-w-md items-stretch justify-around">
        {tabs.map((tab) => {
          const resolved = resolveHref(tab.href);
          const isActive =
            pathname === tab.href ||
            (tab.href !== "/home" && tab.href !== "/account" && pathname.startsWith(tab.href));
          const Icon = tab.icon;

          return (
            <li key={tab.href} className="flex flex-1">
              <Link
                href={resolved}
                aria-label={tab.label}
                aria-current={isActive ? "page" : undefined}
                className={cn(
                  "flex w-full flex-col items-center justify-center gap-0.5 text-[0.68rem] font-medium transition-colors",
                  isActive
                    ? "text-primary"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-5 w-5" aria-hidden="true" />
                {tab.label}
              </Link>
            </li>
          );
        })}

        {/* Search tab — opens the shared overlay */}
        <li className="flex flex-1">
          <button
            type="button"
            onClick={openSearch}
            aria-label="Search"
            className={cn(
              "flex w-full flex-col items-center justify-center gap-0.5 text-[0.68rem] font-medium transition-colors",
              "text-muted-foreground hover:text-foreground",
            )}
          >
            <Search className="h-5 w-5" aria-hidden="true" />
            Search
          </button>
        </li>
      </ul>
    </nav>
  );
}
