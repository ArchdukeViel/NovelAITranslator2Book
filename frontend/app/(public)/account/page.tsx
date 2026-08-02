"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Clock, Bell, Loader2, Library, History, Trophy, FileText, Heart, Info, LifeBuoy, Scale, Settings, LogOut } from "lucide-react";

import { PublicThemeToggle } from "@/components/public/public-theme-toggle";
import { useLogout, usePublicAuth } from "@/hooks/public/use-auth";
import { useLibrary, useHistory } from "@/hooks/public/use-reading-state";
import { useUnreadCount } from "@/hooks/public/use-notifications";

const mobileLibraryLinks = [
  { href: "/account/library", label: "Library", icon: Library },
  { href: "/account/history", label: "History", icon: History },
  { href: "/account/notifications", label: "Notifications", icon: Bell },
  { href: "/account/requests", label: "Requests", icon: Clock },
  { href: "/account/contributions", label: "Contributions", icon: Heart },
  { href: "/account/settings", label: "Settings", icon: Settings },
];

const mobileMoreLinks = [
  { href: "/ranking", label: "Ranking", icon: Trophy },
  { href: "/request-novel", label: "Request Novel", icon: FileText },
  { href: "/contribute", label: "Contribute", icon: Heart },
  { href: "/about", label: "About", icon: Info },
  { href: "/legal", label: "Legal", icon: Scale },
];

export default function AccountPage() {
  const pathname = usePathname();
  const { isAuthenticated, isPending } = usePublicAuth();
  const logout = useLogout();
  const { data: libraryData, isPending: libraryPending } = useLibrary();
  const { data: historyData, isPending: historyPending } = useHistory({ limit: 1 });
  const { data: unreadCount, isPending: unreadPending } = useUnreadCount();

  const isLoading = libraryPending || historyPending || unreadPending;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        <span className="sr-only">Loading account summary</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  const readingCount = libraryData?.filter((n) => n.status === "reading").length ?? 0;
  const totalLibraryCount = libraryData?.length ?? 0;
  const historyItems = historyData?.items ?? [];
  const historyCount = historyItems.length;
  const recentActivity = historyItems[0];
  const unreadNotifications = unreadCount ?? 0;

  return (
    <div>
      <header className="mb-8">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">Account</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Library shortcuts, settings, and more.
        </p>
      </header>

      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        <section aria-labelledby="reading-heading" className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            <h2 id="reading-heading" className="font-metadata text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Currently Reading
            </h2>
          </div>
          <p className="mt-4 text-3xl font-semibold" aria-live="polite" data-testid="reading-count">{readingCount}</p>
          <p className="mt-1 text-sm text-muted-foreground">{totalLibraryCount} total in library</p>
          <Link
            href="/account/library"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            View library
            <Clock className="h-3 w-3" aria-hidden="true" />
          </Link>
        </section>

        <section aria-labelledby="history-heading" className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2">
            <Clock className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            <h2 id="history-heading" className="font-metadata text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Reading History
            </h2>
          </div>
          <p className="mt-4 text-3xl font-semibold" aria-live="polite" data-testid="history-count">{historyCount}</p>
          {recentActivity ? (
            <div className="mt-4 space-y-1">
              <p className="text-sm font-medium text-muted-foreground">Most Recent Activity</p>
              <p className="text-sm font-medium">{recentActivity.slug}</p>
              <p className="text-sm text-muted-foreground">Ch. {recentActivity.chapter_number}</p>
            </div>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">No history yet</p>
          )}
          <Link
            href="/account/history"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            View history
            <Clock className="h-3 w-3" aria-hidden="true" />
          </Link>
        </section>

        <section aria-labelledby="notifications-heading" className="rounded-lg border border-border bg-card p-6">
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            <h2 id="notifications-heading" className="font-metadata text-sm font-medium uppercase tracking-wide text-muted-foreground">
              Unread Notifications
            </h2>
          </div>
          <p className="mt-4 text-3xl font-semibold" aria-live="polite">{unreadNotifications}</p>
          {unreadNotifications > 0 ? (
            <p className="mt-1 text-sm text-muted-foreground">Tap to view</p>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">All caught up</p>
          )}
          <Link
            href="/account/notifications"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            View notifications
            <Clock className="h-3 w-3" aria-hidden="true" />
          </Link>
        </section>
      </div>

      <nav className="lg:hidden border-t border-border bg-card mt-8" aria-label="Mobile account navigation">
        <div className="px-4 py-3">
          <h2 className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">Your account</h2>
          <ul className="mt-2 grid gap-1" role="list">
            {mobileLibraryLinks.map((link) => {
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
          </ul>
        </div>
        <div className="border-t border-border px-4 py-3">
          <h2 className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">More</h2>
          <ul className="mt-2 grid gap-1" role="list">
            {mobileMoreLinks.map((link) => {
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
          </ul>
        </div>
        <div className="border-t border-border px-4 py-3">
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
      </nav>
    </div>
  );
}
