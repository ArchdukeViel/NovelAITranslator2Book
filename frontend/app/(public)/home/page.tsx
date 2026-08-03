"use client";

import Link from "next/link";
import {
  BookOpen,
  Compass,
  Shuffle,
  Sparkles,
  ArrowRight,
  Bookmark,
  Clock,
  ChevronRight,
} from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip } from "@/components/public/genre-chip";
import { NovelRail } from "@/components/public/novel-rail";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { useCatalog, useGenreLabelMap, useHistory, usePublicAuth } from "@/hooks/public";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
import type { PublicNovelSummary } from "@/lib/public-types";

function usefulSourceTitle(sourceTitle: string | null | undefined, title: string): string | null {
  const trimmed = sourceTitle?.trim();
  if (!trimmed || trimmed === title.trim()) {
    return null;
  }
  return trimmed;
}

function synopsisPreview(synopsis: string | null | undefined): string | null {
  const trimmed = synopsis?.trim();
  return trimmed || null;
}

function latestActivityAt(novel: PublicNovelSummary): string | null | undefined {
  return novel.latest_chapter_updated_at ?? novel.added_at;
}

function readableChapterHref(novel: PublicNovelSummary): string | null {
  const latestChapterId = novel.latest_chapter_id?.trim();
  if (latestChapterId) {
    return publicChapterHref(novel.slug, latestChapterId);
  }
  return null;
}

function RailCard({ novel }: { novel: PublicNovelSummary }) {
  return (
    <article role="listitem" className="w-44 shrink-0 snap-start">
      <Link href={publicNovelHref(novel.slug)} className="group block">
        <div className="relative overflow-hidden rounded-lg transition-transform duration-300 ease-out group-hover:-translate-y-1 group-hover:shadow-md">
          <FallbackCover
            title={novel.title}
            sourceTitle={novel.source_title}
            language={novel.language}
            status={novel.publication_status}
            genres={novel.genres}
            className="rounded-lg"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        </div>
        <h3 className="mt-3 line-clamp-2 font-literary text-sm font-semibold leading-snug transition-colors group-hover:text-accent">
          {novel.title}
        </h3>
        <p className="mt-1 font-metadata text-xs text-muted-foreground">
          {novel.translated_count > 0 ? `${novel.translated_count} translated` : "Translation pending"}
        </p>
      </Link>
    </article>
  );
}

