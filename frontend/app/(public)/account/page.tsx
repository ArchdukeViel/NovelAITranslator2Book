"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  Clock,
  Heart,
  History,
  Library,
  Loader2,
  LogOut,
  Settings,
  Trophy,
  FileText,
  Info,
  LifeBuoy,
  Scale,
} from "lucide-react";

import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";

const libraryLinks = [
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account/history", label: "History", icon: History },
  { href: "/account/notifications", label: "Notifications", icon: Bell },
  { href: "/account/requests", label: "Requests", icon: Clock },
  { href: "/account/contributions", label: "Contributions", icon: Heart },
  { href: "/account/settings", label: "Settings", icon: Settings },
];

const moreLinks = [
  { href: "/ranking", label: "Ranking", icon: Trophy },
  { href: "/request-novel", label: "Request Novel", icon: FileText },
  { href: "/contribute", label: "Contribute", icon: Heart },
  { href: "/about", label: "About", icon: Info },
  { href: "/support", label: "Support", icon: LifeBuoy },
  { href: "/legal", label: "Legal", icon: Scale },
];

export default function AccountHubPage() {
  const router = useRouter();
  const { isAuthenticated, isPending } = usePublicAuth();
  const logout = useLogout();

  useEffect(() => {
    if (!isPending && !isAuthenticated) {
      router.replace("/login?mode=signin");
    }
  }, [isPending, isAuthenticated, router]);

  if (isPending) {
    return (
      <main className="mx-auto flex min-h-[50vh] max-w-7xl items-center justify-center px-4 py-8">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
      </main>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">Account</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Library shortcuts, settings, and more.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section aria-labelledby="account-shortcuts-heading">
          <h2 id="account-shortcuts-heading" className="mb-3 font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Your account
          </h2>
          <div className="grid gap-1 rounded-md border border-border bg-card p-2">
            {libraryLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {link.label}
                </Link>
              );
            })}
          </div>
          <div className="mt-3 flex items-center justify-between rounded-md border border-border bg-card p-3">
            <p className="text-sm font-medium">Theme</p>
            <PublicThemeToggle />
          </div>
        </section>

        <section aria-labelledby="account-more-heading">
          <h2 id="account-more-heading" className="mb-3 font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
            More
          </h2>
          <div className="grid gap-1 rounded-md border border-border bg-card p-2">
            {moreLinks.map((link) => {
              const Icon = link.icon;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className="flex items-center gap-3 rounded-sm px-3 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {link.label}
                </Link>
              );
            })}
          </div>
        </section>
      </div>

      <div className="mt-8">
        <button
          type="button"
          onClick={() => logout.mutate()}
          disabled={logout.isPending}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-destructive/40 px-3 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
        >
          {logout.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <LogOut className="h-4 w-4" />
          )}
          {logout.isPending ? "Signing out…" : "Sign out"}
        </button>
      </div>
    </main>
  );
}
