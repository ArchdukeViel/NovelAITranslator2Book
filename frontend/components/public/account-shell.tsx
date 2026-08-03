"use client";

import Link from "next/link";
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
  Clock,
  Heart,
  History,
  Library,
  Loader2,
  LogOut,
  Settings,
  Star,
  LifeBuoy,
} from "lucide-react";

import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";

const sidebarLinks = [
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account/history", label: "History", icon: History },
  { href: "/account/notifications", label: "Notifications", icon: Bell },
  { href: "/account/requests", label: "Requests", icon: Clock },
  { href: "/account/reviews", label: "Reviews", icon: Star },
  { href: "/account/contributions", label: "Contributions", icon: Heart },
  { href: "/account/settings", label: "Settings", icon: Settings },
];

const unavailableLinks = [
  { label: "Support", icon: LifeBuoy },
];

export function AccountShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isAuthenticated, isPending } = usePublicAuth();
  const logout = useLogout();

  useEffect(() => {
    if (!isPending && !isAuthenticated) {
      router.replace(`/login?mode=signin&next=${encodeURIComponent(pathname)}`);
    }
  }, [isPending, isAuthenticated, pathname, router]);

  if (isPending) {
    return (
      <main className="mx-auto flex min-h-[50vh] max-w-7xl items-center justify-center px-4 py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        <span className="sr-only">Checking session</span>
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="flex min-h-screen bg-background">
      <nav
        className="hidden lg:flex lg:flex-col lg:w-64 lg:border-r lg:border-border lg:bg-card lg:fixed lg:inset-y-0 lg:z-10"
        role="navigation"
        aria-label="Account navigation"
      >
        <div className="flex h-16 items-center px-6 border-b border-border">
          <h2 className="font-literary text-xl font-semibold tracking-normal">Account</h2>
        </div>

        <div className="flex flex-1 flex-col px-3 py-4">
          <ul className="flex flex-1 flex-col gap-1" role="list">
            {sidebarLinks.map((link) => {
              const Icon = link.icon;
              const isActive = pathname === link.href;
              return (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    aria-current={isActive ? "page" : undefined}
                    className={`flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    {link.label}
                  </Link>
                </li>
              );
            })}

            {unavailableLinks.map((link) => (
              <li key={link.label}>
                <div className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium text-muted-foreground">
                  <link.icon className="h-4 w-4" aria-hidden="true" />
                  <span>{link.label}</span>
                  <span className="ml-auto text-xs text-muted-foreground/60">Unavailable</span>
                </div>
              </li>
            ))}
          </ul>

          <div className="mt-auto border-t border-border pt-4">
            <div className="flex items-center justify-between rounded-md border border-border bg-card p-3">
              <p className="text-sm font-medium">Theme</p>
              <PublicThemeToggle />
            </div>
            <button
              type="button"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
              className="mt-3 w-full inline-flex items-center justify-center gap-2 rounded-md border border-destructive/40 px-3 py-2 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-50"
            >
              {logout.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LogOut className="h-4 w-4" />
              )}
              {logout.isPending ? "Signing out…" : "Sign out"}
            </button>
          </div>
        </div>
      </nav>

      <div className="flex-1 lg:pl-64">
        <header className="hidden lg:block h-16 border-b border-border" />
        <nav
          aria-label="Account sub-navigation"
          className="flex overflow-x-auto border-b border-border bg-card p-2 gap-1 lg:hidden"
        >
          {sidebarLinks.map((link) => {
            const Icon = link.icon;
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={isActive ? "page" : undefined}
                className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {link.label}
              </Link>
            );
          })}
        </nav>
        <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </div>
      </div>
    </div>
  );
}
