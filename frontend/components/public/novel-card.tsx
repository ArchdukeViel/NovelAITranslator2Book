"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip, TagChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { useGenreLabelMap } from "@/hooks/public/use-genre-labels";
import { authorOrFallback } from "@/lib/public-format";
import { publicNovelHref } from "@/lib/public-routes";
import type { PublicNovelSummary } from "@/lib/public-types";

type DiscoveryNovel = PublicNovelSummary & {
  cover_url?: string | null;
  source_key?: string | null;
  updated_at?: string | null;
};

const MAX_VISIBLE_GENRES = 3;
const MAX_VISIBLE_TAGS = 2;

function genreLabel(slug: string, labelMap: Map<string, string> | null): string {
  if (labelMap) {
    return labelMap.get(slug) ?? slug;
  }
  return slug;
}

interface NovelCardProps {
  novel: DiscoveryNovel;
}

export function NovelCard({ novel }: NovelCardProps) {
  const title = novel.title || novel.slug;
  const sourceTitle = novel.source_title?.trim();
  const showSourceTitle = Boolean(sourceTitle && sourceTitle !== title);
  const genres = novel.genres ?? [];
  const tags = novel.tags ?? [];
  const labelMap = useGenreLabelMap();

  return (
    <div className="group flex h-full flex-col overflow-hidden rounded-lg border border-border bg-card/85 transition-all duration-200 hover:border-accent/30 hover:bg-card">
      {/* Title and metadata - primary click target */}
      <Link href={publicNovelHref(novel.slug)} className="flex-1">
        <div className="aspect-[2/3] overflow-hidden bg-muted">
          {novel.cover_url ? (
            <img
              src={novel.cover_url}
              alt={`Cover for ${title}`}
              className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
            />
          ) : (
            <FallbackCover
              className="rounded-none border-0 shadow-none"
              genres={genres}
              language={novel.language}
              sourceTitle={sourceTitle}
              status={novel.publication_status}
              title={title}
            />
          )}
        </div>

        <div className="p-4">
          <h2 className="line-clamp-2 font-literary text-base font-semibold leading-snug group-hover:text-accent">
            {title}
          </h2>
          {showSourceTitle && (
            <p className="mt-1 line-clamp-1 font-literary text-sm text-accent">
              {sourceTitle}
            </p>
          )}
          <p className="mt-1 text-sm text-muted-foreground">
            {authorOrFallback(novel.author)}
          </p>

          <NovelMetadataRow
            className="mt-3"
            chapterCount={novel.chapter_count}
            translatedCount={novel.translated_count}
            source={novel.source_key ?? novel.language}
            status={novel.publication_status}
            updatedAt={novel.updated_at}
          />

          {novel.synopsis && (
            <p className="mt-3 line-clamp-3 text-sm leading-6 text-muted-foreground">
              {novel.synopsis}
            </p>
          )}

          {(genres.length > 0 || tags.length > 0) && (
            <div className="mt-3 flex flex-wrap items-center gap-1.5">
              {genres.slice(0, MAX_VISIBLE_GENRES).map((genre) => (
                <GenreChip key={genre} label={genreLabel(genre, labelMap)} />
              ))}
              {genres.length > MAX_VISIBLE_GENRES && (
                <span className="text-xs text-muted-foreground">
                  +{genres.length - MAX_VISIBLE_GENRES}
                </span>
              )}
              {tags.slice(0, MAX_VISIBLE_TAGS).map((tag) => (
                <TagChip key={tag} label={tag} />
              ))}
              {tags.length > MAX_VISIBLE_TAGS && (
                <span className="text-xs text-muted-foreground">
                  +{tags.length - MAX_VISIBLE_TAGS}
                </span>
              )}
            </div>
          )}

          <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary transition-colors group-hover:text-accent">
            <BookOpen className="h-3.5 w-3.5" />
            View details
          </span>
        </div>
      </Link>

      {/* Save button - must not be inside the Link to avoid nested interactive elements. */}
      <div
        className="mt-auto border-t border-border p-4"
        onClick={(e) => e.preventDefault()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") e.stopPropagation();
        }}
      >
        <SaveToLibrary slug={novel.slug} />
      </div>
    </div>
  );
}
