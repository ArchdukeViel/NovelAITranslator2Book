"use client";

import Link from "next/link";

import { AuthGate } from "@/components/public/auth-gate";
import { useHistory } from "@/hooks/public";
import type { HistoryEntry } from "@/lib/public-types";

/**
 * Reading_History page — displays the authenticated user's reading history
 * in most-recent-first order by read_at.
 * Gated behind AuthGate; guests see LoginPrompt.
 * Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
 */
export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Reading History</h1>
      <AuthGate>
        <HistoryList />
      </AuthGate>
    </div>
  );
}

function HistoryList() {
  const { data, isPending, isError } = useHistory(true);

  if (isPending) {
    return <p className="text-sm opacity-70">Loading history…</p>;
  }

  if (isError) {
    return <p className="text-sm text-red-600">Failed to load reading history.</p>;
  }

  if (!data || data.length === 0) {
    return (
      <p className="text-sm opacity-70">
        No reading history yet. Start reading a novel to see your history here.
      </p>
    );
  }

  // Sort entries by read_at in descending order (most recent first)
  const sorted = [...data].sort(
    (a: HistoryEntry, b: HistoryEntry) =>
      new Date(b.read_at).getTime() - new Date(a.read_at).getTime()
  );

  return (
    <ul className="space-y-3">
      {sorted.map((entry, index) => (
        <li
          key={`${entry.slug}-${entry.read_at}-${index}`}
          className="flex items-center justify-between rounded-md border p-3"
        >
          <Link
            href={`/novel/${encodeURIComponent(entry.slug)}`}
            className="text-sm font-medium underline hover:opacity-80"
          >
            {entry.slug}
          </Link>
          <time className="text-xs opacity-60" dateTime={entry.read_at}>
            {formatReadAt(entry.read_at)}
          </time>
        </li>
      ))}
    </ul>
  );
}

function formatReadAt(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
}
