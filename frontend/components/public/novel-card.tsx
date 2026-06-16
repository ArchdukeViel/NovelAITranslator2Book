"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { authorOrFallback } from "@/lib/public-format";
import type { PublicNovelSummary } from "@/lib/public-types";

interface NovelCardProps {
  novel: PublicNovelSummary;
}

export function NovelCard({ novel }: NovelCardProps) {
  return (
    <div className="group flex h-full flex-col rounded-lg border border-border bg-card p-4 transition-all duration-200 hover:border-accent/30">
      {/* Title and metadata — primary click target */}
      <Link href={`/novels/${encodeURIComponent(novel.slug)}`} className="flex-1">
        <h2 className="text-base font-semibold font-literary leading-snug group-hover:text-accent">
          {novel.title || novel.slug}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {authorOrFallback(novel.author)}
        </p>

        {/* Badges row */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          <Badge tone="neutral" className="font-metadata text-xs">
            {novel.translated_count}/{novel.chapter_count} ch.
          </Badge>
          {novel.language && (
            <Badge tone="neutral" className="font-metadata text-xs">
              {novel.language}
            </Badge>
          )}
          {novel.status && (
            <Badge tone="amber" className="font-metadata text-xs">
              {novel.status}
            </Badge>
          )}
        </div>

        {/* Read CTA */}
        <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary transition-colors group-hover:text-accent">
          <BookOpen className="h-3.5 w-3.5" />
          View details
        </span>
      </Link>

      {/* Save button — must NOT be inside the Link to avoid nested interactive element */}
      <div
        className="mt-4 pt-3 border-t border-border"
        onClick={(e) => e.preventDefault()}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation(); }}
      >
        <SaveToLibrary slug={novel.slug} />
      </div>
    </div>
  );
}
