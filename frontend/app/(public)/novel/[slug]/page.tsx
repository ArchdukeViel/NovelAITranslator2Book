"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CalendarDays,
  Clock,
  Flag,
  Library,
} from "lucide-react";

import { ContinueReading } from "@/components/public/continue-reading";
import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip, TagChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { RatingReview } from "@/components/public/rating-review";
import { RequestControl } from "@/components/public/request-control";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { SectionHeader } from "@/components/public/section-header";
import { StatusBadge } from "@/components/public/status-badge";
import { ApiError } from "@/lib/api";
import {
  authorOrFallback,
  sortChaptersAscending,
} from "@/lib/public-format";
import type { PublicChapterSummary } from "@/lib/public-types";
import { useChapters, useGenreLabelMap, useNovel, usePublicAuth } from "@/hooks/public";

function chapterDisplayTitle(chapter: PublicChapterSummary): string {
  return (
    chapter.title ||
    `Chapter ${chapter.chapter_number ?? chapter.chapter_id}`
  );
}

function formatAddedDate(value: string): string {
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

function chapterHref(slug: string, chapterId: string): string {
  return `/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapterId)}`;
}

function LoadingState() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />
      <div className="mt-10 grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)]">
        <div className="aspect-[2/3] animate-pulse rounded-lg bg-muted" />
        <div className="space-y-5">
          <div className="h-5 w-32 animate-pulse rounded bg-muted" />
          <div className="h-12 w-3/4 animate-pulse rounded bg-muted" />
          <div className="h-4 w-1/2 animate-pulse rounded bg-muted" />
          <div className="h-24 w-full animate-pulse rounded bg-muted" />
        </div>
      </div>
    </main>
  );
}

function BackToBrowse() {
  return (
    <Link
      className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      href="/browse-novels"
    >
      <ArrowLeft className="h-4 w-4" />
      Back to Browse
    </Link>
  );
}

function ErrorState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />
      <div className="mt-12 max-w-xl">
        <h1 className="font-literary text-3xl font-medium tracking-normal">
          {title}
        </h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          {description}
        </p>
      </div>
    </main>
  );
}

function ChapterRow({
  chapter,
  slug,
}: {
  chapter: PublicChapterSummary;
  slug: string;
}) {
  return (
    <div className="group flex flex-col gap-3 border-b border-border/70 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <h3 className="truncate font-literary text-base font-medium transition-colors group-hover:text-accent">
          {chapterDisplayTitle(chapter)}
        </h3>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {chapter.chapter_number !== null && (
            <span className="font-metadata">Chapter {chapter.chapter_number}</span>
          )}
          {chapter.translated ? (
            <span className="font-metadata text-accent">Translated</span>
          ) : (
            <StatusBadge status="Pending" />
          )}
        </div>
      </div>
      {chapter.translated ? (
        <Link
          className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium transition-colors hover:bg-muted"
          href={chapterHref(slug, chapter.chapter_id)}
        >
          <BookOpen className="h-4 w-4" />
          Read
        </Link>
      ) : (
        <span className="inline-flex h-9 shrink-0 items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />
          Not translated
        </span>
      )}
    </div>
  );
}

