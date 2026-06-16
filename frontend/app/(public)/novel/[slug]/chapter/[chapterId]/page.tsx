"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen } from "lucide-react";

import { ReaderControls } from "@/components/public/reader-controls";
import {
  useChapter,
  usePublicAuth,
  useRecordHistory,
  useUpdateProgress,
} from "@/hooks/public";
import { ApiError } from "@/lib/api";
import { toReaderError, widthClass } from "@/lib/public-format";
import { useReaderPrefsStore } from "@/lib/reader-prefs";

import "../../../../reader.css";

/**
 * ChapterNav — reusable previous/next navigation component.
 * Used at both top and bottom of the reader.
 */
function ChapterNav({
  slug,
  previousChapterId,
  nextChapterId,
  novelHref,
}: {
  slug: string;
  previousChapterId: string | null;
  nextChapterId: string | null;
  novelHref: string;
}) {
  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3"
      aria-label="Chapter navigation"
    >
      <div className="flex items-center gap-3">
        {previousChapterId ? (
          <Link
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors hover:bg-muted"
            href={`/novels/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(previousChapterId)}`}
          >
            ← Previous
          </Link>
        ) : (
          <span className="inline-flex h-9 items-center rounded-md border px-3 text-sm opacity-40 select-none">
            ← First chapter
          </span>
        )}
        <Link
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors hover:bg-muted"
          href={novelHref}
        >
          <BookOpen className="h-3.5 w-3.5" />
          All chapters
        </Link>
      </div>
      {nextChapterId ? (
        <Link
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors hover:bg-muted"
          href={`/novels/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(nextChapterId)}`}
        >
          Next →
        </Link>
      ) : (
        <span className="inline-flex h-9 items-center rounded-md border px-3 text-sm opacity-40 select-none">
          Latest chapter →
        </span>
      )}
    </nav>
  );
}

/**
 * Reader_View — chapter reading page with theme, font-size, and width controls.
 * Uses the public-scoped useChapter hook (no owner credential).
 * Theme applied via data-reader-theme attribute; NEVER toggles html.dark.
 * Requirements: 5.1–5.8, 6.1–6.8, 15.1, 15.4
 */
export default function ChapterPage() {
  const params = useParams<{ slug: string; chapterId: string }>();
  const slug = decodeURIComponent(params.slug);
  const chapterId = decodeURIComponent(params.chapterId);
  const novelHref = `/novels/${encodeURIComponent(slug)}`;

  const { data, isPending, isError, error } = useChapter(slug, chapterId);
  const { isAuthenticated } = usePublicAuth();
  const updateProgress = useUpdateProgress(slug);
  const recordHistory = useRecordHistory();
  const trackedChapterRef = useRef<string | null>(null);
  const { theme, fontSize, width } = useReaderPrefsStore();

  // --- Reading progress / history tracking (unchanged) ---
  useEffect(() => {
    if (!isAuthenticated || !data || trackedChapterRef.current === chapterId) {
      return;
    }
    trackedChapterRef.current = chapterId;
    updateProgress.mutate({
      chapter_id: chapterId,
      progress_percent: 0,
    });
    recordHistory.mutate({
      slug,
      chapter_id: chapterId,
    });
  }, [chapterId, data, isAuthenticated, recordHistory, slug, updateProgress]);

  // --- 404: chapter-unavailable message ---
  if (
    isError &&
    error instanceof ApiError &&
    error.status === 404
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Chapter Unavailable</h1>
          <p className="mt-2 text-sm opacity-70">
            This chapter could not be found or is not available.
          </p>
          <Link
            href={novelHref}
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium underline hover:opacity-80"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Novel
          </Link>
        </div>
      </div>
    );
  }

  // --- Other errors: sanitized error message via toReaderError ---
  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="mt-2 text-sm opacity-70">{toReaderError(error)}</p>
          <Link
            href={novelHref}
            className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium underline hover:opacity-80"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Novel
          </Link>
        </div>
      </div>
    );
  }

  // --- Loading state: reader-themed skeleton, not generic spinner ---
  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground" />
          <p className="text-sm opacity-70">Loading chapter…</p>
        </div>
      </div>
    );
  }

  // --- Main reader view ---
  const novelTitle = data.novel_title || slug;
  const chapterTitle = data.title || `Chapter ${chapterId}`;

  return (
    <div
      data-reader-theme={theme}
      className={`reader-container ${widthClass(width)}`}
      style={{ fontSize: `${fontSize}px` }}
    >
      {/* Breadcrumb / header bar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 text-sm">
          <Link
            href={novelHref}
            className="inline-flex items-center gap-1.5 opacity-75 hover:opacity-100"
          >
            <ArrowLeft className="h-4 w-4" />
            {novelTitle}
          </Link>
          <span className="opacity-40 select-none">/</span>
          <span className="opacity-75">{chapterTitle}</span>
        </div>
        <ReaderControls />
      </div>
      <div className="mb-4 rounded-md border px-3 py-2 text-sm opacity-80">
        <div className="flex items-start gap-2">
          <BookOpen className="mt-0.5 h-4 w-4" />
          <p>
            Report chapter issue for this chapter will be connected in a later backend phase.
          </p>
        </div>
      </div>

      {/* Top chapter navigation */}
      <ChapterNav
        slug={slug}
        previousChapterId={data.previous_chapter_id}
        nextChapterId={data.next_chapter_id}
        novelHref={novelHref}
      />

      {/* Chapter header */}
      <header className="mt-8 mb-8">
        <h1 className="text-3xl font-semibold tracking-normal">
          {chapterTitle}
        </h1>
        {data.novel_title && (
          <p className="mt-1 text-sm opacity-60">
            from {novelTitle}
          </p>
        )}
      </header>

      {/* Chapter text */}
      <article className="reader-text whitespace-pre-wrap font-serif leading-[1.9]">
        {data.text}
      </article>

      {/* Bottom chapter navigation */}
      <div className="mt-10 border-t pt-5">
        <ChapterNav
          slug={slug}
          previousChapterId={data.previous_chapter_id}
          nextChapterId={data.next_chapter_id}
          novelHref={novelHref}
        />
      </div>
    </div>
  );
}
