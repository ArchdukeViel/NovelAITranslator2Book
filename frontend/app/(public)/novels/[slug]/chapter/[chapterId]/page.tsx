"use client";

import { Fragment, useEffect, useRef } from "react";
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
import { widthClass } from "@/lib/public-format";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
import type { PublicReaderBlock } from "@/lib/public-types";
import { useReaderPrefsStore } from "@/lib/reader-prefs";

import "../../../../reader.css";

const protocolMarkerPattern = /^\s*(?:\[CHAPTER[^\]]*\]|\[P\s+p\d{4}\])\s*/i;

function readerDisplayText(text: string): string {
  const lines: string[] = [];
  for (const line of text.split(/\r?\n/)) {
    let current = line;
    let hadMarker = false;
    while (protocolMarkerPattern.test(current)) {
      current = current.replace(protocolMarkerPattern, "");
      hadMarker = true;
    }
    if (hadMarker && current.trim() === "") {
      continue;
    }
    lines.push(current);
  }
  return lines.join("\n").replace(/\n+$/, "");
}

type ReaderDisplayBlock =
  | {
      type: "line";
      text: string;
    }
  | {
      type: "break";
    };

type ReaderDisplayGroup = {
  type: "group";
  lines: string[];
};

function readerDisplayBlocks(data: { text: string; reader_blocks?: PublicReaderBlock[] }): ReaderDisplayBlock[] {
  if (Array.isArray(data.reader_blocks)) {
    const blocks = data.reader_blocks.flatMap((block): ReaderDisplayBlock[] => {
      if (typeof block === "string") {
        const text = readerDisplayText(block).trim();
        return text ? [{ type: "line", text }] : [];
      }
      if (block?.type === "break") {
        return [{ type: "break" }];
      }
      const text = readerDisplayText(String(block?.text ?? "")).trim();
      return text ? [{ type: "line", text }] : [];
    });
    if (blocks.length > 0) {
      return blocks;
    }
  }
  const cleaned = readerDisplayText(data.text);
  return cleaned
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter((block) => block.length > 0)
    .flatMap((block, index): ReaderDisplayBlock[] =>
      index === 0 ? [{ type: "line", text: block }] : [{ type: "break" }, { type: "line", text: block }]
    );
}

function readerDisplayGroups(data: { text: string; reader_blocks?: PublicReaderBlock[] }): ReaderDisplayGroup[] {
  const groups: ReaderDisplayGroup[] = [];
  let lines: string[] = [];

  const flush = () => {
    if (lines.length === 0) {
      return;
    }
    groups.push({ type: "group", lines });
    lines = [];
  };

  for (const block of readerDisplayBlocks(data)) {
    if (block.type === "break") {
      flush();
      continue;
    }
    lines.push(block.text);
  }
  flush();

  return groups;
}

function ChapterNav({
  slug,
  previousChapterId,
  nextChapterId,
  previousChapterUnavailable = false,
  nextChapterUnavailable = false,
  novelHref,
}: {
  slug: string;
  previousChapterId: string | null;
  nextChapterId: string | null;
  previousChapterUnavailable?: boolean;
  nextChapterUnavailable?: boolean;
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
            href={publicChapterHref(slug, previousChapterId)}
          >
            ← Previous
          </Link>
        ) : previousChapterUnavailable ? (
          <span className="reader-nav-disabled">Previous unavailable</span>
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
          href={publicChapterHref(slug, nextChapterId)}
        >
          Next →
        </Link>
      ) : nextChapterUnavailable ? (
        <span className="reader-nav-disabled">Next unavailable</span>
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
  const novelHref = publicNovelHref(slug);

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
        Could not load this chapter. It may be unavailable or there may be a connection issue. Try the novel page to find available chapters.
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

  const publicSlug = data.slug?.trim() || slug;
  const publicNovelHrefValue = publicNovelHref(publicSlug);
  const novelTitle = data.novel_title || slug;
  const chapterTitle = data.title || (data.chapter_number != null ? `Chapter ${data.chapter_number}` : "Untitled chapter");
  const displayGroups = readerDisplayGroups(data);

  return (
    <div data-reader-theme={theme} className="reader-container">
      <main className={`reader-shell ${widthClass(width)}`}>
        <header className="reader-chrome">
          <div className="min-w-0">
            <Link href={publicNovelHrefValue} className="reader-back-link">
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
          slug={publicSlug}
          previousChapterId={data.previous_chapter_id}
          nextChapterId={data.next_chapter_id}
          previousChapterUnavailable={data.previous_chapter_unavailable}
          nextChapterUnavailable={data.next_chapter_unavailable}
          novelHref={publicNovelHrefValue}
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
            className="reader-text font-literary"
            style={{ fontSize: `${fontSize}px` }}
          >
            {displayGroups.map((group, groupIndex) => (
              <Fragment key={`${data.chapter_id}-group-${groupIndex}`}>
                {groupIndex > 0 ? (
                  <div
                    className="reader-source-break"
                    aria-hidden="true"
                  />
                ) : null}
                <div
                  className="reader-source-group"
                  data-reader-source-group="true"
                >
                  {group.lines.map((line, lineIndex) => (
                    <p
                      key={`${data.chapter_id}-group-${groupIndex}-line-${lineIndex}`}
                      className="reader-source-line whitespace-pre-wrap"
                    >
                      {line}
                    </p>
                  ))}
                </div>
              </Fragment>
            ))}
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
            slug={publicSlug}
            previousChapterId={data.previous_chapter_id}
            nextChapterId={data.next_chapter_id}
            previousChapterUnavailable={data.previous_chapter_unavailable}
            nextChapterUnavailable={data.next_chapter_unavailable}
            novelHref={publicNovelHrefValue}
          />
        </div>
      </main>
    </div>
  );
}
