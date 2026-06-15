"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Languages, RefreshCw, RotateCw, Trash2 } from "lucide-react";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LibraryRowActions } from "@/components/admin/library/library-row-actions";
import { TranslationModal } from "@/components/admin/library/translation-modal";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { SortableHeader } from "@/components/admin/sortable-header";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";
import { api, type ActivityRecord, type ChapterSummary, type NovelMetadata, type NovelSummary } from "@/lib/api";

type LibrarySortKey = "novel" | "source" | "listed" | "raw" | "translated" | "status";
type LibraryAction = "translate" | "recrawl" | "delete";

const TRANSLATION_LANGUAGES = ["English", "Indonesian"] as const;

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

function metadataText(metadata: NovelMetadata | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function chapterSortValue(chapter: ChapterSummary) {
  const parsed = Number(chapter.id);
  return Number.isFinite(parsed) ? parsed : Number.MAX_SAFE_INTEGER;
}

export default function LibraryPage() {
  const queryClient = useQueryClient();
  const [selectedNovelIds, setSelectedNovelIds] = React.useState<Set<string>>(new Set());
  const { sortKey, sortDirection, handleSort } = useSortableTable<LibrarySortKey>("novel", "asc");
  const [pendingDeleteRows, setPendingDeleteRows] = React.useState<NovelSummary[] | null>(null);
  const [translationNovel, setTranslationNovel] = React.useState<NovelSummary | null>(null);
  const [translationLanguage, setTranslationLanguage] = React.useState<(typeof TRANSLATION_LANGUAGES)[number]>("English");
  const [selectedTranslationChapterIds, setSelectedTranslationChapterIds] = React.useState<Set<string>>(new Set());
  // Note: activeGeminiToken removed - provider credential now comes from Admin_API, server-managed (Task 4)
  const translationNovelId = translationNovel?.novel_id;

  const novels = useQuery({
    queryKey: ["novels"],
    queryFn: () => api.novels()
  });
  const rows = Array.isArray(novels.data) ? novels.data : [];
  const unexpectedPayload = novels.data && !Array.isArray(novels.data);
  const translationMetadata = useQuery({
    queryKey: ["novel", translationNovelId],
    queryFn: () => api.novel(translationNovelId ?? ""),
    enabled: Boolean(translationNovelId)
  });
  const translationChapters = useQuery({
    queryKey: ["chapters", translationNovelId],
    queryFn: () => api.chapters(translationNovelId ?? ""),
    enabled: Boolean(translationNovelId)
  });
  const translationChapterRows = React.useMemo(() => {
    return Array.isArray(translationChapters.data)
      ? [...translationChapters.data].sort((left, right) => {
          const leftValue = chapterSortValue(left);
          const rightValue = chapterSortValue(right);
          if (leftValue !== rightValue) {
            return leftValue - rightValue;
          }
          return left.id.localeCompare(right.id);
        })
      : [];
  }, [translationChapters.data]);
  const selectedTranslationCount = selectedTranslationChapterIds.size;
  const allTranslationChaptersSelected =
    translationChapterRows.length > 0 && translationChapterRows.every((chapter) => selectedTranslationChapterIds.has(chapter.id));
  const translationChapterSelection = React.useMemo(() => {
    return [...selectedTranslationChapterIds]
      .sort((left, right) => {
        const leftNumber = Number(left);
        const rightNumber = Number(right);
        if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber !== rightNumber) {
          return leftNumber - rightNumber;
        }
        return left.localeCompare(right);
      })
      .join(";");
  }, [selectedTranslationChapterIds]);

  const selectedRows = React.useMemo(
    () => rows.filter((novel) => selectedNovelIds.has(novel.novel_id)),
    [rows, selectedNovelIds]
  );

  React.useEffect(() => {
    if (!translationNovelId || !Array.isArray(translationChapters.data)) {
      return;
    }
    setSelectedTranslationChapterIds(
      new Set(translationChapters.data.filter((chapter) => !chapter.translated).map((chapter) => chapter.id))
    );
  }, [translationNovelId, translationChapters.data]);

  const sortedRows = React.useMemo(() => {
    return [...rows].sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      return compareSortableValues(leftValue, rightValue, sortDirection);
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

        // Provider credential now managed server-side via Admin_API
        const activity = await api.createTranslationActivity({
          novel_id: novel.novel_id,
          source_key: novel.source,
          kind: "translate",
          chapters: "all",
          provider_key: "gemini",
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
      setPendingDeleteRows(null);
    }
  });

  const runTranslationDialog = useMutation({
    mutationFn: async () => {
      if (!translationNovel) {
        throw new Error("No novel selected for translation.");
      }
      if (!translationNovel.source) {
        throw new Error(`${translationNovel.novel_id} has no source key.`);
      }
      if (!translationChapterSelection) {
        throw new Error("Select at least one chapter to translate.");
      }

      // Provider credential now managed server-side via Admin_API - no client-side token sync needed
      const activity = await api.createTranslationActivity({
        novel_id: translationNovel.novel_id,
        source_key: translationNovel.source,
        kind: "translate",
        chapters: translationChapterSelection,
        provider_key: "gemini",
        metadata: {
          library_action: "translate",
          target_language: translationLanguage,
          selected_chapter_count: selectedTranslationChapterIds.size
        }
      });
      return api.runActivity(activity.id);
    },
    onSuccess: () => {
      invalidateLibrary();
      void queryClient.invalidateQueries({ queryKey: ["chapters", translationNovelId] });
      setTranslationNovel(null);
      setSelectedTranslationChapterIds(new Set());
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

  const openTranslationDialog = (novel: NovelSummary) => {
    setTranslationNovel(novel);
    setTranslationLanguage("English");
    setSelectedTranslationChapterIds(new Set());
    runTranslationDialog.reset();
  };

  const closeTranslationDialog = () => {
    if (runTranslationDialog.isPending) {
      return;
    }
    setTranslationNovel(null);
    setSelectedTranslationChapterIds(new Set());
  };

  const toggleTranslationChapter = (chapterId: string) => {
    setSelectedTranslationChapterIds((current) => {
      const next = new Set(current);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      return next;
    });
  };

  const toggleAllTranslationChapters = () => {
    setSelectedTranslationChapterIds(
      allTranslationChaptersSelected ? new Set() : new Set(translationChapterRows.map((chapter) => chapter.id))
    );
  };

  const runAction = (action: LibraryAction, actionRows: NovelSummary[]) => {
    if (actionRows.length === 0 || runLibraryAction.isPending) {
      return;
    }
    if (action === "translate") {
      openTranslationDialog(actionRows[0]);
      return;
    }
    if (action === "delete") {
      setPendingDeleteRows(actionRows);
      return;
    }
    runLibraryAction.mutate({ action, novels: actionRows });
  };

  const dialogTitle =
    metadataText(translationMetadata.data, "translated_title") ||
    translationNovel?.title ||
    metadataText(translationMetadata.data, "title") ||
    translationNovel?.novel_id ||
    "-";
  const dialogAuthor =
    metadataText(translationMetadata.data, "translated_author") ||
    translationNovel?.author ||
    metadataText(translationMetadata.data, "author") ||
    "-";
  const dialogSynopsis =
    metadataText(translationMetadata.data, "translated_synopsis") ||
    metadataText(translationMetadata.data, "synopsis") ||
    "-";
  const translationDialogLoading = translationMetadata.isLoading || translationChapters.isLoading;
  const translationDialogError = translationMetadata.error || translationChapters.error;

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
              disabled={selectedRows.length !== 1 || runLibraryAction.isPending || runTranslationDialog.isPending}
              title={selectedRows.length === 1 ? "Choose chapters to translate" : "Select one novel to translate"}
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
        <ErrorBanner error={runLibraryAction.error} fallback="Failed to run library action." />
        <ErrorBanner error={novels.error} fallback="Failed to load novels." />
        {unexpectedPayload ? (
          <div className="border-t px-4 py-3 text-sm text-destructive">
            Unexpected novels payload. Expected an array.
          </div>
        ) : null}
        <PanelBody className="p-0">
          <div className="seamless-scrollbar max-h-[640px] overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-[1] border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <TableCheckbox checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all novels" />
                  </th>
                  <SortableHeader label="Novel" sortKey="novel" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="min-w-[280px]" />
                  <SortableHeader label="Source" sortKey="source" activeKey={sortKey} direction={sortDirection} onSort={handleSort} />
                  <SortableHeader label="Listed chapters" sortKey="listed" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-36" />
                  <SortableHeader label="Raw chapters" sortKey="raw" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-32" />
                  <SortableHeader label="Translated chapters" sortKey="translated" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-44" />
                  <SortableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-36" />
                  <th className="w-[360px] px-4 py-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {novels.isLoading ? (
                  <LoadingRows colSpan={8} label="Loading library..." />
                ) : novels.error ? (
                  <EmptyState title="Failed to load novels." colSpan={8} />
                ) : unexpectedPayload ? (
                  <EmptyState title="Unexpected novels payload." colSpan={8} />
                ) : sortedRows.length ? (
                  sortedRows.map((novel) => {
                    const sourceUrl = novel.source_url?.trim();
                    const rawChapters = novel.scraped_count ?? 0;
                    const translatedChapters = novel.translated_count ?? 0;
                    const listedChapters = novel.chapter_count;
                    const missingSource = !novel.source;
                    return (
                      <tr className="border-b last:border-0" key={novel.novel_id}>
                        <td className="px-4 py-3">
                          <TableCheckbox
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
                          <LibraryRowActions
                            novel={novel}
                            missingSource={missingSource}
                            pending={runLibraryAction.isPending}
                            translationPending={runTranslationDialog.isPending}
                            onTranslate={(row) => runAction("translate", [row])}
                            onRecrawl={(row) => runAction("recrawl", [row])}
                            onDelete={(row) => runAction("delete", [row])}
                          />
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <EmptyState title="No novels in the library yet." colSpan={8} />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <TranslationModal
        open={Boolean(translationNovel)}
        novelId={translationNovel?.novel_id ?? ""}
        title={dialogTitle}
        author={dialogAuthor}
        synopsis={dialogSynopsis}
        language={translationLanguage}
        languages={TRANSLATION_LANGUAGES}
        chapters={translationChapterRows}
        selectedChapterIds={selectedTranslationChapterIds}
        selectedCount={selectedTranslationCount}
        allSelected={allTranslationChaptersSelected}
        loading={translationDialogLoading}
        loadError={translationDialogError}
        runError={runTranslationDialog.error}
        pending={runTranslationDialog.isPending}
        onLanguageChange={(language) => setTranslationLanguage(language as (typeof TRANSLATION_LANGUAGES)[number])}
        onToggleAll={toggleAllTranslationChapters}
        onToggleChapter={toggleTranslationChapter}
        onCancel={closeTranslationDialog}
        onConfirm={() => runTranslationDialog.mutate()}
      />

      <ConfirmDialog
        open={Boolean(pendingDeleteRows)}
        title="Delete selected novels"
        description={`Delete ${pendingDeleteRows?.length ?? 0} selected novel(s)?`}
        confirmLabel="Delete"
        destructive
        pending={runLibraryAction.isPending}
        onConfirm={() => {
          if (pendingDeleteRows) {
            runLibraryAction.mutate({ action: "delete", novels: pendingDeleteRows });
          }
        }}
        onCancel={() => setPendingDeleteRows(null)}
        auditNotice="This action is recorded in the audit log."
      />
    </>
  );
}
