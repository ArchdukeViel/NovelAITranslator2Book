"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, BookOpen, Clock, Flag } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { ContinueReading } from "@/components/public/continue-reading";
import { RatingReview } from "@/components/public/rating-review";
import { RequestControl } from "@/components/public/request-control";
import { SaveToLibrary } from "@/components/public/save-to-library";
import { useNovel, useChapters, usePublicAuth } from "@/hooks/public";
import { ApiError } from "@/lib/api";
import {
  authorOrFallback,
  sortChaptersAscending,
  toReaderError,
} from "@/lib/public-format";

export default function NovelDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = decodeURIComponent(params.slug);
  const { isAuthenticated, isPending: authPending } = usePublicAuth();

  const novel = useNovel(slug);
  const chapters = useChapters(slug);

  // 404 from novel endpoint → not-found message
  if (novel.isError) {
    const err = novel.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
          <Link
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            href="/browse-novels"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Browse
          </Link>
          <div className="mt-12 text-center">
            <h1 className="text-2xl font-semibold font-literary">Novel not found</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              The novel you&apos;re looking for doesn&apos;t exist or has been removed.
            </p>
          </div>
        </main>
      );
    }

    // Other errors → sanitized error message
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Link
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          href="/browse-novels"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Browse
        </Link>
        <div className="mt-12 text-center">
          <h1 className="text-2xl font-semibold font-literary">Something went wrong</h1>
          <p className="mt-2 text-sm text-muted-foreground">{toReaderError(err)}</p>
        </div>
      </main>
    );
  }

  // Loading state
  if (novel.isPending) {
    return (
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <Link
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          href="/browse-novels"
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

  // Find first translated chapter for "Start Reading" affordance
  const firstTranslatedChapter = sortedChapters.find((ch) => ch.translated);
  const firstChapterId = firstTranslatedChapter?.chapter_id ?? null;

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        href="/browse-novels"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Browse
      </Link>

      {/* Novel header */}
      <header className="my-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary md:text-4xl">
          {data.title || slug}
        </h1>
        <p className="mt-2 text-base text-muted-foreground">
          {authorOrFallback(data.author)}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge tone="neutral" className="font-metadata">
            {data.translated_count} translated
          </Badge>
          <Badge tone="neutral" className="font-metadata">
            {data.chapter_count} listed
          </Badge>
          {data.language && (
            <Badge tone="neutral" className="font-metadata">
              {data.language}
            </Badge>
          )}
          {data.status && (
            <Badge tone="amber" className="font-metadata">
              {data.status}
            </Badge>
          )}
        </div>
      </header>

      {/* Reader actions panel — groups all user-facing controls together */}
      <Panel className="mb-8">
        <PanelHeader>
          <PanelTitle>Reader Actions</PanelTitle>
        </PanelHeader>
        <PanelBody className="flex flex-col gap-4 p-4">
          {/* Authenticated: save + continue reading side-by-side */}
          {!authPending && isAuthenticated && (
            <div className="flex flex-wrap items-center gap-3">
              <SaveToLibrary slug={slug} />
              <ContinueReading slug={slug} firstChapterId={firstChapterId} />
            </div>
          )}

          {/* Guest: single sign-in CTA instead of repeated login prompts */}
          {!authPending && !isAuthenticated && (
            <div className="flex flex-wrap items-center gap-3">
              {firstChapterId && (
                <Link
                  className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
                  href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(firstChapterId)}`}
                >
                  <BookOpen className="h-4 w-4" />
                  Start Reading
                </Link>
              )}
              {!firstChapterId && (
                <span className="text-sm text-muted-foreground">
                  No translated chapters available yet.
                </span>
              )}
              <SaveToLibrary slug={slug} />
            </div>
          )}

          {/* Auth pending: loading state */}
          {authPending && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-foreground" />
              Checking session…
            </div>
          )}

          {/* Report novel issue placeholder */}
          <section className="rounded-md border border-border bg-muted/30 p-4">
            <div className="flex items-start gap-3">
              <Flag className="mt-0.5 h-4 w-4 text-muted-foreground" />
              <div>
                <h3 className="text-sm font-medium">Report novel issue</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Reporting for this novel will be connected in a later backend phase.
                </p>
              </div>
            </div>
          </section>

          <RatingReview slug={slug} />
          <RequestControl slug={slug} />
        </PanelBody>
      </Panel>

      {/* Chapter list */}
      <Panel>
        <PanelHeader>
          <PanelTitle className="font-metadata">
            Chapters ({sortedChapters.length})
          </PanelTitle>
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
                  className="flex items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/30"
                  key={chapter.chapter_id}
                >
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">
                      {chapter.title ||
                        `Chapter ${chapter.chapter_number ?? chapter.chapter_id}`}
                    </div>
                    {chapter.chapter_number !== null && (
                      <div className="mt-0.5 text-xs font-metadata text-muted-foreground">
                        Chapter {chapter.chapter_number}
                      </div>
                    )}
                  </div>
                  {chapter.translated ? (
                    <Link
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-border bg-background px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
                      href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapter.chapter_id)}`}
                    >
                      <BookOpen className="h-3.5 w-3.5" />
                      Read
                    </Link>
                  ) : (
                    <span className="inline-flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                      <Badge tone="amber" className="font-metadata text-xs">
                        Pending
                      </Badge>
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
