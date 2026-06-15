"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody } from "@/components/ui/panel";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { authorOrFallback } from "@/lib/public-format";
import type { PublicNovelSummary } from "@/lib/public-types";

interface NovelCardProps {
  novel: PublicNovelSummary;
}

export function NovelCard({ novel }: NovelCardProps) {
  return (
    <Panel className="h-full transition-colors hover:border-primary">
      <PanelBody>
        {/* Title and metadata — primary click target */}
        <Link href={`/novel/${encodeURIComponent(novel.slug)}`}>
          <h2 className="text-base font-semibold">
            {novel.title || novel.slug}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {authorOrFallback(novel.author)}
          </p>

          {/* Badges row */}
          <div className="mt-2 flex flex-wrap gap-1.5">
            <Badge tone="blue">{novel.translated_count} translated</Badge>
            <Badge tone="neutral">{novel.chapter_count} chapters</Badge>
            {novel.language && (
              <Badge tone="neutral">{novel.language}</Badge>
            )}
            {novel.status && (
              <Badge tone="amber">{novel.status}</Badge>
            )}
          </div>

          {/* Read CTA */}
          <span className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-primary">
            <BookOpen className="h-3.5 w-3.5" />
            View details
          </span>
        </Link>

        {/* Save button — must NOT be inside the Link to avoid nested interactive element */}
        <div
          className="mt-3"
          onClick={(e) => e.preventDefault()}
          onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") e.stopPropagation(); }}
        >
          <SaveToLibrary slug={novel.slug} />
        </div>
      </PanelBody>
    </Panel>
  );
}
