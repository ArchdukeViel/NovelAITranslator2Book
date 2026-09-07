"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { BookOpen, ChevronRight } from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip, TagChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { authorOrFallback } from "@/lib/public-format";
import { publicNovelHref, publicChapterHref } from "@/lib/public-routes";
import type { PublicGenreInfo, PublicNovelSummary } from "@/lib/public-types";
import { cn } from "@/lib/utils";

type DiscoveryNovel = PublicNovelSummary & {
  cover_url?: string | null;
  source_key?: string | null;
  updated_at?: string | null;
  views?: number | null;
  rating?: number | null;
};

const CARD_SURFACE = "bg-card shadow-card dark:ring-1 dark:ring-white/5";
const CARD_LIFT =
  "transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-raised motion-reduce:hover:translate-y-0 motion-reduce:transition-none";

const MAX_VISIBLE_GENRES = 3;
const MAX_VISIBLE_TAGS = 2;

/** Wraps a cover Image with graceful fallback on load error. */
function CoverImage({
  coverUrl,
  title,
  genres,
  language,
  sourceTitle,
  status,
}: {
  coverUrl: string;
  title: string;
  genres?: PublicGenreInfo[] | null;
  language?: string | null;
  sourceTitle?: string | null;
  status?: string | null;
}) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <FallbackCover
        className="rounded-none border-0 shadow-none"
        genres={genres}
        language={language}
        sourceTitle={sourceTitle}
        status={status}
        title={title}
      />
    );
  }

  return (
    <Image
      src={coverUrl}
      alt={`Cover for ${title}`}
      fill
      sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 20vw"
      onError={() => setFailed(true)}
      className="h-full w-full object-cover transition-transform duration-300 ease-out group-hover:scale-[1.02] motion-reduce:group-hover:scale-100 motion-reduce:transition-none"
    />
  );
}

interface NovelCardProps {
  novel: DiscoveryNovel;
  layout?: "card" | "list";
}

