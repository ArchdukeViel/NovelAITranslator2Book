"use client";

import Link from "next/link";
import { BookOpen, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useProgress, usePublicAuth } from "@/hooks/public";
import { ApiError } from "@/lib/api";
import { publicChapterHref } from "@/lib/public-routes";

interface ContinueReadingProps {
  slug: string;
  /** First available chapter ID to offer "Start reading" when no saved progress. */
  firstChapterId?: string | null;
  /** Page already renders its own primary Start/Continue CTA; suppress the duplicate when there is no saved progress. */
  hasHeroCta?: boolean;
  /** Novel detail's sole primary CTA allows guests to start reading directly. */
  allowGuestStart?: boolean;
  primary?: boolean;
}

export function ContinueReading({ slug, firstChapterId, hasHeroCta = false, allowGuestStart = false, primary = false }: ContinueReadingProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const progress = useProgress(slug);

  if (authPending) {
    return (
      <Button className={primary ? "w-full" : undefined} variant="outline" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking progress
      </Button>
    );
  }

  if (!isAuthenticated) {
    if (allowGuestStart && firstChapterId) {
      return (
        <Link
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          href={publicChapterHref(slug, firstChapterId)}
        >
          <BookOpen className="h-4 w-4" />
          Start Reading
        </Link>
      );
    }
    return <LoginPrompt />;
  }

  if (progress.isPending) {
    return (
      <Button variant="outline" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading progress
      </Button>
    );
  }

  // 404 from progress endpoint means "no saved progress" — not an error.
  // Show "Start Reading" or "No chapters available" instead of an error message.
  const isNoProgress =
    progress.isError &&
    progress.error instanceof ApiError &&
    progress.error.status === 404;

  if (progress.isError && !isNoProgress) {
    return (
      <p className="text-sm text-destructive">
        Could not load saved progress.
      </p>
    );
  }

  const chapterId = progress.data?.chapter_id;
  const chapterNumber = progress.data?.chapter_number;

  // Has saved progress → Continue Reading (show chapter number if available)
  if (chapterId) {
    const href = publicChapterHref(slug, chapterId);
    return (
      <Link
        aria-label={chapterNumber != null ? `Continue Reading from Ch. ${chapterNumber}` : "Continue Reading"}
        className={primary ? "inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90" : "inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"}
        href={href}
      >
        <BookOpen className="h-4 w-4" />
        Continue Reading
      </Link>
    );
  }

  // No saved progress but chapters exist → Start Reading
  if (firstChapterId) {
    if (hasHeroCta) {
      return null;
    }
    const href = publicChapterHref(slug, firstChapterId);
    return (
      <Link
        className={primary ? "inline-flex h-11 w-full items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90" : "inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"}
        href={href}
      >
        <BookOpen className="h-4 w-4" />
        Start Reading
      </Link>
    );
  }

  // No progress and no chapters available
  if (hasHeroCta) {
    return null;
  }
  return (
    <p className="text-sm text-muted-foreground">
      No chapters available to read yet.
    </p>
  );
}
