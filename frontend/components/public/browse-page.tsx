"use client";

import {
  useEffect,
  useState,
  FormEvent,
  Suspense,
  useMemo,
  useRef,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  BookOpen,
  Check,
  ChevronDown,
  Filter,
  Minus,
  Search,
  Shuffle,
  X,
} from "lucide-react";

import { NovelCard } from "@/components/public/novel-card";
import { StatusBadge } from "@/components/public/status-badge";
import { useCatalog, useDebounce, useGenres, useTags } from "@/hooks/public";
import { publicApi } from "@/lib/public-api";
import { hasNextPage } from "@/lib/public-format";
import { publicNovelHref } from "@/lib/public-routes";
import { toPublicationStatus } from "@/lib/public-types";
import type {
  CatalogOrder,
  CatalogParams,
  CatalogSortField,
} from "@/lib/public-types";
import { cn } from "@/lib/utils";

const STATUS_FILTERS = [
  { value: "", label: "Any status" },
  { value: "Ongoing", label: "Ongoing" },
  { value: "Completed", label: "Completed" },
  { value: "Hiatus", label: "Hiatus" },
  { value: "Dropped", label: "Dropped" },
] as const;

const SORT_OPTIONS: { value: CatalogSortField; label: string }[] = [
  { value: "added_at", label: "Recently added" },
  { value: "updated_at", label: "Recently updated" },
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
    raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
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
// Tag combobox and dropdown sub-component
// ---------------------------------------------------------------------------

const TAG_CATEGORIES = [
  "All",
  "Protagonist Archetypes",
  "Adaptations",
  "Power Systems",
  "Themes",
  "World & Setting",
] as const;

type TagCategory = (typeof TAG_CATEGORIES)[number];

const TAG_CATEGORY_MAP: Record<string, TagCategory> = {
  "Anime Adaptation": "Adaptations",
  "Light Novel Adaptation": "Adaptations",
  "Manga Adaptation": "Adaptations",
  "Web Novel Adaptation": "Adaptations",
  "Female Adventurer": "Protagonist Archetypes",
  "Gender Bender": "Protagonist Archetypes",
  "Overpowered / Cheat": "Protagonist Archetypes",
  "Male Protagonist": "Protagonist Archetypes",
  "Female Protagonist": "Protagonist Archetypes",
  "Antihero Protagonist": "Protagonist Archetypes",
  "Clever Protagonist": "Protagonist Archetypes",
  Magic: "Power Systems",
  Cultivation: "Power Systems",
  System: "Power Systems",
  "Level System": "Power Systems",
  "Martial Arts": "Power Systems",
  Adventure: "World & Setting",
  Fantasy: "World & Setting",
  Guild: "World & Setting",
  "Isekai Reincarnation": "World & Setting",
  Spirits: "World & Setting",
  Dungeon: "World & Setting",
  Family: "Themes",
  "Happy Ending": "Themes",
  "Interspecies Romance": "Themes",
  "Graphic Violence": "Themes",
  "Omorashi / Watersports": "Themes",
  R15: "Themes",
  Serious: "Themes",
  "Social Status Difference": "Themes",
};

const DEFAULT_AVAILABLE_TAGS: { name: string; name_ja: string | null }[] = [
  { name: "Adventure", name_ja: null },
  { name: "Anime Adaptation", name_ja: null },
  { name: "Family", name_ja: null },
  { name: "Fantasy", name_ja: null },
  { name: "Female Adventurer", name_ja: null },
  { name: "Gender Bender", name_ja: null },
  { name: "Graphic Violence", name_ja: null },
  { name: "Guild", name_ja: null },
  { name: "Happy Ending", name_ja: null },
  { name: "Interspecies Romance", name_ja: null },
  { name: "Isekai Reincarnation", name_ja: null },
  { name: "Light Novel Adaptation", name_ja: null },
  { name: "Manga Adaptation", name_ja: null },
  { name: "Overpowered / Cheat", name_ja: null },
  { name: "R15", name_ja: null },
  { name: "Serious", name_ja: null },
  { name: "Social Status Difference", name_ja: null },
  { name: "Spirits", name_ja: null },
];

interface TagFilterComboboxProps {
  label: string;
  placeholder?: string;
  tone: "include" | "exclude";
  query: string;
  onQueryChange: (v: string) => void;
  selectedSet: Set<string>;
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
  allSelected: Set<string>;
  availableTags?: { name: string; name_ja?: string | null }[];
}

function TagFilterCombobox({
  label,
  placeholder = "Select...",
  tone,
  query,
  onQueryChange,
  selectedSet,
  onAdd,
  onRemove,
  allSelected,
  availableTags = [],
}: TagFilterComboboxProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<TagCategory>("All");
  const [highlightedIndex, setHighlightedIndex] = useState<number>(-1);

  const debouncedQuery = useDebounce(query.trim(), 200);

  const {
    data: searchResults,
    isFetching,
    isError,
  } = useQuery({
    queryKey: ["public", "tag-search", debouncedQuery.toLowerCase()],
    queryFn: () =>
      publicApi.searchTags({
        q: debouncedQuery,
        include_adult: false,
        limit: 20,
      }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30_000,
  });

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const visibleTags = useMemo(() => {
    let source: { name: string; name_ja?: string | null }[];
    if (debouncedQuery.length >= 2 && searchResults !== undefined) {
      source = searchResults;
    } else if (query.trim().length > 0) {
      const q = query.trim().toLowerCase();
      source = availableTags.filter((t) => {
        const matchName = t.name.toLowerCase().includes(q);
        const matchJa = t.name_ja ? t.name_ja.toLowerCase().includes(q) : false;
        return matchName || matchJa;
      });
    } else {
      source = availableTags;
    }

    return source
      .filter((t) => !allSelected.has(t.name))
      .filter((t) => {
        if (selectedCategory !== "All") {
          const cat = TAG_CATEGORY_MAP[t.name] ?? "Themes";
          if (cat !== selectedCategory) return false;
        }
        return true;
      });
  }, [
    debouncedQuery,
    searchResults,
    query,
    availableTags,
    allSelected,
    selectedCategory,
  ]);

  const showDropdown = isOpen || query.trim().length >= 2;
  const isDoneSearching = !isFetching && !isError;
  const activeHighlight =
    highlightedIndex >= 0 && highlightedIndex < visibleTags.length
      ? highlightedIndex
      : -1;

  return (
    <div ref={containerRef} className="relative">
      <div
        onClick={() => {
          setIsOpen(true);
          inputRef.current?.focus();
        }}
        className={`flex min-h-[38px] w-full flex-wrap items-center gap-1.5 rounded-lg border bg-muted/40 px-2.5 py-1.5 text-xs transition-colors cursor-text ${
          showDropdown
            ? "border-border ring-1 ring-ring bg-card"
            : "border-border/60 hover:border-border"
        }`}
      >
        {/* Selected tag chips */}
        {Array.from(selectedSet)
          .sort()
          .map((tag) => (
            <span
              key={tag}
              className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                tone === "exclude"
                  ? "border border-destructive/30 bg-destructive/10 text-destructive dark:bg-destructive/20"
                  : "border border-border/60 bg-background/80 text-foreground shadow-xs"
              }`}
            >
              <span>{tag}</span>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(tag);
                }}
                className="relative inline-flex h-4 w-4 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
                aria-label={`Remove tag ${tag}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}

        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            onQueryChange(e.target.value);
            if (!isOpen) setIsOpen(true);
            setHighlightedIndex(-1);
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Escape") {
              setIsOpen(false);
              onQueryChange("");
              setHighlightedIndex(-1);
            } else if (e.key === "ArrowDown") {
              e.preventDefault();
              if (!isOpen) {
                setIsOpen(true);
              } else if (visibleTags.length > 0) {
                setHighlightedIndex((prev) => (prev + 1) % visibleTags.length);
              }
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              if (visibleTags.length > 0) {
                setHighlightedIndex((prev) =>
                  prev <= 0 ? visibleTags.length - 1 : prev - 1,
                );
              }
            } else if (e.key === "Enter" && activeHighlight >= 0) {
              e.preventDefault();
              onAdd(visibleTags[activeHighlight].name);
              onQueryChange("");
              setHighlightedIndex(-1);
            } else if (
              e.key === "Backspace" &&
              !query &&
              selectedSet.size > 0
            ) {
              const arr = Array.from(selectedSet).sort();
              onRemove(arr[arr.length - 1]);
            }
          }}
          placeholder={placeholder}
          autoComplete="off"
          aria-label={`${label} tag search`}
          className="min-w-[4rem] flex-1 bg-transparent py-0.5 text-xs text-foreground outline-none placeholder:text-muted-foreground/70"
        />

        {/* Right controls */}
        <div className="ml-auto flex items-center gap-1 pl-1 text-muted-foreground">
          {selectedSet.size > 0 && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                Array.from(selectedSet).forEach(onRemove);
              }}
              aria-label={`Clear all ${label}`}
              className="relative rounded p-0.5 hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <span className="h-4 w-[1px] bg-border/60" />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsOpen(!isOpen);
              if (!isOpen) inputRef.current?.focus();
            }}
            aria-label={`Toggle ${label} dropdown`}
            className="relative p-0.5 hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform duration-150 ${
                showDropdown ? "rotate-180 text-foreground" : ""
              }`}
            />
          </button>
        </div>
      </div>

      {/* Dropdown Menu (Image 4) */}
      {showDropdown && (
        <div
          className="absolute left-0 right-0 top-full z-40 mt-1 max-h-72 overflow-hidden rounded-md border border-border bg-card shadow-lg animate-in fade-in-50 zoom-in-95"
          role="listbox"
          aria-label={`${label} options`}
        >
          {/* Category filter pills */}
          <div className="flex items-center gap-1 overflow-x-auto border-b border-border/50 bg-muted/30 p-1.5 text-xs no-scrollbar">
            {TAG_CATEGORIES.map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedCategory(cat);
                  setHighlightedIndex(-1);
                  inputRef.current?.focus();
                }}
                className={`rounded px-2 py-0.5 text-[11px] font-medium whitespace-nowrap transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                  selectedCategory === cat
                    ? "bg-foreground text-background font-semibold"
                    : "border border-border/60 bg-background/80 text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          {/* Available tags scrollable list */}
          <div className="max-h-56 overflow-y-auto p-1">
            {isFetching && debouncedQuery.length >= 2 && (
              <p className="px-2.5 py-2 text-xs italic text-muted-foreground">
                Searching…
              </p>
            )}

            {isError && (
              <p className="px-2.5 py-2 text-xs text-muted-foreground">
                Search unavailable.
              </p>
            )}

            {visibleTags.length > 0
              ? visibleTags.map((tag, idx) => {
                  const isHighlighted = idx === activeHighlight;
                  return (
                    <button
                      key={tag.name}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAdd(tag.name);
                        onQueryChange("");
                        setHighlightedIndex(-1);
                        inputRef.current?.focus();
                      }}
                      onMouseEnter={() => setHighlightedIndex(idx)}
                      className={`flex w-full items-center justify-between rounded px-2.5 py-2 text-left text-xs transition-colors pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                        isHighlighted
                          ? "bg-primary/10 text-primary dark:bg-primary/20 dark:text-primary font-medium"
                          : "text-foreground hover:bg-primary/10 hover:text-primary dark:hover:bg-primary/20 dark:hover:text-primary"
                      }`}
                    >
                      <span>{tag.name}</span>
                      {tag.name_ja && (
                        <span className="text-[11px] text-muted-foreground">
                          ({tag.name_ja})
                        </span>
                      )}
                    </button>
                  );
                })
              : isDoneSearching && (
                  <p className="p-3 text-center text-xs text-muted-foreground">
                    No matching tags.
                  </p>
                )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

