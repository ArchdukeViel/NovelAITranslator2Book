"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Bookmark, BookOpen, LayoutGrid, List, Loader2 } from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { useLibrary, usePublicAuth, useRemoveFromLibrary } from "@/hooks/public";
import { publicNovelHref } from "@/lib/public-routes";
import type { LibraryItem } from "@/lib/public-types";

type GroupKey = "reading" | "plan" | "completed" | "dropped" | "unknown";
type SortKey = "slug-asc" | "slug-desc" | "added-desc" | "added-asc";
type ViewMode = "board" | "list";

const GROUP_ORDER: GroupKey[] = ["reading", "plan", "completed", "dropped", "unknown"];

const GROUP_LABEL: Record<GroupKey, string> = {
  reading: "Reading",
  plan: "Plan to read",
  completed: "Completed",
  dropped: "Dropped",
  unknown: "Unknown",
};

function groupKey(status: string): GroupKey {
  switch (status) {
    case "reading":
      return "reading";
    case "completed":
      return "completed";
    case "paused":
      return "dropped";
    default:
      return "unknown";
  }
}

function formatAddedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function LibraryPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();
  const library = useLibrary();
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("added-desc");
  const [view, setView] = useState<ViewMode | null>(null);
  const [isDesktop, setIsDesktop] = useState(false);

  // Default: list on mobile, board on desktop (md+). Read after mount to avoid
  // hydration mismatch; explicit Board/List toggle overrides the media default.
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia("(min-width: 768px)");
    const update = () => setIsDesktop(mql.matches);
    update();
    mql.addEventListener("change", update);
    return () => mql.removeEventListener("change", update);
  }, []);

  const effectiveView: ViewMode = view ?? (isDesktop ? "board" : "list");

  const grouped = useMemo(() => {
    const items: LibraryItem[] = (library.data ?? []).filter((item) =>
      item.slug.toLowerCase().includes(query.trim().toLowerCase()),
    );
    const compare = (a: LibraryItem, b: LibraryItem): number => {
      switch (sort) {
        case "slug-asc":
          return a.slug.localeCompare(b.slug);
        case "slug-desc":
          return b.slug.localeCompare(a.slug);
        case "added-asc":
          return a.added_at.localeCompare(b.added_at);
        case "added-desc":
          return b.added_at.localeCompare(a.added_at);
      }
    };
    items.sort(compare);
    return GROUP_ORDER.reduce(
      (acc, key) => {
        acc[key] = items.filter((item) => groupKey(item.status) === key);
        return acc;
      },
      {} as Record<GroupKey, LibraryItem[]>,
    );
  }, [library.data, query, sort]);

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        href="/browse-novels"
      >
        <BookOpen className="h-4 w-4" />
        Back to Browse
      </Link>

      <header className="mt-6 mb-8">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">My Library</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Novels you have saved for later.
        </p>
      </header>

      {authPending ? (
        <LoadingState label="Checking session" />
      ) : !isAuthenticated ? (
        <LoginPrompt />
      ) : library.isPending ? (
        <LoadingState label="Loading library" />
      ) : library.isError ? (
        <section className="rounded-md border border-border bg-muted/40 p-4">
          <p className="text-sm text-destructive">Could not load your library.</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try refreshing the page, or return to browse.
          </p>
        </section>
      ) : library.data.length === 0 ? (
        <EmptyLibraryState
          description="Save a novel from its detail page and it will appear here."
          title="Your library is empty."
        />
      ) : (
        <>
          <LibraryControls
            onQueryChange={setQuery}
            onSortChange={setSort}
            onViewChange={setView}
            query={query}
            sort={sort}
            view={effectiveView}
          />
          <div className="mt-6 space-y-10">
            {GROUP_ORDER.map((key) => (
              <LibraryGroup items={grouped[key]} key={key} title={GROUP_LABEL[key]} view={effectiveView} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}

function LoadingState({ label }: { label: string }) {
  return (
    <section className="rounded-md border border-border bg-muted/40 p-4">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {label}
      </div>
    </section>
  );
}

function EmptyLibraryState({
  description,
  title,
}: {
  description: string;
  title: string;
}) {
  return (
    <section className="rounded-md border border-border bg-muted/40 p-6 text-center">
      <Bookmark className="mx-auto h-8 w-8 text-muted-foreground" />
      <p className="mt-3 text-sm font-medium">{title}</p>
      <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      <Link
        className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-accent underline hover:text-foreground"
        href="/browse-novels"
      >
        Browse novels
      </Link>
    </section>
  );
}

function LibraryControls({
  onQueryChange,
  onSortChange,
  onViewChange,
  query,
  sort,
  view,
}: {
  onQueryChange: (value: string) => void;
  onSortChange: (value: SortKey) => void;
  onViewChange: (value: ViewMode) => void;
  query: string;
  sort: SortKey;
  view: ViewMode;
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
      <label className="flex-1">
        <span className="sr-only">Search by slug</span>
        <input
          className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="Search by slug"
          type="search"
          value={query}
        />
      </label>
      <label className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Sort</span>
        <select
          className="h-9 rounded-md border border-border bg-background px-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          onChange={(event) => onSortChange(event.target.value as SortKey)}
          value={sort}
        >
          <option value="added-desc">Recently added</option>
          <option value="added-asc">Oldest added</option>
          <option value="slug-asc">Slug A-Z</option>
          <option value="slug-desc">Slug Z-A</option>
        </select>
      </label>
      <div aria-label="View" className="flex rounded-md border border-border p-0.5" role="group">
        <button
          aria-label="Board view"
          aria-pressed={view === "board"}
          className="inline-flex h-8 w-9 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={() => onViewChange("board")}
          type="button"
        >
          <LayoutGrid className="h-4 w-4" />
        </button>
        <button
          aria-label="List view"
          aria-pressed={view === "list"}
          className="inline-flex h-8 w-9 items-center justify-center rounded text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          onClick={() => onViewChange("list")}
          type="button"
        >
          <List className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

function LibraryGroup({
  items,
  title,
  view,
}: {
  items: LibraryItem[];
  title: string;
  view: ViewMode;
}) {
  return (
    <section>
      <h2 className="mb-3 font-literary text-xl font-semibold">{title}</h2>
      {items.length === 0 ? (
        <p className="rounded-md border border-border bg-muted/40 p-4 text-sm text-muted-foreground">
          No novels in this group yet.
        </p>
      ) : view === "board" ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((item) => (
            <BoardCard item={item} key={item.slug} />
          ))}
        </div>
      ) : (
        <div className="divide-y rounded-md border border-border bg-card">
          {items.map((item) => (
            <LibraryRow item={item} key={item.slug} />
          ))}
        </div>
      )}
    </section>
  );
}

function BoardCard({ item }: { item: LibraryItem }) {
  const removeFromLibrary = useRemoveFromLibrary(item.slug);
  const novelHref = publicNovelHref(item.slug);

  return (
    <article className="flex flex-col rounded-md border border-border bg-card p-4">
      <Link className="truncate font-medium hover:text-accent" href={novelHref}>
        {item.slug}
      </Link>
      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
        <span className="rounded bg-muted px-1.5 py-0.5 font-metadata font-medium">
          {GROUP_LABEL[groupKey(item.status)]}
        </span>
        <span className="font-metadata">{formatAddedAt(item.added_at)}</span>
      </div>
      <div className="mt-3 flex gap-2">
        <Link
          className="inline-flex h-8 flex-1 items-center justify-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
          href={novelHref}
        >
          <BookOpen className="h-3.5 w-3.5" />
          View
        </Link>
        <RemoveButton item={item} removeFromLibrary={removeFromLibrary} />
      </div>
    </article>
  );
}

function LibraryRow({ item }: { item: LibraryItem }) {
  const removeFromLibrary = useRemoveFromLibrary(item.slug);
  const novelHref = publicNovelHref(item.slug);

  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <Link className="truncate text-sm font-medium hover:text-accent" href={novelHref}>
          {item.slug}
        </Link>
        <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="rounded bg-muted px-1.5 py-0.5 font-metadata font-medium">
            {GROUP_LABEL[groupKey(item.status)]}
          </span>
          <span className="font-metadata">{formatAddedAt(item.added_at)}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Link
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
          href={novelHref}
        >
          <BookOpen className="h-3.5 w-3.5" />
          View
        </Link>
        <RemoveButton item={item} removeFromLibrary={removeFromLibrary} />
      </div>
    </div>
  );
}

function RemoveButton({
  item,
  removeFromLibrary,
}: {
  item: LibraryItem;
  removeFromLibrary: { isPending: boolean; mutate: () => void };
}) {
  return (
    <button
      aria-label={`Remove ${item.slug} from library`}
      className="inline-flex h-8 items-center justify-center rounded-md border border-destructive/40 px-2.5 text-xs font-medium text-destructive transition-colors hover:bg-destructive/10"
      disabled={removeFromLibrary.isPending}
      onClick={() => removeFromLibrary.mutate()}
      type="button"
    >
      {removeFromLibrary.isPending ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
      ) : (
        "Remove"
      )}
    </button>
  );
}
