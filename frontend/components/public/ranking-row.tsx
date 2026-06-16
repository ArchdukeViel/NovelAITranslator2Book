import Link from "next/link";
import { BookOpen } from "lucide-react";

interface RankingRowProps {
  href: string;
  meta?: string;
  rank: number;
  title: string;
}

export function RankingRow({ href, meta, rank, title }: RankingRowProps) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-4 p-4 transition-colors hover:bg-muted/50"
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-accent/10 font-metadata text-sm font-medium text-accent">
        {rank}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium group-hover:text-accent">
          {title}
        </p>
        {meta && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {meta}
          </p>
        )}
      </div>
      <span className="inline-flex shrink-0 items-center gap-1.5 text-sm text-primary group-hover:text-accent">
        <BookOpen className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">Open</span>
      </span>
    </Link>
  );
}