function LoadingState() {
  return (
    <div className="flex flex-col gap-4">
      {Array.from({ length: 5 }).map((_, index) => (
        <div
          key={index}
          className="overflow-hidden rounded-xl border border-border/80 bg-card p-3.5 sm:p-4"
        >
          <div className="space-y-3">
            <div className="h-5 w-2/3 animate-pulse rounded bg-muted" />
            <div className="flex gap-3 sm:gap-4">
              <div className="aspect-2/3 w-24 sm:w-28 md:w-32 shrink-0 animate-pulse rounded-lg bg-muted" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
                <div className="h-3 w-full animate-pulse rounded bg-muted" />
                <div className="h-3 w-4/5 animate-pulse rounded bg-muted" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// BrowseContent
// ---------------------------------------------------------------------------

function BrowseContent({
  basePath,
  preset,
}: Pick<BrowsePageProps, "basePath" | "preset">) {
  const searchParams = useSearchParams();
  const router = useRouter();

  const q = searchParams.get("q") ?? undefined;
  const publicationStatus = toPublicationStatus(
    searchParams.get("publication_status"),
  );
  const search_synopsis = searchParams.get("search_synopsis") === "true";
  const sort_by = (searchParams.get("sort_by") ?? undefined) as
    | CatalogSortField
    | undefined;
  const order = (searchParams.get("order") ?? undefined) as
    | CatalogOrder
    | undefined;
  const genre_op = (searchParams.get("genre_op") ?? "and") as "and" | "or";
  const tag_op = (searchParams.get("tag_op") ?? "and") as "and" | "or";
  const min_chapters_raw = searchParams.get("min_chapters");
  const max_chapters_raw = searchParams.get("max_chapters");
  const min_chapters = min_chapters_raw ? Number(min_chapters_raw) : undefined;
  const max_chapters = max_chapters_raw ? Number(max_chapters_raw) : undefined;
  const page = Number(searchParams.get("page") ?? "1") || 1;
  const pageSize = 20;

  const genreIncludeSet = useMemo(
    () =>
      parseCsvWithPreset(
        searchParams.get("genre_include"),
        preset?.genre_include,
      ),
    [searchParams, preset?.genre_include],
  );
  const genreExcludeSet = useMemo(
    () => parseCsvParam(searchParams.get("genre_exclude")),
    [searchParams],
  );
  const tagIncludeSet = useMemo(
    () =>
      parseCsvWithPreset(searchParams.get("tag_include"), preset?.tag_include),
    [searchParams, preset?.tag_include],
  );
  const tagExcludeSet = useMemo(
    () => parseCsvParam(searchParams.get("tag_exclude")),
    [searchParams],
  );

  const allTagSet = useMemo(
    () => new Set([...tagIncludeSet, ...tagExcludeSet]),
    [tagIncludeSet, tagExcludeSet],
  );

  const hasGenreFilters = genreIncludeSet.size > 0 || genreExcludeSet.size > 0;
  const hasTagFilters = tagIncludeSet.size > 0 || tagExcludeSet.size > 0;

  const [filtersOpen, setFiltersOpen] = useState(false);

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
  const {
    data: genresData,
    isPending: genresPending,
    isError: genresError,
  } = useGenres();

  // Fetch available tags for tag comboboxes
  const { data: allTagsData } = useTags();
  const availableTags = useMemo(
    () =>
      allTagsData && allTagsData.length > 0
        ? allTagsData
        : DEFAULT_AVAILABLE_TAGS,
    [allTagsData],
  );

  const params: CatalogParams = {
    q,
    search_synopsis: search_synopsis || undefined,
    publication_status: publicationStatus,
    source_key: preset?.source_key,
    sort_by: sort_by ?? "added_at",
    order: order ?? "desc",
    min_chapters,
    max_chapters,
    genre_include: serializeSet(genreIncludeSet),
    genre_exclude: serializeSet(genreExcludeSet),
    genre_op: genre_op !== "and" ? genre_op : undefined,
    tag_include: serializeSet(tagIncludeSet),
    tag_exclude: serializeSet(tagExcludeSet),
    tag_op: tag_op !== "and" ? tag_op : undefined,
    page,
    page_size: pageSize,
  };
  const { data, isPending, isError, error } = useCatalog(params);

  const hasActiveFilters = Boolean(
    q ||
    search_synopsis ||
    publicationStatus ||
    min_chapters !== undefined ||
    max_chapters !== undefined ||
    hasGenreFilters ||
    hasTagFilters ||
    genre_op !== "and" ||
    tag_op !== "and",
  );
  const activeFilterCount =
    Number(Boolean(q)) +
    Number(Boolean(search_synopsis)) +
    Number(Boolean(publicationStatus)) +
    Number(min_chapters !== undefined || max_chapters !== undefined) +
    genreIncludeSet.size +
    genreExcludeSet.size +
    tagIncludeSet.size +
    tagExcludeSet.size +
    Number(genre_op !== "and") +
    Number(tag_op !== "and");

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
    if (saved)
      requestAnimationFrame(() => window.scrollTo(0, Number(saved) || 0));
    const save = () => sessionStorage.setItem(key, String(window.scrollY));
    window.addEventListener("pagehide", save);
    return () => window.removeEventListener("pagehide", save);
  }, [basePath, searchParams]);

  function pushParams(next: CatalogParams) {
    const sp = new URLSearchParams();
    if (next.q) sp.set("q", next.q);
    if (next.search_synopsis) sp.set("search_synopsis", "true");
    if (next.publication_status)
      sp.set("publication_status", next.publication_status);
    if (next.sort_by && next.sort_by !== "added_at")
      sp.set("sort_by", next.sort_by);
    if (next.order && next.order !== "desc") sp.set("order", next.order);
    if (next.min_chapters !== undefined)
      sp.set("min_chapters", String(next.min_chapters));
    if (next.max_chapters !== undefined)
      sp.set("max_chapters", String(next.max_chapters));
    if (next.genre_include) {
      const values = parseCsvParam(next.genre_include);
      for (const presetValue of parseCsvParam(preset?.genre_include ?? null))
        values.delete(presetValue);
      const serialized = serializeSet(values);
      if (serialized) sp.set("genre_include", serialized);
    }
    if (next.genre_exclude) sp.set("genre_exclude", next.genre_exclude);
    if (next.genre_op && next.genre_op !== "and")
      sp.set("genre_op", next.genre_op);
    if (next.tag_include) {
      const values = parseCsvParam(next.tag_include);
      for (const presetValue of parseCsvParam(preset?.tag_include ?? null))
        values.delete(presetValue);
      const serialized = serializeSet(values);
      if (serialized) sp.set("tag_include", serialized);
    }
    if (next.tag_exclude) sp.set("tag_exclude", next.tag_exclude);
    if (next.tag_op && next.tag_op !== "and") sp.set("tag_op", next.tag_op);
    if (next.page && next.page > 1) sp.set("page", String(next.page));
    const query = sp.toString();
    router.replace(`${basePath}${query ? `?${query}` : ""}`, { scroll: false });
  }

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const nextQuery = String(formData.get("q") ?? "").trim();
    pushParams({ ...params, q: nextQuery || undefined, page: 1 });
  }

  function handleSearchSynopsisChange(checked: boolean) {
    pushParams({
      ...params,
      search_synopsis: checked ? true : undefined,
      page: 1,
    });
  }

  function handleStatusChange(nextStatus: string) {
    pushParams({
      ...params,
      publication_status: toPublicationStatus(nextStatus),
      page: 1,
    });
  }

  function handleSortChange(nextSortBy: CatalogSortField) {
    pushParams({ ...params, sort_by: nextSortBy, page: 1 });
  }

  function handleOrderChange(nextOrder: CatalogOrder) {
    pushParams({ ...params, order: nextOrder, page: 1 });
  }

  function handleGenreOpChange(op: "and" | "or") {
    pushParams({
      ...params,
      genre_op: op !== "and" ? op : undefined,
      page: 1,
    });
  }

  function handleTagOpChange(op: "and" | "or") {
    pushParams({
      ...params,
      tag_op: op !== "and" ? op : undefined,
      page: 1,
    });
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

  /** 2-state genre click: neutral ↔ include (clears legacy exclude if set) */
  function handleGenreClick(slug: string) {
    const nextInclude = new Set(genreIncludeSet);
    const nextExclude = new Set(genreExcludeSet);
    if (nextInclude.has(slug)) {
      nextInclude.delete(slug);
      nextExclude.delete(slug);
    } else if (nextExclude.has(slug)) {
      nextExclude.delete(slug);
      nextInclude.delete(slug);
    } else {
      nextInclude.add(slug);
      nextExclude.delete(slug);
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

  function removeParam(name: string, value?: string) {
    const sp = new URLSearchParams(searchParams.toString());
    let destination = basePath;
    if (value) {
      const presetValue = preset?.[name as "genre_include" | "tag_include"] as
        | string
        | undefined;
      const values = parseCsvWithPreset(sp.get(name), presetValue);
      values.delete(value);
      if (parseCsvParam(presetValue ?? null).has(value))
        destination = "/browse-novels";
      if (values.size) sp.set(name, serializeSet(values)!);
      else sp.delete(name);
    } else {
      sp.delete(name);
    }
    sp.delete("page");
    router.replace(`${destination}${sp.toString() ? `?${sp}` : ""}`, {
      scroll: false,
    });
  }

  const novels = data?.novels ?? [];
  const total = data?.total ?? 0;
  const effectiveSort = sort_by ?? "added_at";
  const effectiveOrder = order ?? "desc";

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_minmax(0,1fr)] lg:items-start">
      {filtersOpen && (
        <button
          type="button"
          aria-label="Close filters"
          className="fixed inset-0 z-40 bg-black/50 animate-in fade-in duration-300 ease-out motion-reduce:animate-none motion-reduce:transition-none lg:hidden"
          onClick={() => setFiltersOpen(false)}
        />
      )}
      <section
        aria-label="Browse filters"
        role={filtersOpen ? "dialog" : undefined}
        aria-modal={filtersOpen ? "true" : undefined}
        className={`${filtersOpen ? "fixed slide-in-from-bottom animate-in duration-300 ease-out motion-reduce:animate-none" : "hidden"} inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-xl bg-card p-4 shadow-xl ring-1 ring-border/60 transition-all duration-300 ease-out motion-reduce:transition-none lg:static lg:block lg:max-h-none lg:overflow-visible lg:rounded-xl lg:bg-card/60 lg:p-0 lg:shadow-xs`}
      >
        <div className="sticky top-0 z-10 mb-4 flex items-center justify-between gap-3 border-b border-border/60 bg-card px-1 pb-3 pt-1 lg:rounded-t-xl lg:px-4 lg:pt-4">
          <h2 className="flex items-center gap-2 font-semibold text-sm text-foreground">
            <Filter className="h-4 w-4 text-primary" /> Filters
          </h2>
          {hasActiveFilters && (
            <button
              type="button"
              onClick={handleClearFilters}
              className="relative text-xs font-medium text-primary transition-colors duration-150 hover:underline cursor-pointer motion-reduce:transition-none focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
            >
              Clear all
            </button>
          )}
        </div>
        <div className="space-y-5 lg:px-4 lg:pb-4">
          <form onSubmit={handleSearchSubmit}>
            <label
              htmlFor="catalog-search"
              className="text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Search
            </label>
            <div className="relative mt-2">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                id="catalog-search"
                name="q"
                type="search"
                defaultValue={q ?? ""}
                placeholder="Search by title or author"
                className="h-10 w-full rounded-lg border border-border/60 bg-muted/40 pl-9 pr-9 text-xs sm:text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-border focus:bg-card focus:ring-2 focus:ring-primary"
              />
              <button
                type="submit"
                aria-label="Search"
                className="relative absolute right-1.5 top-1/2 -translate-y-1/2 inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/80 hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary cursor-pointer pointer-coarse:after:absolute pointer-coarse:after:-inset-2"
              >
                <Search className="h-3.5 w-3.5" />
                <span className="sr-only">Search</span>
              </button>
            </div>
            <div className="mt-2.5 flex items-center gap-2">
              <input
                id="search-synopsis"
                name="search_synopsis"
                type="checkbox"
                checked={search_synopsis}
                onChange={(e) => handleSearchSynopsisChange(e.target.checked)}
                className="h-4 w-4 rounded border-border/60 text-primary focus:ring-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
              />
              <label
                htmlFor="search-synopsis"
                className="cursor-pointer select-none text-xs text-muted-foreground hover:text-foreground"
              >
                Search in synopsis
              </label>
            </div>
          </form>

          <div className="mt-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              <Filter className="h-3.5 w-3.5 text-muted-foreground" />
              Status
            </div>
            <div
              className="flex items-center gap-1 overflow-x-auto rounded-lg border border-border/60 bg-muted/40 p-1 no-scrollbar"
              role="group"
              aria-label="Status filter"
            >
              <button
                type="button"
                onClick={() => handleStatusChange("")}
                className={cn(
                  "flex-1 whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium text-center transition-all duration-150 cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary",
                  !publicationStatus
                    ? "bg-background text-foreground shadow-xs font-semibold"
                    : "text-muted-foreground hover:text-foreground hover:bg-background/50",
                )}
                aria-pressed={!publicationStatus}
              >
                All
              </button>
              {STATUS_FILTERS.filter((f) => f.value !== "").map(
                ({ value, label }) => {
                  const isSelected =
                    publicationStatus === toPublicationStatus(value);
                  return (
                    <button
                      key={value}
                      type="button"
                      onClick={() => handleStatusChange(value)}
                      className={cn(
                        "flex-1 whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium text-center transition-all duration-150 cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary",
                        isSelected
                          ? "bg-background text-foreground shadow-xs font-semibold"
                          : "text-muted-foreground hover:text-foreground hover:bg-background/50",
                      )}
                      aria-pressed={isSelected}
                    >
                      {label}
                    </button>
                  );
                },
              )}
            </div>
          </div>

          <div className="mt-5">
            <label
              htmlFor="sort-by-select"
              className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              Order by
            </label>
            <div className="grid grid-cols-2 gap-2">
              <select
                id="sort-by-select"
                aria-label="Sort by"
                value={effectiveSort}
                onChange={(e) =>
                  handleSortChange(e.target.value as CatalogSortField)
                }
                className="h-9 w-full rounded-lg border border-border/60 bg-muted/40 px-2.5 text-xs text-foreground outline-none transition-colors focus:border-border focus:bg-card focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary cursor-pointer"
              >
                {SORT_OPTIONS.map(({ value, label }) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
              <div
                className="grid grid-cols-2 h-9 w-full items-center rounded-lg border border-border/60 bg-muted/40 p-0.5 text-xs"
                role="group"
                aria-label="Sort direction"
              >
                <button
                  type="button"
                  onClick={() => handleOrderChange("desc")}
                  aria-pressed={effectiveOrder === "desc"}
                  className={`h-full w-full rounded-md text-center text-xs font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                    effectiveOrder === "desc"
                      ? "bg-background text-foreground shadow-xs font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Desc
                </button>
                <button
                  type="button"
                  onClick={() => handleOrderChange("asc")}
                  aria-pressed={effectiveOrder === "asc"}
                  className={`h-full w-full rounded-md text-center text-xs font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                    effectiveOrder === "asc"
                      ? "bg-background text-foreground shadow-xs font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  Asc
                </button>
              </div>
            </div>
          </div>

          {/* Advanced search: chapter count + genre + tag filters */}
          <form
            id="catalog-filters-form"
            onSubmit={handleAdvancedSubmit}
            className="mt-5 space-y-5 border-t border-border/60 pt-5"
          >
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Chapter count
              </p>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <label htmlFor="min-chapters" className="sr-only">
                  Minimum
                </label>
                <input
                  id="min-chapters"
                  name="min_chapters"
                  type="number"
                  min={0}
                  step={1}
                  defaultValue={min_chapters ?? ""}
                  placeholder="Min"
                  aria-label="Minimum"
                  className="h-9 w-full rounded-lg border border-border/60 bg-muted/40 px-3 text-center text-xs text-foreground outline-none transition-colors focus:border-border focus:bg-card focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
                <span className="text-sm font-medium text-muted-foreground">
                  –
                </span>
                <label htmlFor="max-chapters" className="sr-only">
                  Maximum
                </label>
                <input
                  id="max-chapters"
                  name="max_chapters"
                  type="number"
                  min={0}
                  step={1}
                  defaultValue={max_chapters ?? ""}
                  placeholder="Max"
                  aria-label="Maximum"
                  className="h-9 w-full rounded-lg border border-border/60 bg-muted/40 px-3 text-center text-xs text-foreground outline-none transition-colors focus:border-border focus:bg-card focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                />
              </div>
            </div>

            {/* Genre filters (Matching Image 1) */}
            <div className="border-t border-border/60 pt-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Genre
                </p>
                <div
                  className="inline-flex h-7 items-center rounded-lg border border-border/60 bg-muted/40 p-0.5 text-xs"
                  role="group"
                  aria-label="Genre match mode"
                >
                  <button
                    type="button"
                    onClick={() => handleGenreOpChange("and")}
                    aria-pressed={genre_op === "and"}
                    aria-label="AND"
                    className={`rounded-md px-2.5 py-0.5 text-[11px] font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                      genre_op === "and"
                        ? "bg-background text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    And
                  </button>
                  <button
                    type="button"
                    onClick={() => handleGenreOpChange("or")}
                    aria-pressed={genre_op === "or"}
                    aria-label="OR"
                    className={`rounded-md px-2.5 py-0.5 text-[11px] font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                      genre_op === "or"
                        ? "bg-background text-foreground shadow-xs font-semibold"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    Or
                  </button>
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
                  className="grid grid-cols-2 gap-x-2 gap-y-0.5"
                  role="group"
                  aria-label="Genre filters"
                >
                  {genresData.map((genre) => {
                    const isSelected = genreIncludeSet.has(genre.slug);
                    const isExcluded = genreExcludeSet.has(genre.slug);
                    return (
                      <button
                        key={genre.slug}
                        type="button"
                        onClick={() => handleGenreClick(genre.slug)}
                        aria-label={
                          isSelected
                            ? `${genre.name_en ?? genre.slug}: included`
                            : isExcluded
                              ? `${genre.name_en ?? genre.slug}: excluded`
                              : `${genre.name_en ?? genre.slug}: not selected`
                        }
                        aria-pressed={isSelected}
                        className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors select-none cursor-pointer pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                          isSelected
                            ? "bg-primary/10 font-medium text-foreground"
                            : isExcluded
                              ? "bg-destructive/10 font-medium text-destructive"
                              : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                        }`}
                      >
                        <span
                          className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-xs border transition-colors ${
                            isSelected
                              ? "border-primary bg-primary text-primary-foreground"
                              : isExcluded
                                ? "border-destructive bg-destructive text-destructive-foreground"
                                : "border-border/60 bg-background"
                          }`}
                        >
                          {isSelected && (
                            <Check className="h-3 w-3 stroke-[3]" />
                          )}
                          {isExcluded && (
                            <Minus className="h-3 w-3 stroke-[3]" />
                          )}
                        </span>
                        <span className="truncate">
                          {genre.name_en ?? genre.slug}
                        </span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Tag filters (Matching Images 2, 3, 4) */}
            <div className="border-t border-border/60 pt-4 space-y-3">
              {/* Include Tags */}
              <div>
                <div className="mb-1.5 flex items-center justify-between gap-2">
                  <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Tags
                  </label>
                  <div
                    className="inline-flex h-7 items-center rounded-lg border border-border/60 bg-muted/40 p-0.5 text-xs"
                    role="group"
                    aria-label="Tag match mode"
                  >
                    <button
                      type="button"
                      onClick={() => handleTagOpChange("and")}
                      aria-pressed={tag_op === "and"}
                      aria-label="AND"
                      className={`rounded-md px-2.5 py-0.5 text-[11px] font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                        tag_op === "and"
                          ? "bg-background text-foreground shadow-xs font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      And
                    </button>
                    <button
                      type="button"
                      onClick={() => handleTagOpChange("or")}
                      aria-pressed={tag_op === "or"}
                      aria-label="OR"
                      className={`rounded-md px-2.5 py-0.5 text-[11px] font-medium transition-colors cursor-pointer pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center pointer-coarse:justify-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary ${
                        tag_op === "or"
                          ? "bg-background text-foreground shadow-xs font-semibold"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      Or
                    </button>
                  </div>
                </div>
                <span className="sr-only">Required</span>
                <span className="sr-only">Must include</span>
                <span className="sr-only">
                  Add required tags on the left, blocked tags on the right.
                </span>
                <TagFilterCombobox
                  label="Must include"
                  placeholder="Select..."
                  tone="include"
                  query={includeTagQuery}
                  onQueryChange={setIncludeTagQuery}
                  selectedSet={tagIncludeSet}
                  onAdd={handleTagIncludeAdd}
                  onRemove={handleTagIncludeRemove}
                  allSelected={allTagSet}
                  availableTags={availableTags}
                />
              </div>

              {/* Exclude Tags */}
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-xs font-semibold uppercase tracking-wider text-destructive">
                    Tags Exclude
                  </label>
                </div>
                <span className="sr-only">Blocked</span>
                <span className="sr-only">Exclude</span>
                <TagFilterCombobox
                  label="Exclude"
                  placeholder="Select..."
                  tone="exclude"
                  query={excludeTagQuery}
                  onQueryChange={setExcludeTagQuery}
                  selectedSet={tagExcludeSet}
                  onAdd={handleTagExcludeAdd}
                  onRemove={handleTagExcludeRemove}
                  allSelected={allTagSet}
                  availableTags={availableTags}
                />
              </div>
            </div>

            {/* Desktop Apply filters button */}
            <div className="pt-2">
              <button
                type="submit"
                className="inline-flex min-h-[44px] h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-xs sm:text-sm font-semibold text-primary-foreground shadow-xs transition-colors hover:bg-primary/90 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary cursor-pointer"
              >
                Apply filters
              </button>
            </div>
          </form>
        </div>
        <div className="sticky bottom-0 -mx-4 mt-4 flex gap-3 border-t border-border/60 bg-card p-4 lg:hidden">
          <button
            type="button"
            onClick={handleClearFilters}
            className="min-h-[44px] h-11 flex-1 rounded-lg border border-border/60 text-xs font-semibold text-foreground hover:bg-muted/60 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary cursor-pointer"
          >
            Clear
          </button>
          <button
            type="submit"
            form="catalog-filters-form"
            onClick={() => setFiltersOpen(false)}
            className="min-h-[44px] h-11 flex-1 rounded-lg bg-primary text-xs font-semibold text-primary-foreground shadow-xs hover:bg-primary/90 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary cursor-pointer"
          >
            Apply
          </button>
        </div>
      </section>

      <section aria-label="Catalog results">
        <div className="mb-3 flex flex-wrap items-center justify-between lg:justify-end gap-2">
          <button
            type="button"
            onClick={() => setFiltersOpen(true)}
            className="inline-flex min-h-[44px] h-11 items-center gap-1.5 rounded-lg border border-border/60 px-3 text-xs font-medium transition-all duration-150 ease-out hover:bg-muted/60 active:scale-95 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary motion-reduce:active:scale-100 motion-reduce:transition-none lg:hidden cursor-pointer"
          >
            <Filter className="h-3.5 w-3.5" /> Filters
            {activeFilterCount ? ` (${activeFilterCount})` : ""}
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={novels.length === 0}
              onClick={() =>
                novels.length &&
                router.push(
                  publicNovelHref(
                    novels[Math.floor(Math.random() * novels.length)].slug,
                  ),
                )
              }
              className="inline-flex min-h-[44px] h-11 items-center gap-1.5 rounded-lg border border-border/60 bg-card px-3 text-xs font-medium text-foreground transition-colors hover:bg-muted/60 focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-50 cursor-pointer"
            >
              <Shuffle className="h-3.5 w-3.5" /> Surprise me
            </button>
          </div>
        </div>

        <div className="mb-5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          {q && (
            <button
              type="button"
              aria-label="Remove search filter"
              onClick={() => removeParam("q")}
              className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Search className="h-3.5 w-3.5" />
              &ldquo;{q}&rdquo;
              <X className="h-3 w-3" />
            </button>
          )}
          {search_synopsis && (
            <button
              type="button"
              aria-label="Remove synopsis search filter"
              onClick={() => removeParam("search_synopsis")}
              className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 font-metadata text-xs pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Search className="h-3.5 w-3.5" />
              Synopsis search
              <X className="h-3 w-3" />
            </button>
          )}
          {publicationStatus && (
            <button
              type="button"
              aria-label="Remove status filter"
              onClick={() => removeParam("publication_status")}
              className="pointer-coarse:min-h-[44px] pointer-coarse:inline-flex pointer-coarse:items-center focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-md"
            >
              <StatusBadge status={publicationStatus} />
            </button>
          )}
          {(min_chapters !== undefined || max_chapters !== undefined) && (
            <button
              type="button"
              aria-label="Remove chapter count filter"
              onClick={() => {
                const sp = new URLSearchParams(searchParams.toString());
                sp.delete("min_chapters");
                sp.delete("max_chapters");
                sp.delete("page");
                router.replace(`${basePath}${sp.toString() ? `?${sp}` : ""}`, {
                  scroll: false,
                });
              }}
              className="inline-flex items-center gap-1 rounded-md bg-muted px-2.5 py-1 font-metadata text-xs pointer-coarse:min-h-[44px] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
            >
              <BookOpen className="h-3.5 w-3.5" />
              {min_chapters ?? 0}–{max_chapters ?? "∞"} ch.
              <X className="h-3 w-3" />
            </button>
          )}
          {Array.from(genreIncludeSet).map((slug) => (
            <button
              key={`gi-${slug}`}
              type="button"
              aria-label={`Remove included genre ${slug}`}
              onClick={() => removeParam("genre_include", slug)}
              className="inline-flex min-h-11 min-w-11 items-center justify-center text-xs text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              × {slug}
            </button>
          ))}
          {Array.from(genreExcludeSet).map((slug) => (
            <button
              key={`ge-${slug}`}
              type="button"
              aria-label={`Remove excluded genre ${slug}`}
              onClick={() => removeParam("genre_exclude", slug)}
              className="inline-flex min-h-11 min-w-11 items-center justify-center text-xs text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              × {slug}
            </button>
          ))}
          {Array.from(tagIncludeSet).map((tag) => (
            <button
              key={`ti-${tag}`}
              type="button"
              aria-label={`Remove included tag ${tag}`}
              onClick={() => removeParam("tag_include", tag)}
              className="inline-flex min-h-11 min-w-11 items-center justify-center text-xs text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              × {tag}
            </button>
          ))}
          {Array.from(tagExcludeSet).map((tag) => (
            <button
              key={`te-${tag}`}
              type="button"
              aria-label={`Remove excluded tag ${tag}`}
              onClick={() => removeParam("tag_exclude", tag)}
              className="inline-flex min-h-11 min-w-11 items-center justify-center text-xs text-primary focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs"
            >
              × {tag}
            </button>
          ))}
          {hasActiveFilters && (
            <button
              className="relative inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-accent focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
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
              className="relative text-sm text-primary transition-colors hover:text-accent focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
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
                className="relative inline-flex items-center gap-1.5 text-sm text-primary transition-colors hover:text-accent focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary rounded-xs pointer-coarse:after:absolute pointer-coarse:after:-inset-2.5"
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
            <div className="flex flex-col gap-4">
              {novels.map((novel) => (
                <NovelCard key={novel.novel_id} novel={novel} layout="list" />
              ))}
            </div>

            {hasNextPage(total, page, pageSize) && (
              <div className="mt-8 flex justify-center">
                <button
                  className="inline-flex min-h-[44px] h-11 items-center justify-center rounded-md border border-border bg-card px-6 text-sm font-medium transition-colors hover:bg-muted focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-primary"
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

export function BrowsePage({
  basePath,
  description: _description,
  title,
  preset,
}: BrowsePageProps) {
  return (
    <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:px-8">
      <h1 className="sr-only">{title}</h1>
      <div>
        <Suspense fallback={<LoadingState />}>
          <BrowseContent basePath={basePath} preset={preset} />
        </Suspense>
      </div>
    </main>
  );
}
