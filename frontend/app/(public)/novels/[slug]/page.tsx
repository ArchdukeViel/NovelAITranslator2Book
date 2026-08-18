"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  CalendarDays,
  Clock,
  Flag,
  Library,
  Search,
} from "lucide-react";

import { ContinueReading } from "@/components/public/continue-reading";
import { FallbackCover } from "@/components/public/fallback-cover";
import { GenreChip, TagChip } from "@/components/public/genre-chip";
import { NovelMetadataRow } from "@/components/public/novel-metadata-row";
import { RatingReview } from "@/components/public/rating-review";
import { RequestControl } from "@/components/public/request-control";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { CommunityReviews } from "@/components/public/community-reviews";
import { StatusBadge } from "@/components/public/status-badge";
import { ApiError } from "@/lib/api";
import { ErrorState, LoadingState } from "@/components/ui/page-state";
import {
  authorOrFallback,
  sortChaptersAscending,
} from "@/lib/public-format";
import { publicChapterHref } from "@/lib/public-routes";
import type { PublicChapterSummary } from "@/lib/public-types";
import { useChapters, useGenreLabelMap, useNovel, useProgress } from "@/hooks/public";

type NovelTab = "overview" | "chapters" | "reviews";

const NOVEL_TABS: ReadonlyArray<{ id: NovelTab; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "chapters", label: "Chapters" },
  { id: "reviews", label: "Reviews" },
];

function formatLanguage(value: string | null | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed.toLowerCase().replaceAll("_", "-");
  if (normalized === "ja" || normalized.startsWith("ja-") || normalized.includes("japanese") || trimmed === "日本語") {
    return "Japanese";
  }
  if (normalized === "zh" || normalized.startsWith("zh-") || normalized.includes("chinese") || trimmed === "中文") {
    return "Chinese";
  }
  if (normalized === "ko" || normalized.startsWith("ko-") || normalized.includes("korean") || trimmed === "한국어") {
    return "Korean";
  }
  if (normalized === "en" || normalized.startsWith("en-") || normalized.includes("english")) {
    return "English";
  }
  return trimmed;
}

function isJapaneseLanguage(value: string | null | undefined): boolean {
  const normalized = value?.trim().toLowerCase().replaceAll("_", "-");
  return Boolean(
    normalized &&
      (normalized === "ja" || normalized.startsWith("ja-") || normalized.includes("japanese") || normalized === "日本語")
  );
}

function chapterDisplayTitle(chapter: PublicChapterSummary): string {
  return chapter.title?.trim() || `Chapter ${chapter.chapter_number ?? chapter.chapter_id}`;
}

function hasSourceNumber(chapter: PublicChapterSummary): boolean {
  if (chapter.chapter_number === null || chapter.chapter_number === undefined || !chapter.title?.trim()) {
    return false;
  }

  const number = String(chapter.chapter_number);
  return new RegExp(`(?:^|[^0-9])${number}(?:[^0-9]|$)`).test(chapter.title);
}

function shouldShowGeneratedChapterNumber(chapter: PublicChapterSummary): boolean {
  return Boolean(chapter.title?.trim()) && chapter.chapter_number !== null && chapter.chapter_number !== undefined && !hasSourceNumber(chapter);
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
  return publicChapterHref(slug, chapterId);
}

function chapterAnchorId(chapterId: string): string {
  return `chapter-${encodeURIComponent(chapterId)}`;
}

type VolumeGroup = {
  key: string;
  label: string;
  ordinal: number | null;
  chapters: PublicChapterSummary[];
};

function chapterSectionKey(chapter: PublicChapterSummary): string | null {
  const sourceId = chapter.section_source_id?.trim();
  if (sourceId) {
    return `source:${sourceId}`;
  }
  if (chapter.section_ordinal !== null && chapter.section_ordinal !== undefined) {
    return `ordinal:${chapter.section_ordinal}`;
  }
  const title = chapter.section_title?.trim() || chapter.part?.trim();
  return title ? `legacy:${title}` : null;
}

