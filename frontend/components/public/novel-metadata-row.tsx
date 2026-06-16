import { BookOpen, CalendarDays, LibraryBig } from "lucide-react";

import { StatusBadge } from "@/components/public/status-badge";
import { cn } from "@/lib/utils";

interface NovelMetadataRowProps {
  chapterCount?: number | null;
  className?: string;
  source?: string | null;
  status?: string | null;
  translatedCount?: number | null;
  updatedAt?: string | null;
}

function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function NovelMetadataRow({
  chapterCount,
  className,
  source,
  status,
  translatedCount,
  updatedAt,
}: NovelMetadataRowProps) {
  const hasChapterCount =
    typeof chapterCount === "number" || typeof translatedCount === "number";

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 text-xs text-muted-foreground",
        className
      )}
    >
      <StatusBadge status={status} />
      {source && (
        <span className="inline-flex items-center gap-1 font-metadata">
          <LibraryBig className="h-3.5 w-3.5" />
          {source}
        </span>
      )}
      {hasChapterCount && (
        <span className="inline-flex items-center gap-1 font-metadata">
          <BookOpen className="h-3.5 w-3.5" />
          {typeof translatedCount === "number" ? `${translatedCount}/` : ""}
          {typeof chapterCount === "number" ? chapterCount : "?"} ch.
        </span>
      )}
      {updatedAt && (
        <span className="inline-flex items-center gap-1 font-metadata">
          <CalendarDays className="h-3.5 w-3.5" />
          {formatDate(updatedAt)}
        </span>
      )}
    </div>
  );
}
