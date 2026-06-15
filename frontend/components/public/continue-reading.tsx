"use client";

import Link from "next/link";
import { BookOpen, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LoginPrompt } from "@/components/public/login-prompt";
import { useProgress, usePublicAuth } from "@/hooks/public";

interface ContinueReadingProps {
  slug: string;
}

export function ContinueReading({ slug }: ContinueReadingProps) {
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

  if (progress.isError) {
    return (
      <p className="text-sm text-destructive">
        Could not load saved progress.
      </p>
    );
  }

  const chapterId = progress.data?.chapter_id;
  if (!chapterId) {
    return (
      <Button variant="outline" disabled>
        <BookOpen className="h-4 w-4" />
        No saved progress yet
      </Button>
    );
  }

  return (
    <Link
      className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
      href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(chapterId)}`}
    >
      <BookOpen className="h-4 w-4" />
      Continue Reading
    </Link>
  );
}
