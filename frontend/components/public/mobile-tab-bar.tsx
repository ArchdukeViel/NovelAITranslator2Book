"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Home, BookOpen, Search, Library, User } from "lucide-react";

import { usePublicAuth } from "@/hooks/public/use-auth";
import { cn } from "@/lib/utils";

const tabs = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse", icon: BookOpen },
  { href: "/browse-novels?focus=search", label: "Search", icon: Search },
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account", label: "Account", icon: User },
];

export function MobileTabBar() {
  const pathname = usePathname();
  const { isAuthenticated } = usePublicAuth();

  function resolveHref(href: string): string {
    if (!isAuthenticated) {
      if (href === "/account/library") {
        return "/login?mode=signin&next=%2Faccount%2Flibrary";
      }
      if (href === "/account") {
        return "/login?mode=signin";
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
            (tab.href !== "/home" &&
              tab.href !== "/browse-novels?focus=search" &&
              tab.href !== "/account" &&
              pathname.startsWith(tab.href));
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
      </ul>
    </nav>
  );
}
