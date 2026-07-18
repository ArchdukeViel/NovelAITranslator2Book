"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  Bookmark,
  Compass,
  FileText,
  Library,
  LifeBuoy,
  Search,
} from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip } from "@/components/public/genre-chip";
import { LatestUpdateRow } from "@/components/public/latest-update-row";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { SectionHeader } from "@/components/public/section-header";
import { groupDateLabel } from "@/lib/date-group";
import { useCatalog, useGenreLabelMap, usePublicAuth } from "@/hooks/public";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
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

function readableChapterHref(novel: PublicNovelSummary): string | null {
  const latestChapterId = novel.latest_chapter_id?.trim();
  if (latestChapterId) {
    return publicChapterHref(novel.slug, latestChapterId);
  }
  return null;
}

function latestChapterHref(novel: PublicNovelSummary): string {
  return readableChapterHref(novel) ?? publicNovelHref(novel.slug);
}

function primaryGenre(novel: PublicNovelSummary): string | null {
  return novel.genres?.find(Boolean) ?? null;
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
  const heroDetailHref = featuredNovel ? publicNovelHref(featuredNovel.slug) : null;
  const heroReadableHref = featuredNovel ? readableChapterHref(featuredNovel) : null;
  const utilityItems = [
    {
      href: "/request-novel",
      icon: FileText,
      label: "Request Novel",
    },
    {
      href: "/browse-novels",
      icon: Search,
      label: "Browse Library",
    },
    {
      href: "/contact",
      icon: LifeBuoy,
      label: "Contact",
    },
    isAuthenticated
      ? {
          href: "/account/library",
          icon: Library,
          label: "Library",
        }
      : {
          href: "/login?mode=signin",
          icon: Bookmark,
          label: "Save Reading",
        },
  ];

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
      <section
        className="relative isolate min-h-[85vh] overflow-hidden border-b border-border/80"
        aria-label="Featured Dokushodo novel"
      >
        {featuredNovel && (
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
                  Featured
                </span>

                <h1 className="mt-5 max-w-2xl font-literary text-4xl font-semibold leading-tight tracking-normal text-foreground drop-shadow md:text-6xl">
                  {featuredNovel.title}
                </h1>

                {heroSourceTitle && (
                  <p className="mt-3 max-w-2xl font-literary text-base text-accent drop-shadow">
                    {heroSourceTitle}
                  </p>
                )}

                <NovelMetadataRow
                  className="mt-5"
                  chapterCount={featuredNovel.chapter_count}
                  translatedCount={featuredNovel.translated_count}
                  source={featuredNovel.language}
                  status={featuredNovel.publication_status}
                />

                <p className="mt-5 max-w-2xl line-clamp-3 text-sm leading-6 text-foreground/80 drop-shadow md:text-base md:leading-7">
                  {heroSynopsis ?? "Synopsis unavailable for this novel."}
                </p>

                {featuredNovel.genres && featuredNovel.genres.length > 0 && (
                  <div className="mt-5 flex flex-wrap gap-2">
                    {featuredNovel.genres.map((genre) => (
                      <GenreChip key={genre} label={genreLabels?.get(genre) ?? genre} />
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
                  {heroDetailHref && (
                    <Link
                      href={heroDetailHref}
                      className={
                        heroReadableHref
                          ? "inline-flex h-11 items-center justify-center gap-2 rounded-sm border border-accent/40 bg-background/70 px-5 font-metadata text-xs font-medium uppercase tracking-wide text-accent backdrop-blur transition-colors hover:bg-accent/10"
                          : "inline-flex h-11 items-center justify-center gap-2 rounded-sm bg-primary px-5 font-metadata text-xs font-medium uppercase tracking-wide text-primary-foreground transition-colors hover:bg-primary/90"
                      }
                    >
                      View Details
                      <ArrowRight className="h-4 w-4" />
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
        )}
      </section>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* ── Reader utility links ── */}
        <section className="grid gap-3 border-b border-border/70 py-8 sm:grid-cols-2 lg:grid-cols-4">
          {utilityItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.label}
                href={item.href}
                className="group flex min-h-24 flex-col items-center justify-center gap-3 rounded-sm border border-border/80 bg-card/55 px-4 py-5 text-center transition-colors hover:border-primary/40 hover:bg-card"
              >
                <Icon className="h-5 w-5 text-foreground/70 transition-colors group-hover:text-primary" />
                <span className="font-literary text-sm font-semibold text-foreground">
                  {item.label}
                </span>
              </Link>
            );
          })}
        </section>

        <section className="grid gap-8 py-14 lg:grid-cols-[minmax(0,1fr)_18rem]">
          <div>
            <SectionHeader
              title="Latest Releases"
              description="Newest catalog entries, shown with generated reading plates until safe cover metadata exists."
              actionHref="/browse-novels"
              actionLabel="View all"
            />
            <div className="mt-6 grid gap-x-4 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
              {novels.slice(0, 6).map((novel) => {
                const genre = primaryGenre(novel);
                return (
                  <Link
                    key={novel.novel_id}
                    href={publicNovelHref(novel.slug)}
                    className="group block"
                  >
                    <div className="overflow-hidden rounded-sm border border-border/80 bg-card/60">
                      <FallbackCover
                        title={novel.title}
                        sourceTitle={novel.source_title}
                        language={novel.language}
                        status={novel.publication_status}
                        genres={novel.genres}
                        className="rounded-none border-0 shadow-none"
                      />
                    </div>
                    <div className="mt-3">
                      <p className="line-clamp-2 font-literary text-base font-semibold leading-snug text-foreground group-hover:text-accent">
                        {novel.title}
                      </p>
                      <p className="mt-1 font-metadata text-xs uppercase tracking-wide text-muted-foreground">
                        {novel.translated_count > 0
                          ? `${novel.translated_count} translated`
                          : "No translated chapters yet"}
                        {genre ? ` / ${genreLabels?.get(genre) ?? genre}` : ""}
                      </p>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>

          <aside className="space-y-5">
            <div className="rounded-sm border border-border/80 bg-card/55 p-5">
              <h2 className="border-l-2 border-primary pl-3 font-literary text-xl font-semibold">
                Reading Paths
              </h2>
              <div className="mt-5 space-y-2">
                <Link
                  href="/browse-novels"
                  className="flex items-center justify-between border-b border-border/60 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  Browse by genre
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/request-novel"
                  className="flex items-center justify-between border-b border-border/60 py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  Request a source URL
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href={isAuthenticated ? "/account/library" : "/login?mode=signin"}
                  className="flex items-center justify-between py-3 text-sm text-muted-foreground transition-colors hover:text-foreground"
                >
                  {isAuthenticated ? "Open library" : "Save reading state"}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>

            <div className="rounded-sm border border-border/80 bg-card/55 p-5">
              <h2 className="border-l-2 border-primary pl-3 font-literary text-xl font-semibold">
                Catalog Notes
              </h2>
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                Covers here are generated placeholders. Public source cover metadata is still gated until it can be handled safely.
              </p>
            </div>
          </aside>
        </section>

        {/* ── Recently Added (compact rows) ── */}
        <section className="pb-16">
          <SectionHeader
            title="Recent Updates"
            description="Latest readable chapter activity and catalog additions."
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
                  <div className="mt-2 divide-y divide-border/60 overflow-hidden rounded-sm border border-border/80 bg-card/45">
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
