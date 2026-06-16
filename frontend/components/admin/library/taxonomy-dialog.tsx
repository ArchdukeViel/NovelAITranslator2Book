"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { X } from "lucide-react";
import * as React from "react";

import { DialogShell } from "@/components/admin/dialog-shell";
import { ErrorBanner } from "@/components/admin/error-banner";
import { Button } from "@/components/ui/button";
import { useGenres } from "@/hooks/public/use-genres";
import { useDebounce } from "@/hooks/public/use-debounce";
import { api, describeApiError } from "@/lib/api";
import type { NovelSummary } from "@/lib/api-types";
import { publicApi } from "@/lib/public-api";
import type { PublicTagSearchResult } from "@/lib/public-types";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export type TaxonomyDialogProps = {
  open: boolean;
  novel: NovelSummary | null;
  onClose: () => void;
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TaxonomyDialog({ open, novel, onClose }: TaxonomyDialogProps) {
  const queryClient = useQueryClient();
  const novelId = novel?.novel_id ?? "";

  // --- local selection state (optimistic, committed on save) ---
  const [selectedSlugs, setSelectedSlugs] = React.useState<Set<string>>(new Set());
  const [selectedTags, setSelectedTags] = React.useState<string[]>([]);
  const [tagInput, setTagInput] = React.useState("");
  const [saveError, setSaveError] = React.useState<unknown>(null);
  const debouncedQuery = useDebounce(tagInput.trim(), 300);

  // --- data loading ---
  const taxonomy = useQuery({
    queryKey: ["admin", "taxonomy", novelId],
    queryFn: () => api.getTaxonomy(novelId),
    enabled: open && Boolean(novelId)
  });

  const genresQuery = useGenres();

  const tagSearch = useQuery({
    queryKey: ["public", "tag-search", debouncedQuery],
    queryFn: () => publicApi.searchTags({ q: debouncedQuery, include_adult: true, limit: 8 }),
    enabled: open && debouncedQuery.length >= 2
  });

  // Reset selection when taxonomy data arrives or dialog re-opens
  React.useEffect(() => {
    if (!open) {
      setTagInput("");
      setSaveError(null);
      return;
    }
    if (taxonomy.data) {
      setSelectedSlugs(new Set(taxonomy.data.genres));
      setSelectedTags([...taxonomy.data.tags]);
    }
  }, [open, taxonomy.data]);

  const isLoading = taxonomy.isLoading || genresQuery.isLoading;
  const loadError = taxonomy.error ?? genresQuery.error;

  // --- genre toggles ---
  const toggleGenre = (slug: string) => {
    setSelectedSlugs((prev) => {
      const next = new Set(prev);
      if (next.has(slug)) next.delete(slug);
      else next.add(slug);
      return next;
    });
  };

  // --- tag add / remove ---
  const addTag = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed || selectedTags.includes(trimmed)) return;
    setSelectedTags((prev) => [...prev, trimmed]);
    setTagInput("");
  };

  const removeTag = (name: string) => {
    setSelectedTags((prev) => prev.filter((t) => t !== name));
  };

  // --- save ---
  const saveMutation = useMutation({
    mutationFn: () =>
      api.setTaxonomy(novelId, {
        genre_slugs: [...selectedSlugs],
        tags: [...selectedTags]
      }),
    onSuccess: () => {
      setSaveError(null);
      void queryClient.invalidateQueries({ queryKey: ["admin", "taxonomy", novelId] });
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      onClose();
    },
    onError: (err: unknown) => {
      setSaveError(err);
    }
  });

  // --- tag search results (exclude already selected) ---
  const filteredTagResults = React.useMemo(() => {
    const results = tagSearch.data ?? [];
    return results.filter((r: PublicTagSearchResult) => !selectedTags.includes(r.name));
  }, [tagSearch.data, selectedTags]);

  // --- genre display name helper ---
  const genreLabel = (slug: string) => {
    const match = genresQuery.data?.find((g) => g.slug === slug);
    return match?.name_ja || match?.name_en || slug;
  };

  // --- footer ---
  const footer = (
    <div className="flex items-center justify-end gap-3">
      <Button variant="outline" onClick={onClose} disabled={saveMutation.isPending}>
        Cancel
      </Button>
      <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
        {saveMutation.isPending ? "Saving\u2026" : "Save taxonomy"}
      </Button>
    </div>
  );

  return (
    <DialogShell
      open={open}
      title={`Taxonomy \u2014 ${novel?.title || novelId}`}
      description="Edit genre and tag assignments. Scraper-assigned items are preserved on save."
      onClose={onClose}
      className="max-w-2xl"
      footer={footer}
    >
      <div className="space-y-5 p-4">
        {/* Loading / error */}
        {loadError ? <ErrorBanner error={loadError} fallback="Failed to load taxonomy." /> : null}
        {saveError ? <ErrorBanner error={saveError} fallback="Failed to save taxonomy." /> : null}

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading taxonomy\u2026</p>
        ) : (
          <>
            {/* ---- Genre section ---- */}
            <section>
              <h3 className="mb-2 text-sm font-medium">Genres</h3>
              {genresQuery.data && genresQuery.data.length > 0 ? (
                <div className="flex flex-wrap gap-2">
                  {genresQuery.data.map((genre) => {
                    const active = selectedSlugs.has(genre.slug);
                    return (
                      <button
                        key={genre.slug}
                        type="button"
                        onClick={() => toggleGenre(genre.slug)}
                        className={
                          "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium transition-colors " +
                          (active
                            ? "bg-secondary text-secondary-foreground"
                            : "border border-border/70 text-muted-foreground hover:bg-muted")
                        }
                      >
                        {genre.name_ja || genre.name_en || genre.slug}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">No genres available.</p>
              )}
            </section>

            {/* ---- Tag section ---- */}
            <section>
              <h3 className="mb-2 text-sm font-medium">Tags</h3>

              {/* Selected tags as removable chips */}
              {selectedTags.length > 0 ? (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {selectedTags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 rounded-md border border-border/70 px-2 py-1 text-xs text-muted-foreground"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="ml-0.5 rounded-sm p-0.5 hover:bg-muted"
                        aria-label={`Remove tag ${tag}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}

              {/* Search input */}
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="Search tags (2+ chars)\u2026"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addTag(tagInput);
                  }
                }}
              />

              {/* Dropdown results */}
              {debouncedQuery.length >= 2 ? (
                <div className="mt-1.5 rounded-md border border-border bg-card text-sm shadow-sm">
                  {tagSearch.isLoading ? (
                    <div className="px-3 py-2 text-muted-foreground">Searching\u2026</div>
                  ) : tagSearch.error ? (
                    <div className="px-3 py-2 text-destructive">Search failed</div>
                  ) : filteredTagResults.length > 0 ? (
                    filteredTagResults.map((tag) => (
                      <button
                        key={tag.name}
                        type="button"
                        onClick={() => addTag(tag.name)}
                        className="block w-full px-3 py-1.5 text-left hover:bg-muted"
                      >
                        <span>{tag.name}</span>
                        {tag.name_ja && tag.name_ja !== tag.name ? (
                          <span className="ml-1.5 text-muted-foreground">({tag.name_ja})</span>
                        ) : null}
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-2 text-muted-foreground">
                      No results. Press Enter to add &ldquo;{debouncedQuery}&rdquo; as a new tag.
                    </div>
                  )}
                </div>
              ) : null}
            </section>
          </>
        )}
      </div>
    </DialogShell>
  );
}
