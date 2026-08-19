"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, FileText, Library, BarChart3 } from "lucide-react";

import { NotificationIndicator } from "@/components/public/notification-indicator";
import { SearchEntry } from "@/components/public/search-entry";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { PublicBrand } from "@/components/public/public-brand";
import { PublicSidebar } from "@/components/public/public-sidebar";
import { cn } from "@/lib/utils";

const desktopNavItems = [
  { href: "/browse-novels", label: "Browse", icon: BookOpen },
  { href: "/account/request-novels", label: "Request", icon: FileText },
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/ranking", label: "Ranking", icon: BarChart3 },
];

export function PublicHeader() {
  const pathname = usePathname();
  const [isVisible, setIsVisible] = useState(true);

  // Auto-hide header on scroll down, reveal on scroll up or at top
  useEffect(() => {
    let lastScrollY = window.scrollY;

    function handleScroll() {
      const currentScrollY = window.scrollY;
      const scrollDifference = currentScrollY - lastScrollY;

      // Always show at or near top
      if (currentScrollY <= 20) {
        setIsVisible(true);
      } else if (scrollDifference > 10 && currentScrollY > 60) {
        // Scrolling down
        setIsVisible(false);
      } else if (scrollDifference < -10) {
        // Scrolling up
        setIsVisible(true);
      }

      lastScrollY = currentScrollY;
    }

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-40 border-b border-border/40 bg-background/95 backdrop-blur transition-transform duration-200",
        isVisible ? "translate-y-0" : "-translate-y-full",
      )}
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-3 sm:px-6 lg:px-8">
        <div className="flex items-center gap-2 shrink-0">
          <PublicSidebar />
          <PublicBrand className="shrink-0" />
        </div>

        <nav aria-label="Primary" className="hidden items-center gap-1 xl:flex">
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

        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <SearchEntry />
          <NotificationIndicator />
          <CurrentUserIndicator />
        </div>
      </div>
    </header>
  );
}
