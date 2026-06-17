"use client";

import Link from "next/link";
import { ArrowRight, BookOpen } from "lucide-react";

import { GenreChip } from "@/components/public/genre-chip";
import { LatestUpdateRow } from "@/components/public/latest-update-row";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { NovelCard } from "@/components/public/novel-card";
import { SectionHeader } from "@/components/public/section-header";
import { useCatalog } from "@/hooks/public";

export default function HomePage() {
  const { data, isPending, isError } = useCatalog({
    sort_by: "added_at",
    order: "desc",
    page_size: 8,
  });

  const novels = data?.novels ?? [];
  const featuredNovel = novels[0];

  // ── Loading ──
  if (isPending) {
    return (
      <main>
        <section
          className="relative isolate min-h-[85vh] overflow-hidden"
          aria-label="Featured Dokushodo novel"
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
      </main>
    );
  }

  // ── Error ──
  if (isError) {
    return (
      <main>
        <div className="mx-auto max-w-7xl px-4 py-24 text-center sm:px-6 lg:px-8">
          <BookOpen className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-4 text-sm text-muted-foreground">
            Catalog temporarily unavailable. Please try again later.
          </p>
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
          <p className="mt-4 text-sm text-muted-foreground">
            No novels yet. Check back soon.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main>
      {/* ── Hero ── */}
      <section
        className="relative isolate min-h-[85vh] overflow-hidden"
        aria-label="Featured Dokushodo novel"
      >
        {featuredNovel && (
          <>
            <div
              className="absolute inset-0 -z-30 bg-cover bg-center opacity-35 dark:opacity-25"
              style={{
                backgroundImage:
                  "url('https://images.unsplash.com/photo-1771893327514-842e33b8bf85?w=1600&h=900&fit=crop&auto=format')",
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
                <span className="font-metadata text-xs uppercase tracking-[0.2em] text-accent">
                  Latest Release
                </span>

                <h1 className="mt-5 max-w-2xl font-literary text-5xl font-medium leading-tight tracking-normal text-foreground md:text-7xl">
                  {featuredNovel.title}
                </h1>

                <NovelMetadataRow
                  className="mt-5"
                  chapterCount={featuredNovel.chapter_count}
                  translatedCount={featuredNovel.translated_count}
                  source={featuredNovel.language}
                  status={featuredNovel.status}
                />

                {featuredNovel.genres && featuredNovel.genres.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    {featuredNovel.genres.map((genre) => (
                      <GenreChip key={genre} label={genre} />
                    ))}
                  </div>
                )}

                <div className="mt-8 flex flex-wrap gap-3">
                  <Link
                    href={`/novel/${featuredNovel.slug}`}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                  >
                    <BookOpen className="h-4 w-4" />
                    Start Reading
                  </Link>
                  <Link
                    href={`/novel/${featuredNovel.slug}`}
                    className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-accent/40 bg-background/70 px-5 text-sm font-medium text-accent backdrop-blur transition-colors hover:bg-accent/10"
                  >
                    View Details
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </div>
              </div>

              <div
                className="pointer-events-none absolute right-10 top-1/2 hidden -translate-y-1/2 font-literary text-6xl text-foreground/10 [writing-mode:vertical-rl] xl:block"
                aria-hidden="true"
              >
                Stories from another world
              </div>
            </div>
          </>
        )}
      </section>

      {/* ── Latest Updates ── */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <section className="py-14">
          <SectionHeader
            title="Latest Updates"
            actionHref="/browse-novels"
            actionLabel="View all"
          />
          <div className="mt-4 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {novels.slice(0, 6).map((novel) => (
              <LatestUpdateRow
                key={novel.novel_id}
                href={`/novel/${novel.slug}`}
                title={novel.title || novel.slug}
                chapterLabel={
                  novel.translated_count > 0
                    ? `Chapter ${novel.translated_count} translated`
                    : undefined
                }
                updatedAt={novel.added_at}
                sourceTitle={
                  novel.title !== novel.slug ? novel.title : undefined
                }
              />
            ))}
          </div>
        </section>

        {/* ── Latest Novels ── */}
        <section className="mb-12">
          <SectionHeader
            title="Latest Novels"
            description="Recently added works from the catalog."
            actionHref="/browse-novels"
            actionLabel="Browse all"
          />
          <div className="mt-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {novels.map((novel) => (
              <NovelCard key={novel.novel_id} novel={novel} />
            ))}
          </div>
        </section>

        {/* ── Browse the library ── */}
        <section className="mb-16">
          <SectionHeader
            title="Browse the library"
            description="The full catalog is available with search, filter, and sort."
            actionHref="/browse-novels"
            actionLabel="Browse novels"
          />
          <div className="mt-6 flex flex-col items-center justify-center rounded-lg bg-card/70 px-4 py-14 text-center ring-1 ring-border">
            <BookOpen className="mb-4 h-10 w-10 text-muted-foreground/50" />
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              Ranking data is not live yet. All available novels can be found in the catalog.
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
