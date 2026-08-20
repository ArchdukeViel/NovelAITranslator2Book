"use client";

import {
  useDeferredValue,
  useState,
  useSyncExternalStore,
} from "react";
import Link from "next/link";
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  Compass,
  FilePlus2,
  Newspaper,
  Shuffle,
  Trophy,
  TrendingUp,
} from "lucide-react";

import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { NovelRail } from "@/components/public/novel-rail";
import {
  useCatalog,
  useHistory,
  usePublicAuth,
  usePublicRankings,
} from "@/hooks/public";
import { isPublicRequestAbortError } from "@/lib/public-api";
import {
  HOME_CATALOG_PARAMS,
  HOME_RANKING_LIMIT,
  HOME_RANKING_PERIOD,
} from "@/lib/public-home-data";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
import type { PublicNovelSummary, PublicRankingItem } from "@/lib/public-types";
import { cn } from "@/lib/utils";

/* ---------------------------------- helpers ---------------------------------- */

function usefulSourceTitle(
  sourceTitle: string | null | undefined,
  title: string,
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

function latestActivityAt(
  novel: PublicNovelSummary,
): string | null | undefined {
  return novel.latest_chapter_updated_at ?? novel.added_at;
}

function readableChapterHref(novel: PublicNovelSummary): string | null {
  const latestChapterId = novel.latest_chapter_id?.trim();
  if (latestChapterId) {
    return publicChapterHref(novel.slug, latestChapterId);
  }
  return null;
}

function relativeTime(
  iso: string | null | undefined,
  nowMs: number | null,
): string | null {
  if (!iso) return null;
  if (nowMs === null) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffMs = nowMs - then;
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

/** Honest freshness flag derived from the real added_at catalog field. */
function isNewlyAdded(
  iso: string | null | undefined,
  nowMs: number | null,
  withinDays = 14,
): boolean {
  if (!iso) return false;
  if (nowMs === null) return false;
  const added = new Date(iso).getTime();
  if (Number.isNaN(added)) return false;
  return nowMs - added <= withinDays * 24 * 60 * 60 * 1000;
}

function NewBadge() {
  return (
    <span className="absolute left-2 top-2 z-10 rounded-sm bg-primary px-1.5 py-0.5 font-metadata text-[10px] font-bold uppercase tracking-wider text-primary-foreground shadow-sm">
      New
    </span>
  );
}

/* --------------------------- shared surface utilities ------------------------ */
/* Elevation discipline: cards are SOLID one step up from the paper (bg-card vs
   bg-background), resting on shadow-card; hover lifts with shadow-raised. Dark
   mode shadows are near-invisible, so a 5% white ring carries the edge instead.
   Only the hero may use a heavier shadow than shadow-raised. */

const CARD_SURFACE = "bg-card shadow-card dark:ring-1 dark:ring-white/5";

const CARD_LIFT =
  "transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-raised";

const CLIENT_NOW_MS = Date.now();
const EMPTY_SUBSCRIBE = () => () => {};

function useHydratedNow(): number | null {
  return useSyncExternalStore(
    EMPTY_SUBSCRIBE,
    () => CLIENT_NOW_MS,
    () => null,
  );
}

/* ------------------------------- rail novel card ------------------------------ */

function RailCard({
  novel,
  lastReadChapter,
  nowMs,
}: {
  novel: PublicNovelSummary;
  nowMs: number | null;
  lastReadChapter?: {
    chapter_number?: number | null;
    chapter_id?: string | null;
  };
}) {
  const targetHref = lastReadChapter?.chapter_id
    ? publicChapterHref(novel.slug, lastReadChapter.chapter_id)
    : publicNovelHref(novel.slug);

  return (
    <article role="listitem" className="w-44 shrink-0 snap-start">
      <Link href={targetHref} className="group block">
        <div className="relative overflow-hidden rounded-md bg-card p-1.5 shadow-card transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-raised hover:ring-1 hover:ring-primary/40">
          {isNewlyAdded(novel.added_at, nowMs) &&
            !lastReadChapter && <NewBadge />}
          {lastReadChapter && (
            <span className="absolute left-2 top-2 z-10 rounded-sm bg-primary px-1.5 py-0.5 font-metadata text-[10px] font-bold uppercase tracking-wider text-primary-foreground shadow-sm">
              {lastReadChapter.chapter_number
                ? `Ch. ${lastReadChapter.chapter_number}`
                : "Resume"}
            </span>
          )}
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
          <span>
            {novel.genres?.[0]?.name_en ??
              novel.genres?.[0]?.slug ??
              "Web Novel"}
          </span>
          <span>
            {novel.translated_count > 0
              ? `${novel.translated_count} Ch`
              : "Pending"}
          </span>
        </div>
      </Link>
    </article>
  );
}

function RailCardSkeleton() {
  return (
    <div className="w-44 shrink-0 animate-pulse">
      <div className="aspect-[2/3] w-full rounded-md bg-muted/60" />
      <div className="mt-2.5 h-4 w-3/4 rounded bg-muted/60" />
      <div className="mt-1.5 flex justify-between">
        <div className="h-3 w-12 rounded bg-muted/40" />
        <div className="h-3 w-8 rounded bg-muted/40" />
      </div>
    </div>
  );
}

/* ---------------------------------- banner tile ------------------------------- */

function ImageBannerTile({
  href,
  icon: Icon,
  title,
  subtitle,
  bgImage,
}: {
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  subtitle?: string;
  bgImage: string;
}) {
  return (
    <Link
      href={href}
      className="group relative flex h-24 sm:h-28 flex-1 min-w-[45%] md:min-w-[20%] items-center justify-center overflow-hidden rounded-xl bg-card shadow-md transition-all duration-300 ease-out hover:-translate-y-1 hover:shadow-xl hover:ring-1 hover:ring-primary/40"
      style={{
        backgroundImage: `url(${bgImage})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {/* Dark overlay with hover reaction */}
      <div
        className="absolute inset-0 bg-black/45 transition-opacity duration-200 group-hover:bg-black/60"
        aria-hidden="true"
      />
      {/* Subtle vignette border */}
      <div className="absolute inset-0 ring-1 ring-inset ring-white/10 rounded-xl" />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center gap-1.5 px-3 text-center text-white">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15 backdrop-blur-xs transition-transform duration-300 group-hover:scale-110">
          <Icon className="h-4.5 w-4.5 text-white" />
        </div>
        <span className="font-literary text-base sm:text-lg font-bold tracking-wide text-white drop-shadow-sm">
          {title}
        </span>
        {subtitle && (
          <span className="font-metadata text-[10px] sm:text-[11px] font-medium tracking-wider text-white/80 uppercase">
            {subtitle}
          </span>
        )}
      </div>
    </Link>
  );
}

/* ------------------------------ recent update item ---------------------------- */

function RecentUpdateItem({
  novel,
  nowMs,
}: {
  novel: PublicNovelSummary;
  nowMs: number | null;
}) {
  const when = relativeTime(latestActivityAt(novel), nowMs);
  const chapterNum = novel.latest_chapter_number;
  const chapterTitle = novel.latest_chapter_title?.trim() || null;
  const chapterText =
    chapterLabel(chapterNum) ?? (chapterTitle ? chapterTitle : null);
  const chapterHref = readableChapterHref(novel);

  return (
    <div className="flex items-start gap-4 border-b border-border/20 p-4 transition-colors last:border-0 hover:bg-muted/50">
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
          <span className="font-metadata text-xs text-muted-foreground">
            {when ?? "—"}
          </span>
          <div className="h-px flex-1 bg-border/20" />
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

function RankedItem({
  ranking,
}: {
  ranking: PublicRankingItem;
}) {
  const { novel } = ranking;
  return (
    <li>
      <Link
        href={publicNovelHref(novel.slug)}
        className="group flex items-center gap-3 rounded p-2 transition-colors hover:bg-muted/50"
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
              ranking.rank === 1
                ? "bg-primary text-primary-foreground"
                : "bg-background/90 text-foreground",
            )}
          >
            {ranking.rank}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <h4 className="truncate text-[13px] font-semibold text-foreground transition-colors group-hover:text-primary">
            {novel.title}
          </h4>
          <p className="mt-0.5 truncate font-metadata text-[11px] text-muted-foreground">
            {ranking.unique_views.toLocaleString()} unique novel views
          </p>
        </div>
      </Link>
    </li>
  );
}

/* ------------------------------ trending sidebar item ------------------------- */

function TrendingItem({
  ranking,
}: {
  ranking: PublicRankingItem;
}) {
  const { novel, rank } = { novel: ranking.novel, rank: ranking.rank };
  return (
    <li>
      <Link
        href={publicNovelHref(novel.slug)}
        className="group flex items-center gap-4"
      >
        <span
          className={cn(
            "w-8 text-center font-literary text-3xl font-bold",
            rank === 1 ? "text-primary" : "text-muted-foreground/60",
          )}
        >
          {rank}
        </span>
        <div className="min-w-0 flex-1 border-b border-border/20 pb-2 transition-colors group-hover:border-primary/50">
          <h4 className="line-clamp-1 font-literary text-base font-medium text-foreground transition-colors group-hover:text-primary">
            {novel.title}
          </h4>
          <div className="mt-1 flex items-center gap-1.5">
            <TrendingUp
              className="h-3.5 w-3.5 text-muted-foreground"
              aria-hidden="true"
            />
            <span className="font-metadata text-xs text-muted-foreground">
              {ranking.unique_views.toLocaleString()} unique novel views
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
    <div className={cn(CARD_SURFACE, "rounded-lg", className)}>
      <div className="flex items-center justify-between border-b border-border/20 p-4">
        <h2 className="font-literary text-lg font-semibold text-foreground">
          {title}
        </h2>
        {action}
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------ page ----------------------------------- */

export default function HomePage() {
  const { data, isPending, isError, error, refetch } = useCatalog(HOME_CATALOG_PARAMS);

  const novels = data?.novels ?? [];
  const spotlightNovels = novels.filter((novel) =>
    Boolean(synopsisPreview(novel.synopsis) && readableChapterHref(novel)),
  );
  const spotlightNovel = spotlightNovels[0];
  const [heroIndex, setHeroIndex] = useState(0);
  const [rankingTab, setRankingTab] = useState<"daily" | "weekly" | "monthly">(
    HOME_RANKING_PERIOD,
  );
  const nowMs = useHydratedNow();
  const rankingQuery = usePublicRankings(rankingTab, HOME_RANKING_LIMIT);
  const trendingQuery = usePublicRankings(HOME_RANKING_PERIOD, HOME_RANKING_LIMIT, {
    enabled: rankingTab !== HOME_RANKING_PERIOD,
  });
  const currentSpotlight = spotlightNovels[heroIndex] ?? spotlightNovel;

  // Keep personalization out of the first render. The server-hydrated catalog
  // and weekly ranking are useful to guests before auth/history are needed.
  const personalizationEnabled = useDeferredValue(!isPending);
  const { isAuthenticated } = usePublicAuth({ enabled: personalizationEnabled });
  const heroSourceTitle = currentSpotlight
    ? usefulSourceTitle(currentSpotlight.source_title, currentSpotlight.title)
    : null;
  const heroSynopsis = synopsisPreview(currentSpotlight?.synopsis);
  const heroReadableHref = currentSpotlight
    ? readableChapterHref(currentSpotlight)
    : null;
  const history = useHistory(
    { limit: 12 },
    { enabled: personalizationEnabled },
  );
  const historyItems = history.data?.items ?? [];
  const historyBySlug = new Map(historyItems.map((item) => [item.slug, item]));
  const continueNovels = isAuthenticated
    ? [...new Set(historyItems.map((item) => item.slug))]
        .map((slug) => novels.find((novel) => novel.slug === slug))
        .filter((novel): novel is PublicNovelSummary => Boolean(novel))
    : [];

  const recentlyUpdated = [...novels].sort((left, right) =>
    String(latestActivityAt(right) ?? "").localeCompare(
      String(latestActivityAt(left) ?? ""),
    ),
  );
  const newReleases = novels.slice(0, 12);
  const ranked = rankingQuery.data?.items ?? [];
  const trending =
    rankingTab === HOME_RANKING_PERIOD
      ? ranked
      : trendingQuery.data?.items ?? [];
  const trendingPending =
    rankingTab === HOME_RANKING_PERIOD
      ? rankingQuery.isPending
      : trendingQuery.isPending;

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
    .sort(
      (left, right) =>
        right[1].count - left[1].count || left[0].localeCompare(right[0]),
    )
    .slice(0, 2);

  /* ----------------------------------- settled -------------------------------- */
  return (
    <main className="bg-background">
      <div className="mx-auto w-full max-w-[1600px] grid-cols-1 gap-8 px-4 py-8 sm:px-6 lg:px-8 xl:grid xl:grid-cols-12">
        {/* Left column: main feed */}
        <div className="flex w-full flex-col gap-10 xl:col-span-8 2xl:col-span-9">
          {/* Offline / Error notice banner (non-blocking) */}
          {isError && (
            <div className="flex items-center justify-between rounded-lg border border-primary/30 bg-primary/10 px-4 py-3 text-sm text-primary">
              <span>
                {isPublicRequestAbortError(error)
                  ? "Catalog request was cancelled or timed out. Showing an empty layout."
                  : "Could not connect to catalog backend. Showing layout preview."}
              </span>
              <button
                type="button"
                onClick={() => refetch()}
                className="font-medium underline hover:text-primary-text"
              >
                Try reconnecting
              </button>
            </div>
          )}

          {/* Spotlight hero carousel */}
          <section
            aria-label="Dokushodo spotlight novel"
            className="group relative min-h-[420px] w-full overflow-hidden rounded-xl bg-card shadow-lg"
          >
            {currentSpotlight ? (
              <>
                {/* Atmospheric background layer (subtle palette wash, not a stretched bookplate) */}
                <div
                  className="absolute inset-0 bg-gradient-to-br from-primary/10 via-card to-background"
                  aria-hidden="true"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-background/25 to-transparent" />

                {/* Content Overlay */}
                <div className="relative flex flex-col gap-8 p-6 sm:p-8 lg:grid lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center lg:gap-12 lg:p-10">
                  <div className="order-2 flex min-w-0 flex-col lg:order-1">
                    <div className="mb-3 flex items-center justify-between">
                      <span className="font-metadata text-xs font-semibold uppercase tracking-wider text-primary">
                        Featured Series{" "}
                        {spotlightNovels.length > 1
                          ? `(${heroIndex + 1}/${spotlightNovels.length})`
                          : ""}
                      </span>
                      {spotlightNovels.length > 1 && (
                        <div
                          className="z-10 flex gap-1.5"
                          aria-label="Featured series carousel controls"
                        >
                          {spotlightNovels.slice(0, 5).map((_, idx) => (
                            <button
                              key={idx}
                              type="button"
                              onClick={() => setHeroIndex(idx)}
                              className={cn(
                                "h-2 rounded-full transition-all",
                                idx === heroIndex
                                  ? "w-6 bg-primary"
                                  : "w-2 bg-muted-foreground/40 hover:bg-muted-foreground",
                              )}
                              aria-label={`Go to slide ${idx + 1}`}
                            />
                          ))}
                        </div>
                      )}
                    </div>
                    <h1 className="mb-2 font-literary text-3xl font-semibold leading-tight text-foreground sm:text-4xl lg:text-5xl">
                      {currentSpotlight.title}
                    </h1>
                    {heroSourceTitle && (
                      <p className="mb-3 font-literary text-base italic text-muted-foreground sm:text-lg">
                        {heroSourceTitle}
                      </p>
                    )}
                    <NovelMetadataRow
                      className="mb-4"
                      chapterCount={currentSpotlight.chapter_count}
                      translatedCount={currentSpotlight.translated_count}
                      status={currentSpotlight.publication_status}
                    />
                    {heroSynopsis && (
                      <p className="mb-5 max-w-2xl line-clamp-3 text-sm leading-relaxed text-muted-foreground md:text-base">
                        {heroSynopsis}
                      </p>
                    )}
                    {currentSpotlight.genres &&
                      currentSpotlight.genres.length > 0 && (
                        <div className="mb-6 flex flex-wrap gap-2">
                          {currentSpotlight.genres.slice(0, 3).map((genre) => (
                            <GenreChip
                              key={genre.slug}
                              label={genre.name_en ?? genre.slug}
                              labelJa={genre.name_ja}
                            />
                          ))}
                        </div>
                      )}
                    <div className="flex flex-wrap items-center gap-4">
                      {heroReadableHref && (
                        <Link
                          href={heroReadableHref}
                          className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-foreground px-6 text-sm font-semibold text-background shadow-md transition-colors hover:bg-primary hover:text-primary-foreground"
                        >
                          <BookOpen className="h-4 w-4" aria-hidden="true" />
                          Start Reading
                        </Link>
                      )}
                      <Link
                        href={publicNovelHref(currentSpotlight.slug)}
                        className="inline-flex h-11 items-center justify-center gap-1.5 rounded-md bg-card/60 px-5 text-sm font-medium text-foreground backdrop-blur-sm transition-colors hover:bg-muted"
                      >
                        Novel Details
                        <ChevronRight
                          className="h-4 w-4 text-muted-foreground"
                          aria-hidden="true"
                        />
                      </Link>
                    </div>
                  </div>

                  {/* Asymmetric cover card (editorial focal point; stacks above copy on mobile) */}
                  <div className="order-1 flex justify-center lg:order-2 lg:justify-end lg:pr-2">
                    <Link
                      href={publicNovelHref(currentSpotlight.slug)}
                      aria-label={`Open details for ${currentSpotlight.title}`}
                      className="block w-36 shrink-0 rounded-md bg-card p-1.5 shadow-raised ring-1 ring-border/40 transition-transform duration-300 ease-out hover:-rotate-1 hover:scale-[1.02] sm:w-44 lg:w-56"
                    >
                      <FallbackCover
                        title={currentSpotlight.title}
                        sourceTitle={currentSpotlight.source_title}
                        language={currentSpotlight.language}
                        status={currentSpotlight.publication_status}
                        genres={currentSpotlight.genres}
                        className="rounded-sm"
                      />
                    </Link>
                  </div>
                </div>
              </>
            ) : (
              /* Catalog Fallback Hero when catalog has 0 novels or loading error */
              <>
                <div className="absolute inset-0 bg-gradient-to-br from-primary/15 via-card to-background" />
                <div className="relative z-10 flex flex-col justify-between gap-6 p-6 sm:p-8 lg:p-10">
                  <div className="max-w-2xl">
                    <span className="mb-2 inline-block font-metadata text-xs font-semibold uppercase tracking-wider text-primary">
                      Welcome to Dokushodo
                    </span>
                    <h1 className="mb-3 font-literary text-3xl font-semibold leading-tight text-foreground sm:text-4xl">
                      The Way of Reading
                    </h1>
                    <p className="text-sm leading-relaxed text-muted-foreground md:text-base">
                      Discover translated Japanese web novels in a quiet,
                      tactile paperback aesthetic. Explore our catalog or submit
                      new novel requests.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-4">
                    <Link
                      href="/browse-novels"
                      className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-foreground px-6 text-sm font-semibold text-background shadow-md transition-colors hover:bg-primary hover:text-primary-foreground"
                    >
                      <BookOpen className="h-4 w-4" aria-hidden="true" />
                      Browse Catalog
                    </Link>
                    <Link
                      href="/account/request-novels"
                      className="inline-flex h-11 items-center justify-center gap-1.5 rounded-md bg-card/60 px-5 text-sm font-medium text-foreground backdrop-blur-sm transition-colors hover:bg-muted"
                    >
                      Request a Novel
                      <ChevronRight
                        className="h-4 w-4 text-muted-foreground"
                        aria-hidden="true"
                      />
                    </Link>
                  </div>
                </div>
              </>
            )}
          </section>

          {/* Continue reading shelf or Guest login prompt (Above shortcuts) */}
          {isAuthenticated && continueNovels.length > 0 ? (
            <NovelRail
              title="Continue Reading"
              ariaLabel="Continue reading"
              seeAllHref="/account/history"
            >
              {continueNovels.map((novel) => (
                <RailCard
                  key={novel.novel_id}
                  novel={novel}
                  nowMs={nowMs}
                  lastReadChapter={historyBySlug.get(novel.slug)}
                />
              ))}
            </NovelRail>
          ) : !isAuthenticated ? (
            <section
              aria-label="Guest reading prompt"
              className={cn(
                CARD_SURFACE,
                "flex flex-col items-center justify-between gap-3 rounded-lg px-4 py-3 sm:flex-row sm:px-6",
              )}
            >
              <div className="flex items-center gap-3 text-center sm:text-left">
                <div className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary sm:flex">
                  <BookOpen className="h-4.5 w-4.5" aria-hidden="true" />
                </div>
                <div>
                  <p className="font-literary text-sm font-semibold text-foreground">
                    Keep track of your reading progress
                  </p>
                  <p className="font-metadata text-xs text-muted-foreground">
                    Sign in to bookmark chapters, sync reading history, and
                    resume where you left off.
                  </p>
                </div>
              </div>
              <Link
                href="/login"
                className="inline-flex h-9 shrink-0 items-center justify-center rounded-md bg-foreground px-4 text-xs font-semibold text-background shadow-xs transition-colors hover:bg-primary hover:text-primary-foreground"
              >
                Sign In
              </Link>
            </section>
          ) : null}

          {/* Discovery banner tiles (Quick shortcuts with background art) */}
          <section
            aria-label="Discovery shortcuts"
            className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-4"
          >
            <ImageBannerTile
              href="/browse-novels"
              icon={Compass}
              title="Browse Novels"
              subtitle="Full Catalog"
              bgImage="/assets/shortcuts/browse-novels.svg"
            />
            <ImageBannerTile
              href="/ranking"
              icon={Trophy}
              title="Ranking"
              subtitle="Top Series"
              bgImage="/assets/shortcuts/ranking.svg"
            />
            <ImageBannerTile
              href="/random"
              icon={Shuffle}
              title="Random Novel"
              subtitle="Let chance decide"
              bgImage="/assets/shortcuts/random-novel.svg"
            />
            <ImageBannerTile
              href="/account/request-novels"
              icon={FilePlus2}
              title="Request Novel"
              subtitle="Ask for a translation"
              bgImage="/assets/shortcuts/request-novel.svg"
            />
          </section>

          {/* New releases grid (Stitch "New Novels") */}
          <section aria-label="New releases" className="flex flex-col gap-6">
            <div className="flex items-end justify-between border-b border-border/20 pb-2">
              <h2 className="font-literary text-2xl font-semibold text-foreground">
                New Novels
              </h2>
              <Link
                href="/browse-novels?sort_by=added_at&order=desc"
                className="rounded-sm bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                See More
              </Link>
            </div>
            {isPending ? (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div
                    key={i}
                    className="animate-pulse rounded-lg bg-card p-2.5 shadow-card"
                  >
                    <div className="aspect-[2/3] w-full rounded bg-muted/60" />
                    <div className="mt-2.5 h-4 w-3/4 rounded bg-muted/60" />
                    <div className="mt-2 h-3 w-1/2 rounded bg-muted/40" />
                  </div>
                ))}
              </div>
            ) : newReleases.length > 0 ? (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
                {newReleases.map((novel) => (
                  <Link
                    key={novel.novel_id}
                    href={publicNovelHref(novel.slug)}
                    className={cn(
                      CARD_SURFACE,
                      CARD_LIFT,
                      "group flex flex-col gap-2 rounded-lg p-2.5",
                    )}
                  >
                    <div className="relative aspect-[2/3] w-full overflow-hidden rounded-sm bg-muted">
                      {isNewlyAdded(novel.added_at, nowMs) && <NewBadge />}
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
                        <span className="rounded-sm bg-muted px-1.5 py-0.5 font-metadata text-[10px] text-muted-foreground">
                          {novel.genres?.[0]?.name_en ??
                            novel.genres?.[0]?.slug ??
                            "Web Novel"}
                        </span>
                        <span className="font-metadata text-[10px] text-muted-foreground">
                          {novel.translated_count > 0
                            ? `${novel.translated_count} Ch`
                            : "Pending"}
                        </span>
                      </div>
                      <p className="mt-1 font-metadata text-[10px] text-muted-foreground">
                        Added {relativeTime(novel.added_at, nowMs) ?? "recently"}
                      </p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="rounded-lg bg-muted/60 p-8 text-center text-sm text-muted-foreground">
                Catalog empty — new translations added regularly.
              </div>
            )}
          </section>

          {/* Recently updated list */}
          <section
            aria-label="Recently updated"
            className="flex flex-col gap-6"
          >
            <div className="flex items-end justify-between border-b border-border/20 pb-2">
              <h2 className="font-literary text-2xl font-semibold text-foreground">
                Recent Updates
              </h2>
              <Link
                href="/browse-novels?sort_by=updated_at&order=desc"
                className="rounded-sm bg-muted/50 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                See More
              </Link>
            </div>
            <div className={cn(CARD_SURFACE, "flex flex-col rounded-lg")}>
              {recentlyUpdated.length > 0 ? (
                recentlyUpdated
                  .slice(0, 6)
                  .map((novel) => (
                    <RecentUpdateItem
                      key={novel.novel_id}
                      novel={novel}
                      nowMs={nowMs}
                    />
                  ))
              ) : (
                <div className="p-6 text-center text-sm text-muted-foreground">
                  No recent chapter updates yet.
                </div>
              )}
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
                .filter((novel) =>
                  novel.genres?.some((item) => item.slug === slug),
                )
                .slice(0, 12)
                .map((novel) => (
                  <RailCard
                    key={novel.novel_id}
                    novel={novel}
                    nowMs={nowMs}
                  />
                ))}
            </NovelRail>
          ))}

          {/* Community & Translation Request callout */}
          <section
            aria-label="Community & Requests"
            className={cn(CARD_SURFACE, "rounded-xl p-6 sm:p-8")}
          >
            <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
              <div className="space-y-2">
                <div className="inline-flex items-center gap-1.5 text-xs font-medium text-primary">
                  <span className="font-metadata uppercase tracking-wider">
                    Community Requests
                  </span>
                </div>
                <h2 className="font-literary text-2xl font-semibold text-foreground">
                  Can&apos;t find the novel you&apos;re looking for?
                </h2>
                <p className="max-w-xl text-sm leading-relaxed text-muted-foreground">
                  Submit web novel links (Syosetu, Kakuyomu, Hameln) to our
                  community queue for machine-assisted translation.
                </p>
              </div>
              <Link
                href="/account/request-novels"
                className="inline-flex h-11 shrink-0 items-center justify-center gap-2.5 rounded-md border border-primary/30 bg-primary/10 px-6 font-medium text-primary shadow-sm transition-all hover:bg-primary hover:text-primary-foreground"
              >
                <FilePlus2 className="h-4 w-4" />
                <span>Request Translation</span>
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
                href={`/ranking?period=${rankingTab}`}
                className="rounded-sm bg-muted/50 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                See More
              </Link>
            }
          >
            <div className="flex gap-4 border-b border-border/20 px-4 pt-3 pb-2 text-xs font-medium text-muted-foreground">
              <button
                type="button"
                onClick={() => setRankingTab("daily")}
                className={cn(
                  "pb-1 transition-colors cursor-pointer",
                  rankingTab === "daily"
                    ? "border-b-2 border-primary font-semibold text-primary"
                    : "hover:text-foreground",
                )}
              >
                Daily
              </button>
              <button
                type="button"
                onClick={() => setRankingTab("weekly")}
                className={cn(
                  "pb-1 transition-colors cursor-pointer",
                  rankingTab === "weekly"
                    ? "border-b-2 border-primary font-semibold text-primary"
                    : "hover:text-foreground",
                )}
              >
                Weekly
              </button>
              <button
                type="button"
                onClick={() => setRankingTab("monthly")}
                className={cn(
                  "pb-1 transition-colors cursor-pointer",
                  rankingTab === "monthly"
                    ? "border-b-2 border-primary font-semibold text-primary"
                    : "hover:text-foreground",
                )}
              >
                Monthly
              </button>
            </div>
            <ul className="flex flex-col gap-1 p-2">
              {ranked.length > 0 ? (
                ranked.slice(0, 3).map((ranking) => (
                  <RankedItem key={ranking.novel.novel_id} ranking={ranking} />
                ))
              ) : (
                <li className="p-4 text-center text-xs text-muted-foreground">
                  {rankingQuery.isPending ? "Loading ranking data…" : "Ranking data unavailable"}
                </li>
              )}
            </ul>
          </WidgetCard>

          {/* Latest News */}
          <WidgetCard
            title="Latest News"
            action={
              <Link
                href="/news"
                className="rounded-sm bg-muted/50 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
              >
                View All
              </Link>
            }
          >
            <ul className="flex flex-col gap-3 p-4">
              <li>
                <Link href="/news" className="group block">
                  <span className="font-literary text-xs font-medium text-foreground transition-colors group-hover:text-primary">
                    FAQ, news, and your reviews
                  </span>
                  <span className="mt-0.5 block font-metadata text-[11px] text-muted-foreground">
                    August 2026
                  </span>
                </Link>
              </li>
              <li>
                <Link href="/news" className="group block">
                  <span className="font-literary text-xs font-medium text-foreground transition-colors group-hover:text-primary">
                    Library board and account shell
                  </span>
                  <span className="mt-0.5 block font-metadata text-[11px] text-muted-foreground">
                    August 2026
                  </span>
                </Link>
              </li>
              <li>
                <Link href="/news" className="group block">
                  <span className="font-literary text-xs font-medium text-foreground transition-colors group-hover:text-primary">
                    Reader settings, progress, and resume
                  </span>
                  <span className="mt-0.5 block font-metadata text-[11px] text-muted-foreground">
                    August 2026
                  </span>
                </Link>
              </li>
            </ul>
          </WidgetCard>

          {/* Trending uses the weekly unique-novel-view ranking. */}
          <WidgetCard
            title="Trending"
            action={
              <Link href="/ranking?period=weekly" className="text-xs text-muted-foreground hover:text-primary">
                Weekly
              </Link>
            }
            className="flex h-full flex-col p-6 [&>div:first-child]:mb-6 [&>div:first-child]:border-b [&>div:first-child]:border-border/20 [&>div:first-child]:p-0 [&>div:first-child]:pb-4"
          >
            <ul className="flex flex-1 flex-col gap-5">
              {trending.length > 0 ? (
                trending.map((ranking) => (
                  <TrendingItem
                    key={ranking.novel.novel_id}
                    ranking={ranking}
                  />
                ))
              ) : (
                <li className="py-4 text-center text-xs text-muted-foreground">
                  {trendingPending ? "Loading ranking data…" : "Ranking data unavailable"}
                </li>
              )}
            </ul>
            <Link
              href="/ranking?period=weekly"
              className="mt-6 inline-flex w-full items-center justify-center rounded-md bg-muted/50 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              View Full Ranking
            </Link>
          </WidgetCard>
        </aside>
      </div>
    </main>
  );
}
