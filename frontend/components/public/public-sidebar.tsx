"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import { BookOpen, FileText, Heart, Home, Library, Trophy, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { CurrentUserIndicator } from "@/components/public/current-user-indicator";
import { usePublicAuth } from "@/hooks/public/use-auth";
import { cn } from "@/lib/utils";

const mainNavItems = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/browse-novels", label: "Browse Novels", icon: BookOpen },
  { href: "/ranking", label: "Ranking", icon: Trophy },
  { href: "/request-novel", label: "Request Novel", icon: FileText },
  { href: "/contribute", label: "Contribute", icon: Heart },
  { href: "/account/library", label: "Library", icon: Library },
];

const accountNavItems = [
  { href: "/account/requests", label: "Requests" },
  { href: "/account/contributions", label: "Contributions" },
  { href: "/account/settings", label: "Settings" },
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
  const visibleMainNavItems = isAuthenticated
    ? mainNavItems
    : mainNavItems.filter((item) => item.href !== "/account/library");

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
          "fixed inset-y-0 left-0 z-50 w-[min(22rem,calc(100vw-2rem))] transform border-r border-border/60 bg-background shadow-2xl transition-transform duration-200 ease-in-out",
          isOpen ? "translate-x-0" : "invisible -translate-x-full"
        )}
      >
        <div className="flex h-full flex-col px-5 py-5">
          <div className="mb-6 flex items-center justify-between gap-3">
            <div>
              <p className="font-literary text-lg font-semibold">読書堂</p>
              <p className="mt-1 text-xs text-muted-foreground">Dokushodo navigation</p>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              aria-label="Close navigation menu"
              onClick={onClose}
            >
              <X className="h-5 w-5" />
            </Button>
          </div>

          <div className="mb-5 rounded-lg bg-muted/60 p-3">
            <CurrentUserIndicator onNavigate={onClose} />
          </div>

          <nav className="flex-1 space-y-6">
            <div>
              <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Public
              </p>
              <div className="mt-2 space-y-1">
                {visibleMainNavItems.map((item) => {
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
                        "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                        isActive
                          ? "bg-secondary text-accent"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground"
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
                <p className="px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Account
                </p>
                <div className="mt-2 space-y-1">
                  {accountNavItems.map((item) => {
                    const isActive = pathname === item.href;
                    return (
                      <Link
                        key={item.href}
                        href={item.href}
                        onClick={onClose}
                        className={cn(
                          "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors",
                          isActive
                            ? "bg-secondary text-accent"
                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                        )}
                      >
                        {item.label}
                      </Link>
                    );
                  })}
                </div>
              </div>
            )}
          </nav>

          <p className="mt-6 border-t border-border/60 pt-4 text-xs leading-5 text-muted-foreground">
            Dokushodo is powered by Novel AI.
          </p>
        </div>
      </aside>
    </>
  );
}
