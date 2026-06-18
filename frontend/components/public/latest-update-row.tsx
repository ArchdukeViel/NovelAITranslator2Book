"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { groupDateLabel, todayTimeLabel } from "@/lib/date-group";

interface LatestUpdateRowProps {
  chapterLabel?: string;
  href: string;
  latestChapterNumber?: number | null;
  latestChapterTitle?: string | null;
  sourceTitle?: string | null;
  title: string;
  updatedAt?: string | null;
}

function latestChapterLabel(
  chapterNumber: number | null | undefined,
  chapterTitle: string | null | undefined,
): string | null {
  const title = chapterTitle?.trim();
  if (typeof chapterNumber === "number" && title) {
    return `Chapter ${chapterNumber}: ${title}`;
  }
  if (typeof chapterNumber === "number") {
    return `Chapter ${chapterNumber}`;
  }
  return title || null;
}

export function LatestUpdateRow({
  chapterLabel,
  href,
  latestChapterNumber,
  latestChapterTitle,
  sourceTitle,
  title,
  updatedAt,
}: LatestUpdateRowProps) {
  const timeLabel = groupDateLabel(updatedAt);
  const timeDetail = todayTimeLabel(updatedAt);
  const displayChapterLabel =
    latestChapterLabel(latestChapterNumber, latestChapterTitle) ?? chapterLabel;

  return (
    <Link
      href={href}
      className="group flex items-center gap-4 px-4 py-4 transition-colors hover:bg-card"
    >
      <div className="flex h-12 w-9 shrink-0 items-center justify-center rounded-sm border border-border/70 bg-muted text-muted-foreground">
        <BookOpen className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-literary text-sm font-semibold group-hover:text-accent">
          {title}
        </p>
        {sourceTitle && (
          <p className="mt-0.5 truncate font-literary text-xs text-muted-foreground">
            {sourceTitle}
          </p>
        )}
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          {displayChapterLabel && <span>{displayChapterLabel}</span>}
          {/* For today items: show actual time detail.
              For older items: show nothing (group header is sufficient). */}
          {timeLabel === "Today" && timeDetail && (
            <span className="font-metadata tracking-wide text-muted-foreground/60">
              {timeDetail}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
