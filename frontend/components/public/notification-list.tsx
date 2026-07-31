"use client";

import { Check, Loader2, Mail, MoreHorizontal, X } from "lucide-react";
import { useState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { NotificationItem, NotificationStatus } from "@/lib/public-types";

interface NotificationListProps {
  items: NotificationItem[];
  onRead: (id: number) => void;
  onArchive: (id: number) => void;
  onReadAll: () => void;
  isReadingAll?: boolean;
  isLoading?: boolean;
  emptyMessage?: string;
}

const statusStyles: Record<NotificationStatus, string> = {
  unread: "bg-info/10 text-info-foreground dark:text-info border-info/20",
  read: "bg-muted text-muted-foreground border-border/50",
  archived: "bg-destructive/10 text-destructive border-destructive/20",
};

const severityStyles: Record<NotificationItem["severity"], string> = {
  info: "bg-info/10 text-info-foreground dark:text-info border-info/20",
  success: "bg-success/10 text-success-foreground dark:text-success border-success/20",
  warning: "bg-warning/10 text-warning-foreground dark:text-warning border-warning/20",
  error: "bg-destructive/10 text-destructive border-destructive/20",
};

const eventTypeLabels: Record<NotificationItem["event_type"], string> = {
  "translation.completed": "Translation completed",
  "translation.failed": "Translation failed",
  "translation.requires_review": "Translation needs review",
};

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function safeActionUrl(url: string | null): string | null {
  if (!url || !url.startsWith("/") || url.startsWith("//")) {
    return null;
  }
  try {
    const parsed = new URL(url, "http://novelai.local");
    if (parsed.origin !== "http://novelai.local") {
      return null;
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
}

export function NotificationList({
  items,
  onRead,
  onArchive,
  onReadAll,
  isReadingAll,
  isLoading,
  emptyMessage = "No notifications yet.",
}: NotificationListProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" role="img" data-testid="notification-list-loader" />
        <span className="sr-only">Loading notifications...</span>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-muted-foreground">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="space-y-3" role="list" aria-label="Notifications">
      {items.length > 0 && items[0].status === "unread" && (
        <Button
          variant="outline"
          size="sm"
          onClick={onReadAll}
          disabled={isReadingAll}
          className="w-full justify-start"
        >
          {isReadingAll ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />
              Marking all as read…
            </>
          ) : (
            <>
              <Check className="mr-2 h-4 w-4" aria-hidden="true" />
              Mark all as read
            </>
          )}
        </Button>
      )}

      {items.map((notification) => {
        const isUnread = notification.status === "unread";
        const actionUrl = safeActionUrl(notification.action_url);

        return (
          <article
            key={notification.id}
            className={cn(
              "relative flex gap-3 rounded-lg border p-4 transition-colors",
              isUnread ? "bg-card ring-1 ring-info/20" : "bg-card/50",
              statusStyles[notification.status]
            )}
            role="listitem"
            aria-label={
              `${eventTypeLabels[notification.event_type]}, ${notification.status}, ${formatDate(notification.created_at)}`
            }
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-start gap-2">
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
                    severityStyles[notification.severity]
                  )}
                >
                  {notification.severity}
                </span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium",
                    statusStyles[notification.status]
                  )}
                >
                  {notification.status}
                </span>
              </div>
              <h3 className={cn("mt-1 font-medium text-sm", isUnread ? "font-semibold" : "")}>
                {notification.title}
              </h3>
              <p className="mt-1 text-sm text-muted-foreground line-clamp-2">{notification.body}</p>
              <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Mail className="h-3 w-3" aria-hidden="true" />
                  {eventTypeLabels[notification.event_type]}
                </span>
                <time dateTime={notification.created_at}>{formatDate(notification.created_at)}</time>
              </div>
            </div>

            <div className="flex items-start gap-2">
              {actionUrl && (
                <Link
                  href={actionUrl}
                  className="inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
                >
                  View
                </Link>
              )}
              <div className="relative">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  aria-label="More actions"
                  aria-expanded={expandedId === notification.id}
                  aria-haspopup="true"
                  onClick={() => setExpandedId(expandedId === notification.id ? null : notification.id)}
                >
                  <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
                </Button>
                {expandedId === notification.id && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setExpandedId(null)}
                      aria-hidden="true"
                    />
                    <div className="absolute right-0 z-20 mt-1 w-40 rounded-md border bg-popover p-1 shadow-md">
                      {isUnread && (
                        <button
                          type="button"
                          className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-sm text-left hover:bg-accent"
                          onClick={() => onRead(notification.id)}
                        >
                          <Check className="h-4 w-4" aria-hidden="true" />
                          Mark as read
                        </button>
                      )}
                      <button
                        type="button"
                        className="flex w-full items-center gap-2 rounded-sm px-3 py-2 text-sm text-left text-destructive hover:bg-accent"
                        onClick={() => onArchive(notification.id)}
                      >
                        <X className="h-4 w-4" aria-hidden="true" />
                        Archive
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          </article>
        );
      })}
    </div>
  );
}
