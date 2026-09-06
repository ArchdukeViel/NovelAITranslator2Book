"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X } from "lucide-react";

import { publicApi } from "@/lib/public-api";
import { useGenres } from "@/hooks/public/use-genres";
import { useDebounce } from "@/hooks/public/use-debounce";
import {
  useSearchOverlay,
  loadRecentSearches,
  recordRecentSearch,
  clearRecentSearches,
} from "@/lib/search-overlay";
import { cn } from "@/lib/utils";
import type { PublicGenreResponse, PublicNovelSummary, PublicTagSearchResult } from "@/lib/public-types";

// One shared search overlay (DESIGN.md — Search contract). Opened from the
// desktop header search field, the mobile Search tab, or the `/` shortcut.
// Desktop: centered overlay. Mobile: full-screen surface. Groups results into
// Novels, Authors, Genres & Tags, plus local recent searches when the query
// is empty. Debounced 225ms, cancels in-flight requests, replaces stale
// results in place (no flicker), and shows an honest error state.

const DEBOUNCE_MS = 225;
const GROUP_CAP = 5;
const MIN_QUERY_LENGTH = 2;

type NovelRow = { kind: "novel"; novel: PublicNovelSummary };
type AuthorRow = { kind: "author"; name: string };
type TagRow = { kind: "tag"; tag: PublicTagSearchResult };
type GenreRow = { kind: "genre"; genre: PublicGenreResponse };
type SeeAllRow = { kind: "see-all"; query: string };
type SearchRow = NovelRow | AuthorRow | TagRow | GenreRow | SeeAllRow;

interface SearchResults {
  novels: PublicNovelSummary[];
  authors: string[];
  tags: PublicTagSearchResult[];
  genres: PublicGenreResponse[];
}

const EMPTY_RESULTS: SearchResults = { novels: [], authors: [], tags: [], genres: [] };

export function SearchOverlay() {
  const isOpen = useSearchOverlay((state) => state.isOpen);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      const typing =
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable);
      if (e.key === "/" && !typing) {
        e.preventDefault();
        useSearchOverlay.getState().open();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return isOpen ? <SearchOverlayContent /> : null;
}

