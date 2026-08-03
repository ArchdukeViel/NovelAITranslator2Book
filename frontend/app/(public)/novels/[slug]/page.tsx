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
import { useChapters, useGenreLabelMap, useNovel, useProgress, usePublicAuth } from "@/hooks/public";

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
  return publicChapterHref(slug, chapterId);
}

type VolumeGroup = {
  label: string;
  chapters: PublicChapterSummary[];
};

function groupChaptersByVolume(chapters: PublicChapterSummary[], order: "asc" | "desc" = "asc"): VolumeGroup[] {
  const groups = new Map<string, VolumeGroup>();
  groups.set("", { label: "Chapters", chapters: [] });

  for (const ch of chapters) {
    const key = ch.part?.trim() || "";
    if (!groups.has(key)) {
      groups.set(key, { label: key, chapters: [] });
    }
    groups.get(key)!.chapters.push(ch);
  }

  // Build result sorted by the first chapter number in each group
  const groupsArray = Array.from(groups.values());
  for (const g of groupsArray) {
    g.chapters.sort((a, b) =>
      order === "asc"
        ? (a.chapter_number ?? 0) - (b.chapter_number ?? 0)
        : (b.chapter_number ?? 0) - (a.chapter_number ?? 0),
    );
  }
  groupsArray.sort((a, b) => {
    const aMin = Math.min(...a.chapters.map((c) => c.chapter_number ?? 0));
    const bMin = Math.min(...b.chapters.map((c) => c.chapter_number ?? 0));
    const result = aMin - bMin || a.label.localeCompare(b.label);
    return order === "asc" ? result : -result;
  });

  return groupsArray;
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
      className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
      href="/browse-novels"
    >
      <ArrowLeft className="h-4 w-4" />
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
  return (
    <div className={`group flex flex-col gap-3 border-b border-border/70 py-4 last:border-b-0 sm:flex-row sm:items-center sm:justify-between ${isRead ? "opacity-70" : ""}`}>
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
          {isRead && <span className="font-metadata">Read</span>}
          {isLastRead && <span className="rounded bg-primary/15 px-1.5 py-0.5 font-metadata text-primary">Last read</span>}
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
  const router = useRouter();
  const searchParams = useSearchParams();
  const slug = decodeURIComponent(params.slug);
  const { isAuthenticated, isPending: authPending } = usePublicAuth();

  const novel = useNovel(slug);
  const chapters = useChapters(slug);
  const progress = useProgress(slug);
  const genreLabels = useGenreLabelMap();
  const requestedTab = searchParams.get("tab");
  const activeTab = requestedTab === "chapters" || requestedTab === "reviews" ? requestedTab : "overview";
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
  const sortedChapters = chapters.data
    ? sortChaptersAscending(chapters.data)
    : [];
  const translatedChapters = sortedChapters.filter((chapter) => chapter.translated);
  const firstTranslatedChapter = translatedChapters[0] ?? null;
  const latestTranslatedChapter =
    translatedChapters[translatedChapters.length - 1] ?? null;
  const firstChapterId = firstTranslatedChapter?.chapter_id ?? null;
  const progressChapterId = progress.data?.chapter_id ?? null;
  const progressChapterNumber = progress.data?.chapter_number ?? null;
  const normalizedQuery = chapterQuery.trim().toLowerCase();
  const filteredChapters = sortedChapters.filter((chapter) => {
    if (!normalizedQuery) return true;
    return `${chapterDisplayTitle(chapter)} ${chapter.chapter_number ?? ""}`.toLowerCase().includes(normalizedQuery);
  });
  const orderedChapters = chapterOrder === "asc" ? filteredChapters : [...filteredChapters].reverse();
  const visibleChapters = orderedChapters.slice(0, chapterLimit);
  const firstUnread = sortedChapters.find(
    (chapter) => chapter.translated && (progressChapterNumber == null || (chapter.chapter_number ?? 0) > progressChapterNumber)
  );

  function setTab(tab: "overview" | "chapters" | "reviews") {
    const next = new URLSearchParams(searchParams.toString());
    if (tab === "overview") next.delete("tab");
    else next.set("tab", tab);
    router.push(`/novels/${encodeURIComponent(publicSlug)}${next.toString() ? `?${next}` : ""}`, { scroll: false });
  }

  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <BackToBrowse />

      <div className="mt-8 grid gap-8 lg:grid-cols-[280px_minmax(0,1fr)] lg:items-start">
        <aside className="lg:sticky lg:top-24">
          <div className="mx-auto w-full max-w-[260px] lg:mx-0">
            <FallbackCover genres={data.genres} language={data.language} sourceTitle={sourceTitle} status={data.publication_status} title={title} />
          </div>
          <h1 className="mt-5 font-literary text-3xl font-medium leading-tight">{title}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{authorOrFallback(data.author)}</p>
          {showSourceTitle && <p className="mt-2 font-literary text-sm text-accent"><span className="mr-1 font-metadata text-xs uppercase text-muted-foreground">Source title</span>{sourceTitle}</p>}
          <div className="mt-4"><StatusBadge status={data.publication_status} /></div>
          <NovelMetadataRow className="mt-4" chapterCount={data.chapter_count} translatedCount={data.translated_count} source={data.language} />
          <div className="fixed inset-x-0 bottom-0 z-40 flex items-center gap-3 border-t border-border bg-background p-3 shadow-lg lg:static lg:mt-5 lg:block lg:border-0 lg:bg-transparent lg:p-0 lg:shadow-none">
            <div className="flex h-12 w-9 shrink-0 items-center justify-center rounded bg-muted font-literary text-sm lg:hidden">{title.charAt(0)}</div>
            <span className="min-w-0 flex-1 truncate text-sm font-medium lg:hidden">{title}</span>
            <ContinueReading slug={publicSlug} firstChapterId={firstChapterId} allowGuestStart primary />
          </div>
          <div className="mt-4"><SaveToLibrary slug={publicSlug} /></div>
        </aside>

        <div className="min-w-0">
          <nav aria-label="Novel sections" className="sticky top-0 z-20 -mx-1 flex gap-1 overflow-x-auto border-b border-border bg-background/95 p-1 backdrop-blur">
            {(["overview", "chapters", "reviews"] as const).map((tab) => (
              <button key={tab} type="button" onClick={() => setTab(tab)} aria-current={activeTab === tab ? "page" : undefined} className={`shrink-0 rounded-md px-4 py-2 text-sm font-medium capitalize ${activeTab === tab ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted"}`}>
                {tab}
              </button>
            ))}
          </nav>

          {activeTab === "overview" && (
            <div className="space-y-8 py-8">
              <section>
                <h2 className="font-literary text-2xl font-semibold">About this story</h2>
                <p className="mt-4 leading-7 text-muted-foreground">{synopsis || "Synopsis unavailable for this novel."}</p>
              </section>
              {data.added_at && <p className="flex items-center gap-1.5 text-xs text-muted-foreground"><CalendarDays className="h-3.5 w-3.5" />Added {formatAddedDate(data.added_at)}</p>}
              {(data.genres?.length ?? 0) > 0 && <div className="flex flex-wrap gap-2">{(data.genres ?? []).map((genre) => <Link key={genre.slug} href={`/genres/${encodeURIComponent(genre.slug)}`}><GenreChip label={genreLabels?.get(genre.slug) ?? genre.slug} labelJa={genre.name_ja} /></Link>)}</div>}
              {(data.tags?.length ?? 0) > 0 && <div className="flex flex-wrap gap-2">{(data.tags ?? []).map((tag) => <Link key={tag.name} href={`/tags/${encodeURIComponent(tag.name)}`}><TagChip label={tag.name} labelJa={tag.name_ja} /></Link>)}</div>}
              <section className="rounded-lg bg-card/70 p-4 ring-1 ring-border"><div className="flex gap-3"><Flag className="h-4 w-4 text-muted-foreground" /><div><h2 className="text-sm font-medium">Report an issue</h2><p className="mt-1 text-sm">Found a problem? <Link href="/contact" className="text-accent underline">Contact us</Link>.</p></div></div></section>
              <RequestControl slug={publicSlug} />
            </div>
          )}

          {activeTab === "chapters" && (
            <section className="py-8">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><h2 className="font-literary text-2xl font-semibold">Chapters</h2><p className="mt-1 text-sm text-muted-foreground">{sortedChapters.length} total</p></div>
                <div className="flex flex-wrap gap-2">
                  {firstUnread && <a href={`#chapter-${firstUnread.chapter_id}`} className="rounded-md border border-border px-3 py-2 text-xs">First unread</a>}
                  {latestTranslatedChapter && <a href={`#chapter-${latestTranslatedChapter.chapter_id}`} className="rounded-md border border-border px-3 py-2 text-xs">Latest</a>}
                  <button type="button" onClick={() => setGroupsExpanded((value) => !value)} className="rounded-md border border-border px-3 py-2 text-xs">{groupsExpanded ? "Collapse all" : "Expand all"}</button>
                </div>
              </div>
              <div className="mt-5 flex flex-wrap gap-3">
                <label className="relative min-w-52 flex-1"><Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" /><span className="sr-only">Search chapters</span><input value={chapterQuery} onChange={(event) => { setChapterQuery(event.target.value); setChapterLimit(100); }} placeholder="Search chapters" className="h-10 w-full rounded-md border border-border bg-card pl-9 pr-3 text-sm" /></label>
                <button type="button" onClick={() => setChapterOrder((value) => value === "asc" ? "desc" : "asc")} className="rounded-md border border-border px-3 text-sm">{chapterOrder === "asc" ? "Ascending" : "Descending"}</button>
              </div>
              <div className="mt-5 rounded-lg bg-card/70 px-4 ring-1 ring-border sm:px-5">
                {chapters.isPending ? <div className="py-10 text-center">Loading chapters…</div> : chapters.isError ? <div className="py-10 text-center text-sm text-muted-foreground">Could not load chapters.</div> : visibleChapters.length === 0 ? <div className="py-10 text-center"><Library className="mx-auto h-10 w-10 text-muted-foreground/50" /><p className="mt-3 text-sm text-muted-foreground">No chapters matched.</p></div> : groupChaptersByVolume(visibleChapters, chapterOrder).map((group) => (
                  <details key={group.label} open={groupsExpanded} className="group/volume border-b border-border/70 last:border-b-0">
                    <summary className="flex cursor-pointer items-center justify-between py-3 text-sm font-medium"><span>{group.label}</span><span className="text-xs text-muted-foreground">{group.chapters.length}</span></summary>
                    <div className="border-t border-border/40">{group.chapters.map((chapter) => <div id={`chapter-${chapter.chapter_id}`} key={chapter.chapter_id}><ChapterRow chapter={chapter} slug={publicSlug} isLastRead={progressChapterId === chapter.chapter_id} isRead={progressChapterNumber != null && chapter.chapter_number != null && chapter.chapter_number <= progressChapterNumber} /></div>)}</div>
                  </details>
                ))}
              </div>
              {orderedChapters.length > chapterLimit && <button type="button" onClick={() => setChapterLimit((value) => value + 100)} className="mt-5 rounded-md border border-border px-4 py-2 text-sm">Show more chapters</button>}
            </section>
          )}

          {activeTab === "reviews" && (
            <div className="space-y-8 py-8">
              <RatingReview slug={publicSlug} />
              <CommunityReviews slug={publicSlug} />
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
