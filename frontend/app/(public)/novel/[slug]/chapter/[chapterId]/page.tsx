"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen, Flag } from "lucide-react";

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
      className="reader-nav flex flex-wrap items-center justify-between gap-3"
      aria-label="Chapter navigation"
    >
      <div className="flex flex-wrap items-center gap-2">
        {previousChapterId ? (
          <Link
            className="reader-nav-link"
            href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(previousChapterId)}`}
          >
            ← Previous
          </Link>
        ) : (
          <span className="reader-nav-disabled">← First chapter</span>
        )}
        <Link className="reader-nav-link" href={novelHref}>
          <BookOpen className="h-3.5 w-3.5" />
          All chapters
        </Link>
      </div>
      {nextChapterId ? (
        <Link
          className="reader-nav-link reader-nav-link-strong"
          href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(nextChapterId)}`}
        >
          Next →
        </Link>
      ) : (
        <span className="reader-nav-disabled">Latest chapter →</span>
      )}
    </nav>
  );
}

function ReaderMessage({
  children,
  theme,
  title,
  novelHref,
}: {
  children: React.ReactNode;
  theme: "light" | "dark" | "sepia";
  title: string;
  novelHref: string;
}) {
  return (
    <div data-reader-theme={theme} className="reader-container">
      <main className="reader-shell max-w-2xl">
        <Link href={novelHref} className="reader-back-link">
          <ArrowLeft className="h-4 w-4" />
          Back to Novel
        </Link>
        <section className="reader-state">
          <h1 className="font-literary text-2xl font-medium tracking-normal">
            {title}
          </h1>
          <div className="mt-3 text-sm reader-muted">{children}</div>
          <Link
            href="/browse-novels"
            className="mt-6 inline-flex items-center gap-1 text-sm underline reader-muted transition-colors hover:text-foreground"
          >
            <BookOpen className="h-4 w-4" />
            Browse the library
          </Link>
        </section>
      </main>
    </div>
  );
}

export default function ChapterPage() {
  const params = useParams<{ slug: string; chapterId: string }>();
  const slug = decodeURIComponent(params.slug);
  const chapterId = decodeURIComponent(params.chapterId);
  const novelHref = `/novel/${encodeURIComponent(slug)}`;

  const { data, isPending, isError, error } = useChapter(slug, chapterId);
  const { isAuthenticated } = usePublicAuth();
  const updateProgress = useUpdateProgress(slug);
  const recordHistory = useRecordHistory();
  const trackedChapterRef = useRef<string | null>(null);
  const { theme, fontSize, width } = useReaderPrefsStore();

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

  if (isError && error instanceof ApiError && error.status === 404) {
    return (
      <ReaderMessage
        title="Chapter Unavailable"
        theme={theme}
        novelHref={novelHref}
      >
        This chapter could not be found or is not available.
      </ReaderMessage>
    );
  }

  if (isError) {
    return (
      <ReaderMessage
        title="Something went wrong"
        theme={theme}
        novelHref={novelHref}
      >
        {toReaderError(error)}
      </ReaderMessage>
    );
  }

  if (isPending) {
    return (
      <div data-reader-theme={theme} className="reader-container">
        <main className="reader-shell max-w-2xl">
          <div className="reader-state">
            <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-current border-t-transparent opacity-60" />
            <p className="text-sm reader-muted">Loading chapter...</p>
          </div>
        </main>
      </div>
    );
  }

  const novelTitle = data.novel_title || slug;
  const chapterTitle = data.title || (data.chapter_number != null ? `Chapter ${data.chapter_number}` : "Untitled chapter");

  return (
    <div data-reader-theme={theme} className="reader-container">
      <main className={`reader-shell ${widthClass(width)}`}>
        <header className="reader-chrome">
          <div className="min-w-0">
            <Link href={novelHref} className="reader-back-link">
              <ArrowLeft className="h-4 w-4" />
              <span className="font-literary">{novelTitle}</span>
            </Link>
            <p className="mt-2 truncate text-xs font-metadata reader-muted">
              {data.chapter_number != null ? `Chapter ${data.chapter_number}` : "\u00a0"}
            </p>
          </div>
          <ReaderControls />
        </header>

        <ChapterNav
          slug={slug}
          previousChapterId={data.previous_chapter_id}
          nextChapterId={data.next_chapter_id}
          novelHref={novelHref}
        />

        <article className="reader-article">
          <header className="reader-title-block">
            <p className="font-metadata text-xs uppercase tracking-[0.22em] reader-muted">
              {novelTitle}
            </p>
            <h1 className="mt-4 font-literary text-3xl font-medium leading-tight tracking-normal md:text-4xl">
              {chapterTitle}
            </h1>
          </header>

          <div
            className="reader-text whitespace-pre-wrap font-literary"
            style={{ fontSize: `${fontSize}px` }}
          >
            {data.text}
          </div>
        </article>

        <section className="reader-report" aria-label="Report chapter issue">
          <Flag className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            Found a problem with this chapter?{" "}
            <Link
              href="/contact"
              className="underline transition-colors hover:text-foreground"
            >
              Contact us
            </Link>{" "}
            to report it.
          </p>
        </section>

        <div className="reader-bottom-nav">
          <ChapterNav
            slug={slug}
            previousChapterId={data.previous_chapter_id}
            nextChapterId={data.next_chapter_id}
            novelHref={novelHref}
          />
        </div>
      </main>
    </div>
  );
}
