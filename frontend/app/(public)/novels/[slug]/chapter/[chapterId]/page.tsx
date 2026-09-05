"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Flag } from "lucide-react";

import { ReaderControls } from "@/components/public/reader-controls";
import { GlossaryAnnotationHighlighter } from "@/components/public/glossary-annotation-highlighter";
import { ReaderErrorBoundary } from "@/components/reader/reader-error-boundary";
import {
  useChapter,
  usePublicAuth,
  useProgress,
  useRecordHistory,
  useUpdateProgress,
} from "@/hooks/public";
import { ApiError } from "@/lib/api";
import { publicApi } from "@/lib/public-api";
import { widthClass } from "@/lib/public-format";
import { publicChapterHref, publicNovelHref } from "@/lib/public-routes";
import type {
  PublicGlossaryAnnotation,
  PublicReaderBlock,
} from "@/lib/public-types";
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
      sourceBlockIndex: number | null;
    }
  | {
      type: "break";
    };

type ReaderDisplayParagraph = {
  kind: "dialogue" | "narration";
  text: string;
  sourceBlockIndices: number[];
};

function readerParagraphText(lines: string[]): string {
  return lines
    .map((line) => line.replace(/\s+/g, " ").trim())
    .filter((line) => line.length > 0)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();
}

const dialogueQuotePairs: Array<{ open: string; close: string }> = [
  { open: '"', close: '"' },
  { open: "'", close: "'" },
  { open: "“", close: "”" },
  { open: "‘", close: "’" },
  { open: "「", close: "」" },
  { open: "『", close: "』" },
];

function isDialogueLine(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) {
    return false;
  }
  const withoutTrailingPunctuation = trimmed
    .replace(/[.!?…。！？]*$/u, "")
    .trimEnd();
  return dialogueQuotePairs.some(
    ({ open, close }) =>
      withoutTrailingPunctuation.startsWith(open) &&
      withoutTrailingPunctuation.endsWith(close) &&
      withoutTrailingPunctuation.length > open.length + close.length,
  );
}

function readerDisplayBlocks(data: {
  text: string;
  reader_blocks?: PublicReaderBlock[];
}): ReaderDisplayBlock[] {
  if (Array.isArray(data.reader_blocks)) {
    const blocks = data.reader_blocks.flatMap(
      (block, sourceBlockIndex): ReaderDisplayBlock[] => {
        if (typeof block === "string") {
          const text = readerDisplayText(block).trim();
          return text ? [{ type: "line", text, sourceBlockIndex }] : [];
        }
        if (block?.type === "break") {
          return [{ type: "break" }];
        }
        const text = readerDisplayText(String(block?.text ?? "")).trim();
        return text ? [{ type: "line", text, sourceBlockIndex }] : [];
      },
    );
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
      index === 0
        ? [{ type: "line", text: block, sourceBlockIndex: null }]
        : [
            { type: "break" },
            { type: "line", text: block, sourceBlockIndex: null },
          ],
    );
}

function readerDisplayParagraphs(data: {
  text: string;
  reader_blocks?: PublicReaderBlock[];
}): ReaderDisplayParagraph[] {
  const paragraphs: ReaderDisplayParagraph[] = [];
  let lines: string[] = [];
  let sourceBlockIndices: number[] = [];

  const flush = () => {
    const text = readerParagraphText(lines);
    if (!text) {
      lines = [];
      sourceBlockIndices = [];
      return;
    }
    paragraphs.push({ kind: "narration", text, sourceBlockIndices });
    lines = [];
    sourceBlockIndices = [];
  };

  for (const block of readerDisplayBlocks(data)) {
    if (block.type === "break") {
      flush();
      continue;
    }
    const text = readerParagraphText([block.text]);
    if (!text) {
      continue;
    }
    if (isDialogueLine(text)) {
      flush();
      paragraphs.push({
        kind: "dialogue",
        text,
        sourceBlockIndices:
          block.sourceBlockIndex === null ? [] : [block.sourceBlockIndex],
      });
      continue;
    }
    lines.push(text);
    if (block.sourceBlockIndex !== null) {
      sourceBlockIndices.push(block.sourceBlockIndex);
    }
  }
  flush();

  return paragraphs;
}

