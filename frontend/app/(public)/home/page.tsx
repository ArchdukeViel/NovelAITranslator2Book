"use client";

import Link from "next/link";
import { ArrowRight, BookOpen, Clock, Compass, FileText, Library, LogIn } from "lucide-react";

import { GenreChip } from "@/components/public/genre-chip";
import { LatestUpdateRow } from "@/components/public/latest-update-row";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { SectionHeader } from "@/components/public/section-header";
import { groupDateLabel } from "@/lib/date-group";
import { useCatalog, useGenreLabelMap, usePublicAuth } from "@/hooks/public";
import type { PublicNovelSummary } from "@/lib/public-types";

const LATEST_UPDATE_GROUP_ORDER = [
  "Today",
  "Yesterday",
  "1 week ago",
  "2 weeks ago",
  "3 weeks ago",
  "1 month ago",
  "2 months ago",
  "3 months ago",
  "Earlier",
] as const;

function latestUpdateGroupRank(label: string): number {
  const index = LATEST_UPDATE_GROUP_ORDER.indexOf(
    label as (typeof LATEST_UPDATE_GROUP_ORDER)[number]
  );
  return index === -1 ? LATEST_UPDATE_GROUP_ORDER.length : index;
}

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

function latestChapterHref(novel: PublicNovelSummary): string {
  if (novel.latest_chapter_id) {
    return `/novel/${novel.slug}/chapter/${encodeURIComponent(novel.latest_chapter_id)}`;
  }
  return `/novel/${novel.slug}`;
}

export default function HomePage() {
  const { data, isPending, isError, refetch } = useCatalog({
    sort_by: "added_at",
    order: "desc",
    page_size: 8,
  });

  const novels = data?.novels ?? [];
  const featuredNovel = novels[0];
  const genreLabels = useGenreLabelMap();
  const { isAuthenticated } = usePublicAuth();
  const heroSourceTitle = featuredNovel
    ? usefulSourceTitle(featuredNovel.source_title, featuredNovel.title)
    : null;
  const heroSynopsis = synopsisPreview(featuredNovel?.synopsis);

  // ── Loading ──
  if (isPending) {
    return (
      <main>
        <section
          className="relative isolate min-h-[85vh] overflow-hidden"
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
                  Featured
                </span>

                <h1 className="mt-5 max-w-2xl font-literary text-5xl font-medium leading-tight tracking-normal text-foreground md:text-7xl">
                  {featuredNovel.title}
                </h1>

                {heroSourceTitle && (
                  <p className="mt-3 max-w-2xl font-literary text-base text-accent">
                    {heroSourceTitle}
                  </p>
                )}

                <NovelMetadataRow
                  className="mt-5"
                  chapterCount={featuredNovel.chapter_count}
                  translatedCount={featuredNovel.translated_count}
                  source={featuredNovel.language}
                  status={featuredNovel.status}
                />

                <p className="mt-5 max-w-2xl line-clamp-3 text-sm leading-6 text-muted-foreground md:text-base md:leading-7">
                  {heroSynopsis ?? "Synopsis unavailable for this novel."}
                </p>

                {featuredNovel.genres && featuredNovel.genres.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    {featuredNovel.genres.map((genre) => (
                      <GenreChip key={genre} label={genreLabels?.get(genre) ?? genre} />
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

      {/* ── Recently Added (compact rows) ── */}
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <section className="py-14">
          <SectionHeader
            title="Recently Added"
            description="New novels added to the catalog."
            actionHref="/browse-novels"
            actionLabel="View all"
          />
          {(() => {
            // Group novels by their date label (Today, Yesterday, etc.)
            const grouped = new Map<string, typeof novels>();
            const groupOrder: string[] = [];

            for (const novel of novels.slice(0, 8)) {
              const label = groupDateLabel(latestActivityAt(novel)) ?? "Earlier";
              if (!grouped.has(label)) {
                grouped.set(label, []);
                groupOrder.push(label);
              }
              grouped.get(label)!.push(novel);
            }

            return groupOrder
              .sort((left, right) => latestUpdateGroupRank(left) - latestUpdateGroupRank(right))
              .map((label) => (
                <div key={label} className="mt-6 first:mt-4">
                  <h3 className="font-metadata text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {label}
                  </h3>
                  <div className="mt-2 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                    {grouped.get(label)!.map((novel) => (
                      <LatestUpdateRow
                        key={novel.novel_id}
                        href={latestChapterHref(novel)}
                        title={novel.title}
                        chapterLabel={
                          novel.translated_count > 0
                            ? `Chapter ${novel.translated_count} translated`
                            : undefined
                        }
                        latestChapterNumber={novel.latest_chapter_number}
                        latestChapterTitle={novel.latest_chapter_title}
                        updatedAt={latestActivityAt(novel)}
                        sourceTitle={novel.source_title ?? undefined}
                      />
                    ))}
                  </div>
                </div>
              ));
          })()}
        </section>

        {/* ── Reader utility links ── */}
        <section className="mb-12 grid gap-4 md:grid-cols-2">
          <div className="rounded-lg border border-border bg-card/70 p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                <FileText className="h-5 w-5" />
              </span>
              <div>
                <h2 className="font-literary text-lg font-semibold">Request a novel</h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Send a supported source URL for review when a novel is not in the catalog yet.
                </p>
                <Link
                  href="/request-novel"
                  className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-accent transition-colors hover:text-foreground"
                >
                  Open request form
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card/70 p-5">
            {isAuthenticated ? (
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                  <Library className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="font-literary text-lg font-semibold">Your reading shelf</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Return to saved novels or check the chapters you opened recently.
                  </p>
                  <div className="mt-4 flex flex-wrap gap-3">
                    <Link
                      href="/account/library"
                      className="inline-flex items-center gap-2 text-sm font-medium text-accent transition-colors hover:text-foreground"
                    >
                      Open library
                      <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                    <Link
                      href="/account/history"
                      className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                    >
                      <Clock className="h-3.5 w-3.5" />
                      Reading history
                    </Link>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-muted text-muted-foreground">
                  <LogIn className="h-5 w-5" />
                </span>
                <div>
                  <h2 className="font-literary text-lg font-semibold">Save your reading state</h2>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Sign in to keep a library, reading history, and chapter progress.
                  </p>
                  <Link
                    href="/login"
                    className="mt-4 inline-flex items-center gap-2 text-sm font-medium text-accent transition-colors hover:text-foreground"
                  >
                    Sign in
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ── Browse the catalog CTA ── */}
        <section className="mb-16">
          <div className="flex flex-col items-center justify-center rounded-lg bg-card/70 px-4 py-14 text-center ring-1 ring-border">
            <Compass className="mb-4 h-10 w-10 text-muted-foreground/50" />
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              Browse the full catalog of translated novels.
            </p>
            <Link
              href="/browse-novels"
              className="mt-5 inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Compass className="h-4 w-4" />
              Browse the catalog
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
}