export default function NovelDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug);
  const { isAuthenticated, isPending: authPending } = usePublicAuth();

  const novel = useNovel(slug);
  const chapters = useChapters(slug);
  const genreLabels = useGenreLabelMap();

  if (novel.isError) {
    const err = novel.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <ErrorState
          title="Novel not found"
          description="The novel you're looking for doesn't exist or has been removed."
        />
      );
    }

    return (
      <ErrorState
        title="Something went wrong"
        description="Could not load this novel. Try browsing the catalog or check back later."
      />
    );
  }

  if (novel.isPending) {
    return <LoadingState />;
  }

  const data = novel.data;
  const title = data.title || slug;
  const synopsis = data.synopsis?.trim();
  const sourceTitle = data.source_title?.trim();
  const showSourceTitle = Boolean(sourceTitle && sourceTitle !== title);
  const sortedChapters = chapters.data
    ? sortChaptersAscending(chapters.data)
    : [];
  const translatedChapters = sortedChapters.filter((chapter) => chapter.translated);
  const firstTranslatedChapter = translatedChapters[0] ?? null;
  const latestTranslatedChapter =
    translatedChapters[translatedChapters.length - 1] ?? null;
  const firstChapterId = firstTranslatedChapter?.chapter_id ?? null;

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />

      <section className="relative mt-8 overflow-hidden rounded-lg bg-card/60 p-5 shadow-sm ring-1 ring-border sm:p-6 lg:p-8">
        <div
          className="absolute inset-x-0 top-0 -z-10 h-40 bg-gradient-to-b from-secondary to-transparent"
          aria-hidden="true"
        />
        <div className="grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start">
          <div className="mx-auto w-full max-w-[260px] lg:mx-0">
            <FallbackCover
              genres={data.genres}
              language={data.language}
              sourceTitle={sourceTitle}
              status={data.status}
              title={title}
            />
          </div>

          <div className="min-w-0">
            <p className="font-metadata text-xs uppercase tracking-[0.22em] text-accent">
              Story Detail
            </p>
            <h1 className="mt-3 max-w-4xl font-literary text-4xl font-medium leading-tight tracking-normal text-foreground md:text-5xl">
              {title}
            </h1>
            <p className="mt-3 text-base text-muted-foreground">
              {authorOrFallback(data.author)}
            </p>
            {showSourceTitle && (
              <p className="mt-2 text-sm text-muted-foreground">
                <span className="font-metadata text-xs uppercase tracking-[0.14em] text-accent">
                  Source title
                </span>{" "}
                <span className="font-literary text-foreground">
                  {sourceTitle}
                </span>
              </p>
            )}

            <NovelMetadataRow
              className="mt-5"
              chapterCount={data.chapter_count}
              translatedCount={data.translated_count}
              source={data.language}
              status={data.status}
            />

            {data.added_at && (
              <p className="mt-3 flex items-center gap-1.5 font-metadata text-xs text-muted-foreground">
                <CalendarDays className="h-3.5 w-3.5" />
                Added {formatAddedDate(data.added_at)}
              </p>
            )}

            {(data.genres?.length ?? 0) > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {(data.genres ?? []).map((genre) => (
                  <Link
                    key={genre}
                    href={`/browse-novels?genre_include=${encodeURIComponent(genre)}`}
                  >
                    <GenreChip label={genreLabels?.get(genre) ?? genre} className="hover:bg-accent/15 transition-colors" />
                  </Link>
                ))}
              </div>
            )}

            {(data.tags?.length ?? 0) > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {(data.tags ?? []).map((tag) => (
                  <Link
                    key={tag}
                    href={`/browse-novels?tag_include=${encodeURIComponent(tag)}`}
                  >
                    <TagChip label={tag} className="hover:bg-accent/15 transition-colors" />
                  </Link>
                ))}
              </div>
            )}

            <div className="mt-7 flex flex-wrap gap-3">
              {firstTranslatedChapter && (
                <Link
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                  href={chapterHref(slug, firstTranslatedChapter.chapter_id)}
                >
                  <BookOpen className="h-4 w-4" />
                  Start Reading
                </Link>
              )}
              {latestTranslatedChapter &&
                latestTranslatedChapter.chapter_id !== firstChapterId && (
                  <Link
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-accent/40 bg-background/70 px-5 text-sm font-medium text-accent transition-colors hover:bg-accent/10"
                    href={chapterHref(slug, latestTranslatedChapter.chapter_id)}
                  >
                    Latest Chapter
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                )}
              {!firstTranslatedChapter && (
                <span className="inline-flex h-11 items-center text-sm text-muted-foreground">
                  No translated chapters available yet.
                </span>
              )}
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              {!authPending && isAuthenticated && (
                <>
                  <SaveToLibrary slug={slug} />
                  <ContinueReading slug={slug} firstChapterId={firstChapterId} />
                </>
              )}
              {!authPending && !isAuthenticated && <SaveToLibrary slug={slug} />}
              {authPending && (
                <span className="inline-flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-foreground" />
                  Checking session
                </span>
              )}
            </div>
          </div>
        </div>
      </section>

      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-12">
          <section>
            <SectionHeader
              eyebrow="Synopsis"
              title="About this story"
              description={synopsis || "Synopsis unavailable for this novel."}
            />
          </section>

          <section>
            <SectionHeader
              eyebrow="Chapters"
              title={`Chapter List (${sortedChapters.length})`}
              description={`${sortedChapters.length} chapter${sortedChapters.length !== 1 ? "s" : ""} total. Translated chapters link to the reader; pending chapters are listed for reference.`}
            />
            <div className="mt-5 rounded-lg bg-card/70 px-4 ring-1 ring-border sm:px-5">
              {chapters.isPending ? (
                <div className="flex justify-center py-10">
                  <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-foreground" />
                </div>
              ) : chapters.isError ? (
                <div className="py-10 text-center text-sm text-muted-foreground">
                  Could not load chapters.
                </div>
              ) : sortedChapters.length === 0 ? (
                <div className="py-10 text-center">
                  <Library className="mx-auto h-10 w-10 text-muted-foreground/50" />
                  <p className="mt-3 text-sm text-muted-foreground">
                    No chapters available yet.
                  </p>
                </div>
              ) : (
                sortedChapters.map((chapter) => (
                  <ChapterRow
                    chapter={chapter}
                    key={chapter.chapter_id}
                    slug={slug}
                  />
                ))
              )}
            </div>
          </section>
        </div>

        <aside className="space-y-5 lg:sticky lg:top-24 lg:self-start">
          <section className="rounded-lg bg-card/70 p-4 ring-1 ring-border">
            <div className="flex items-start gap-3">
              <Flag className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <h2 className="text-sm font-medium">Report an issue</h2>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  Found a problem with this novel?{" "}
                  <Link
                    href="/contact"
                    className="text-accent underline transition-colors hover:text-foreground"
                  >
                    Contact us
                  </Link>{" "}
                  to report it.
                </p>
              </div>
            </div>
          </section>

          <RatingReview slug={slug} />
          <RequestControl slug={slug} />
        </aside>
      </div>
    </main>
  );
}
