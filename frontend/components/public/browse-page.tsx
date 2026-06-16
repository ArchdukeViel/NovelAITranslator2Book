"use client";

import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { BookOpen, Filter, Search, X } from "lucide-react";

import { NovelCard } from "@/components/public/novel-card";
import { useCatalog } from "@/hooks/public";
import {
  hasNextPage,
  toReaderError,
} from "@/lib/public-format";
import type { CatalogParams } from "@/lib/public-types";

interface BrowsePageProps {
  basePath: "/home" | "/browse-novels";
  title: string;
  description: string;
}

function BrowseContent({ basePath }: { basePath: BrowsePageProps["basePath"] }) {
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
    router.push(`${basePath}?${sp.toString()}`);
  }

  function handleNextPage() {
    pushParams({ ...params, page: page + 1 });
  }

  function handleClearFilters() {
    router.push(basePath);
  }

  if (isPending) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground">Loading catalog...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16">
        <p className="text-sm text-destructive">{toReaderError(error)}</p>
        <button
          className="text-sm text-primary hover:underline"
          onClick={() => router.refresh()}
          type="button"
        >
          Try again
        </button>
      </div>
    );
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;

  if (novels.length === 0 && hasActiveFilters) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16">
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
          type="button"
        >
          <X className="h-3.5 w-3.5" />
          Clear filters
        </button>
      </div>
    );
  }

  if (novels.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16">
        <BookOpen className="h-10 w-10 text-muted-foreground/50" />
        <p className="text-sm text-muted-foreground">
          No novels available yet. Check back later.
        </p>
      </div>
    );
  }

  return (
    <>
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
        <span>
          {total} novel{total !== 1 ? "s" : ""}
        </span>
        {hasActiveFilters && (
          <button
            className="inline-flex items-center gap-1 text-primary hover:underline"
            onClick={handleClearFilters}
            type="button"
          >
            <X className="h-3.5 w-3.5" />
            Clear
          </button>
        )}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {novels.map((novel) => (
          <NovelCard key={novel.novel_id} novel={novel} />
        ))}
      </div>

      {hasNextPage(total, page, pageSize) && (
        <div className="mt-6 flex justify-center">
          <button
            className="inline-flex h-9 items-center justify-center rounded-md border px-4 text-sm font-medium hover:bg-muted"
            onClick={handleNextPage}
            type="button"
          >
            Next page
          </button>
        </div>
      )}
    </>
  );
}

export function BrowsePage({ basePath, description, title }: BrowsePageProps) {
  return (
    <main className="mx-auto max-w-6xl px-5 py-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal">{title}</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          {description}
        </p>
      </header>

      <Suspense
        fallback={
          <div className="flex flex-col items-center justify-center gap-3 py-16">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
            <p className="text-sm text-muted-foreground">Loading catalog...</p>
          </div>
        }
      >
        <BrowseContent basePath={basePath} />
      </Suspense>
    </main>
  );
}
