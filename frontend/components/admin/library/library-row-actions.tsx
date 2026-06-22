"use client";

import { BookOpen, Eye, EyeOff, FileEdit, Languages, RefreshCw, Tags, Trash2 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { NovelSummary } from "@/lib/api";
import { publicNovelHref } from "@/lib/public-routes";
import { cn } from "@/lib/utils";

export type LibraryRowActionsProps = {
  novel: NovelSummary;
  missingSource: boolean;
  pending: boolean;
  translationPending: boolean;
  onTranslate: (novel: NovelSummary) => void;
  onRecrawl: (novel: NovelSummary) => void;
  onDelete: (novel: NovelSummary) => void;
  onEditTaxonomy: (novel: NovelSummary) => void;
  onPublish: (novel: NovelSummary) => void;
  onUnpublish: (novel: NovelSummary) => void;
};

function latestChapterText(novel: NovelSummary) {
  const number = novel.latest_chapter_number;
  const title = novel.latest_chapter_title?.trim();
  if (typeof number === "number" && title) {
    return `Latest: Ch. ${number} ${title}`;
  }
  if (typeof number === "number") {
    return `Latest: Ch. ${number}`;
  }
  if (title) {
    return `Latest: ${title}`;
  }
  return null;
}

export function LibraryRowActions({
  novel,
  missingSource,
  pending,
  translationPending,
  onTranslate,
  onRecrawl,
  onDelete,
  onEditTaxonomy,
  onPublish,
  onUnpublish
}: LibraryRowActionsProps) {
  const published = novel.is_published === true;
  const translatedCount = novel.translated_count ?? 0;
  const canPublish = translatedCount > 0;
  const publishHelper = published
    ? "Published novels appear in the public catalog when at least one translated chapter is available."
    : canPublish
      ? "Published novels appear in the public catalog when at least one translated chapter is available."
      : "Translate at least one chapter before publishing.";
  const latest = latestChapterText(novel);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={published ? "green" : "neutral"}>
          {published ? "Published" : "Unpublished"}
        </Badge>
        {novel.publication_status ? (
          <span className="text-xs text-muted-foreground">
            Source status: {novel.publication_status}
          </span>
        ) : null}
      </div>
      <div className="text-xs leading-5 text-muted-foreground">
        <div>{publishHelper}</div>
        {latest ? <div>{latest}</div> : null}
      </div>
      <div className="flex flex-wrap gap-2">
        {published ? (
          <Button size="sm" variant="outline" onClick={() => onUnpublish(novel)} disabled={pending}>
            <EyeOff className="h-4 w-4" />
            {pending ? "Unpublishing" : "Unpublish"}
          </Button>
        ) : (
          <Button
            size="sm"
            onClick={() => onPublish(novel)}
            disabled={!canPublish || pending}
            title={canPublish ? "Publish this novel" : "Translate at least one chapter before publishing."}
          >
            <Eye className="h-4 w-4" />
            {pending ? "Publishing" : "Publish"}
          </Button>
        )}
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
          href={publicNovelHref(novel.novel_id)}
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
        <Button size="sm" variant="outline" onClick={() => onEditTaxonomy(novel)} disabled={pending}>
          <Tags className="h-4 w-4" />
          Taxonomy
        </Button>
      </div>
    </div>
  );
}