export function NovelCard({ novel, layout = "card" }: NovelCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isList = layout === "list";
  const title = novel.title || novel.slug;
  const sourceTitle = novel.source_title?.trim();
  const showSourceTitle = Boolean(sourceTitle && sourceTitle !== title);
  const genres = novel.genres ?? [];
  const tags = novel.tags ?? [];

  if (isList) {
    const readHref = novel.latest_chapter_id
      ? publicChapterHref(novel.slug, novel.latest_chapter_id)
      : publicNovelHref(novel.slug);

    return (
      <div
        className={cn(
          "group relative flex flex-col justify-between overflow-hidden rounded-xl border border-border/60 bg-card p-3.5 sm:p-4 shadow-card hover:shadow-raised transition-all duration-300 ease-out dark:border-white/10 motion-reduce:transition-none",
        )}
      >
        <div className="space-y-3">
          {/* Top Header: English Title + Japanese Title */}
          <div>
            <Link
              href={publicNovelHref(novel.slug)}
              className="group/title block rounded-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <h2 className="line-clamp-2 font-sans text-base sm:text-lg font-semibold leading-snug text-foreground transition-colors group-hover/title:text-primary motion-reduce:transition-none">
                {title}
              </h2>
              {showSourceTitle && (
                <p
                  lang="ja"
                  className="mt-0.5 line-clamp-1 font-sans text-xs text-muted-foreground/80"
                >
                  {sourceTitle}
                </p>
              )}
            </Link>
          </div>

          {/* Middle Row: Cover + Stats Grid & Action Buttons */}
          <div className="flex gap-3 sm:gap-4">
            {/* Cover image on left */}
            <Link
              href={publicNovelHref(novel.slug)}
              tabIndex={-1}
              aria-hidden="true"
              className="group/cover relative block shrink-0 self-start overflow-hidden rounded-lg border border-border/60 bg-muted/40 shadow-xs focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <div className="relative aspect-2/3 w-24 sm:w-28 md:w-32 overflow-hidden rounded-lg">
                {novel.cover_url ? (
                  <CoverImage
                    coverUrl={novel.cover_url}
                    title={title}
                    genres={genres}
                    language={novel.language}
                    sourceTitle={sourceTitle}
                    status={novel.publication_status}
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
            </Link>

            {/* Right side: Stats Grid + Action Buttons */}
            <div className="flex flex-1 min-w-0 flex-col justify-between self-stretch">
              {/* Stats Grid - 3-column stats pill grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 sm:gap-2">
                {/* Status */}
                <div className="col-span-2 sm:col-span-3 flex items-center justify-center rounded-lg border border-border/60 bg-muted/40 px-2.5 py-1.5 text-center gap-1.5 dark:border-white/10">
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Status
                  </span>
                  <span className="text-muted-foreground/40">•</span>
                  <div className="flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "h-2 w-2 rounded-full shrink-0",
                        novel.publication_status === "ongoing"
                          ? "bg-emerald-500 shadow-[0_0_6px_rgba(16,185,129,0.4)]"
                          : novel.publication_status === "completed"
                            ? "bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.4)]"
                            : novel.publication_status === "hiatus"
                              ? "bg-amber-500 shadow-[0_0_6px_rgba(245,158,11,0.4)]"
                              : novel.publication_status === "cancelled"
                                ? "bg-rose-500 shadow-[0_0_6px_rgba(244,63,94,0.4)]"
                                : "bg-muted-foreground",
                      )}
                    />
                    <span className="text-xs font-semibold leading-none capitalize text-foreground">
                      {novel.publication_status || "Unknown"}
                    </span>
                  </div>
                </div>

                {/* Views */}
                <div className="flex flex-col items-center justify-center rounded-lg border border-border/60 bg-muted/40 px-2 sm:px-2.5 py-1.5 text-center gap-0.5 dark:border-white/10">
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Views
                  </span>
                  <span className="text-xs font-semibold leading-none tabular-nums text-foreground">
                    {novel.views
                      ? novel.views >= 1000
                        ? `${(novel.views / 1000).toFixed(1)}k`
                        : novel.views.toLocaleString()
                      : "0"}
                  </span>
                </div>

                {/* Chapters */}
                <div className="flex flex-col items-center justify-center rounded-lg border border-border/60 bg-muted/40 px-2 sm:px-2.5 py-1.5 text-center gap-0.5 dark:border-white/10">
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Chapters
                  </span>
                  <span className="text-xs font-semibold leading-none tabular-nums text-foreground">
                    {novel.chapter_count}
                  </span>
                </div>

                {/* Rating */}
                <div className="col-span-2 sm:col-span-1 flex flex-col items-center justify-center rounded-lg border border-border/60 bg-muted/40 px-2 sm:px-2.5 py-1.5 text-center gap-0.5 dark:border-white/10">
                  <span className="font-sans text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Rating
                  </span>
                  <div className="flex items-center justify-center gap-1 text-xs font-semibold leading-none tabular-nums text-foreground">
                    <span aria-hidden="true" className="text-amber-500">
                      ★
                    </span>
                    <span>{novel.rating ? novel.rating.toFixed(1) : "0"}</span>
                  </div>
                </div>
              </div>

              {/* Action Buttons: Add to Library + Start Reading */}
              <div className="flex flex-col gap-1.5 mt-2">
                <div
                  className="w-full"
                  onClick={(e) => e.preventDefault()}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") e.stopPropagation();
                  }}
                >
                  <SaveToLibrary compactGuest slug={novel.slug} />
                </div>
                <Link
                  href={readHref}
                  className="inline-flex h-9 sm:h-10 w-full items-center justify-center gap-1.5 rounded-lg border border-border/70 bg-muted/30 text-xs font-semibold text-foreground transition-colors hover:bg-muted/70 hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <BookOpen className="h-3.5 w-3.5" />
                  Start Reading
                </Link>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section: Taxonomy Chips + Synopsis */}
        <div className="mt-3 space-y-2.5 border-t border-border/60 pt-3">
          {(genres.length > 0 || tags.length > 0) && (
            <div className="flex flex-wrap items-center gap-1.5">
              {genres.map((genre) => (
                <GenreChip
                  key={genre.slug}
                  label={genre.name_en ?? genre.slug}
                  labelJa={genre.name_ja}
                  className="rounded-full px-2.5 py-0.5 text-[11px] font-medium border-border/60 bg-muted/40 text-foreground"
                />
              ))}
              {tags.map((tag) => (
                <TagChip
                  key={tag.name}
                  label={tag.name}
                  labelJa={tag.name_ja}
                  className="rounded-full px-2.5 py-0.5 text-[11px] font-medium border-border/60 bg-muted/30 text-muted-foreground hover:text-foreground hover:bg-muted/60"
                />
              ))}
            </div>
          )}

          {novel.synopsis && (
            <p
              className={cn(
                "text-xs sm:text-sm leading-relaxed text-muted-foreground transition-all",
                expanded ? "line-clamp-none" : "line-clamp-2 sm:line-clamp-3",
              )}
            >
              {novel.synopsis}
            </p>
          )}

          {/* ponytail: boolean toggle clamp; upgrade to auto-measuring overflow and height animation when design spec requires it */}
          <div className="flex items-center justify-between pt-0.5">
            {novel.synopsis ? (
              <button
                type="button"
                onClick={() => setExpanded((prev) => !prev)}
                className="cursor-pointer text-xs font-semibold text-foreground underline underline-offset-4 hover:text-foreground/80 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
              >
                {expanded ? "Show less" : "Show more"}
              </button>
            ) : (
              <span />
            )}
            <Link
              href={publicNovelHref(novel.slug)}
              className="group/details inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground hover:underline underline-offset-4 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              <span>Novel Details</span>
              <ChevronRight
                className="h-3.5 w-3.5 transition-transform duration-150 group-hover/details:translate-x-0.5 motion-reduce:transition-none"
                aria-hidden="true"
              />
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "group flex h-full flex-col overflow-hidden rounded-lg",
        CARD_SURFACE,
        CARD_LIFT,
      )}
    >
      {/* Title and metadata - primary click target */}
      <Link
        href={publicNovelHref(novel.slug)}
        className="flex min-w-0 flex-1 flex-col"
      >
        <div className="relative aspect-2/3 shrink-0 overflow-hidden bg-muted">
          {novel.cover_url ? (
            <CoverImage
              coverUrl={novel.cover_url}
              title={title}
              genres={genres}
              language={novel.language}
              sourceTitle={sourceTitle}
              status={novel.publication_status}
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

        <div className="flex min-w-0 flex-1 flex-col justify-between p-4">
          <div>
            <h2 className="line-clamp-2 font-literary text-base font-semibold leading-snug transition-colors duration-200 group-hover:text-accent motion-reduce:transition-none">
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
                  <GenreChip
                    key={genre.slug}
                    label={genre.name_en ?? genre.slug}
                    labelJa={genre.name_ja}
                  />
                ))}
                {genres.length > MAX_VISIBLE_GENRES && (
                  <span className="text-xs text-muted-foreground">
                    +{genres.length - MAX_VISIBLE_GENRES}
                  </span>
                )}
                {tags.slice(0, MAX_VISIBLE_TAGS).map((tag) => (
                  <TagChip
                    key={tag.name}
                    label={tag.name}
                    labelJa={tag.name_ja}
                  />
                ))}
                {tags.length > MAX_VISIBLE_TAGS && (
                  <span className="text-xs text-muted-foreground">
                    +{tags.length - MAX_VISIBLE_TAGS}
                  </span>
                )}
              </div>
            )}
          </div>

          <span className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary transition-colors duration-200 group-hover:text-accent motion-reduce:transition-none">
            <BookOpen className="h-3.5 w-3.5" />
            View details
          </span>
        </div>
      </Link>

      {/* Save button - must not be inside the Link to avoid nested interactive elements. */}
      <div
        className="mt-auto border-t border-border/40 p-4"
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
