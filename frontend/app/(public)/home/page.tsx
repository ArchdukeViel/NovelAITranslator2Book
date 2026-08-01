"use client";

import Link from "next/link";
import {
  BookOpen,
  Compass,
  Shuffle,
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
        <FallbackCover
          title={novel.title}
          sourceTitle={novel.source_title}
          language={novel.language}
          status={novel.publication_status}
          genres={novel.genres}
          className="rounded-md"
        />
        <h3 className="mt-3 line-clamp-2 font-literary text-sm font-semibold group-hover:text-accent">
          {novel.title}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
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
          className="relative isolate min-h-[85vh] overflow-hidden border-b border-border/80"
          aria-label="Loading featured novel"
        >
          <div className="mx-auto flex min-h-[85vh] max-w-7xl items-end px-4 pb-14 pt-24 sm:px-6 lg:px-8 lg:pb-20">
            <div className="max-w-3xl">
              <div className="h-8 w-48 animate-pulse rounded bg-muted" />
              <div className="mt-5 h-14 w-3/4 animate-pulse rounded bg-muted" />
              <div className="mt-5 h-5 w-64 animate-pulse rounded bg-muted" />
              <div className="mt-8 flex gap-3">
                <div className="h-11 w-36 animate-pulse rounded-md bg-muted" />
                <div className="h-11 w-36 animate-pulse rounded-md bg-muted" />
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <section className="py-14">
            <div className="h-6 w-40 animate-pulse rounded bg-muted" />
            <div className="mt-6 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 rounded-lg bg-muted/60 p-3"
                >
                  <div className="h-10 w-10 shrink-0 animate-pulse rounded bg-muted" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
                    <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="mb-16">
            <div className="flex flex-col items-center justify-center rounded-lg bg-card/70 px-4 py-14 text-center ring-1 ring-border">
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
          <p className="mt-4 text-sm font-medium text-foreground">
            Could not load the catalog
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Something went wrong fetching novels. This is usually temporary.
          </p>
          <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => refetch()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
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
          <p className="mt-4 text-sm font-medium text-foreground">
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
      {/* ── Hero ── */}
      {spotlightNovel && (
        <section
          className="relative isolate min-h-[85vh] overflow-hidden border-b border-border/80"
          aria-label="Dokushodo spotlight novel"
        >
          <>
            <div
              className="absolute inset-0 -z-30 bg-cover bg-center opacity-55 dark:opacity-45"
              style={{
                backgroundImage:
                  "url('/assets/dokushodo/home/hero-torii-forest.png')",
              }}
              aria-hidden="true"
            />
            <div
              className="absolute inset-0 -z-[25] bg-cover bg-center opacity-[0.08] mix-blend-screen"
              style={{
                backgroundImage:
                  "url('/assets/dokushodo/texture/charcoal-washi.png')",
              }}
              aria-hidden="true"
            />
            <div
              className="absolute inset-0 -z-20 bg-gradient-to-t from-background via-background/80 to-background/20"
              aria-hidden="true"
            />
            <div
              className="absolute inset-0 -z-10 bg-gradient-to-r from-background via-background/75 to-transparent"
              aria-hidden="true"
            />

            <div className="mx-auto flex min-h-[85vh] max-w-7xl items-end px-4 pb-14 pt-24 sm:px-6 lg:px-8 lg:pb-20">
              <div className="max-w-3xl">
                <span className="font-metadata text-xs uppercase tracking-[0.2em] text-accent drop-shadow">
                  Spotlight
                </span>

                <h1 className="mt-5 max-w-2xl font-literary text-4xl font-semibold leading-tight tracking-normal text-foreground drop-shadow md:text-6xl">
                  {spotlightNovel.title}
                </h1>

                {heroSourceTitle && (
                  <p className="mt-3 max-w-2xl font-literary text-base text-accent drop-shadow">
                    {heroSourceTitle}
                  </p>
                )}

                <NovelMetadataRow
                  className="mt-5"
                  chapterCount={spotlightNovel.chapter_count}
                  translatedCount={spotlightNovel.translated_count}
                  source={spotlightNovel.language}
                  status={spotlightNovel.publication_status}
                />

                <p className="mt-5 max-w-2xl line-clamp-3 text-sm leading-6 text-foreground/80 drop-shadow md:text-base md:leading-7">
                  {heroSynopsis ?? "Synopsis unavailable for this novel."}
                </p>

{spotlightNovel.genres && spotlightNovel.genres.length > 0 && (
                   <div className="mt-5 flex flex-wrap gap-2">
                     {spotlightNovel.genres.map((genre) => (
                       <GenreChip key={genre.slug} label={genreLabels?.get(genre.slug) ?? genre.slug} />
                     ))}
                   </div>
                 )}

                {!heroReadableHref && (
                  <p className="mt-6 text-sm font-medium text-foreground/70">
                    No translated chapters yet.
                  </p>
                )}

                <div className="mt-8 flex flex-wrap gap-3">
                  {heroReadableHref && (
                    <Link
                      href={heroReadableHref}
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-sm bg-primary px-5 font-metadata text-xs font-medium uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary/90"
                    >
                      <BookOpen className="h-4 w-4" />
                      Start Reading
                    </Link>
                  )}
                </div>
              </div>

              <div
                className="pointer-events-none absolute right-12 top-1/2 hidden -translate-y-1/2 border-l border-border/60 pl-8 font-literary text-4xl leading-loose text-accent/45 [writing-mode:vertical-rl] xl:block"
                aria-hidden="true"
              >
                異世界の物語
              </div>
            </div>
          </>
        </section>
      )}

      <div className="mx-auto max-w-7xl space-y-14 px-4 py-14 sm:px-6 lg:px-8">
        {isAuthenticated ? (
          continueNovels.length > 0 && (
            <NovelRail title="Continue Reading" ariaLabel="Continue reading" seeAllHref="/account/history">
              {continueNovels.map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
            </NovelRail>
          )
        ) : (
          <section aria-label="Continue reading" className="rounded-lg border border-border bg-card/60 p-6">
            <h2 className="font-literary text-xl font-semibold">Continue Reading</h2>
            <p className="mt-2 text-sm text-muted-foreground">Sign in to pick up where you left off.</p>
            <Link href="/login?mode=signin" className="mt-4 inline-flex text-sm font-medium text-primary">Sign in</Link>
          </section>
        )}

        <NovelRail title="New Releases" ariaLabel="New releases" seeAllHref="/browse-novels?sort_by=added_at&order=desc">
          {novels.slice(0, 12).map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
        </NovelRail>

        <NovelRail title="Recently Updated" ariaLabel="Recently updated" seeAllHref="/browse-novels?sort_by=updated_at&order=desc">
          {recentlyUpdated.slice(0, 12).map((novel) => <RailCard key={novel.novel_id} novel={novel} />)}
        </NovelRail>

        {topGenres.map(([slug, genre]) => (
          <NovelRail key={slug} title={genre.label} ariaLabel={`${genre.label} novels`} seeAllHref={`/genres/${encodeURIComponent(slug)}`}>
            {novels.filter((novel) => novel.genres?.some((item) => item.slug === slug)).slice(0, 12).map((novel) => (
              <RailCard key={novel.novel_id} novel={novel} />
            ))}
          </NovelRail>
        ))}

        <Link href="/random" className="flex w-44 flex-col items-center justify-center rounded-lg border border-border bg-card/60 px-5 py-10 text-center hover:border-primary/40">
          <Shuffle className="h-8 w-8 text-primary" />
          <span className="mt-4 font-literary font-semibold">Surprise Me</span>
          <span className="mt-1 text-xs text-muted-foreground">Open a random novel</span>
        </Link>
      </div>
    </main>
  );
}
