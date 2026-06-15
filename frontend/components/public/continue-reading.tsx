"use client";

import Link from "next/link";
import { BookOpen } from "lucide-react";

import { useAuthMe } from "@/hooks/public/use-auth";
import { useProgress } from "@/hooks/public";

interface ContinueReadingProps {
  slug: string;
}

/**
 * Continue-reading affordance for authenticated users.
 * Fetches reading progress and shows a link to resume from the last chapter.
 * On progress fetch failure: renders nothing (graceful degradation).
 * Guests never trigger the progress endpoint.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
 */
export function ContinueReading({ slug }: ContinueReadingProps) {
  const { data: authUser } = useAuthMe();
  const isAuthenticated = authUser?.role === "user";

  const { data: progress, isError } = useProgress(slug, isAuthenticated);

  // On failure or no progress data: render nothing
  if (isError || !progress?.chapter_id) {
    return null;
  }

  return (
    <Link
      href={`/novel/${encodeURIComponent(slug)}/chapter/${encodeURIComponent(progress.chapter_id)}`}
      className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted"
    >
      <BookOpen className="h-4 w-4" />
      Continue Reading
    </Link>
  );
}
