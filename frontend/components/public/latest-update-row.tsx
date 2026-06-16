import Link from "next/link";
import { BookOpen, Clock } from "lucide-react";

interface LatestUpdateRowProps {
  chapterLabel?: string;
  href: string;
  sourceTitle?: string | null;
  title: string;
}

export function LatestUpdateRow({
  chapterLabel,
  href,
  sourceTitle,
  title,
}: LatestUpdateRowProps) {
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
        {chapterLabel && (
          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            <span>{chapterLabel}</span>
          </div>
        )}
      </div>
    </Link>
  );
}
