"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { ReaderControls } from "@/components/public/reader-controls";
import { useChapter } from "@/hooks/public";
import { ApiError } from "@/lib/api";
import { toReaderError, widthClass } from "@/lib/public-format";
import { useReaderPrefsStore } from "@/lib/reader-prefs";

import "../../../../reader.css";

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

  const { data, isPending, isError, error } = useChapter(slug, chapterId);
  const { theme, fontSize, width } = useReaderPrefsStore();

  // 404: chapter-unavailable message
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
            href={`/novel/${encodeURIComponent(slug)}`}
            className="mt-4 inline-block text-sm underline hover:opacity-80"
          >
            Back to Novel
          </Link>
        </div>
      </div>
    );
  }

  // Other errors: sanitized error message via toReaderError
  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold">Error</h1>
          <p className="mt-2 text-sm opacity-70">{toReaderError(error)}</p>
          <Link
            href={`/novel/${encodeURIComponent(slug)}`}
            className="mt-4 inline-block text-sm underline hover:opacity-80"
          >
            Back to Novel
          </Link>
        </div>
      </div>
    );
  }

  // Loading indicator while pending
  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center p-8">
        <p className="text-sm opacity-70">Loading chapter…</p>
      </div>
    );
  }

  return (
    <div
      data-reader-theme={theme}
      className={`reader-container ${widthClass(width)}`}
      style={{ fontSize: `${fontSize}px` }}
    >
      {/* Controls bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <Link
          href={`/novel/${encodeURIComponent(slug)}`}
          className="text-sm opacity-75 hover:opacity-100"
        >
          ← Back to Novel
        </Link>
        <ReaderControls />
      </div>

      {/* Chapter header */}
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal">
          {data.title || `Chapter ${chapterId}`}
        </h1>
      </header>

      {/* Chapter text */}
      <article className="whitespace-pre-wrap font-serif leading-[1.9]">
        {data.text}
      </article>

      {/* Chapter navigation */}
      <nav className="mt-10 flex justify-between gap-3 border-t pt-5">
        {data.previous_chapter_id ? (
          <Link
            className="inline-flex h-9 items-center rounded-md border px-3 text-sm hover:opacity-80"
            href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(data.previous_chapter_id)}`}
          >
            ← Previous
          </Link>
        ) : (
          <span />
        )}
        {data.next_chapter_id ? (
          <Link
            className="inline-flex h-9 items-center rounded-md border px-3 text-sm hover:opacity-80"
            href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(data.next_chapter_id)}`}
          >
            Next →
          </Link>
        ) : (
          <span />
        )}
      </nav>
    </div>
  );
}
