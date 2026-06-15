"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen, Clock } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { AuthGate } from "@/components/public/auth-gate";
import { ContinueReading } from "@/components/public/continue-reading";
import { RatingReview } from "@/components/public/rating-review";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { useNovel, useChapters } from "@/hooks/public";
import { ApiError } from "@/lib/api";
import {
  authorOrFallback,
  sortChaptersAscending,
  toReaderError,
} from "@/lib/public-format";

export default function NovelDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug);

  const novel = useNovel(slug);
  const chapters = useChapters(slug);

  // 404 from novel endpoint → not-found message
  if (novel.isError) {
    const err = novel.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <main className="mx-auto max-w-5xl px-5 py-8">
          <Link
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            href="/"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Browse
          </Link>
          <div className="mt-12 text-center">
            <h1 className="text-2xl font-semibold">Novel not found</h1>
            <p className="mt-2 text-muted-foreground">
              The novel you&apos;re looking for doesn&apos;t exist or has been removed.
            </p>
          </div>
        </main>
      );
    }

    // Other errors → sanitized error message
    return (
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Link
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          href="/"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Browse
        </Link>
        <div className="mt-12 text-center">
          <h1 className="text-2xl font-semibold">Something went wrong</h1>
          <p className="mt-2 text-muted-foreground">{toReaderError(err)}</p>
        </div>
      </main>
    );
  }

  // Loading state
  if (novel.isPending) {
    return (
      <main className="mx-auto max-w-5xl px-5 py-8">
        <Link
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          href="/"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Browse
        </Link>
        <div className="mt-12 flex justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-muted border-t-foreground" />
        </div>
      </main>
    );
  }

  const data = novel.data;
  const sortedChapters = chapters.data
    ? sortChaptersAscending(chapters.data)
    : [];

  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        href="/"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="my-6">
        <h1 className="text-3xl font-semibold tracking-normal">
          {data.title || slug}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {authorOrFallback(data.author)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge tone="blue">{data.translated_count} translated</Badge>
          <Badge tone="neutral">{data.chapter_count} listed</Badge>
        </div>
      </header>

      {/* Save to library — user-only, gated by AuthGate */}
      <div className="my-4">
        <AuthGate fallback={null}>
          <SaveToLibrary slug={slug} />
        </AuthGate>
      </div>

      {/* Continue reading — user-only, gated by AuthGate */}
      <div className="my-4">
        <AuthGate fallback={null}>
          <ContinueReading slug={slug} />
        </AuthGate>
      </div>

      {/* Rating/review — user-only, gated by AuthGate */}
      <div className="my-4">
        <AuthGate>
          <RatingReview slug={slug} />
        </AuthGate>
      </div>

      <Panel>
        <PanelHeader>
          <PanelTitle>Chapters</PanelTitle>
        </PanelHeader>
        <PanelBody className="p-0">
          {chapters.isPending ? (
            <div className="flex justify-center py-8">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-muted border-t-foreground" />
            </div>
          ) : chapters.isError ? (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              {toReaderError(chapters.error)}
            </div>
          ) : sortedChapters.length === 0 ? (
            <div className="px-4 py-6 text-center text-sm text-muted-foreground">
              No chapters available yet.
            </div>
          ) : (
            <div className="divide-y">
              {sortedChapters.map((chapter) => (
                <div
                  className="flex items-center justify-between gap-3 px-4 py-3"
                  key={chapter.chapter_id}
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {chapter.title ||
                        `Chapter ${chapter.chapter_number ?? chapter.chapter_id}`}
                    </div>
                    {chapter.chapter_number !== null && (
                      <div className="text-xs text-muted-foreground">
                        Chapter {chapter.chapter_number}
                      </div>
                    )}
                  </div>
                  {chapter.translated ? (
                    <Link
                      className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-sm font-medium hover:bg-muted"
                      href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapter.chapter_id)}`}
                    >
                      <BookOpen className="h-3.5 w-3.5" />
                      Read
                    </Link>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      <Badge tone="amber">Pending</Badge>
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </PanelBody>
      </Panel>
    </main>
  );
}