function groupChaptersByVolume(chapters: PublicChapterSummary[]): VolumeGroup[] {
  const groups: VolumeGroup[] = [];
  const hasSections = chapters.some((chapter) => chapterSectionKey(chapter) !== null);
  let lastGroupKey: string | null = null;

  for (const chapter of chapters) {
    const sectionKey = chapterSectionKey(chapter);
    const groupKey = sectionKey ?? (hasSections ? "ungrouped" : "flat");
    let group = groups.at(-1);
    if (!group || lastGroupKey !== groupKey) {
      const label =
        chapter.section_title?.trim() ||
        chapter.part?.trim() ||
        (sectionKey ? `Section ${chapter.section_ordinal ?? ""}`.trim() : "");
      group = {
        key: `${groupKey}:run:${groups.length}`,
        label: label || (hasSections ? "Chapters" : ""),
        ordinal: chapter.section_ordinal ?? null,
        chapters: [],
      };
      groups.push(group);
      lastGroupKey = groupKey;
    }
    group.chapters.push(chapter);
  }

  return groups;
}

function PageLoadingState() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />
      <LoadingState label="Loading novel details..." />
    </main>
  );
}

function BackToBrowse() {
  return (
    <Link
      className="inline-flex min-h-11 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      href="/browse-novels"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to Browse
    </Link>
  );
}

function PageErrorState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />
      <div className="mt-12">
        <ErrorState title={title} description={description} />
      </div>
    </main>
  );
}

function ChapterRow({
  chapter,
  slug,
  isLastRead,
  isRead,
}: {
  chapter: PublicChapterSummary;
  slug: string;
  isLastRead?: boolean;
  isRead?: boolean;
}) {
  const canRead = chapter.translated && (!chapter.availability_status || chapter.availability_status === "available");
  const availabilityLabel =
    chapter.availability_status === "unavailable" || chapter.availability_status === "refresh_failed"
      ? "Unavailable"
      : "Not translated";

  return (
    <div
      className={`group flex flex-col gap-3 border-b border-border/70 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between ${isRead ? "opacity-70" : ""}`}
    >
      <div className="min-w-0">
        <h3 className="break-words font-literary text-base font-medium transition-colors group-hover:text-accent">
          {chapterDisplayTitle(chapter)}
        </h3>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          {shouldShowGeneratedChapterNumber(chapter) && (
            <span className="font-metadata">Chapter {chapter.chapter_number}</span>
          )}
          {canRead && <span className="font-metadata text-accent">Translated</span>}
          {isRead && <span className="font-metadata">Read</span>}
          {isLastRead && (
            <span className="rounded bg-primary/15 px-1.5 py-0.5 font-metadata text-primary">
              Last read
            </span>
          )}
        </div>
      </div>
      {canRead ? (
        <Link
          className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-md border border-border bg-card px-3 text-sm font-medium transition-colors hover:bg-muted"
          href={chapterHref(slug, chapter.chapter_id)}
        >
          <BookOpen className="h-4 w-4" aria-hidden="true" />
          Read
        </Link>
      ) : (
        <span className="inline-flex min-h-11 shrink-0 items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" aria-hidden="true" />
          {availabilityLabel}
        </span>
      )}
    </div>
  );
}

