"use client";

import { BookOpen, FileEdit, Languages, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { NovelSummary } from "@/lib/api";
import { cn } from "@/lib/utils";

export type LibraryRowActionsProps = {
  novel: NovelSummary;
  missingSource: boolean;
  pending: boolean;
  translationPending: boolean;
  onTranslate: (novel: NovelSummary) => void;
  onRecrawl: (novel: NovelSummary) => void;
  onDelete: (novel: NovelSummary) => void;
};

export function LibraryRowActions({
  novel,
  missingSource,
  pending,
  translationPending,
  onTranslate,
  onRecrawl,
  onDelete
}: LibraryRowActionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        size="sm"
        onClick={() => onTranslate(novel)}
        disabled={missingSource || pending || translationPending}
        title={missingSource ? "Source key missing" : "Choose chapters to translate"}
      >
        <Languages className="h-4 w-4" />
        Translate
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => onRecrawl(novel)}
        disabled={missingSource || pending}
        title={missingSource ? "Source key missing" : "Check and scrape latest chapters"}
      >
        <RefreshCw className="h-4 w-4" />
        Recrawl
      </Button>
      <Button size="sm" variant="destructive" onClick={() => onDelete(novel)} disabled={pending}>
        <Trash2 className="h-4 w-4" />
        Delete
      </Button>
      <Link
        className={cn(
          "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
        )}
        href={`/novel/${encodeURIComponent(novel.novel_id)}`}
      >
        <BookOpen className="h-4 w-4" />
        Reader
      </Link>
      <Link
        className={cn(
          "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
        )}
        href={`/admin/editor?novel=${encodeURIComponent(novel.novel_id)}`}
      >
        <FileEdit className="h-4 w-4" />
        Editor
      </Link>
    </div>
  );
}
