"use client";

import { Bell, Loader2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { useUnreadCount, usePublicAuth } from "@/hooks/public";

export function NotificationIndicator() {
  const { isAuthenticated, isPending } = usePublicAuth();
  const { data: unreadCount = 0, isLoading, refetch } = useUnreadCount();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (isAuthenticated && !isPending) {
      refetch();
    }
  }, [isAuthenticated, isPending, refetch]);

  if (!mounted || isPending || !isAuthenticated) {
    return null;
  }

  const showBadge = unreadCount > 0;
  const displayCount = unreadCount > 99 ? "99+" : String(unreadCount);

  return (
    <Link
      href="/account/notifications"
      aria-label={showBadge ? `${unreadCount} unread notifications` : "No unread notifications"}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-sm hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Bell className="h-4 w-4" aria-hidden="true" />
      {showBadge && (
        <span
          className="absolute -top-1 -right-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-medium text-destructive-foreground"
          aria-live="polite"
          aria-atomic="true"
        >
          {displayCount}
        </span>
      )}
      {isLoading && !showBadge && (
        <Loader2 className="absolute -top-1 -right-1 h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" role="img" data-testid="unread-count-loader" />
      )}
    </Link>
  );
}