export default function NovelDetailPage() {
  const params = useParams<{ slug: string }>();
  const router = useRouter();
  const searchParams = useSearchParams();
  const slug = decodeURIComponent(params.slug);

  const novel = useNovel(slug);
  const chapters = useChapters(slug);
  const progress = useProgress(slug);
  const genreLabels = useGenreLabelMap();
  const requestedTab = searchParams.get("tab");
  const activeTab: NovelTab =
    requestedTab === "chapters" || requestedTab === "reviews" ? requestedTab : "overview";
  const [chapterQuery, setChapterQuery] = useState("");
  const [chapterOrder, setChapterOrder] = useState<"asc" | "desc">("asc");
  const [groupsExpanded, setGroupsExpanded] = useState(true);
  const [chapterLimit, setChapterLimit] = useState(100);

  if (novel.isError) {
    const err = novel.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <PageErrorState
          title="Novel not found"
          description="The novel you're looking for doesn't exist or has been removed."
        />
      );
    }

    return (
      <PageErrorState
        title="Something went wrong"
        description="Could not load this novel. Try browsing the catalog or check back later."
      />
    );
  }

  if (novel.isPending) {
    return <PageLoadingState />;
  }

  const data = novel.data;
  const publicSlug = data.slug?.trim() || slug;
  const title = data.title || slug;
  const synopsis = data.synopsis?.trim();
  const sourceTitle = data.source_title?.trim();
  const showSourceTitle = Boolean(sourceTitle && sourceTitle !== title);
  const languageLabel = formatLanguage(data.language);
  const showJapaneseTaxonomy = isJapaneseLanguage(data.language);
  const sortedChapters = chapters.data ? sortChaptersAscending(chapters.data) : [];
  const readableChapters = sortedChapters.filter(
    (chapter) => chapter.translated && (!chapter.availability_status || chapter.availability_status === "available")
  );
  const firstTranslatedChapter = readableChapters[0] ?? null;
  const latestTranslatedChapter = readableChapters[readableChapters.length - 1] ?? null;
  const firstChapterId = firstTranslatedChapter?.chapter_id ?? null;
  const progressChapterId = progress.data?.chapter_id ?? null;
  const progressChapterNumber = progress.data?.chapter_number ?? null;
  const normalizedQuery = chapterQuery.trim().toLowerCase();
  const filteredChapters = sortedChapters.filter((chapter) => {
    if (!normalizedQuery) return true;
    return `${chapterDisplayTitle(chapter)} ${chapter.chapter_number ?? ""} ${chapter.section_title ?? ""}`
      .toLowerCase()
      .includes(normalizedQuery);
  });
  const orderedChapters = chapterOrder === "asc" ? filteredChapters : [...filteredChapters].reverse();
  const visibleChapters = orderedChapters.slice(0, chapterLimit);
  const firstUnread = sortedChapters.find(
    (chapter) =>
      chapter.translated &&
      (!chapter.availability_status || chapter.availability_status === "available") &&
      (progressChapterNumber == null || (chapter.chapter_number ?? 0) > progressChapterNumber)
  );

  function setTab(tab: NovelTab) {
    const next = new URLSearchParams(searchParams.toString());
    if (tab === "overview") next.delete("tab");
    else next.set("tab", tab);
    router.push(
      `/novels/${encodeURIComponent(publicSlug)}${next.toString() ? `?${next}` : ""}`,
      { scroll: false }
    );
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />

      <header className="mt-8 grid gap-6 border-b border-border/70 pb-8 lg:grid-cols-[220px_minmax(0,1fr)_auto] lg:items-end lg:gap-8">
        <div className="mx-auto w-full max-w-[220px] lg:mx-0">
          <FallbackCover
            genres={data.genres}
            language={data.language}
            sourceTitle={sourceTitle}
            status={data.publication_status}
            title={title}
          />
        </div>

        <div className="min-w-0">
          <h1 className="font-literary text-3xl font-medium leading-tight sm:text-4xl">
            {title}
          </h1>
          <p className="mt-3 text-base text-muted-foreground">{authorOrFallback(data.author)}</p>
          {showSourceTitle && (
            <p className="mt-2 break-words font-literary text-sm text-accent">
              <span className="mr-2 font-metadata text-xs uppercase text-muted-foreground">
                Source title
              </span>
              {sourceTitle}
            </p>
          )}
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <StatusBadge status={data.publication_status} />
            <NovelMetadataRow
              chapterCount={data.chapter_count}
              source={languageLabel}
              translatedCount={data.translated_count}
              updatedAt={data.latest_chapter_updated_at}
            />
          </div>
        </div>

        <div className="flex flex-col items-stretch gap-2 sm:flex-row lg:w-48 lg:flex-col">
          <ContinueReading
            allowGuestStart
            firstChapterId={firstChapterId}
            primary
            slug={publicSlug}
          />
          <SaveToLibrary compactGuest slug={publicSlug} />
        </div>
      </header>

      <nav
        aria-label="Novel sections"
        className="sticky top-0 z-20 -mx-1 mt-6 flex gap-1 overflow-x-auto border-b border-border bg-background/95 p-1 backdrop-blur"
        role="tablist"
      >
        {NOVEL_TABS.map((tab) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              aria-controls={`novel-panel-${tab.id}`}
              aria-selected={isActive}
              className={`min-h-11 shrink-0 rounded-md px-4 py-2 text-sm font-medium transition-colors ${isActive ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}
              id={`novel-tab-${tab.id}`}
              key={tab.id}
              onClick={() => setTab(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          );
        })}
      </nav>

      {activeTab === "overview" && (
        <section
          aria-labelledby="novel-tab-overview"
          className="space-y-8 py-8"
          id="novel-panel-overview"
          role="tabpanel"
          tabIndex={0}
        >
          <section>
            <h2 className="font-literary text-2xl font-semibold">About this story</h2>
            <p className="mt-4 leading-7 text-muted-foreground">
              {synopsis || "Synopsis unavailable for this novel."}
            </p>
          </section>

          {data.added_at && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <CalendarDays className="h-3.5 w-3.5" aria-hidden="true" />
              Added {formatAddedDate(data.added_at)}
            </p>
          )}

          {(data.genres?.length ?? 0) > 0 && (
            <section aria-labelledby="novel-genres-heading" className="space-y-2">
              <h3 className="text-sm font-medium" id="novel-genres-heading">
                Genres
              </h3>
              <div className="flex flex-wrap gap-2">
                {(data.genres ?? []).map((genre) => (
                  <Link
                    href={`/genres/${encodeURIComponent(genre.slug)}`}
                    key={genre.slug}
                    className="min-h-11 inline-flex items-center"
                  >
                    <GenreChip
                      label={genreLabels?.get(genre.slug) ?? genre.slug}
                      labelJa={showJapaneseTaxonomy ? genre.name_ja : undefined}
                    />
                  </Link>
                ))}
              </div>
            </section>
          )}

          {(data.tags?.length ?? 0) > 0 && (
            <section aria-labelledby="novel-tags-heading" className="space-y-2">
              <h3 className="text-sm font-medium" id="novel-tags-heading">
                Tags
              </h3>
              <div className="flex flex-wrap gap-2">
                {(data.tags ?? []).map((tag) => (
                  <Link
                    href={`/tags/${encodeURIComponent(tag.name)}`}
                    key={tag.name}
                    className="min-h-11 inline-flex items-center"
                  >
                    <TagChip
                      label={tag.name}
                      labelJa={showJapaneseTaxonomy ? tag.name_ja : undefined}
                    />
                  </Link>
                ))}
              </div>
            </section>
          )}

          <div className="border-t border-border/60 pt-4">
            <Link
              className="inline-flex min-h-11 items-center gap-2 text-sm text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline"
              href="/contact"
            >
              <Flag className="h-4 w-4" aria-hidden="true" />
              Report an issue
            </Link>
          </div>
        </section>
      )}

      {activeTab === "chapters" && (
        <section
          aria-labelledby="novel-tab-chapters"
          className="py-8"
          id="novel-panel-chapters"
          role="tabpanel"
          tabIndex={0}
        >
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-literary text-2xl font-semibold">Chapters</h2>
              <p className="mt-1 text-sm text-muted-foreground">{sortedChapters.length} total</p>
            </div>
            <div className="flex flex-wrap gap-2">
              {firstUnread && (
                <a
                  className="inline-flex min-h-11 items-center rounded-md border border-border px-3 py-2 text-xs"
                  href={`#${chapterAnchorId(firstUnread.chapter_id)}`}
                >
                  First unread
                </a>
              )}
              {latestTranslatedChapter && (
                <a
                  className="inline-flex min-h-11 items-center rounded-md border border-border px-3 py-2 text-xs"
                  href={`#${chapterAnchorId(latestTranslatedChapter.chapter_id)}`}
                >
                  Latest
                </a>
              )}
              <button
                className="min-h-11 rounded-md border border-border px-3 py-2 text-xs"
                onClick={() => setGroupsExpanded((value) => !value)}
                type="button"
              >
                {groupsExpanded ? "Collapse all" : "Expand all"}
              </button>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <label className="relative min-w-52 flex-1">
              <Search
                aria-hidden="true"
                className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
              />
              <span className="sr-only">Search chapters</span>
              <input
                className="h-11 w-full rounded-md border border-border bg-card pl-9 pr-3 text-sm"
                onChange={(event) => {
                  setChapterQuery(event.target.value);
                  setChapterLimit(100);
                }}
                placeholder="Search chapters"
                value={chapterQuery}
              />
            </label>
            <button
              className="min-h-11 rounded-md border border-border px-3 text-sm"
              onClick={() => setChapterOrder((value) => (value === "asc" ? "desc" : "asc"))}
              type="button"
            >
              {chapterOrder === "asc" ? "Ascending" : "Descending"}
            </button>
          </div>

          <div className="mt-5 rounded-md border border-border bg-card/70 px-4 sm:px-5">
            {chapters.isPending ? (
              <div className="py-10 text-center">Loading chapters...</div>
            ) : chapters.isError ? (
              <div className="py-10 text-center text-sm text-muted-foreground">
                Could not load chapters.
              </div>
            ) : visibleChapters.length === 0 ? (
              <div className="py-10 text-center">
                <Library className="mx-auto h-10 w-10 text-muted-foreground/50" aria-hidden="true" />
                <p className="mt-3 text-sm text-muted-foreground">No chapters matched.</p>
              </div>
            ) : (
              groupChaptersByVolume(visibleChapters).map((group) =>
                group.label ? (
                  <details
                    className="group/volume border-b border-border/70 last:border-b-0"
                    key={group.key}
                    open={groupsExpanded}
                  >
                    <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 py-3 text-sm font-medium">
                      <span className="break-words">{group.label}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {group.chapters.length}
                      </span>
                    </summary>
                    <div className="border-t border-border/40">
                      {group.chapters.map((chapter) => (
                        <div id={chapterAnchorId(chapter.chapter_id)} key={chapter.chapter_id}>
                          <ChapterRow
                            chapter={chapter}
                            isLastRead={progressChapterId === chapter.chapter_id}
                            isRead={
                              progressChapterNumber != null &&
                              chapter.chapter_number != null &&
                              chapter.chapter_number <= progressChapterNumber
                            }
                            slug={publicSlug}
                          />
                        </div>
                      ))}
                    </div>
                  </details>
                ) : (
                  <div key={group.key}>
                    {group.chapters.map((chapter) => (
                      <div id={chapterAnchorId(chapter.chapter_id)} key={chapter.chapter_id}>
                        <ChapterRow
                          chapter={chapter}
                          isLastRead={progressChapterId === chapter.chapter_id}
                          isRead={
                            progressChapterNumber != null &&
                            chapter.chapter_number != null &&
                            chapter.chapter_number <= progressChapterNumber
                          }
                          slug={publicSlug}
                        />
                      </div>
                    ))}
                  </div>
                )
              )
            )}
          </div>

          {orderedChapters.length > chapterLimit && (
            <button
              className="mt-5 min-h-11 rounded-md border border-border px-4 py-2 text-sm"
              onClick={() => setChapterLimit((value) => value + 100)}
              type="button"
            >
              Show more chapters
            </button>
          )}

          <details className="mt-8 border-t border-border/60 pt-5">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium">
              <span>Request translation</span>
              <span className="text-xs font-normal text-muted-foreground">
                Missing or untranslated chapter?
              </span>
            </summary>
            <div className="pt-4">
              <RequestControl slug={publicSlug} />
            </div>
          </details>
        </section>
      )}

      {activeTab === "reviews" && (
        <section
          aria-labelledby="novel-tab-reviews"
          className="space-y-8 py-8"
          id="novel-panel-reviews"
          role="tabpanel"
          tabIndex={0}
        >
          <h2 className="font-literary text-2xl font-semibold">Reviews</h2>
          <RatingReview slug={publicSlug} />
          <CommunityReviews slug={publicSlug} />
        </section>
      )}
    </main>
  );
}