function annotationsForParagraph(
  paragraph: ReaderDisplayParagraph,
  annotations: PublicGlossaryAnnotation[],
): PublicGlossaryAnnotation[] {
  return annotations.flatMap((annotation) => {
    const relevantMatches = annotation.matches.filter(
      (match) =>
        match.block_index === undefined ||
        paragraph.sourceBlockIndices.length === 0 ||
        paragraph.sourceBlockIndices.includes(match.block_index),
    );
    if (relevantMatches.length === 0) {
      return [];
    }

    const paragraphLower = paragraph.text.toLocaleLowerCase();
    const remappedMatches: PublicGlossaryAnnotation["matches"] = [];
    for (const surface of [
      ...new Set(relevantMatches.map((match) => match.surface).filter(Boolean)),
    ]) {
      const surfaceLower = surface.toLocaleLowerCase();
      let start = paragraphLower.indexOf(surfaceLower);
      while (start >= 0 && remappedMatches.length < relevantMatches.length) {
        remappedMatches.push({
          surface: paragraph.text.slice(start, start + surface.length),
          start,
          end: start + surface.length,
        });
        start = paragraphLower.indexOf(surfaceLower, start + surface.length);
      }
    }
    return remappedMatches.length > 0
      ? [{ ...annotation, matches: remappedMatches }]
      : [];
  });
}

