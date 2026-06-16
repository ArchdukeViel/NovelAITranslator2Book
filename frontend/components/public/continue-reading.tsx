"use client";

import Link from "next/link";
import { BookOpen, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useProgress, usePublicAuth } from "@/hooks/public";
import { ApiError } from "@/lib/api";

interface ContinueReadingProps {
  slug: string;
  /** First available chapter ID to offer "Start reading" when no saved progress. */
  firstChapterId?: string | null;
}

export function ContinueReading({ slug, firstChapterId }: ContinueReadingProps) {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const progress = useProgress(slug);

  if (authPending) {
    return (
      <Button variant="outline" disabled>
        <Loader2 className="h-4 w-4 animate-spin" />
        Checking progress
      </Button>
    );
  }

  if (!isAuthenticated) {
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

  // Has saved progress → Continue Reading (show chapter ID if available)
  if (chapterId) {
    const href = `/novels/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapterId)}`;
    return (
      <Link
        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
        href={href}
      >
        <BookOpen className="h-4 w-4" />
        Continue from Ch. {chapterId}
      </Link>
    );
  }

  // No saved progress but chapters exist → Start Reading
  if (firstChapterId) {
    const href = `/novels/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(firstChapterId)}`;
    return (
      <Link
        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
        href={href}
      >
        <BookOpen className="h-4 w-4" />
        Start Reading
      </Link>
    );
  }

  // No progress and no chapters available
  return (
    <p className="text-sm text-muted-foreground">
      No chapters available to read yet.
    </p>
  );
}
