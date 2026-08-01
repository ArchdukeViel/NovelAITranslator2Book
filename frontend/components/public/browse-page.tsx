"use client";

import { useEffect, useState, FormEvent, Suspense, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowDownAZ,
  ArrowUpAZ,
  BookOpen,
  Filter,
  LayoutGrid,
  List,
  MinusCircle,
  PlusCircle,
  Search,
  Shuffle,
  X,
} from "lucide-react";

import { NovelCard } from "@/components/public/novel-card";
import { StatusBadge } from "@/components/public/status-badge";
import { useCatalog, useDebounce, useGenres } from "@/hooks/public";
import { publicApi } from "@/lib/public-api";
import { hasNextPage } from "@/lib/public-format";
import { publicNovelHref } from "@/lib/public-routes";
import type {
  CatalogOrder,
  CatalogParams,
  CatalogSortField,
} from "@/lib/public-types";

const STATUS_FILTERS = [
  { value: "", label: "Any status" },
  { value: "Ongoing", label: "Ongoing" },
  { value: "Completed", label: "Completed" },
  { value: "Hiatus", label: "Hiatus" },
  { value: "Dropped", label: "Dropped" },
] as const;

const SORT_OPTIONS: { value: CatalogSortField; label: string }[] = [
  { value: "added_at", label: "Recently added" },
  { value: "title", label: "Title" },
  { value: "chapter_count", label: "Chapter count" },
];

const ORDER_OPTIONS: { value: CatalogOrder; label: string }[] = [
  { value: "desc", label: "Descending" },
  { value: "asc", label: "Ascending" },
];