function ChapterNav({
  slug,
  previousChapterId,
  nextChapterId,
  previousChapterUnavailable = false,
  nextChapterUnavailable = false,
  novelHref,
  emphasizeNext = false,
}: {
  slug: string;
  previousChapterId: string | null;
  nextChapterId: string | null;
  previousChapterUnavailable?: boolean;
  nextChapterUnavailable?: boolean;
  novelHref: string;
  emphasizeNext?: boolean;
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
            ← Previous chapter
          </Link>
        ) : previousChapterUnavailable ? (
          <span className="reader-nav-disabled">Previous unavailable</span>
        ) : (
          <span className="reader-nav-disabled">← First chapter</span>
        )}
        <Link className="reader-nav-link" href={novelHref}>
          <BookOpen className="h-3.5 w-3.5" />
          Back to novel
        </Link>
      </div>
      {nextChapterId ? (
        <Link
          className={`reader-nav-link ${emphasizeNext ? "reader-nav-link-strong" : ""}`}
          href={publicChapterHref(slug, nextChapterId)}
        >
          Next chapter →
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

function useSafeQueryClient() {
  try {
    return useQueryClient();
  } catch {
    return null;
  }
}

export default function ChapterPage() {
  const params = useParams<{ slug: string; chapterId: string }>();
  const router = useRouter();
  const slug = decodeURIComponent(params.slug);
  const chapterId = decodeURIComponent(params.chapterId);
  const novelHref = publicNovelHref(slug);

  const { data, isPending, isError, error } = useChapter(slug, chapterId);
  const { isAuthenticated } = usePublicAuth();
  const savedProgress = useProgress(slug);
  const updateProgress = useUpdateProgress(slug);
  const recordHistory = useRecordHistory();
  const queryClient = useSafeQueryClient();
  const trackedChapterRef = useRef<string | null>(null);
  const restoredChapterRef = useRef<string | null>(null);
  const prefetchedNextRef = useRef<string | null>(null);
  const progressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [scrollProgress, setScrollProgress] = useState(0);
  const { theme, fontSize, width } = useReaderPrefsStore();

  useEffect(() => {
    const nextId = data?.next_chapter_id;
    if (
      !nextId ||
      scrollProgress < 70 ||
      prefetchedNextRef.current === nextId
    ) {
      return;
    }
    prefetchedNextRef.current = nextId;
    const targetSlug = data.slug?.trim() || slug;
    if (queryClient) {
      void queryClient.prefetchQuery({
        queryKey: ["public", "chapter", targetSlug, nextId],
        queryFn: ({ signal }) => publicApi.chapter(targetSlug, nextId, signal),
        staleTime: 1000 * 60 * 5,
      });
    }
    router.prefetch?.(publicChapterHref(targetSlug, nextId));
  }, [
    data?.next_chapter_id,
    data?.slug,
    queryClient,
    router,
    scrollProgress,
    slug,
  ]);

  useEffect(() => {
    if (!isAuthenticated || !data || trackedChapterRef.current === chapterId) {
      return;
    }
    trackedChapterRef.current = chapterId;
    recordHistory.mutate({
      slug,
      chapter_id: chapterId,
    });
  }, [chapterId, data, isAuthenticated, recordHistory, slug]);

  useEffect(() => {
    if (!data || restoredChapterRef.current === chapterId) return;
    const localKey = `reader-position:${slug}:${chapterId}`;
    const percent =
      isAuthenticated && savedProgress.data?.chapter_id === chapterId
        ? savedProgress.data.progress_percent
        : Number(localStorage.getItem(localKey) ?? 0);
    restoredChapterRef.current = chapterId;
    if (percent > 0) {
      const restore = () => {
        const maximum = Math.max(
          0,
          document.documentElement.scrollHeight - window.innerHeight,
        );
        window.scrollTo(0, (maximum * Math.min(100, percent)) / 100);
      };
      requestAnimationFrame(() => requestAnimationFrame(restore));
      const article = document.querySelector(".reader-article");
      let observer: ResizeObserver | null = null;
      if (article && typeof ResizeObserver !== "undefined") {
        observer = new ResizeObserver(() => {
          restore();
          observer?.disconnect();
        });
      }
      if (article) observer?.observe(article);
      return () => observer?.disconnect();
    }
  }, [chapterId, data, isAuthenticated, savedProgress.data, slug]);

  useEffect(() => {
    if (!data) return;
    const localKey = `reader-position:${slug}:${chapterId}`;
    function update() {
      const maximum = Math.max(
        1,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      const percent = Math.min(
        100,
        Math.max(0, (window.scrollY / maximum) * 100),
      );
      setScrollProgress(percent);
      if (!isAuthenticated) localStorage.setItem(localKey, String(percent));
      else {
        if (progressTimerRef.current) clearTimeout(progressTimerRef.current);
        progressTimerRef.current = setTimeout(
          () =>
            updateProgress.mutate({
              chapter_id: chapterId,
              progress_percent: percent,
            }),
          500,
        );
      }
    }
    function flush() {
      const maximum = Math.max(
        1,
        document.documentElement.scrollHeight - window.innerHeight,
      );
      const percent = Math.min(
        100,
        Math.max(0, (window.scrollY / maximum) * 100),
      );
      if (isAuthenticated)
        updateProgress.mutate({
          chapter_id: chapterId,
          progress_percent: percent,
        });
      else localStorage.setItem(localKey, String(percent));
    }
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("pagehide", flush);
    requestAnimationFrame(update);
    return () => {
      window.removeEventListener("scroll", update);
      window.removeEventListener("pagehide", flush);
      if (progressTimerRef.current) clearTimeout(progressTimerRef.current);
    };
  }, [chapterId, data, fontSize, isAuthenticated, slug, updateProgress, width]);

  useEffect(() => {
    const chapter = data;
    if (!chapter) return;
    const previousChapterId = chapter.previous_chapter_id;
    const nextChapterId = chapter.next_chapter_id;
    const publicSlug = chapter.slug?.trim() || slug;
    function navigate(event: KeyboardEvent) {
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement
      )
        return;
      if (event.key === "ArrowLeft" && previousChapterId)
        router.push(publicChapterHref(publicSlug, previousChapterId));
      if (event.key === "ArrowRight" && nextChapterId)
        router.push(publicChapterHref(publicSlug, nextChapterId));
    }
    window.addEventListener("keydown", navigate);
    return () => window.removeEventListener("keydown", navigate);
  }, [data, router, slug]);

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
        Could not load this chapter. It may be unavailable or there may be a
        connection issue. Try the novel page to find available chapters.
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
  const chapterTitle =
    data.title ||
    (data.chapter_number != null
      ? `Chapter ${data.chapter_number}`
      : "Untitled chapter");
  const displayParagraphs = readerDisplayParagraphs(data);
  const glossaryAnnotations = data.glossary_annotations ?? [];

  return (
    <div data-reader-theme={theme} className="reader-container">
      <div
        role="progressbar"
        aria-label="Reading progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(scrollProgress)}
        className="fixed inset-x-0 top-0 z-50 h-[3px] bg-muted"
      >
        <div
          className="h-full bg-primary transition-[width] duration-100"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>
      <main className={`reader-shell ${widthClass(width)}`}>
        <header className="reader-chrome">
          <div className="min-w-0">
            <Link href={publicNovelHrefValue} className="reader-back-link">
              <ArrowLeft className="h-4 w-4" />
              <span className="font-literary">{novelTitle}</span>
            </Link>
            <p className="mt-2 truncate text-xs font-metadata reader-muted">
              {data.chapter_number != null
                ? `Chapter ${data.chapter_number}`
                : "\u00a0"}
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

        <ReaderErrorBoundary
          novelSlug={typeof slug === "string" ? slug : undefined}
          chapterId={typeof chapterId === "string" ? chapterId : undefined}
        >
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
              {displayParagraphs.map((paragraph, paragraphIndex) => (
                <p
                  key={`${data.chapter_id}-paragraph-${paragraphIndex}`}
                  className={`reader-source-paragraph reader-source-paragraph--${paragraph.kind}`}
                  data-reader-source-group="true"
                >
                  <GlossaryAnnotationHighlighter
                    text={paragraph.text}
                    annotations={annotationsForParagraph(
                      paragraph,
                      glossaryAnnotations,
                    )}
                  />
                </p>
              ))}
            </div>
          </article>
        </ReaderErrorBoundary>

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
            emphasizeNext
          />
        </div>
      </main>
    </div>
  );
}
