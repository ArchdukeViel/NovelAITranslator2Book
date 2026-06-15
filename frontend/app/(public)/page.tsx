"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

import { useCatalog } from "@/hooks/public";
import { NovelCard } from "@/components/public/novel-card";
import {
  toReaderError,
  hasNextPage,
  clearedCatalogParams,
} from "@/lib/public-format";
import type { CatalogParams } from "@/lib/public-types";

function BrowseContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const q = searchParams.get("q") ?? undefined;
  const language = searchParams.get("language") ?? undefined;
  const page = Number(searchParams.get("page") ?? "1") || 1;
  const pageSize = 20;

  const params: CatalogParams = { q, language, page, page_size: pageSize };
  const { data, isPending, isError, error } = useCatalog(params);

  const hasActiveFilters = Boolean(q || language);

  function pushParams(next: CatalogParams) {
    const sp = new URLSearchParams();
    if (next.q) sp.set("q", next.q);
    if (next.language) sp.set("language", next.language);
    if (next.page && next.page > 1) sp.set("page", String(next.page));
    router.push(`/?${sp.toString()}`);
  }

  function handleNextPage() {
    pushParams({ ...params, page: page + 1 });
  }

  function handleClearFilters() {
    const cleared = clearedCatalogParams();
    pushParams(cleared);
  }

  // Loading state
  if (isPending) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-destructive">{toReaderError(error)}</p>
      </div>
    );
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;

  // Empty state: no results with active query
  if (novels.length === 0 && q) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-muted-foreground">
          No results found for &ldquo;{q}&rdquo;
        </p>
        <button
          className="mt-4 text-sm text-primary hover:underline"
          onClick={handleClearFilters}
        >
          Clear filters
        </button>
      </div>
    );
  }

  // Empty state: unfiltered catalog is empty
  if (novels.length === 0) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm text-muted-foreground">
          No novels available yet. Check back later!
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Clear filters control */}
      {hasActiveFilters && (
        <div className="mb-4">
          <button
            className="text-sm text-primary hover:underline"
            onClick={handleClearFilters}
          >
            Clear filters
          </button>
        </div>
      )}

      {/* Novel grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {novels.map((novel) => (
          <NovelCard key={novel.novel_id} novel={novel} />
        ))}
      </div>

      {/* Next page control */}
      {hasNextPage(total, page, pageSize) && (
        <div className="mt-6 flex justify-center">
          <button
            className="inline-flex h-9 items-center justify-center rounded-md border px-4 text-sm font-medium hover:bg-muted"
            onClick={handleNextPage}
          >
            Next page
          </button>
        </div>
      )}
    </>
  );
}

export default function HomePage() {
  return (
    <main className="mx-auto max-w-6xl px-5 py-8">
      <header className="mb-6 flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-normal">
          Novel AI Reader
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Public reader for translated Japanese web novels managed by the
          crawler and translation pipeline.
        </p>
      </header>

      <Suspense
        fallback={
          <div className="flex items-center justify-center py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
          </div>
        }
      >
        <BrowseContent />
      </Suspense>
    </main>
  );
}
