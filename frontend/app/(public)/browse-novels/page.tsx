import type { Metadata } from "next";
import { Suspense } from "react";
import { BrowsePage } from "@/components/public/browse-page";

export async function generateMetadata({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const params = await searchParams;
  const q = typeof params.q === "string" ? params.q.trim() : "";
  const entries = Object.entries(params).sort(([left], [right]) => left.localeCompare(right));
  const utilityFilters = entries.filter(
    ([key, value]) =>
      !["sort_by", "order", "page", "view"].includes(key) &&
      typeof value === "string" &&
      value.length > 0,
  );
  const canonicalParams = new URLSearchParams();
  for (const [key, value] of entries) {
    if (["sort_by", "order", "view"].includes(key) || typeof value !== "string" || !value) continue;
    canonicalParams.set(key, value);
  }
  const canonicalQuery = canonicalParams.toString();
  const canonical = `/browse-novels${canonicalQuery ? `?${canonicalQuery}` : ""}`;
  if (q) {
    return {
      title: `Search results for "${q}"`,
      description: `Search results for "${q}" on Dokushodo.`,
      robots: { index: false, follow: true },
      alternates: { canonical },
    };
  }
  return {
    title: "Browse Novels",
    description: "Browse the translated novel library on Dokushodo: search by title or author, narrow by status, genre, or chapter count.",
    robots: utilityFilters.length ? { index: false, follow: true } : undefined,
    alternates: { canonical },
  };
}

function BrowseNovelsSkeleton() {
  return (
    <div
      role="status"
      aria-label="Loading catalog"
      className="mx-auto grid max-w-7xl gap-4 px-4 py-10 sm:grid-cols-2 lg:grid-cols-3 sm:px-6 lg:px-8"
    >
      {Array.from({ length: 6 }).map((_, index) => (
        <div
          key={index}
          className="overflow-hidden rounded-lg border border-border bg-card/70"
        >
          <div className="aspect-[2/3] animate-pulse bg-muted" />
          <div className="space-y-3 p-4">
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function BrowseNovelsPage() {
  return (
    <Suspense fallback={<BrowseNovelsSkeleton />}>
      <BrowsePage
        basePath="/browse-novels"
        title="Browse the library"
        description="Search by title or author, then narrow by status, genre, or chapter count."
      />
    </Suspense>
  );
}
