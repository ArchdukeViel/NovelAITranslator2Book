"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  BookOpen,
  Clock,
  FileText,
  Heart,
  History,
  Home,
  Library,
  Settings,
  Trophy,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { PublicBrand } from "@/components/public/public-brand";
import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { usePublicAuth } from "@/hooks/public/use-auth";
import { cn } from "@/lib/utils";

const mainNavItems = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse Novels", icon: BookOpen },
  { href: "/ranking", label: "Ranking", icon: Trophy },
  { href: "/request-novel", label: "Request Novel", icon: FileText },
  { href: "/contribute", label: "Contribute", icon: Heart },
];

const accountNavItems = [
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account/history", label: "History", icon: History },
  { href: "/account/requests", label: "Requests", icon: Clock },
  { href: "/account/contributions", label: "Contributions", icon: Heart },
  { href: "/account/settings", label: "Settings", icon: Settings },
];

export function PublicSidebar({
  isOpen,
  onClose,
}: {
  isOpen?: boolean;
  onClose?: () => void;
}) {
  const pathname = usePathname();
  const { isAuthenticated } = usePublicAuth();

  useEffect(() => {
    if (!isOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose?.();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-background/70 backdrop-blur-sm"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Public navigation"
        aria-hidden={!isOpen}
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-[min(18rem,calc(100vw-2rem))] transform border-r border-border/80 bg-background shadow-2xl transition-transform duration-200 ease-in-out",
          isOpen ? "translate-x-0" : "invisible -translate-x-full"
        )}
      >
        <div className="flex h-full flex-col px-3 py-4">
          <div className="mb-5 flex items-center justify-between gap-3 px-1">
            <PublicBrand />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Close navigation menu"
              onClick={onClose}
              className="h-8 w-8 rounded-sm text-primary hover:bg-primary/10"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          <div className="mb-3 rounded-sm border border-border/70 bg-card/45 p-2">
            <CurrentUserIndicator onNavigate={onClose} />
          </div>

          <div className="mb-4 flex items-center justify-between rounded-sm border border-border/70 bg-card/45 px-3 py-2">
            <p className="font-metadata text-xs font-medium uppercase tracking-wide text-foreground">
              Theme
            </p>
            <PublicThemeToggle />
          </div>

          <nav className="flex-1 space-y-5">
            <div>
              <p className="px-2 font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Public
              </p>
              <div className="mt-2 space-y-1">
                {mainNavItems.map((item) => {
                  const isActive =
                    pathname === item.href ||
                    (item.href !== "/home" && pathname.startsWith(item.href));
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={onClose}
                      className={cn(
                        "flex items-center gap-3 rounded-sm border-l-2 px-3 py-2.5 text-sm font-medium transition-colors",
                        isActive
                          ? "border-primary bg-card text-primary"
                          : "border-transparent text-muted-foreground hover:bg-card/70 hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>

            {isAuthenticated && (
              <div>
                <p className="px-2 font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Account
                </p>
                <div className="mt-2 space-y-1">
                  {accountNavItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={onClose}
                        className={cn(
                          "flex items-center gap-3 rounded-sm border-l-2 px-3 py-2.5 text-sm font-medium transition-colors",
                          isActive
                            ? "border-primary bg-card text-primary"
                            : "border-transparent text-muted-foreground hover:bg-card/70 hover:text-foreground"
                        )}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}
          </nav>

          <p className="mt-6 border-t border-border/60 px-2 pt-4 font-metadata text-[0.68rem] uppercase leading-5 tracking-wide text-muted-foreground">
            Dokushodo is powered by Novel AI.
          </p>
        </div>
      </aside>
    </>
  );
}
