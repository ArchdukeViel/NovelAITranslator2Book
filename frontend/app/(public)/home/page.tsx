"use client";

import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FilePlus2,
  Shuffle,
  TrendingUp,
} from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { NovelRail } from "@/components/public/novel-rail";
import {
  useCatalog,
  useGenreLabelMap,
  useHistory,
  usePublicAuth,
} from "@/hooks/public";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
import type { PublicNovelSummary } from "@/lib/public-types";
import { cn } from "@/lib/utils";

/* ---------------------------------- helpers ---------------------------------- */

function usefulSourceTitle(
  sourceTitle: string | null | undefined,
  title: string
): string | null {
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

function relativeTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffMs = Date.now() - then;
  if (diffMs < 0) return "just now";
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} mo${months === 1 ? "" : "s"} ago`;
  const years = Math.floor(months / 12);
  return `${years} yr${years === 1 ? "" : "s"} ago`;
}

function chapterLabel(number: number | null | undefined): string | null {
  if (typeof number !== "number" || Number.isNaN(number)) return null;
  return `Chapter ${number}`;
}

/* ------------------------------- rail novel card ------------------------------ */

function RailCard({ novel }: { novel: PublicNovelSummary }) {
  return (
    <article role="listitem" className="w-44 shrink-0 snap-start">
      <Link href={publicNovelHref(novel.slug)} className="group block">
        <div className="relative overflow-hidden rounded-md border border-border/40 bg-card p-1.5 transition-all duration-300 ease-out hover:-translate-y-1 hover:border-primary/40 hover:shadow-md">
          <FallbackCover
            title={novel.title}
            sourceTitle={novel.source_title}
            language={novel.language}
            status={novel.publication_status}
            genres={novel.genres}
            className="rounded-sm"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-background/80 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
        </div>
        <h3 className="mt-2.5 line-clamp-2 font-literary text-sm font-semibold leading-snug transition-colors group-hover:text-primary">
          {novel.title}
        </h3>
        <div className="mt-1 flex items-center justify-between font-metadata text-[11px] text-muted-foreground">
          <span>{novel.genres?.[0]?.name_en ?? novel.genres?.[0]?.slug ?? "Web Novel"}</span>
          <span>{novel.translated_count > 0 ? `${novel.translated_count} Ch` : "Pending"}</span>
        </div>
      </Link>
    </article>
  );
}

/* ---------------------------------- banner tile ------------------------------- */

function BannerTile({
  href,
  icon: Icon,
  title,
  subtitle,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle: string;
}) {
  return (
    <Link
      href={href}
      className="group relative flex h-28 items-center justify-center overflow-hidden rounded-lg border border-border/60 bg-card transition-colors hover:border-primary/40"
    >
      <div className="absolute inset-0 bg-gradient-to-r from-muted/60 to-muted/20 transition-transform duration-500 group-hover:scale-105" />
      <div className="relative flex flex-col items-center gap-1.5 text-center">
        <Icon className="h-7 w-7 text-primary" />
        <span className="font-literary text-lg font-semibold text-foreground">{title}</span>
        <span className="font-metadata text-[11px] uppercase tracking-wider text-muted-foreground">
          {subtitle}
        </span>
      </div>
    </Link>
  );
}

/* ------------------------------ recent update item ---------------------------- */

function RecentUpdateItem({ novel }: { novel: PublicNovelSummary }) {
  const when = relativeTime(latestActivityAt(novel));
  const chapterNum = novel.latest_chapter_number;
  const chapterTitle = novel.latest_chapter_title?.trim() || null;
  const chapterText =
    chapterLabel(chapterNum) ?? (chapterTitle ? chapterTitle : null);
  const chapterHref = readableChapterHref(novel);

  return (
    <div className="flex items-start gap-4 border-b border-border/50 p-4 transition-colors last:border-0 hover:bg-card/70">
      <Link
        href={publicNovelHref(novel.slug)}
        className="block w-12 shrink-0 overflow-hidden rounded"
        aria-hidden="true"
        tabIndex={-1}
      >
        <FallbackCover
          title={novel.title}
          sourceTitle={novel.source_title}
          language={novel.language}
          status={novel.publication_status}
          genres={novel.genres}
          className="rounded"
        />
      </Link>
      <div className="min-w-0 flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className="font-metadata text-xs text-muted-foreground">{when ?? "—"}</span>
          <div className="h-px flex-1 bg-border/60" />
        </div>
        <Link
          href={publicNovelHref(novel.slug)}
          className="block truncate font-literary text-base font-medium leading-tight text-foreground transition-colors hover:text-primary"
        >
          {novel.title}
        </Link>
        <div className="mt-2 flex flex-col gap-1">
          {chapterHref && chapterText ? (
            <Link
              href={chapterHref}
              className="truncate font-metadata text-[13px] text-muted-foreground transition-colors hover:text-primary"
            >
              {chapterTitle ? `${chapterText} · ${chapterTitle}` : chapterText}
            </Link>
          ) : (
            <span className="font-metadata text-[13px] text-muted-foreground">
              Translation pending
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------ ranked sidebar item --------------------------- */

function RankedItem({ novel, rank }: { novel: PublicNovelSummary; rank: number }) {
  return (
    <li>
      <Link
        href={publicNovelHref(novel.slug)}
        className="group flex items-center gap-3 rounded p-2 transition-colors hover:bg-card/70"
      >
        <div className="relative w-10 shrink-0 overflow-hidden rounded">
          <FallbackCover
            title={novel.title}
            sourceTitle={novel.source_title}
            language={novel.language}
            status={novel.publication_status}
            genres={novel.genres}
            className="rounded"
          />
          <span
            className={cn(
              "absolute left-0 top-0 rounded-br px-1 text-[10px] font-bold",
              rank === 1
                ? "bg-primary text-primary-foreground"
                : "bg-background/90 text-foreground"
            )}
          >
            {rank}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="truncate text-[13px] font-semibold text-foreground transition-colors group-hover:text-primary">
            {novel.title}
          </h4>
          <p className="mt-0.5 truncate font-metadata text-[11px] text-muted-foreground">
            {novel.translated_count > 0
              ? `${novel.translated_count} translated chapters`
              : "Translation pending"}
          </p>
        </div>
      </Link>
    </li>
  );
}

/* ------------------------------ trending sidebar item ------------------------- */

function TrendingItem({ novel, rank }: { novel: PublicNovelSummary; rank: number }) {
  return (
    <li>
      <Link
        href={publicNovelHref(novel.slug)}
        className="group flex items-center gap-4"
      >
        <span
          className={cn(
            "w-8 text-center font-literary text-3xl font-bold",
            rank === 1 ? "text-primary" : "text-muted-foreground/60"
          )}
        >
          {rank}
        </span>
        <div className="min-w-0 flex-1 border-b border-border/50 pb-2 transition-colors group-hover:border-primary/50">
          <h4 className="line-clamp-1 font-literary text-base font-medium text-foreground transition-colors group-hover:text-primary">
            {novel.title}
          </h4>
          <div className="mt-1 flex items-center gap-1.5">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
            <span className="font-metadata text-xs text-muted-foreground">
              {novel.translated_count > 0
                ? `${novel.translated_count} chapters translated`
                : "Awaiting translation"}
            </span>
          </div>
        </div>
      </Link>
    </li>
  );
}

/* ---------------------------------- widget card ------------------------------- */

function WidgetCard({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-lg border border-border/60 bg-muted/30", className)}>
      <div className="flex items-center justify-between border-b border-border/50 p-4">
        <h2 className="font-literary text-lg font-semibold text-foreground">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------ page ----------------------------------- */

export default function HomePage() {
  const { data, isPending, isError, refetch } = useCatalog({
    sort_by: "added_at",
    order: "desc",
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
  const newReleases = novels.slice(0, 12);
  const ranked = [...novels]
    .sort(
      (left, right) =>
        right.translated_count - left.translated_count || left.title.localeCompare(right.title)
    )
    .slice(0, 5);
  const trending = [...novels]
    .sort((left, right) => right.chapter_count - left.chapter_count)
    .slice(0, 5);

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

  /* ---------------------------------- loading --------------------------------- */
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
              <div className="flex gap-3 pt-4">
                <div className="h-11 w-40 animate-pulse rounded-md bg-muted" />
              </div>
            </div>
          </div>
        </section>
        <div className="mx-auto max-w-7xl space-y-12 px-4 py-14 sm:px-6 lg:px-8">
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
            {Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="aspect-[2/3] animate-pulse rounded-md bg-muted" />
                <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
              </div>
            ))}
          </div>
        </div>
        <span className="sr-only" role="status">
          Loading catalog…
        </span>
      </main>
    );
  }

  /* ----------------------------------- error ---------------------------------- */
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
              Browse the catalog
            </Link>
          </div>
        </div>
      </main>
    );
  }

  /* ----------------------------------- empty ---------------------------------- */
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
              Browse the catalog
            </Link>
          </div>
        </div>
      </main>
    );
  }

  /* ----------------------------------- settled -------------------------------- */
  return (
    <main className="bg-background">
      <div className="mx-auto w-full max-w-[1600px] grid-cols-1 gap-8 px-4 py-8 sm:px-6 lg:px-8 xl:grid xl:grid-cols-12">
        {/* Left column: main feed */}
        <div className="flex w-full flex-col gap-10 xl:col-span-8 2xl:col-span-9">
          {/* Spotlight hero */}
          {spotlightNovel && (
            <section
              aria-label="Dokushodo spotlight novel"
              className="relative isolate overflow-hidden rounded-xl border border-border/80 bg-card/60 p-6 shadow-sm sm:p-8 lg:p-10"
            >
              <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-12 lg:gap-12">
                <div className="space-y-4 lg:col-span-8">
                  <span className="font-metadata text-xs font-semibold uppercase tracking-wider text-primary">
                    Spotlight
                  </span>
                  <h1 className="font-literary text-3xl font-semibold leading-tight tracking-tight text-foreground sm:text-4xl lg:text-5xl">
                    {spotlightNovel.title}
                  </h1>
                  {heroSourceTitle && (
                    <p className="font-literary text-base text-accent">{heroSourceTitle}</p>
                  )}
                  <NovelMetadataRow
                    className="mt-2"
                    chapterCount={spotlightNovel.chapter_count}
                    translatedCount={spotlightNovel.translated_count}
                    source={spotlightNovel.language}
                    status={spotlightNovel.publication_status}
                  />
                  <p className="max-w-2xl line-clamp-3 text-sm leading-relaxed text-muted-foreground md:text-base">
                    {heroSynopsis ?? "Synopsis unavailable for this novel."}
                  </p>
                  {spotlightNovel.genres && spotlightNovel.genres.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {spotlightNovel.genres.map((genre) => (
                        <GenreChip
                          key={genre.slug}
                          label={genreLabels?.get(genre.slug) ?? genre.slug}
                        />
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap items-center gap-4 pt-2">
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
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Discovery banner tiles */}
          <section aria-label="Discovery shortcuts" className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <BannerTile
              href="/random"
              icon={Shuffle}
              title="Random Novel"
              subtitle="Let chance decide"
            />
            <BannerTile
              href="/request-novel"
              icon={FilePlus2}
              title="Request Novel"
              subtitle="Ask for a translation"
            />
          </section>

          {/* Continue reading */}
          {isAuthenticated && continueNovels.length > 0 && (
            <NovelRail
              title="Continue Reading"
              ariaLabel="Continue reading"
              seeAllHref="/account/history"
            >
              {continueNovels.map((novel) => (
                <RailCard key={novel.novel_id} novel={novel} />
              ))}
            </NovelRail>
          )}

          {/* New releases grid (Stitch "New Novels") */}
          <section aria-label="New releases" className="flex flex-col gap-6">
            <div className="flex items-end justify-between border-b border-border/60 pb-2">
              <h2 className="font-literary text-2xl font-semibold text-foreground">New Releases</h2>
              <Link
                href="/browse-novels?sort_by=added_at&order=desc"
                className="rounded-sm border border-border/60 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                See More
              </Link>
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
              {newReleases.map((novel) => (
                <Link
                  key={novel.novel_id}
                  href={publicNovelHref(novel.slug)}
                  className="group flex flex-col gap-2 rounded-lg border border-border/40 bg-card p-2 transition-all duration-300 ease-out hover:-translate-y-1 hover:border-primary/40 hover:shadow-md"
                >
                  <div className="relative aspect-[2/3] w-full overflow-hidden rounded-sm bg-muted">
                    <FallbackCover
                      title={novel.title}
                      sourceTitle={novel.source_title}
                      language={novel.language}
                      status={novel.publication_status}
                      genres={novel.genres}
                      className="rounded-sm"
                    />
                  </div>
                  <div className="mt-1">
                    <h3 className="line-clamp-2 text-sm font-semibold leading-snug text-foreground">
                      {novel.title}
                    </h3>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="rounded-sm border border-border/50 px-1.5 py-0.5 font-metadata text-[10px] text-muted-foreground">
                        {novel.genres?.[0]?.name_en ?? novel.genres?.[0]?.slug ?? "Web Novel"}
                      </span>
                      <span className="font-metadata text-[10px] text-muted-foreground">
                        {novel.translated_count > 0 ? `${novel.translated_count} Ch` : "Pending"}
                      </span>
                    </div>
                    <p className="mt-1 font-metadata text-[10px] text-muted-foreground">
                      Added {relativeTime(novel.added_at) ?? "recently"}
                    </p>
                  </div>
                </Link>
              ))}
            </div>
          </section>

          {/* Recently updated list */}
          <section aria-label="Recently updated" className="flex flex-col gap-4">
            <div className="flex items-end justify-between border-b border-border/60 pb-2">
              <h2 className="font-literary text-2xl font-semibold text-foreground">
                Recently Updated
              </h2>
              <Link
                href="/browse-novels?sort_by=updated_at&order=desc"
                className="rounded-sm border border-border/60 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                See More
              </Link>
            </div>
            <div className="flex flex-col rounded-lg border border-border/60 bg-muted/30">
              {recentlyUpdated.slice(0, 6).map((novel) => (
                <RecentUpdateItem key={novel.novel_id} novel={novel} />
              ))}
            </div>
          </section>

          {/* Genre curations */}
          {topGenres.map(([slug, genre]) => (
            <NovelRail
              key={slug}
              title={genre.label}
              ariaLabel={`${genre.label} novels`}
              seeAllHref={`/genres/${encodeURIComponent(slug)}`}
            >
              {novels
                .filter((novel) => novel.genres?.some((item) => item.slug === slug))
                .slice(0, 12)
                .map((novel) => (
                  <RailCard key={novel.novel_id} novel={novel} />
                ))}
            </NovelRail>
          ))}

          {/* Surprise me callout */}
          <section
            aria-label="Discovery"
            className="rounded-xl border border-border/80 bg-card p-6 shadow-sm sm:p-8"
          >
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-1.5 text-xs font-medium text-accent">
                  <span className="font-metadata uppercase tracking-wider">Unplanned Journey</span>
                </div>
                <h2 className="font-literary text-2xl font-semibold text-foreground">
                  Looking for something unexpected?
                </h2>
                <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                  Let chance decide your next story. Jump directly into a random novel from our
                  translated library.
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

        {/* Right column: sidebar widgets */}
        <aside className="mt-10 flex w-full flex-col gap-6 xl:col-span-4 xl:mt-0 2xl:col-span-3">
          {/* Novel ranking */}
          <WidgetCard
            title="Novel Ranking"
            action={
              <Link
                href="/browse-novels?sort_by=chapter_count&order=desc"
                className="rounded-sm border border-border/60 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                See More
              </Link>
            }
          >
            <ul className="flex flex-col gap-1 p-2">
              {ranked.map((novel, i) => (
                <RankedItem key={novel.novel_id} novel={novel} rank={i + 1} />
              ))}
            </ul>
          </WidgetCard>

          {/* Longest series (by chapter count — honest, catalog-derived) */}
          <WidgetCard
            title="Longest Series"
            action={
              <Link
                href="/browse-novels?sort_by=chapter_count&order=desc"
                className="rounded-sm border border-border/60 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                See More
              </Link>
            }
          >
            <ul className="flex flex-col gap-3 p-4">
              {trending.slice(0, 3).map((novel) => (
                <li key={novel.novel_id}>
                  <Link
                    href={publicNovelHref(novel.slug)}
                    className="group flex items-center gap-3"
                  >
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <BookOpen className="h-4 w-4" aria-hidden="true" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <span className="block truncate text-sm font-semibold text-foreground transition-colors group-hover:text-primary">
                        {novel.title}
                      </span>
                      <span className="block font-metadata text-xs text-muted-foreground">
                        {novel.chapter_count} chapters
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </WidgetCard>

          {/* Most chapters (honest replacement for Stitch's fake "Trending") */}
          <WidgetCard title="Most Chapters" className="flex h-full flex-col p-6 [&>div:first-child]:mb-6 [&>div:first-child]:border-b [&>div:first-child]:p-0 [&>div:first-child]:pb-4">
            <ul className="flex flex-1 flex-col gap-5">
              {trending.map((novel, i) => (
                <TrendingItem key={novel.novel_id} novel={novel} rank={i + 1} />
              ))}
            </ul>
            <Link
              href="/browse-novels?sort_by=chapter_count&order=desc"
              className="mt-6 inline-flex w-full items-center justify-center rounded-md border border-border/60 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:border-border hover:text-foreground"
            >
              View Full Catalog
            </Link>
          </WidgetCard>
        </aside>
      </div>
    </main>
  );
}
