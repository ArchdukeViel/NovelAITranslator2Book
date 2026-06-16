"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { groupDateLabel } from "@/lib/date-group";

interface LatestUpdateRowProps {
  chapterLabel?: string;
  href: string;
  sourceTitle?: string | null;
  title: string;
  updatedAt?: string | null;
}

export function LatestUpdateRow({
  chapterLabel,
  href,
  sourceTitle,
  title,
  updatedAt,
}: LatestUpdateRowProps) {
  const timeLabel = groupDateLabel(updatedAt);

  return (
    <Link
      href={href}
      className="group flex items-center gap-3 rounded-lg bg-card/70 p-3 transition-colors hover:bg-card"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
        <BookOpen className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium group-hover:text-accent">
          {title}
        </p>
        {sourceTitle && (
          <p className="mt-0.5 truncate font-literary text-xs text-muted-foreground">
            {sourceTitle}
          </p>
        )}
        <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
          {chapterLabel && <span>{chapterLabel}</span>}
          {timeLabel && (
            <span className="font-metadata tracking-wide text-muted-foreground/60">
              {timeLabel}
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
