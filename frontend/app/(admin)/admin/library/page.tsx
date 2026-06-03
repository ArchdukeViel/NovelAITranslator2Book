"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, FileEdit, Languages, RefreshCw, RotateCw, Trash2 } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api, type ActivityRecord, type NovelSummary } from "@/lib/api";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";

type LibrarySortKey = "novel" | "source" | "listed" | "raw" | "translated" | "status";
type SortDirection = "asc" | "desc";
type LibraryAction = "translate" | "recrawl" | "delete";

function translationState(novel: NovelSummary) {
  const total = novel.chapter_count;
  const translated = novel.translated_count ?? 0;
  if (total > 0 && translated >= total) {
    return "translated";
  }
  if (translated > 0) {
    return "partial";
  }
  return "untranslated";
}

function translationBadge(novel: NovelSummary) {
  const state = translationState(novel);
  if (state === "translated") {
    return <Badge tone="green">Translated</Badge>;
  }
  if (state === "partial") {
    return <Badge tone="amber">Partial</Badge>;
  }
  return <Badge tone="neutral">Untranslated</Badge>;
}

function sortValue(novel: NovelSummary, key: LibrarySortKey) {
  if (key === "novel") {
    return `${novel.title || novel.novel_id} ${novel.author || ""}`.toLowerCase();
  }
  if (key === "source") {
    return `${novel.source || ""} ${novel.source_url || ""}`.toLowerCase();
  }
  if (key === "listed") {
    return novel.chapter_count;
  }
  if (key === "raw") {
    return novel.scraped_count ?? 0;
  }
  if (key === "translated") {
    return novel.translated_count ?? 0;
  }
  return translationState(novel);
}

function sortPointer(key: LibrarySortKey, activeKey: LibrarySortKey, direction: SortDirection) {
  if (key !== activeKey) {
    return "";
  }
  return direction === "asc" ? " \u25B2" : " \u25BC";
}