export default function HomePage() {
  const { data, isPending, isError, refetch } = useCatalog({
    sort_by: "added_at",
    order: "desc",
    // ponytail: one public catalog page supports up to 100 summaries. Add a
    // bulk-by-slug/history endpoint when libraries routinely exceed this.
    page_size: 100,
  });

  const novels = data?.novels ?? [];
  const spotlightNovel = novels.find(
    (novel) => Boolean(synopsisPreview(novel.synopsis) && readableChapterHref(novel))
  );
  const genreLabels = useGenreLabelMap();
  const { isAuthenticated } = usePublicAuth();
  const heroSourceTitle = spotlightNovel
    ? usefulSourceTitle(spotlightNovel.source_title, spotlightNovel.title)
    : null;
  const heroSynopsis = synopsisPreview(spotlightNovel?.synopsis);
  const heroReadableHref = spotlightNovel ? readableChapterHref(spotlightNovel) : null;
  const history = useHistory({ limit: 12 });
  const continueNovels = isAuthenticated
    ? [...new Set((history.data?.items ?? []).map((item) => item.slug))]
        .map((slug) => novels.find((novel) => novel.slug === slug))
        .filter((novel): novel is PublicNovelSummary => Boolean(novel))
    : [];
  const recentlyUpdated = [...novels].sort((left, right) =>
    String(latestActivityAt(right) ?? "").localeCompare(String(latestActivityAt(left) ?? ""))
  );
  const genreCounts = new Map<string, { count: number; label: string }>();
  for (const novel of novels.filter((item) => item.translated_count > 0)) {
    for (const genre of novel.genres ?? []) {
      const current = genreCounts.get(genre.slug);
      genreCounts.set(genre.slug, {
        count: (current?.count ?? 0) + 1,
        label: genre.name_en ?? genre.name_ja ?? genre.slug,
      });
    }
  }
  const topGenres = [...genreCounts.entries()]
    .sort((left, right) => right[1].count - left[1].count || left[0].localeCompare(right[0]))
    .slice(0, 2);

  // ── Loading ──
  if (isPending) {
    return (
      <main>
        <section
          className="relative isolate min-h-[80vh] overflow-hidden border-b border-border/80 bg-card/30"
          aria-label="Loading featured novel"
        >
          <div className="mx-auto flex min-h-[80vh] max-w-7xl items-end px-4 pb-14 pt-20 sm:px-6 lg:px-8 lg:pb-20">
            <div className="max-w-3xl space-y-4">
              <div className="h-6 w-32 animate-pulse rounded bg-muted" />
              <div className="h-12 w-3/4 animate-pulse rounded-lg bg-muted" />
              <div className="h-5 w-64 animate-pulse rounded bg-muted" />
              <div className="pt-4 flex gap-3">
                <div className="h-11 w-40 animate-pulse rounded-md bg-muted" />
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-7xl space-y-12 px-4 py-14 sm:px-6 lg:px-8">
          <section className="py-6">
            <div className="h-6 w-40 animate-pulse rounded bg-muted" />
            <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3.5 rounded-lg border border-border/60 bg-card/60 p-4"
                >
                  <div className="h-12 w-12 shrink-0 animate-pulse rounded bg-muted" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
                    <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-16">
            <div className="flex flex-col items-center justify-center rounded-lg border border-border/80 bg-card/70 px-4 py-14 text-center">
              <div className="h-10 w-10 animate-pulse rounded-full bg-muted" />
              <div className="mt-4 h-4 w-64 animate-pulse rounded bg-muted" />
              <div className="mt-5 h-10 w-40 animate-pulse rounded-md bg-muted" />
            </div>
          </section>
        </div>

        <span className="sr-only" role="status">
          Loading catalog…
        </span>
      </main>
    );
  }

  // ── Error ──
  if (isError) {
    return (
      <main>
        <div className="mx-auto max-w-7xl px-4 py-24 text-center sm:px-6 lg:px-8">
          <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-4 text-base font-semibold text-foreground">
            Could not load the catalog
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Something went wrong fetching novels. This is usually temporary.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => refetch()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none"
            >
              Try again
            </button>
            <Link
              href="/browse-novels"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-accent/40 px-5 text-sm font-medium text-accent transition-colors hover:bg-accent/10"
            >
              <Compass className="h-4 w-4" />
              Browse the catalog
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // ── Empty ──
  if (novels.length === 0) {
    return (
      <main>
        <div className="mx-auto max-w-7xl px-4 py-24 text-center sm:px-6 lg:px-8">
          <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-4 text-base font-semibold text-foreground">
            No novels in the catalog yet
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            New translations are added regularly. You can also request a novel
            to be translated.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/request-novel"
              className="inline-flex h-11 items-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Request a novel
            </Link>
            <Link
              href="/browse-novels"
              className="inline-flex h-11 items-center gap-2 rounded-md border border-accent/40 px-5 text-sm font-medium text-accent transition-colors hover:bg-accent/10"
            >
              <Compass className="h-4 w-4" />
              Browse the catalog
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="bg-background">
      {/* ── Asymmetric Literary Hero ── */}
      {spotlightNovel && (
        <section
          className="relative isolate overflow-hidden border-b border-border/80 bg-card/40 py-12 sm:py-16 lg:py-20"
          aria-label="Dokushodo spotlight novel"
        >
          <div className="mx-auto grid max-w-7xl grid-cols-1 items-end px-4 sm:px-6 lg:grid-cols-12 lg:gap-12 lg:px-8">
            <div className="lg:col-span-8">
              <span className="font-metadata text-xs font-semibold uppercase text-accent">
                Spotlight
              </span>

              <h1 className="mt-2 font-literary text-3xl font-semibold leading-tight tracking-tight text-foreground sm:text-5xl lg:text-6xl">
                {spotlightNovel.title}
              </h1>

              {heroSourceTitle && (
                <p className="mt-2 font-literary text-base text-accent">
                  {heroSourceTitle}
                </p>
              )}

              <NovelMetadataRow
                className="mt-4"
                chapterCount={spotlightNovel.chapter_count}
                translatedCount={spotlightNovel.translated_count}
                source={spotlightNovel.language}
                status={spotlightNovel.publication_status}
              />

              <p className="mt-4 max-w-2xl line-clamp-3 text-sm leading-relaxed text-muted-foreground md:text-base">
                {heroSynopsis ?? "Synopsis unavailable for this novel."}
              </p>

              {spotlightNovel.genres && spotlightNovel.genres.length > 0 && (
                <div className="mt-4 flex flex-wrap gap-2">
                  {spotlightNovel.genres.map((genre) => (
                    <GenreChip key={genre.slug} label={genreLabels?.get(genre.slug) ?? genre.slug} />
                  ))}
                </div>
              )}

              {!heroReadableHref && (
                <p className="mt-5 text-sm font-medium text-muted-foreground">
                  No translated chapters yet.
                </p>
              )}

              <div className="mt-7 flex flex-wrap items-center gap-4">
                {heroReadableHref && (
                  <Link
                    href={heroReadableHref}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
                  >
                    <BookOpen className="h-4 w-4" />
                    Start Reading
                  </Link>
                )}
                <Link
                  href={publicNovelHref(spotlightNovel.slug)}
                  className="inline-flex h-11 items-center justify-center gap-1.5 rounded-md border border-border bg-card px-5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  Novel details
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </Link>
              </div>
            </div>

            {/* Asymmetric Spotlight Cover Card */}
            <div className="hidden lg:col-span-4 lg:flex lg:justify-end">
              <div className="group relative w-64 overflow-hidden rounded-lg border border-border/80 bg-card p-3 shadow-md transition-transform duration-300 hover:-translate-y-1">
                <FallbackCover
                  title={spotlightNovel.title}
                  sourceTitle={spotlightNovel.source_title}
                  language={spotlightNovel.language}
                  status={spotlightNovel.publication_status}
                  genres={spotlightNovel.genres}
                  className="rounded-md shadow-sm"
                />
                <div className="mt-3 space-y-1 px-1">
                  <p className="line-clamp-1 font-literary text-xs font-semibold text-foreground">
                    {spotlightNovel.title}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ── Catalog Sections & Bento Layout ── */}
      <div className="mx-auto max-w-7xl space-y-16 px-4 py-14 sm:px-6 lg:px-8">
        {/* Continue Reading Section */}
        {isAuthenticated ? (
          continueNovels.length > 0 && (
            <NovelRail title="Continue Reading" ariaLabel="Continue reading" seeAllHref="/account/history">
              {continueNovels.map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
            </NovelRail>
          )
        ) : (
          <section aria-label="Continue reading" className="rounded-lg border border-border/80 bg-card p-6 shadow-sm sm:p-8">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Bookmark className="h-4 w-4 text-primary" />
                  <h2 className="font-literary text-xl font-semibold text-foreground">Continue Reading</h2>
                </div>
                <p className="text-sm text-muted-foreground">Sign in to pick up where you left off across all your devices.</p>
              </div>
              <Link
                href="/login?mode=signin"
                className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90"
              >
                Sign in
              </Link>
            </div>
          </section>
        )}

        {/* Bento Grid Spotlight + Rails */}
        <section aria-label="Catalog highlights" className="grid gap-6 md:grid-cols-12">
          {/* Main Rail Span */}
          <div className="md:col-span-12">
            <NovelRail title="New Releases" ariaLabel="New releases" seeAllHref="/browse-novels?sort_by=added_at&order=desc">
              {novels.slice(0, 12).map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
            </NovelRail>
          </div>
        </section>

        {/* Recently Updated Rail */}
        <NovelRail title="Recently Updated" ariaLabel="Recently updated" seeAllHref="/browse-novels?sort_by=updated_at&order=desc">
          {recentlyUpdated.slice(0, 12).map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
        </NovelRail>

        {/* Genre Curations */}
        {topGenres.map(([slug, genre]) => (
          <NovelRail key={slug} title={genre.label} ariaLabel={`${genre.label} novels`} seeAllHref={`/genres/${encodeURIComponent(slug)}`}>
            {novels.filter((novel) => novel.genres?.some((item) => item.slug === slug)).slice(0, 12).map((novel) => (
              <RailCard key={novel.novel_id} novel={novel} />
            ))}
          </NovelRail>
        ))}

        {/* Asymmetric Surprise Me Callout */}
        <section aria-label="Discovery" className="rounded-xl border border-border/80 bg-card p-6 shadow-sm sm:p-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
            <div className="space-y-2">
              <div className="inline-flex items-center gap-1.5 text-xs font-medium text-accent">
                <Clock className="h-3.5 w-3.5" />
                <span className="font-metadata uppercase tracking-wider">Unplanned Journey</span>
              </div>
              <h2 className="font-literary text-2xl font-semibold text-foreground">Looking for something unexpected?</h2>
              <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                Let chance decide your next story. Jump directly into a random novel from our translated library.
              </p>
            </div>
            <Link
              href="/random"
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2.5 rounded-md border border-primary/30 bg-primary/10 px-6 font-medium text-primary shadow-sm transition-all hover:bg-primary hover:text-primary-foreground"
            >
              <Shuffle className="h-4 w-4" />
              <span>Surprise Me</span>
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
