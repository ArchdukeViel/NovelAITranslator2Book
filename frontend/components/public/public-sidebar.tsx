"use client";

import { useEffect, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createPortal } from "react-dom";
import {
  BarChart3,
  BookOpen,
  HandHeart,
  HelpCircle,
  Home,
  Library,
  Menu,
  Newspaper,
  FilePlus2,
  Shuffle,
  X,
} from "lucide-react";

const subscribeToNothing = () => () => {};
const getClientMounted = () => true;
const getServerMounted = () => false;

import { PublicThemeSegmentedControl } from "@/components/public/public-theme-toggle";
import { PublicBrand } from "@/components/public/public-brand";
import { usePublicAuth } from "@/hooks/public/use-auth";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/home", label: "Home", icon: Home },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/browse-novels", label: "Browse Novels", icon: BookOpen },
  { href: "/ranking", label: "Ranking", icon: BarChart3 },
  { href: "/random", label: "Random Novel", icon: Shuffle },
  { href: "/account/request-novels", label: "Request Novels", icon: FilePlus2 },
  { href: "/account/contributions", label: "Contributions", icon: HandHeart },
  { href: "/faq", label: "FAQ", icon: HelpCircle },
] as const;

/**
 * Fixed left sidebar (Stitch: 240px, hidden by default, slides in via the
 * header hamburger and is dismissed by the backdrop or a close button).
 * Rendered through a portal so it sits above page chrome regardless of
 * stacking context.
 */
export function PublicSidebar() {
  const pathname = usePathname();
  const { isAuthenticated } = usePublicAuth();
  const [openPathname, setOpenPathname] = useState<string | null>(null);
  const mounted = useSyncExternalStore(
    subscribeToNothing,
    getClientMounted,
    getServerMounted,
  );
  const open = openPathname === pathname;

  // Lock body scroll while open and support Escape.
  useEffect(() => {
    if (!open) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpenPathname(null);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = original;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function resolveHref(href: string): string {
    if (!isAuthenticated && href === "/account/library") {
      return "/login?mode=signin&callbackUrl=%2Faccount%2Flibrary";
    }
    return href;
  }

  function isActive(href: string): boolean {
    if (href === "/home") return pathname === "/home" || pathname === "/";
    return pathname === href || pathname.startsWith(`${href}/`);
  }

  const panel = (
    <>
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={() => setOpenPathname(null)}
        className={cn(
          "fixed inset-0 z-50 bg-foreground/40 transition-opacity duration-300",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        )}
      />
      {/* Sidebar */}
      <aside
        id="public-sidebar"
        aria-label="Site navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[min(85vw,320px)] sm:w-80 flex-col overflow-y-auto border-r border-border/30 bg-background py-4 transition-transform duration-300 ease-out",
          open ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="mb-2 flex items-center justify-between px-4">
          <PublicBrand className="text-lg" />
          <button
            type="button"
            onClick={() => setOpenPathname(null)}
            aria-label="Close navigation menu"
            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <nav aria-label="Sidebar" className="flex flex-col gap-1 px-3">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                href={resolveHref(item.href)}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                  active
                    ? "bg-muted text-primary"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-primary",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="mt-auto flex flex-col gap-2 px-4 pt-4">
          <div className="border-t border-border/40 pt-3">
            <PublicThemeSegmentedControl />
          </div>
        </div>
      </aside>
    </>
  );

  return (
    <>
      <button
        type="button"
        onClick={() =>
          setOpenPathname((current) => (current === pathname ? null : pathname))
        }
        aria-label="Open navigation menu"
        aria-expanded={open}
        aria-controls="public-sidebar"
        className="inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-primary"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </button>
      {mounted ? createPortal(panel, document.body) : null}
    </>
  );
}
