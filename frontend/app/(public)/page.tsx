"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { BookOpen, Search, Filter, X } from "lucide-react";

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
    router.push("/");
  }

  // Loading state
  if (isPending) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading catalog…</p>
      </div>
    );
  }

  // Error state with retry
  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <p className="text-sm text-destructive">{toReaderError(error)}</p>
        <button
          className="text-sm text-primary hover:underline"
          onClick={() => router.refresh()}
        >
          Try again
        </button>
      </div>
    );
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;

  // Empty state: no results with active query
  if (novels.length === 0 && hasActiveFilters) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        {q && (
          <p className="text-sm text-muted-foreground">
            No results found for &ldquo;{q}&rdquo;
          </p>
        )}
        {!q && language && (
          <p className="text-sm text-muted-foreground">
            No novels found in {language}.
          </p>
        )}
        <button
          className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline"
          onClick={handleClearFilters}
        >
          <X className="h-3.5 w-3.5" />
          Clear filters
        </button>
      </div>
    );
  }

  // Empty state: unfiltered catalog is empty
  if (novels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <BookOpen className="h-10 w-10 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">
          No novels available yet. Check back later!
        </p>
      </div>
    );
  }

  return (
    <>
      {/* Catalog summary bar */}
      <div className="mb-4 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
        {q && (
          <span className="inline-flex items-center gap-1">
            <Search className="h-3.5 w-3.5" />
            Search: &ldquo;{q}&rdquo;
          </span>
        )}
        {language && (
          <span className="inline-flex items-center gap-1">
            <Filter className="h-3.5 w-3.5" />
            Language: {language}
          </span>
        )}
        <span>{total} novel{total !== 1 ? "s" : ""}</span>
        {hasActiveFilters && (
          <button
            className="inline-flex items-center gap-1 text-primary hover:underline"
            onClick={handleClearFilters}
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        )}
      </div>

      {/* Novel grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {novels.map((novel) => (
          <NovelCard key={novel.novel_id} novel={novel} />
        ))}
      </div>

      {/* Pagination */}
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
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal">
          Novel AI Reader
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Browse and read translated web novels. Sign in to save novels,
          continue reading where you left off, and leave reviews.
        </p>
      </header>

      <Suspense
        fallback={
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">Loading catalog…</p>
          </div>
        }
      >
        <BrowseContent />
      </Suspense>
    </main>
  );
}