interface BrowsePageProps {
  basePath: string;
  title: string;
  description: string;
  preset?: Pick<CatalogParams, "genre_include" | "tag_include" | "source_key">;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Parse comma-separated param from URL into a Set. */
function parseCsvParam(raw: string | null): Set<string> {
  if (!raw) return new Set();
  return new Set(
    raw.split(",").map((s) => s.trim()).filter(Boolean)
  );
}

/** Serialize a Set to a comma-separated string (or undefined if empty). */
function serializeSet(set: Set<string>): string | undefined {
  if (set.size === 0) return undefined;
  return Array.from(set).sort().join(",");
}

function parseCsvWithPreset(raw: string | null, preset?: string): Set<string> {
  return new Set([...parseCsvParam(raw), ...parseCsvParam(preset ?? null)]);
}

// ---------------------------------------------------------------------------
// Tag typeahead internal sub-component
// ---------------------------------------------------------------------------

interface TagFilterSectionProps {
  label: string;
  icon: React.ReactNode;
  tone: "include" | "exclude";
  query: string;
  onQueryChange: (v: string) => void;
  selectedSet: Set<string>;
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
  /** Tags already selected on either side — hide from results. */
  allSelected: Set<string>;
}

function TagFilterSection({
  label,
  icon,
  tone,
  query,
  onQueryChange,
  selectedSet,
  onAdd,
  onRemove,
  allSelected,
}: TagFilterSectionProps) {
  const debouncedQuery = useDebounce(query.trim(), 300);

  const { data, isFetching, isError } = useQuery({
    queryKey: ["public", "tag-search", debouncedQuery.toLowerCase()],
    queryFn: () =>
      publicApi.searchTags({
        q: debouncedQuery,
        include_adult: false,
        limit: 10,
      }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  });

  // Filter out already-selected tags from results
  const filteredResults = useMemo(() => {
    if (!data) return [];
    return data.filter((t) => !allSelected.has(t.name));
  }, [data, allSelected]);

  const showDropdown = query.trim().length >= 2;
  const hasResults = filteredResults.length > 0;
  const isDoneFetching = !isFetching && !isError;

  return (
    <div className="rounded-md bg-background/55 p-3 ring-1 ring-border/45">
      <p className="mb-2 flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground">
        <span className="flex items-center gap-1.5">
          {icon}
          {label}
        </span>
        <span className="font-metadata uppercase tracking-[0.12em] text-muted-foreground/70">
          {tone === "include" ? "Required" : "Blocked"}
        </span>
      </p>

      {/* Selected tag chips */}
      {selectedSet.size > 0 && (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {Array.from(selectedSet).sort().map((tag) => (
            <span
              key={tag}
              className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${
                tone === "include"
                  ? "bg-primary/10 text-foreground ring-1 ring-primary/25"
                  : "bg-destructive/10 text-foreground ring-1 ring-destructive/25"
              }`}
            >
              {tone === "include" ? (
                <PlusCircle className="h-3 w-3 text-primary" aria-hidden="true" />
              ) : (
                <MinusCircle className="h-3 w-3 text-destructive" aria-hidden="true" />
              )}
              {tag}
              <button
                type="button"
                onClick={() => onRemove(tag)}
                className="inline-flex items-center text-muted-foreground transition-colors hover:text-destructive"
                aria-label={`Remove tag ${tag}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Search input */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Escape") onQueryChange(""); }}
          placeholder="Type to search tags…"
          autoComplete="off"
          aria-label={`${label} tag search`}
          className="h-8 w-full rounded-md border border-border/55 bg-card/75 px-2.5 text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground/60 focus:border-accent focus:bg-card"
        />

        {/* Dropdown */}
        {showDropdown && (
          <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-48 overflow-y-auto rounded-md border border-border/60 bg-card shadow-sm" aria-live="polite">
            {/* Loading */}
            {isFetching && (
              <p className="px-2.5 py-2 text-xs italic text-muted-foreground">
                Searching…
              </p>
            )}

            {/* Error */}
            {isError && (
              <p className="px-2.5 py-2 text-xs text-muted-foreground">
                Search unavailable.
              </p>
            )}

            {/* Results */}
            {isDoneFetching && hasResults && (
              <ul role="listbox" aria-label={`${label} tag suggestions`}>
                {filteredResults.map((tag) => (
                  <li key={tag.name} role="option" aria-selected="false">
                    <button
                      type="button"
                      onClick={() => onAdd(tag.name)}
                      className="w-full px-2.5 py-1.5 text-left text-xs text-foreground transition-colors hover:bg-muted"
                    >
                      {tag.name}
                      {tag.name_ja && (
                        <span className="ml-1.5 text-muted-foreground">
                          ({tag.name_ja})
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {/* No results */}
            {isDoneFetching && !hasResults && (
              <p className="px-2.5 py-2 text-xs text-muted-foreground">
                No matching tags.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// BrowseContent
// ---------------------------------------------------------------------------

function BrowseContent({ basePath, preset }: Pick<BrowsePageProps, "basePath" | "preset">) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const q = searchParams.get("q") ?? undefined;
  const publicationStatus = searchParams.get("publication_status") ?? undefined;
  const sort_by = (searchParams.get("sort_by") ?? undefined) as CatalogSortField | undefined;
  const order = (searchParams.get("order") ?? undefined) as CatalogOrder | undefined;
  const min_chapters_raw = searchParams.get("min_chapters");
  const max_chapters_raw = searchParams.get("max_chapters");
  const min_chapters = min_chapters_raw ? Number(min_chapters_raw) : undefined;
  const max_chapters = max_chapters_raw ? Number(max_chapters_raw) : undefined;
  const page = Number(searchParams.get("page") ?? "1") || 1;
  const pageSize = 20;

  const genreIncludeSet = useMemo(() => parseCsvWithPreset(searchParams.get("genre_include"), preset?.genre_include), [searchParams, preset?.genre_include]);
  const genreExcludeSet = useMemo(() => parseCsvParam(searchParams.get("genre_exclude")), [searchParams]);
  const tagIncludeSet = useMemo(() => parseCsvWithPreset(searchParams.get("tag_include"), preset?.tag_include), [searchParams, preset?.tag_include]);
  const tagExcludeSet = useMemo(() => parseCsvParam(searchParams.get("tag_exclude")), [searchParams]);

  const allTagSet = useMemo(() => new Set([...tagIncludeSet, ...tagExcludeSet]), [tagIncludeSet, tagExcludeSet]);

  const hasGenreFilters = genreIncludeSet.size > 0 || genreExcludeSet.size > 0;
  const hasTagFilters = tagIncludeSet.size > 0 || tagExcludeSet.size > 0;

  const [filtersOpen, setFiltersOpen] = useState(false);
  const view = searchParams.get("view") === "list" ? "list" : "grid";

  // Tag search query state
  const [includeTagQuery, setIncludeTagQuery] = useState("");
  const [excludeTagQuery, setExcludeTagQuery] = useState("");

  // Mobile Search tab: focus the catalog search input when arriving via
  // ?focus=search, then strip the param for a clean URL. basePath keeps the
  // cleanup on the current catalog page (home or browse) rather than
  // hard-coding a route.
  useEffect(() => {
    if (searchParams.get("focus") !== "search") return;
    const input = document.getElementById("catalog-search");
    input?.focus();
    const sp = new URLSearchParams(searchParams.toString());
    sp.delete("focus");
    const query = sp.toString();
    router.replace(query ? `${basePath}?${query}` : basePath, {
      scroll: false,
    });
  }, [searchParams, router, basePath]);

  // Fetch genres for the filter UI
  const { data: genresData, isPending: genresPending, isError: genresError } = useGenres();

  const params: CatalogParams = {
    q,
    publication_status: publicationStatus,
    source_key: preset?.source_key,
    sort_by: sort_by ?? "added_at",
    order: order ?? "desc",
    min_chapters,
    max_chapters,
    genre_include: serializeSet(genreIncludeSet),
    genre_exclude: serializeSet(genreExcludeSet),
    tag_include: serializeSet(tagIncludeSet),
    tag_exclude: serializeSet(tagExcludeSet),
    page,
    page_size: pageSize,
  };
  const { data, isPending, isError, error } = useCatalog(params);

  const hasActiveFilters = Boolean(
    q || publicationStatus ||
    min_chapters !== undefined || max_chapters !== undefined ||
    hasGenreFilters || hasTagFilters
  );
  const activeFilterCount =
    Number(Boolean(q)) +
    Number(Boolean(publicationStatus)) +
    Number(min_chapters !== undefined || max_chapters !== undefined) +
    genreIncludeSet.size +
    genreExcludeSet.size +
    tagIncludeSet.size +
    tagExcludeSet.size;

  useEffect(() => {
    if (!filtersOpen) return;
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setFiltersOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [filtersOpen]);

  // Preserve catalog position across a detail-page round trip. Browser/Next
  // restoration remains primary; this covers mobile history entries that
  // lose their scroll offset after client navigation.
  useEffect(() => {
    const key = `catalog-scroll:${basePath}?${searchParams}`;
    const saved = sessionStorage.getItem(key);
    if (saved) requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
    const save = () => sessionStorage.setItem(key, String(window.scrollY));
    window.addEventListener("pagehide", save);
    return () => window.removeEventListener("pagehide", save);
  }, [basePath, searchParams]);

  function pushParams(next: CatalogParams) {
    const sp = new URLSearchParams();
    if (next.q) sp.set("q", next.q);
    if (next.publication_status) sp.set("publication_status", next.publication_status);
    if (next.sort_by && next.sort_by !== "added_at") sp.set("sort_by", next.sort_by);
    if (next.order && next.order !== "desc") sp.set("order", next.order);
    if (next.min_chapters !== undefined) sp.set("min_chapters", String(next.min_chapters));
    if (next.max_chapters !== undefined) sp.set("max_chapters", String(next.max_chapters));
    if (next.genre_include) {
      const values = parseCsvParam(next.genre_include);
      for (const presetValue of parseCsvParam(preset?.genre_include ?? null)) values.delete(presetValue);
      const serialized = serializeSet(values);
      if (serialized) sp.set("genre_include", serialized);
    }
    if (next.genre_exclude) sp.set("genre_exclude", next.genre_exclude);
    if (next.tag_include) {
      const values = parseCsvParam(next.tag_include);
      for (const presetValue of parseCsvParam(preset?.tag_include ?? null)) values.delete(presetValue);
      const serialized = serializeSet(values);
      if (serialized) sp.set("tag_include", serialized);
    }
    if (next.tag_exclude) sp.set("tag_exclude", next.tag_exclude);
    if (view === "list") sp.set("view", "list");
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

  function handleStatusChange(nextStatus: string) {
    pushParams({
      ...params,
      publication_status: nextStatus || undefined,
      page: 1,
    });
  }

  function handleSortChange(nextSortBy: CatalogSortField) {
    pushParams({ ...params, sort_by: nextSortBy, page: 1 });
  }

  function handleOrderChange(nextOrder: CatalogOrder) {
    pushParams({ ...params, order: nextOrder, page: 1 });
  }

  function handleAdvancedSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const minRaw = String(formData.get("min_chapters") ?? "").trim();
    const maxRaw = String(formData.get("max_chapters") ?? "").trim();
    const minVal = minRaw ? Math.max(0, Number(minRaw)) : undefined;
    const maxVal = maxRaw ? Math.max(0, Number(maxRaw)) : undefined;
    pushParams({
      ...params,
      min_chapters: Number.isFinite(minVal) ? minVal : undefined,
      max_chapters: Number.isFinite(maxVal) ? maxVal : undefined,
      page: 1,
    });
  }

  // ---- Genre handlers ----

  /** Tri-state genre click: neutral → include → exclude → neutral */
  function handleGenreClick(slug: string) {
    const nextInclude = new Set(genreIncludeSet);
    const nextExclude = new Set(genreExcludeSet);

    if (nextInclude.has(slug)) {
      // include → exclude
      nextInclude.delete(slug);
      nextExclude.add(slug);
    } else if (nextExclude.has(slug)) {
      // exclude → neutral
      nextExclude.delete(slug);
    } else {
      // neutral → include
      nextInclude.add(slug);
    }

    pushParams({
      ...params,
      genre_include: serializeSet(nextInclude),
      genre_exclude: serializeSet(nextExclude),
      page: 1,
    });
  }

  // ---- Tag handlers ----

  function handleTagIncludeAdd(name: string) {
    const nextInclude = new Set(tagIncludeSet);
    const nextExclude = new Set(tagExcludeSet);
    nextInclude.add(name);
    nextExclude.delete(name); // mutually exclusive
    setIncludeTagQuery("");
    pushParams({
      ...params,
      tag_include: serializeSet(nextInclude),
      tag_exclude: serializeSet(nextExclude),
      page: 1,
    });
  }

  function handleTagIncludeRemove(name: string) {
    const nextInclude = new Set(tagIncludeSet);
    nextInclude.delete(name);
    pushParams({
      ...params,
      tag_include: serializeSet(nextInclude),
      tag_exclude: serializeSet(tagExcludeSet),
      page: 1,
    });
  }

  function handleTagExcludeAdd(name: string) {
    const nextInclude = new Set(tagIncludeSet);
    const nextExclude = new Set(tagExcludeSet);
    nextExclude.add(name);
    nextInclude.delete(name); // mutually exclusive
    setExcludeTagQuery("");
    pushParams({
      ...params,
      tag_include: serializeSet(nextInclude),
      tag_exclude: serializeSet(nextExclude),
      page: 1,
    });
  }

  function handleTagExcludeRemove(name: string) {
    const nextExclude = new Set(tagExcludeSet);
    nextExclude.delete(name);
    pushParams({
      ...params,
      tag_include: serializeSet(tagIncludeSet),
      tag_exclude: serializeSet(nextExclude),
      page: 1,
    });
  }

  function handleNextPage() {
    pushParams({ ...params, page: page + 1 });
  }

  function handleClearFilters() {
    pushParams({ sort_by: params.sort_by, order: params.order, page: 1 });
  }

  function handleViewChange(nextView: "grid" | "list") {
    const sp = new URLSearchParams(searchParams.toString());
    if (nextView === "list") sp.set("view", "list");
    else sp.delete("view");
    router.push(`${basePath}${sp.toString() ? `?${sp}` : ""}`);
  }

  function removeParam(name: string, value?: string) {
    const sp = new URLSearchParams(searchParams.toString());
    let destination = basePath;
    if (value) {
      const presetValue = preset?.[name as "genre_include" | "tag_include"] as string | undefined;
      const values = parseCsvWithPreset(sp.get(name), presetValue);
      values.delete(value);
      if (parseCsvParam(presetValue ?? null).has(value)) destination = "/browse-novels";
      if (values.size) sp.set(name, serializeSet(values)!);
      else sp.delete(name);
    } else {
      sp.delete(name);
    }
    sp.delete("page");
    router.push(`${destination}${sp.toString() ? `?${sp}` : ""}`);
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;
  const effectiveSort = sort_by ?? "added_at";
  const effectiveOrder = order ?? "desc";

  return (
    <div className="grid gap-8 lg:grid-cols-[18rem_minmax(0,1fr)] lg:items-start">
      {filtersOpen && (
        <button
          type="button"
          aria-label="Close filters"
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setFiltersOpen(false)}
        />
      )}
      <section
        aria-label="Browse filters"
        role={filtersOpen ? "dialog" : undefined}
        aria-modal={filtersOpen ? "true" : undefined}
        className={`${filtersOpen ? "fixed" : "hidden"} inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-xl bg-card p-4 shadow-xl ring-1 ring-border lg:static lg:block lg:max-h-none lg:overflow-visible lg:rounded-lg lg:bg-card/60 lg:p-0 lg:shadow-sm`}
      >
        <div className="sticky top-0 z-10 mb-4 flex items-center justify-between gap-3 border-b border-border bg-card px-1 pb-3 pt-1 lg:rounded-t-lg lg:px-4 lg:pt-4">
          <h2 className="flex items-center gap-2 font-medium"><Filter className="h-4 w-4 text-accent" /> Filters</h2>
          {hasActiveFilters && <button type="button" onClick={handleClearFilters} className="text-xs text-primary">Clear all</button>}
        </div>
        <div className="space-y-5 lg:px-4 lg:pb-4">
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

        <div className="mt-5">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium">
            <Filter className="h-4 w-4 text-accent" />
            Status
          </div>
          <div className="flex flex-wrap gap-2">
            {STATUS_FILTERS.map(({ value, label }) => (
              <button
                key={value}
                type="button"
                onClick={() => handleStatusChange(value)}
                className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                  (publicationStatus ?? "") === value
                    ? "bg-primary text-primary-foreground"
                    : "bg-secondary text-secondary-foreground hover:bg-muted"
                }`}
                aria-pressed={(publicationStatus ?? "") === value}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Sort direction stays with filters; sort field lives in the results header. */}
        <div className="mt-5 flex flex-wrap items-end gap-4">
          <div>
            <label
              htmlFor="order-select"
              className="mb-1.5 block font-metadata text-xs uppercase tracking-[0.14em] text-muted-foreground"
            >
              Direction
            </label>
            <select
              id="order-select"
              value={effectiveOrder}
              onChange={(e) => handleOrderChange(e.target.value as CatalogOrder)}
              className="h-9 rounded-md border border-border bg-muted px-3 text-sm text-foreground outline-none transition-colors focus:border-accent focus:bg-card"
            >
              {ORDER_OPTIONS.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Advanced search: chapter count + genre + tag filters */}
          <form id="catalog-filters-form" onSubmit={handleAdvancedSubmit} className="mt-4 space-y-5 border-t border-border/50 pt-4">
            <div>
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="font-metadata text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  Chapter count
                </p>
              </div>
              <div className="flex flex-wrap items-end gap-3">
                <div>
                  <label
                    htmlFor="min-chapters"
                    className="mb-1 block text-xs text-muted-foreground"
                  >
                    Minimum
                  </label>
                  <input
                    id="min-chapters"
                    name="min_chapters"
                    type="number"
                    min={0}
                    step={1}
                    defaultValue={min_chapters ?? ""}
                    placeholder="0"
                    className="h-9 w-24 rounded-md border border-border/60 bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-accent"
                  />
                </div>
                <span className="pb-2 text-muted-foreground">–</span>
                <div>
                  <label
                    htmlFor="max-chapters"
                    className="mb-1 block text-xs text-muted-foreground"
                  >
                    Maximum
                  </label>
                  <input
                    id="max-chapters"
                    name="max_chapters"
                    type="number"
                    min={0}
                    step={1}
                    defaultValue={max_chapters ?? ""}
                    placeholder="∞"
                    className="h-9 w-24 rounded-md border border-border/60 bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-accent"
                  />
                </div>
                <button
                  type="submit"
                  className="inline-flex h-9 items-center gap-1.5 rounded-md bg-primary px-4 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Apply
                </button>
              </div>
            </div>

            {/* Genre filters */}
            <div className="border-t border-border/35 pt-4">
              <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
                <div>
                  <p className="font-metadata text-xs uppercase tracking-[0.14em] text-muted-foreground">
                    Genres
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground/80">
                    Click once to include. Click again to exclude.
                  </p>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-muted-foreground" aria-hidden="true">
                  <span className="inline-flex items-center gap-1">
                    <PlusCircle className="h-3 w-3 text-primary" />
                    Include
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <MinusCircle className="h-3 w-3 text-destructive" />
                    Exclude
                  </span>
                </div>
              </div>

              {genresPending && (
                <p className="text-xs italic text-muted-foreground">
                  Loading genres…
                </p>
              )}

              {genresError && (
                <p className="text-xs italic text-muted-foreground">
                  Genres temporarily unavailable.
                </p>
              )}

              {genresData && genresData.length === 0 && (
                <p className="text-xs italic text-muted-foreground">
                  No genres available.
                </p>
              )}

              {genresData && genresData.length > 0 && (
                <div
                  className="grid grid-cols-2 gap-1.5 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5"
                  role="group"
                  aria-label="Genre filters"
                >
                  {genresData.map((genre) => {
                    const state = genreIncludeSet.has(genre.slug)
                      ? "include"
                      : genreExcludeSet.has(genre.slug)
                        ? "exclude"
                        : "neutral";
                    const stateLabel =
                      state === "include"
                        ? `${genre.name_en ?? genre.slug}: included`
                        : state === "exclude"
                          ? `${genre.name_en ?? genre.slug}: excluded`
                          : `${genre.name_en ?? genre.slug}: not selected`;
                    return (
                      <button
                        key={genre.slug}
                        type="button"
                        onClick={() => handleGenreClick(genre.slug)}
                        aria-label={stateLabel}
                        className={`inline-flex min-h-8 items-center justify-between gap-2 rounded px-2.5 py-1 text-left text-xs font-medium transition-colors ${
                          state === "include"
                            ? "bg-primary/10 text-foreground ring-1 ring-primary/35"
                            : state === "exclude"
                              ? "bg-destructive/10 text-foreground ring-1 ring-destructive/35"
                              : "bg-background/65 text-muted-foreground ring-1 ring-border/40 hover:bg-muted hover:text-foreground"
                        }`}
                      >
                        <span className="truncate">{genre.name_en ?? genre.slug}</span>
                        {state === "include" && (
                          <span className="inline-flex shrink-0 items-center gap-1 rounded bg-primary/20 px-1.5 py-0.5 font-metadata text-[10px] uppercase tracking-[0.08em] text-primary-text">
                            <PlusCircle className="h-3 w-3" aria-hidden="true" />
                            In
                          </span>
                        )}
                        {state === "exclude" && (
                          <span className="inline-flex shrink-0 items-center gap-1 rounded bg-destructive/15 px-1.5 py-0.5 font-metadata text-[10px] uppercase tracking-[0.08em] text-destructive-text">
                            <MinusCircle className="h-3 w-3" aria-hidden="true" />
                            Out
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Tag filters */}
            <div className="border-t border-border/35 pt-4">
              <div className="mb-3">
                <p className="font-metadata text-xs uppercase tracking-[0.14em] text-muted-foreground">
                  Tags
                </p>
                <p className="mt-1 text-xs text-muted-foreground/80">
                  Add required tags on the left, blocked tags on the right.
                </p>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <TagFilterSection
                  label="Must include"
                  tone="include"
                  icon={<PlusCircle className="h-3.5 w-3.5 text-primary" />}
                  query={includeTagQuery}
                  onQueryChange={setIncludeTagQuery}
                  selectedSet={tagIncludeSet}
                  onAdd={handleTagIncludeAdd}
                  onRemove={handleTagIncludeRemove}
                  allSelected={allTagSet}
                />

                <TagFilterSection
                  label="Exclude"
                  tone="exclude"
                  icon={<MinusCircle className="h-3.5 w-3.5 text-destructive" />}
                  query={excludeTagQuery}
                  onQueryChange={setExcludeTagQuery}
                  selectedSet={tagExcludeSet}
                  onAdd={handleTagExcludeAdd}
                  onRemove={handleTagExcludeRemove}
                  allSelected={allTagSet}
                />
              </div>
            </div>
          </form>
        </div>
        <div className="sticky bottom-0 -mx-4 mt-4 flex gap-3 border-t border-border bg-card p-4 lg:hidden">
          <button type="button" onClick={handleClearFilters} className="h-10 flex-1 rounded-md border border-border">Clear</button>
          <button type="submit" form="catalog-filters-form" onClick={() => setFiltersOpen(false)} className="h-10 flex-1 rounded-md bg-primary text-primary-foreground">Apply</button>
        </div>
      </section>

      <section aria-label="Catalog results">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span className="font-metadata">
              {isPending ? "Loading" : total} novel
              {!isPending && total === 1 ? "" : "s"}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" onClick={() => setFiltersOpen(true)} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-xs lg:hidden">
              <Filter className="h-3.5 w-3.5" /> Filters{activeFilterCount ? ` (${activeFilterCount})` : ""}
            </button>
            <label htmlFor="sort-select" className="sr-only">Sort by</label>
            <select id="sort-select" value={effectiveSort} onChange={(e) => handleSortChange(e.target.value as CatalogSortField)} className="h-9 rounded-md border border-border bg-card px-2 text-xs">
              {SORT_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
            <div role="group" aria-label="Catalog view" className="flex rounded-md border border-border">
              <button type="button" aria-label="Grid view" aria-pressed={view === "grid"} onClick={() => handleViewChange("grid")} className="p-2"><LayoutGrid className="h-4 w-4" /></button>
              <button type="button" aria-label="List view" aria-pressed={view === "list"} onClick={() => handleViewChange("list")} className="p-2"><List className="h-4 w-4" /></button>
            </div>
            <button type="button" disabled={novels.length === 0} onClick={() => novels.length && router.push(publicNovelHref(novels[Math.floor(Math.random() * novels.length)].slug))} className="inline-flex h-9 items-center gap-1.5 rounded-md border border-border px-3 text-xs disabled:opacity-50">
              <Shuffle className="h-3.5 w-3.5" /> Surprise me
            </button>
          </div>
        </div>

        <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            {q && (
              <button type="button" aria-label="Remove search filter" onClick={() => removeParam("q")} className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1">
                <Search className="h-3.5 w-3.5" />
                &ldquo;{q}&rdquo;
                <X className="h-3 w-3" />
              </button>
            )}
            {publicationStatus && <button type="button" aria-label="Remove status filter" onClick={() => removeParam("publication_status")}><StatusBadge status={publicationStatus} /></button>}
            {(min_chapters !== undefined || max_chapters !== undefined) && (
              <button type="button" aria-label="Remove chapter count filter" onClick={() => { const sp = new URLSearchParams(searchParams.toString()); sp.delete("min_chapters"); sp.delete("max_chapters"); router.push(`${basePath}${sp.toString() ? `?${sp}` : ""}`); }} className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 font-metadata text-xs">
                <BookOpen className="h-3.5 w-3.5" />
                {min_chapters ?? 0}–{max_chapters ?? "∞"} ch.
                <X className="h-3 w-3" />
              </button>
            )}
            {Array.from(genreIncludeSet).map((slug) => <button key={`gi-${slug}`} type="button" aria-label={`Remove included genre ${slug}`} onClick={() => removeParam("genre_include", slug)} className="text-xs text-primary">× {slug}</button>)}
            {Array.from(genreExcludeSet).map((slug) => <button key={`ge-${slug}`} type="button" aria-label={`Remove excluded genre ${slug}`} onClick={() => removeParam("genre_exclude", slug)} className="text-xs text-primary">× {slug}</button>)}
            {Array.from(tagIncludeSet).map((tag) => <button key={`ti-${tag}`} type="button" aria-label={`Remove included tag ${tag}`} onClick={() => removeParam("tag_include", tag)} className="text-xs text-primary">× {tag}</button>)}
            {Array.from(tagExcludeSet).map((tag) => <button key={`te-${tag}`} type="button" aria-label={`Remove excluded tag ${tag}`} onClick={() => removeParam("tag_exclude", tag)} className="text-xs text-primary">× {tag}</button>)}
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground/70">
              {effectiveOrder === "asc" ? (
                <ArrowDownAZ className="h-3.5 w-3.5" />
              ) : (
                <ArrowUpAZ className="h-3.5 w-3.5" />
              )}
              {SORT_OPTIONS.find((o) => o.value === effectiveSort)?.label}
            </span>
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
            <p className="max-w-md text-sm text-muted-foreground">
              Could not load novels right now. This is usually temporary.
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
                ? "No novels matched this search. Clear filters or try a broader title, author, or status."
                : "The catalog is empty right now. Check back after novels are published."}
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
            <div className={view === "list" ? "grid gap-5" : "grid gap-5 sm:grid-cols-2 xl:grid-cols-3"}>
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

// ---------------------------------------------------------------------------
// Public export
// ---------------------------------------------------------------------------

export function BrowsePage({ basePath, description, title, preset }: BrowsePageProps) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
      <header className="mb-10 max-w-4xl">
        <p className="font-metadata text-xs uppercase tracking-[0.22em] text-accent">
          探索
        </p>
        <h1 className="mt-3 font-literary text-4xl font-medium tracking-normal text-foreground md:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-7 text-muted-foreground">
          {description}
        </p>
      </header>



      <div className="mt-6">
        <Suspense fallback={<LoadingState />}>
          <BrowseContent basePath={basePath} preset={preset} />
        </Suspense>
      </div>
    </main>
  );
}