function SearchOverlayContent() {
  const router = useRouter();
  const close = useSearchOverlay((state) => state.close);
  const { data: allGenres = [] } = useGenres();

  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResults>(EMPTY_RESULTS);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [recents, setRecents] = useState<string[]>(() => loadRecentSearches());
  // Query that actually completed a search cycle — "No matches" only renders
  // after a real response, never during the debounce window.
  const [completedQuery, setCompletedQuery] = useState("");

  const debouncedQuery = useDebounce(query, DEBOUNCE_MS);
  const trimmedQuery = query.trim();
  const shouldSearch = trimmedQuery.length >= MIN_QUERY_LENGTH;
  const debouncedTrimmed = debouncedQuery.trim();
  const shouldSearchDebounced = debouncedTrimmed.length >= MIN_QUERY_LENGTH;

  // Escape closes the dialog from anywhere inside it (input, clear button,
  // result buttons, backdrop), matching dialog expectations.
  useEffect(() => {
    function onWindowKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        close();
      }
    }
    window.addEventListener("keydown", onWindowKeyDown);
    return () => window.removeEventListener("keydown", onWindowKeyDown);
  }, [close]);

  // Focus input on open; return focus to the opener on close. The input
  // mounts inside the same commit as `isOpen` flipping true, so the ref is
  // available synchronously in this effect.
  useEffect(() => {
    inputRef.current?.focus();
    return () => {
      const opener = useSearchOverlay.getState().openerRef;
      if (opener instanceof HTMLElement && opener.isConnected) {
        opener.focus();
      }
    };
  }, []);

  // Search effect: debounced query fires catalog + tag requests; a new
  // keystroke aborts whatever is still in flight; stale results stay visible
  // until the fresh response arrives (no blank/loading flicker).
  useEffect(() => {
    if (!shouldSearchDebounced) {
      abortRef.current?.abort();
      return;
    }
    const controller = new AbortController();
    abortRef.current?.abort();
    abortRef.current = controller;

    async function run() {
      setLoading(true);
      try {
        const [catalogResult, tagsResult] = await Promise.allSettled([
          publicApi.catalog(
            { q: debouncedTrimmed, page_size: GROUP_CAP * 2, sort_by: "title", order: "asc" },
            controller.signal
          ),
          publicApi.searchTags({ q: debouncedTrimmed, limit: GROUP_CAP }, controller.signal),
        ]);
        if (controller.signal.aborted) return;

        const novels =
          catalogResult.status === "fulfilled" ? catalogResult.value.novels.slice(0, GROUP_CAP) : [];
        const matchedAuthors =
          catalogResult.status === "fulfilled"
            ? catalogResult.value.novels
                .map((novel) => novel.author)
                .filter(
                  (author): author is string =>
                    !!author && author.toLowerCase().includes(debouncedTrimmed.toLowerCase())
                )
            : [];
        const authors = [...new Set(matchedAuthors)].slice(0, GROUP_CAP);
        const tags = tagsResult.status === "fulfilled" ? tagsResult.value.slice(0, GROUP_CAP) : [];

        // Genres matched client-side from the (small, cached) genre list.
        const ql = debouncedTrimmed.toLowerCase();
        const genres = allGenres
          .filter((genre) => {
            const hay = [genre.name_ja, genre.name_en].filter(Boolean).join(" ").toLowerCase();
            return hay.includes(ql);
          })
          .slice(0, GROUP_CAP - tags.length);

        const failed = catalogResult.status === "rejected" && tagsResult.status === "rejected";
        setResults({ novels, authors, tags, genres });
        setError(failed && !controller.signal.aborted);
        setActiveIndex(-1);
        setCompletedQuery(debouncedTrimmed);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void run();
    return () => controller.abort();
  }, [shouldSearchDebounced, debouncedTrimmed, allGenres]);

  // Flattened interactive rows for arrow-key navigation. "See all results"
  // is always the last row when there is a query.
  const rows = useMemo<SearchRow[]>(() => {
    if (!shouldSearch) return [];
    const list: SearchRow[] = [
      ...results.novels.map((novel) => ({ kind: "novel" as const, novel })),
      ...results.authors.map((name) => ({ kind: "author" as const, name })),
      ...results.tags.map((tag) => ({ kind: "tag" as const, tag })),
      ...results.genres.map((genre) => ({ kind: "genre" as const, genre })),
    ];
    if (!error && (list.length > 0 || loading)) {
      list.push({ kind: "see-all", query: trimmedQuery });
    }
    return list;
  }, [shouldSearch, trimmedQuery, results, loading, error]);

  const activateRow = useCallback(
    (row: SearchRow | null) => {
      if (!row) return;
      recordRecentSearch(trimmedQuery);
      close();
      setRecents(loadRecentSearches());
      switch (row.kind) {
        case "novel":
          router.push(`/novels/${row.novel.slug}`);
          return;
        case "author":
          router.push(`/browse-novels?q=${encodeURIComponent(row.name)}`);
          return;
        case "tag":
          router.push(`/tags/${encodeURIComponent(row.tag.name)}`);
          return;
        case "genre":
          router.push(`/genres/${encodeURIComponent(row.genre.slug)}`);
          return;
        case "see-all":
          router.push(`/browse-novels?q=${encodeURIComponent(row.query)}`);
          return;
      }
    },
    [trimmedQuery, close, router]
  );

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (rows.length === 0) return;
        setActiveIndex((i) => (i + 1) % rows.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        if (rows.length === 0) return;
        setActiveIndex((i) => (i <= 0 ? rows.length - 1 : i - 1));
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < rows.length) {
          activateRow(rows[activeIndex]);
        } else {
          // Nothing highlighted yet (query just typed): Enter opens the full
          // results page instead of guessing (DESIGN.md — Search contract).
          recordRecentSearch(trimmedQuery);
          close();
          router.push(`/browse-novels?q=${encodeURIComponent(trimmedQuery)}`);
        }
      }
    },
    [rows, activeIndex, trimmedQuery, close, router, activateRow]
  );

  function runRecent(term: string) {
    setQuery(term);
    setRecents(loadRecentSearches());
  }

  function updateQuery(nextQuery: string) {
    setQuery(nextQuery);
    if (nextQuery.trim().length < MIN_QUERY_LENGTH) {
      setResults(EMPTY_RESULTS);
      setError(false);
      setLoading(false);
      setActiveIndex(-1);
      setCompletedQuery("");
    }
  }

  function renderGroupHeader(label: string, count: number) {
    if (count === 0) return null;
    return (
      <p
        className="px-3 pb-1 pt-2.5 font-literary text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground"
      >
        {label}
      </p>
    );
  }

  function rowClass(active: boolean) {
    return cn(
      "flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm transition-colors",
      active ? "bg-primary/10 text-primary" : "text-foreground/90 hover:bg-accent/40"
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center md:items-start md:pt-[12vh]"
      role="dialog"
      aria-modal="true"
      aria-label="Search"
    >
      {/* Backdrop — click closes, focus returns to opener */}
      <button
        type="button"
        aria-label="Close search"
        onClick={() => close()}
        className="absolute inset-0 cursor-default bg-background/70 backdrop-blur-sm motion-safe:animate-[search-overlay-fade-in_150ms_ease-out] md:bg-black/40"
        tabIndex={-1}
      />

      <div
        className={cn(
          "relative z-10 flex w-full flex-col overflow-hidden bg-background shadow-xl motion-safe:animate-[search-overlay-panel-rise_200ms_ease-out]",
          "h-full md:h-auto md:max-h-[min(70vh,480px)] md:max-w-lg md:rounded-xl md:border md:border-primary/25 md:shadow-2xl"
        )}
      >
        {/* Search input */}
        <div className="flex items-center gap-2 border-b border-primary/20 px-3">
          <Search className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <input
            ref={inputRef}
            type="search"
            value={query}
            onChange={(e) => updateQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Search novels…"
            aria-label="Search"
            className="h-12 w-full bg-transparent text-base text-foreground placeholder:text-muted-foreground/60"
          />
          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => {
                updateQuery("");
              }}
              className="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-sm text-muted-foreground hover:text-foreground"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>

        {/* Results */}
        <div
          id="search-overlay-results"
          aria-label="Search results"
          className="flex-1 overflow-y-auto px-1.5 py-1.5 md:min-h-0"
        >
          {/* Empty query: recent searches + genre shortcuts */}
          {!shouldSearch && (
            <div>
              {/* First-run teach-by-action: returning users have recents and
                  never see this; a first-timer gets one tap that runs a real
                  search from real taxonomy — no tutorial, fully skippable. */}
              {recents.length === 0 &&
                allGenres.length > 0 &&
                (allGenres[0].name_en ?? allGenres[0].name_ja) && (
                  <div className="px-1.5 pb-1 pt-1.5">
                    <button
                      type="button"
                      onClick={() =>
                        runRecent(allGenres[0].name_en ?? allGenres[0].name_ja ?? "")
                      }
                      className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm text-foreground hover:bg-accent/40"
                    >
                      <Search
                        className="h-3.5 w-3.5 shrink-0 text-primary"
                        aria-hidden="true"
                      />
                      <span className="truncate">
                        Try{" "}
                        <span dir="auto">
                          “{allGenres[0].name_en ?? allGenres[0].name_ja}”
                        </span>
                      </span>
                    </button>
                  </div>
                )}
              {recents.length > 0 && (
                <>
                  <div className="flex items-center justify-between px-3 pb-1 pt-2.5">
                    <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-muted-foreground">
                      Recent searches
                    </p>
                    <button
                      type="button"
                      onClick={() => {
                        clearRecentSearches();
                        setRecents([]);
                      }}
                      className="inline-flex min-h-[44px] items-center px-2 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                  <ul className="space-y-0.5">
                    {recents.map((term) => (
                      <li key={term}>
                        <button
                          type="button"
                          onClick={() => runRecent(term)}
                          className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm hover:bg-accent/40"
                        >
                          <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                          <span dir="auto" className="truncate">{term}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {allGenres.length > 0 && (
                <>
                  {renderGroupHeader("Genre shortcuts", allGenres.length)}
                  <ul className="space-y-0.5">
                    {allGenres.slice(0, 6).map((genre) => (
                      <li key={genre.slug}>
                        <button
                          type="button"
                          onClick={() => {
                            close();
                            router.push(`/genres/${encodeURIComponent(genre.slug)}`);
                          }}
                          className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm hover:bg-accent/40"
                        >
                          <span className="truncate">
                            {genre.name_en ?? genre.name_ja}
                            {genre.name_en && genre.name_ja !== genre.name_en ? (
                              <span className="ml-1.5 text-muted-foreground">{genre.name_ja}</span>
                            ) : null}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {recents.length === 0 && allGenres.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                  Nothing here yet — try a genre or start typing.
                </p>
              )}
            </div>
          )}

          {/* Live results */}
          {shouldSearch && (
            <>
              {error && (
                <div className="px-3 py-4 text-center text-sm text-muted-foreground" role="status">
                  <p>Search&apos;s unavailable right now.</p>
                  <button
                    type="button"
                    onClick={() => {
                      close();
                      router.push("/browse-novels");
                    }}
                    className="mt-1 inline-flex min-h-[44px] items-center justify-center px-2 underline underline-offset-2 hover:text-foreground"
                  >
                    Browse all novels instead
                  </button>
                </div>
              )}

              {!error && renderGroupHeader("Novels", results.novels.length)}
              {!error && (
                <ul className="space-y-0.5">
                  {results.novels.map((novel, i) => (
                    <li key={novel.novel_id}>
                      <button
                        type="button"
                        onClick={() => activateRow(rows[i] ?? null)}
                        onMouseEnter={() => setActiveIndex(i)}
                        className={rowClass(activeIndex === i)}
                      >
                        <span className="min-w-0 flex-1">
                          <span dir="auto" className="block truncate font-literary font-medium">{novel.title}</span>
                          {novel.source_title && (
                            <span className="block truncate text-xs text-muted-foreground">
                              {novel.source_title}
                            </span>
                          )}
                        </span>
                        {novel.author && (
                          <span dir="auto" className="shrink-0 text-xs text-muted-foreground">{novel.author}</span>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              )}

              {!error && renderGroupHeader("Authors", results.authors.length)}
              {!error && (
                <ul className="space-y-0.5">
                  {results.authors.map((name, i) => {
                    const rowIndex = results.novels.length + i;
                    return (
                      <li key={name}>
                        <button
                          type="button"
                          onClick={() => activateRow(rows[rowIndex] ?? null)}
                          onMouseEnter={() => setActiveIndex(rowIndex)}
                          className={rowClass(activeIndex === rowIndex)}
                        >
                          <span dir="auto" className="truncate">{name}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {!error && renderGroupHeader("Genres & Tags", results.genres.length + results.tags.length)}
              {!error && (
                <ul className="space-y-0.5">
                  {results.tags.map((tag, i) => {
                    const rowIndex = results.novels.length + results.authors.length + i;
                    return (
                      <li key={`tag-${tag.name}`}>
                        <button
                          type="button"
                          onClick={() => activateRow(rows[rowIndex] ?? null)}
                          onMouseEnter={() => setActiveIndex(rowIndex)}
                          className={rowClass(activeIndex === rowIndex)}
                        >
                          <span dir="auto" className="truncate">#{tag.name}</span>
                          {tag.name_ja && tag.name_ja !== tag.name ? (
                            <span className="ml-1.5 text-muted-foreground">{tag.name_ja}</span>
                          ) : null}
                        </button>
                      </li>
                    );
                  })}
                  {results.genres.map((genre, i) => {
                    const rowIndex =
                      results.novels.length + results.authors.length + results.tags.length + i;
                    return (
                      <li key={`genre-${genre.slug}`}>
                        <button
                          type="button"
                          onClick={() => activateRow(rows[rowIndex] ?? null)}
                          onMouseEnter={() => setActiveIndex(rowIndex)}
                          className={rowClass(activeIndex === rowIndex)}
                        >
                          <span className="truncate">{genre.name_en ?? genre.name_ja}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {!error && rows.length === 0 && !loading && completedQuery === trimmedQuery && (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                  No matches for <span dir="auto">“{trimmedQuery}”</span>.
                </p>
              )}

              {/* Initial-load skeletons: only when no stale results exist to
                  hold the space (stale-in-place stays untouched). Same row
                  geometry as real rows so arrival causes no layout shift.
                  Pulse is opacity-only and motion-gated; the sr-only status
                  preserves state meaning under reduced motion. */}
              {!error &&
                loading &&
                results.novels.length === 0 &&
                results.authors.length === 0 &&
                results.tags.length === 0 &&
                results.genres.length === 0 && (
                  <>
                    <p role="status" className="sr-only">
                      Searching…
                    </p>
                    <div aria-hidden="true">
                      {renderGroupHeader("Novels", 1)}
                      <div className="space-y-0.5">
                        {[0, 1].map((i) => (
                          <div
                            key={`novel-skeleton-${i}`}
                            className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2"
                          >
                            <span className="min-w-0 flex-1">
                              <span className="block h-4 w-3/4 rounded bg-muted motion-safe:animate-pulse" />
                              <span className="mt-1.5 block h-3 w-1/2 rounded bg-muted/70 motion-safe:animate-pulse" />
                            </span>
                            <span className="h-3 w-16 shrink-0 rounded bg-muted/70 motion-safe:animate-pulse" />
                          </div>
                        ))}
                      </div>
                      {renderGroupHeader("Authors", 1)}
                      <div className="space-y-0.5">
                        <div className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2">
                          <span className="block h-4 w-2/5 rounded bg-muted motion-safe:animate-pulse" />
                        </div>
                      </div>
                      {renderGroupHeader("Genres & Tags", 1)}
                      <div className="space-y-0.5">
                        {[0, 1].map((i) => (
                          <div
                            key={`tag-skeleton-${i}`}
                            className="flex min-h-[44px] w-full items-center gap-2.5 rounded-md px-3 py-2"
                          >
                            <span className="block h-4 w-1/3 rounded bg-muted motion-safe:animate-pulse" />
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}

              {/* Always-last "see all" row */}
              {!error && rows.length > 0 && (
                <div className="border-t border-border/60 pt-1">
                  <button
                    type="button"
                    onClick={() => activateRow(rows[rows.length - 1] ?? null)}
                    onMouseEnter={() => setActiveIndex(rows.length - 1)}
                    className={rowClass(activeIndex === rows.length - 1)}
                  >
                    <span className="truncate">
                      See all results for <span dir="auto">“{trimmedQuery}”</span>
                    </span>
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