async function syncGeminiToken(apiToken: string | undefined) {
  if (!apiToken?.trim()) {
    return;
  }
  await api.setProviderApiKey({
    provider: "gemini",
    api_key: apiToken,
    apply_globally: true,
    validate_connection: false
  });
}

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const [selectedNovelIds, setSelectedNovelIds] = React.useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = React.useState<LibrarySortKey>("novel");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("asc");
  const activeGeminiToken = useUiStore((state) => state.apiTokens.find((entry) => entry.status === "Active")?.token);

  const novels = useQuery({ queryKey: ["novels"], queryFn: () => api.novels() });
  const rows = novels.data ?? [];

  const selectedRows = React.useMemo(
    () => rows.filter((novel) => selectedNovelIds.has(novel.novel_id)),
    [rows, selectedNovelIds]
  );
  const sortedRows = React.useMemo(() => {
    return [...rows].sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      const direction = sortDirection === "asc" ? 1 : -1;
      if (typeof leftValue === "number" && typeof rightValue === "number") {
        return (leftValue - rightValue) * direction;
      }
      return String(leftValue).localeCompare(String(rightValue)) * direction;
    });
  }, [rows, sortDirection, sortKey]);

  const allRowsSelected = rows.length > 0 && rows.every((novel) => selectedNovelIds.has(novel.novel_id));

  const invalidateLibrary = () => {
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
    void queryClient.invalidateQueries({ queryKey: ["activity"] });
  };

  const runLibraryAction = useMutation({
    mutationFn: async ({ action, novels: actionRows }: { action: LibraryAction; novels: NovelSummary[] }) => {
      const completed: Array<ActivityRecord | void> = [];
      if (action === "delete") {
        const confirmed = window.confirm(`Delete ${actionRows.length} selected novel(s)?`);
        if (!confirmed) {
          return completed;
        }
      }

      for (const novel of actionRows) {
        if (action === "delete") {
          completed.push(await api.deleteNovel(novel.novel_id));
          continue;
        }

        if (!novel.source) {
          throw new Error(`${novel.novel_id} has no source key.`);
        }

        if (action === "recrawl") {
          const activity = await api.createCrawlActivity({
            novel_id: novel.novel_id,
            source_key: novel.source,
            kind: "chapters",
            chapters: "all",
            source_url: novel.source_url || undefined,
            metadata: { library_action: "recrawl" }
          });
          completed.push(await api.runActivity(activity.id));
          continue;
        }

        await syncGeminiToken(activeGeminiToken);
        const activity = await api.createTranslationActivity({
          novel_id: novel.novel_id,
          source_key: novel.source,
          kind: "translate",
          chapters: "all",
          provider: "gemini",
          metadata: {
            library_action: "translate",
            target_language: "English"
          }
        });
        completed.push(await api.runActivity(activity.id));
      }
      return completed;
    },
    onSuccess: () => {
      invalidateLibrary();
      setSelectedNovelIds(new Set());
    }
  });

  const toggleAllRows = () => {
    setSelectedNovelIds(allRowsSelected ? new Set() : new Set(rows.map((novel) => novel.novel_id)));
  };

  const toggleNovel = (novelId: string) => {
    setSelectedNovelIds((current) => {
      const next = new Set(current);
      if (next.has(novelId)) {
        next.delete(novelId);
      } else {
        next.add(novelId);
      }
      return next;
    });
  };

  const handleSort = (key: LibrarySortKey) => {
    if (sortKey === key) {
      setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection("asc");
  };

  const sortHeader = (label: string, key: LibrarySortKey, className = "") => (
    <th className={cn("px-4 py-3", className)}>
      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => handleSort(key)}>
        {label}
        {sortPointer(key, sortKey, sortDirection)}
      </button>
    </th>
  );

  const runAction = (action: LibraryAction, actionRows: NovelSummary[]) => {
    if (actionRows.length === 0 || runLibraryAction.isPending) {
      return;
    }
    runLibraryAction.mutate({ action, novels: actionRows });
  };

  return (
    <>
      <PageHeading
        title="Library"
        description="Manage novels in storage, including raw crawl coverage, translations, recrawls, and deletion."
      />

      <Panel>
        <PanelHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <PanelTitle>Novel Library</PanelTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {selectedRows.length ? `${selectedRows.length} selected` : `${rows.length} novel(s) stored`}
            </p>
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => runAction("translate", selectedRows)}
              disabled={selectedRows.length === 0 || runLibraryAction.isPending}
            >
              <Languages className="h-4 w-4" />
              Translate selected
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => runAction("recrawl", selectedRows)}
              disabled={selectedRows.length === 0 || runLibraryAction.isPending}
            >
              <RefreshCw className="h-4 w-4" />
              Recrawl selected
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => runAction("delete", selectedRows)}
              disabled={selectedRows.length === 0 || runLibraryAction.isPending}
            >
              <Trash2 className="h-4 w-4" />
              Delete selected
            </Button>
            <Button variant="outline" size="sm" onClick={() => void novels.refetch()} disabled={novels.isFetching}>
              <RotateCw className="h-4 w-4" />
              Refresh
            </Button>
          </div>
        </PanelHeader>
        {runLibraryAction.error ? (
          <div className="border-t px-4 py-3 text-sm text-destructive">{runLibraryAction.error.message}</div>
        ) : null}
        <PanelBody className="p-0">
          <div className="seamless-scrollbar max-h-[640px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-[1] border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <input className="table-checkbox" type="checkbox" checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all novels" />
                  </th>
                  {sortHeader("Novel", "novel", "min-w-[280px]")}
                  {sortHeader("Source", "source")}
                  {sortHeader("Listed chapters", "listed", "w-36")}
                  {sortHeader("Raw chapters", "raw", "w-32")}
                  {sortHeader("Translated chapters", "translated", "w-44")}
                  {sortHeader("Status", "status", "w-36")}
                  <th className="w-[360px] px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.length ? (
                  sortedRows.map((novel) => {
                    const sourceUrl = novel.source_url?.trim();
                    const rawChapters = novel.scraped_count ?? 0;
                    const translatedChapters = novel.translated_count ?? 0;
                    const listedChapters = novel.chapter_count;
                    const actionRows = [novel];
                    const missingSource = !novel.source;
                    return (
                      <tr className="border-b last:border-0" key={novel.novel_id}>
                        <td className="px-4 py-3">
                          <input
                            className="table-checkbox"
                            type="checkbox"
                            checked={selectedNovelIds.has(novel.novel_id)}
                            onChange={() => toggleNovel(novel.novel_id)}
                            aria-label={`Select ${novel.novel_id}`}
                          />
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{novel.title || novel.novel_id}</div>
                          <div className="mt-1 font-mono text-xs text-muted-foreground">{novel.novel_id}</div>
                          {novel.author ? <div className="mt-1 text-xs text-muted-foreground">{novel.author}</div> : null}
                        </td>
                        <td className="max-w-[240px] px-4 py-3">
                          <div className="font-medium">{novel.source || "-"}</div>
                          {sourceUrl ? (
                            <a
                              className="mt-1 block truncate text-xs text-muted-foreground hover:text-primary"
                              href={sourceUrl}
                              rel="noreferrer"
                              target="_blank"
                              title={sourceUrl}
                            >
                              {sourceUrl}
                            </a>
                          ) : null}
                        </td>
                        <td className="px-4 py-3 font-medium">{listedChapters}</td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{rawChapters}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {listedChapters ? `${Math.round((rawChapters / listedChapters) * 100)}% raw` : "no chapter list"}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium">{translatedChapters}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {listedChapters ? `${Math.round((translatedChapters / listedChapters) * 100)}% translated` : "no chapter list"}
                          </div>
                        </td>
                        <td className="px-4 py-3">{translationBadge(novel)}</td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              size="sm"
                              onClick={() => runAction("translate", actionRows)}
                              disabled={missingSource || runLibraryAction.isPending}
                              title={missingSource ? "Source key missing" : "Translate all raw chapters"}
                            >
                              <Languages className="h-4 w-4" />
                              Translate
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => runAction("recrawl", actionRows)}
                              disabled={missingSource || runLibraryAction.isPending}
                              title={missingSource ? "Source key missing" : "Check and scrape latest chapters"}
                            >
                              <RefreshCw className="h-4 w-4" />
                              Recrawl
                            </Button>
                            <Button size="sm" variant="destructive" onClick={() => runAction("delete", actionRows)} disabled={runLibraryAction.isPending}>
                              <Trash2 className="h-4 w-4" />
                              Delete
                            </Button>
                            <Link
                              className={cn(
                                "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
                              )}
                              href={`/novel/${encodeURIComponent(novel.novel_id)}`}
                            >
                              <BookOpen className="h-4 w-4" />
                              Reader
                            </Link>
                            <Link
                              className={cn(
                                "inline-flex h-8 items-center justify-center gap-2 rounded-md border border-border bg-background px-2.5 text-xs font-medium transition-colors hover:bg-muted"
                              )}
                              href={`/admin/editor?novel=${encodeURIComponent(novel.novel_id)}`}
                            >
                              <FileEdit className="h-4 w-4" />
                              Editor
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td className="px-4 py-8 text-muted-foreground" colSpan={8}>
                      No novels in the library yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>
    </>
  );
}
