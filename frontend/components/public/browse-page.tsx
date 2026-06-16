"use client";

import { FormEvent, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BookOpen, Filter, LibraryBig, Search, X } from "lucide-react";

import { NovelCard } from "@/components/public/novel-card";
import { SectionHeader } from "@/components/public/section-header";
import { StatusBadge } from "@/components/public/status-badge";
import { useCatalog } from "@/hooks/public";
import { hasNextPage, toReaderError } from "@/lib/public-format";
import type { CatalogParams } from "@/lib/public-types";

const LANGUAGE_FILTERS = [
  { value: "", label: "All sources" },
  { value: "Japanese", label: "Japanese" },
  { value: "Korean", label: "Korean" },
  { value: "Chinese", label: "Chinese" },
  { value: "English", label: "English" },
] as const;

const STATUS_FILTERS = [
  { value: "", label: "Any status" },
  { value: "Ongoing", label: "Ongoing" },
  { value: "Completed", label: "Completed" },
  { value: "Hiatus", label: "Hiatus" },
] as const;

interface BrowsePageProps {
  basePath: "/home" | "/browse-novels";
  title: string;
  description: string;
}

function LoadingState() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 6 }).map((_, index) => (
        <div
          key={index}
          className="overflow-hidden rounded-lg border border-border bg-card/70"
        >
          <div className="aspect-[2/3] animate-pulse bg-muted" />
          <div className="space-y-3 p-4">
            <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
            <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
            <div className="h-3 w-full animate-pulse rounded bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

function BrowseContent({ basePath }: { basePath: BrowsePageProps["basePath"] }) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const q = searchParams.get("q") ?? undefined;
  const language = searchParams.get("language") ?? undefined;
  const status = searchParams.get("status") ?? undefined;
  const page = Number(searchParams.get("page") ?? "1") || 1;
  const pageSize = 20;

  const params: CatalogParams = {
    q,
    language,
    status,
    page,
    page_size: pageSize,
  };
  const { data, isPending, isError, error } = useCatalog(params);

  const hasActiveFilters = Boolean(q || language || status);

  function pushParams(next: CatalogParams) {
    const sp = new URLSearchParams();
    if (next.q) sp.set("q", next.q);
    if (next.language) sp.set("language", next.language);
    if (next.status) sp.set("status", next.status);
    if (next.page && next.page > 1) sp.set("page", String(next.page));
    const query = sp.toString();
    router.push(`${basePath}${query ? `?${query}` : ""}`);
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextQuery = String(formData.get("q") ?? "").trim();
    pushParams({ ...params, q: nextQuery || undefined, page: 1 });
  }

  function handleLanguageChange(nextLanguage: string) {
    pushParams({
      ...params,
      language: nextLanguage || undefined,
      page: 1,
    });
  }

  function handleStatusChange(nextStatus: string) {
    pushParams({
      ...params,
      status: nextStatus || undefined,
      page: 1,
    });
  }

  function handleNextPage() {
    pushParams({ ...params, page: page + 1 });
  }

  function handleClearFilters() {
    router.push(basePath);
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-10">
      <section
        aria-label="Browse filters"
        className="rounded-lg bg-card/75 p-4 shadow-sm ring-1 ring-border sm:p-5"
      >
        <form onSubmit={handleSearchSubmit}>
          <label
            htmlFor="catalog-search"
            className="font-metadata text-xs uppercase tracking-[0.18em] text-accent"
          >
            Search the catalog
          </label>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="catalog-search"
                name="q"
                type="search"
                defaultValue={q ?? ""}
                placeholder="Search by title or author"
                className="h-11 w-full rounded-md border border-border bg-muted pl-10 pr-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-accent focus:bg-card"
              />
            </div>
            <button
              type="submit"
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
            >
              <Search className="h-4 w-4" />
              Search
            </button>
          </div>
        </form>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <LibraryBig className="h-4 w-4 text-accent" />
              Source language
            </div>
            <div className="flex flex-wrap gap-2">
              {LANGUAGE_FILTERS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleLanguageChange(value)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    (language ?? "") === value
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground hover:bg-muted"
                  }`}
                  aria-pressed={(language ?? "") === value}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-medium">
              <Filter className="h-4 w-4 text-accent" />
              Translation status
            </div>
            <div className="flex flex-wrap gap-2">
              {STATUS_FILTERS.map(({ value, label }) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => handleStatusChange(value)}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    (status ?? "") === value
                      ? "bg-primary text-primary-foreground"
                      : "bg-secondary text-secondary-foreground hover:bg-muted"
                  }`}
                  aria-pressed={(status ?? "") === value}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section aria-label="Catalog results">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-metadata">
              {isPending ? "Loading" : total} novel
              {!isPending && total === 1 ? "" : "s"}
            </span>
            {q && (
              <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1">
                <Search className="h-3.5 w-3.5" />
                &ldquo;{q}&rdquo;
              </span>
            )}
            {language && (
              <span className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1">
                <LibraryBig className="h-3.5 w-3.5" />
                {language}
              </span>
            )}
            {status && <StatusBadge status={status} />}
          </div>
          {hasActiveFilters && (
            <button
              className="inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-accent"
              onClick={handleClearFilters}
              type="button"
            >
              <X className="h-3.5 w-3.5" />
              Clear filters
            </button>
          )}
        </div>

        {isPending && <LoadingState />}

        {isError && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg bg-card/75 px-4 py-16 text-center ring-1 ring-border">
            <BookOpen className="h-10 w-10 text-muted-foreground/50" />
            <p className="max-w-md text-sm text-destructive">
              {toReaderError(error)}
            </p>
            <button
              className="text-sm text-primary transition-colors hover:text-accent"
              onClick={() => router.refresh()}
              type="button"
            >
              Try again
            </button>
          </div>
        )}

        {!isPending && !isError && novels.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg bg-card/75 px-4 py-16 text-center ring-1 ring-border">
            <BookOpen className="h-10 w-10 text-muted-foreground/50" />
            <h2 className="font-literary text-xl font-medium">
              No matching novels found
            </h2>
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              {hasActiveFilters
                ? "No translated novels matched this search. Clear filters or try a broader title, author, source language, or status."
                : "The public catalog is empty right now. Check back after translated novels are published."}
            </p>
            {hasActiveFilters && (
              <button
                className="inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-accent"
                onClick={handleClearFilters}
                type="button"
              >
                <X className="h-3.5 w-3.5" />
                Clear filters
              </button>
            )}
          </div>
        )}

        {!isPending && !isError && novels.length > 0 && (
          <>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
              {novels.map((novel) => (
                <NovelCard key={novel.novel_id} novel={novel} />
              ))}
            </div>

            {hasNextPage(total, page, pageSize) && (
              <div className="mt-8 flex justify-center">
                <button
                  className="inline-flex h-10 items-center justify-center rounded-md border border-border bg-card px-6 text-sm font-medium transition-colors hover:bg-muted"
                  onClick={handleNextPage}
                  type="button"
                >
                  Next page
                </button>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

export function BrowsePage({ basePath, description, title }: BrowsePageProps) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-10 max-w-4xl">
        <p className="font-metadata text-xs uppercase tracking-[0.22em] text-accent">
          物語を探す
        </p>
        <h1 className="mt-3 font-literary text-4xl font-medium tracking-normal text-foreground md:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          {description}
        </p>
      </header>

      <SectionHeader
        eyebrow="Discovery"
        title="Find your next translation"
        description="Search by title or author, then narrow the catalog by source language and translation status."
      />

      <div className="mt-6">
        <Suspense fallback={<LoadingState />}>
          <BrowseContent basePath={basePath} />
        </Suspense>
      </div>
    </main>
  );
}
