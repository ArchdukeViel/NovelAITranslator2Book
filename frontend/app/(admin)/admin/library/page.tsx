"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Languages, RefreshCw, RotateCw, Trash2 } from "lucide-react";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LibraryRowActions } from "@/components/admin/library/library-row-actions";
import { RetranslateStaleDialog } from "@/components/admin/library/retranslate-stale-dialog";
import { TaxonomyDialog } from "@/components/admin/library/taxonomy-dialog";
import { TranslationModal } from "@/components/admin/library/translation-modal";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { SortableHeader } from "@/components/admin/sortable-header";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";
import {
  adminApi,
  api,
  type ActivityRecord,
  type ChapterSummary,
  type LibrarySummaryItem,
  type LibrarySummaryResponse,
  type NovelMetadata,
  type NovelPublicationSummary,
  type NovelSummary,
} from "@/lib/api";

type LibrarySortKey = "novel" | "source" | "listed" | "raw" | "translated" | "failed" | "pending" | "status";
type LibraryAction = "translate" | "recrawl" | "delete";

const TRANSLATION_LANGUAGES = ["English", "Indonesian"] as const;

type NovelWithSummary = NovelSummary & {
  summary?: LibrarySummaryItem;
  summaryError?: boolean;
  summaryLoading?: boolean;
};

type SummaryAvailability =
  | { state: "loading" }
  | { state: "ready"; value: LibrarySummaryItem }
  | { state: "unavailable" };

function getSummary(novel: NovelWithSummary): SummaryAvailability {
  if (novel.summaryLoading) {
    return { state: "loading" };
  }
  if (novel.summaryError || novel.summary === undefined) {
    return { state: "unavailable" };
  }
  return { state: "ready", value: novel.summary };
}

function translationState(novel: NovelWithSummary) {
  const summary = getSummary(novel);
  if (summary.state !== "ready") {
    return "unavailable";
  }
  const { total, translated } = summary.value;

  if (total > 0 && translated >= total) {
    return "translated";
  }

  if (translated > 0) {
    return "partial";
  }

  return "untranslated";
}

function translationBadge(novel: NovelWithSummary) {
  const state = translationState(novel);

  if (state === "translated") {
    return <Badge tone="green">Translated</Badge>;
  }

  if (state === "partial") {
    return <Badge tone="amber">Partial</Badge>;
  }

  if (state === "unavailable") {
    return <Badge tone="neutral">Unavailable</Badge>;
  }

  return <Badge tone="neutral">Untranslated</Badge>;
}

function getCount(novel: NovelWithSummary, field: keyof LibrarySummaryItem): number | null {
  const summary = getSummary(novel);
  if (summary.state !== "ready") {
    return null;
  }
  return summary.value[field] as number;
}

function formatCount(count: number | null): string {
  return count === null ? "—" : String(count);
}

function formatPercent(numerator: number | null, denominator: number | null): string {
  if (numerator === null || denominator === null || denominator === 0) {
    return "—";
  }
  return `${Math.round((numerator / denominator) * 100)}%`;
}

function sortValue(novel: NovelWithSummary, key: LibrarySortKey) {
  if (key === "novel") {
    return `${novel.title || novel.novel_id} ${novel.author || ""}`.toLowerCase();
  }

  if (key === "source") {
    return `${novel.source_key || ""} ${novel.source_url || ""}`.toLowerCase();
  }

  const summary = getSummary(novel);
  if (summary.state !== "ready") {
    return -1;
  }

  if (key === "listed") {
    return summary.value.total;
  }

  if (key === "raw") {
    return summary.value.scraped;
  }

  if (key === "translated") {
    return summary.value.translated;
  }

  if (key === "failed") {
    return summary.value.failed;
  }

  if (key === "pending") {
    return summary.value.pending;
  }

  return summary.state;
}

function metadataText(metadata: NovelMetadata | undefined, key: string) {
  const value = metadata?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function applyPublicationSummary(row: NovelSummary, result: NovelPublicationSummary): NovelSummary {
  return {
    ...row,
    title: result.title,
    source_title: result.source_title,
    chapter_count: result.chapter_count,
    translated_count: result.translated_count,
    is_published: result.is_published,
    latest_chapter_id: result.latest_chapter_id,
    latest_chapter_number: result.latest_chapter_number,
    latest_chapter_title: result.latest_chapter_title,
    publication_status: result.publication_status,
  };
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
  const [taxonomyNovel, setTaxonomyNovel] = React.useState<NovelSummary | null>(null);
  const [publicationNotice, setPublicationNotice] = React.useState<string | null>(null);
  const [translationLanguage, setTranslationLanguage] = React.useState<(typeof TRANSLATION_LANGUAGES)[number]>("English");
  const [selectedTranslationChapterIds, setSelectedTranslationChapterIds] = React.useState<Set<string>>(new Set());
  const [retranslateStaleNovel, setRetranslateStaleNovel] = React.useState<NovelSummary | null>(null);

  const translationNovelId = translationNovel?.novel_id;

  const novels = useQuery({
    queryKey: ["novels"],
    queryFn: () => api.novels(),
  });

  const summary = useQuery({
    queryKey: ["library-summary"],
    queryFn: () => adminApi.librarySummary({ refresh: false }),
  });

  const refreshSummary = useMutation({
    mutationFn: () => adminApi.librarySummary({ refresh: true }),
    onSuccess: (data) => {
      queryClient.setQueryData(["library-summary"], data);
    },
  });

  const rows = Array.isArray(novels.data) ? novels.data : [];
  const unexpectedPayload = novels.data && !Array.isArray(novels.data);

  const translationMetadata = useQuery({
    queryKey: ["novel", translationNovelId],
    queryFn: () => api.novel(translationNovelId ?? ""),
    enabled: Boolean(translationNovelId),
  });

  const translationChapters = useQuery({
    queryKey: ["chapters", translationNovelId],
    queryFn: () => api.chapters(translationNovelId ?? ""),
    enabled: Boolean(translationNovelId),
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
    translationChapterRows.length > 0 &&
    translationChapterRows.every((chapter) => selectedTranslationChapterIds.has(chapter.id));

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
    [rows, selectedNovelIds],
  );

  React.useEffect(() => {
    if (!translationNovelId || !Array.isArray(translationChapters.data)) {
      return;
    }

    setSelectedTranslationChapterIds(
      new Set(translationChapters.data.filter((chapter) => !chapter.translated).map((chapter) => chapter.id)),
    );
  }, [translationNovelId, translationChapters.data]);

  const mergedRows = React.useMemo(() => {
    return rows.map((novel) => {
      const summaryAvailability = getSummary(novel);
      return {
        ...novel,
        summaryLoading: summaryAvailability.state === "loading",
        summaryError: summaryAvailability.state === "unavailable",
        summary: summaryAvailability.state === "ready" ? summaryAvailability.value : undefined,
      };
    });
  }, [rows]);

  const sortedRows = React.useMemo(() => {
    return [...mergedRows].sort((left, right) => {
      const leftValue = sortValue(left, sortKey);
      const rightValue = sortValue(right, sortKey);
      return compareSortableValues(leftValue, rightValue, sortDirection);
    });
  }, [mergedRows, sortDirection, sortKey]);

  const allRowsSelected = rows.length > 0 && rows.every((novel) => selectedNovelIds.has(novel.novel_id));

  const invalidateLibrary = () => {
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
    void queryClient.invalidateQueries({ queryKey: ["activity"] });
    void queryClient.invalidateQueries({ queryKey: ["library-summary"] });
  };

  const runLibraryAction = useMutation({
    mutationFn: async ({ action, novels: actionRows }: { action: LibraryAction; novels: NovelSummary[] }) => {
      const completed: Array<ActivityRecord | void> = [];

      for (const novel of actionRows) {
        if (action === "delete") {
          completed.push(await api.deleteNovel(novel.novel_id));
          continue;
        }

        if (!novel.source_key) {
          throw new Error(`${novel.novel_id} has no source key.`);
        }

        if (action === "recrawl") {
          const activity = await api.createCrawlActivity({
            novel_id: novel.novel_id,
            source_key: novel.source_key,
            kind: "chapters",
            chapters: "all",
            source_url: novel.source_url || undefined,
            metadata: { library_action: "recrawl" },
          });

          completed.push(await api.runActivity(activity.id));
          continue;
        }

        const activity = await api.createTranslationActivity({
          novel_id: novel.novel_id,
          source_key: novel.source_key,
          kind: "translate",
          chapters: "all",
          provider_key: "gemini",
          metadata: {
            library_action: "translate",
            target_language: "English",
          },
        });

        completed.push(await api.runActivity(activity.id));
      }

      return completed;
    },
    onSuccess: () => {
      invalidateLibrary();
      setSelectedNovelIds(new Set());
      setPendingDeleteRows(null);
    },
  });

  const runTranslationDialog = useMutation({
    mutationFn: async () => {
      if (!translationNovel) {
        throw new Error("No novel selected for translation.");
      }

      if (!translationNovel.source_key) {
        throw new Error(`${translationNovel.novel_id} has no source key.`);
      }

      if (!translationChapterSelection) {
        throw new Error("Select at least one chapter to translate.");
      }

      const activity = await api.createTranslationActivity({
        novel_id: translationNovel.novel_id,
        source_key: translationNovel.source_key,
        kind: "translate",
        chapters: translationChapterSelection,
        provider_key: "gemini",
        metadata: {
          library_action: "translate",
          target_language: translationLanguage,
          selected_chapter_count: selectedTranslationChapterIds.size,
        },
      });

      return api.runActivity(activity.id);
    },
    onSuccess: () => {
      invalidateLibrary();
      void queryClient.invalidateQueries({ queryKey: ["chapters", translationNovelId] });
      setTranslationNovel(null);
      setSelectedTranslationChapterIds(new Set());
    },
  });

  const runRetranslateStale = useMutation({
    mutationFn: async (options: { includeLegacy: boolean; activate: boolean }) => {
      if (!retranslateStaleNovel) {
        throw new Error("No novel selected.");
      }

      if (!retranslateStaleNovel.source_key) {
        throw new Error(`${retranslateStaleNovel.novel_id} has no source key.`);
      }

      return api.retranslateStale(retranslateStaleNovel.novel_id, {
        include_legacy_unknown: options.includeLegacy,
        activate: options.activate,
        provider_key: null,
        provider_model: null,
      });
    },
    onSuccess: () => {
      setRetranslateStaleNovel(null);
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
      void queryClient.invalidateQueries({ queryKey: ["library-summary"] });
    },
  });

  const publishNovel = useMutation({
    mutationFn: async ({ novel, publish }: { novel: NovelSummary; publish: boolean }) => {
      return publish ? api.publishNovel(novel.novel_id) : api.unpublishNovel(novel.novel_id);
    },
    onSuccess: (result) => {
      queryClient.setQueryData<NovelSummary[]>(["novels"], (current) =>
        Array.isArray(current)
          ? current.map((row) => (row.novel_id === result.novel_id ? applyPublicationSummary(row, result) : row))
          : current,
      );

      setPublicationNotice(
        result.visibility_warnings.includes("adult_hidden_by_default")
          ? "Published adult novels remain hidden from the default public catalog."
          : null,
      );
      void queryClient.invalidateQueries({ queryKey: ["library-summary"] });
    },
  });

  const resumeOnboarding = useMutation({
    mutationFn: async (novel: NovelSummary) => adminApi.resumeOnboarding(novel.novel_id),
    onSuccess: () => {
      invalidateLibrary();
    },
  });

  const cancelOnboarding = useMutation({
    mutationFn: async (novel: NovelSummary) => adminApi.cancelOnboarding(novel.novel_id),
    onSuccess: () => {
      invalidateLibrary();
    },
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
      allTranslationChaptersSelected ? new Set() : new Set(translationChapterRows.map((chapter) => chapter.id)),
    );
  };

  const openTaxonomyDialog = (novel: NovelSummary) => {
    setTaxonomyNovel(novel);
  };

  const closeTaxonomyDialog = () => {
    setTaxonomyNovel(null);
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

  const runPublishAction = (novel: NovelSummary, publish: boolean) => {
    if (publishNovel.isPending) {
      return;
    }

    setPublicationNotice(null);
    publishNovel.mutate({ novel, publish });
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

            <Button
              variant="outline"
              size="sm"
              onClick={() => refreshSummary.mutate()}
              disabled={refreshSummary.isPending}
            >
              <RotateCw className="h-4 w-4" />
              {refreshSummary.isPending ? "Refreshing…" : "Refresh summary"}
            </Button>
          </div>
        </PanelHeader>

        <ErrorBanner error={runLibraryAction.error} fallback="Failed to run library action." />
        <ErrorBanner error={publishNovel.error} fallback="Failed to update publication state." />
        <ErrorBanner error={resumeOnboarding.error} fallback="Failed to resume onboarding." />
        <ErrorBanner error={cancelOnboarding.error} fallback="Failed to cancel onboarding." />
        <ErrorBanner error={novels.error} fallback="Failed to load novels." />
        {summary.error && !summary.isFetching && (
          <ErrorBanner
            error={summary.error}
            fallback="Failed to load library summary. Live storage counts unavailable."
          />
        )}
        {summary.error && summary.isFetching && summary.data && (
          <div className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Background refresh failed — showing previous values.{" "}
            <Button variant="outline" size="sm" className="p-0 h-auto" onClick={() => refreshSummary.mutate()}>
              Retry retry
            </Button>
          </div>
        )}
        {summary.error && (
          <ErrorBanner
            error={summary.error}
            fallback="Failed to load live library summary from storage. Click Refresh summary to retry."
          />
        )}

        {publicationNotice ? (
          <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {publicationNotice}
          </div>
        ) : null}

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
                  <SortableHeader
                    label="Novel"
                    sortKey="novel"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="min-w-[280px]"
                  />
                  <SortableHeader
                    label="Source"
                    sortKey="source"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                  />
                  <SortableHeader
                    label="Listed chapters"
                    sortKey="listed"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-36"
                  />
                  <SortableHeader
                    label="Raw chapters"
                    sortKey="raw"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-32"
                  />
                  <SortableHeader
                    label="Translated chapters"
                    sortKey="translated"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-44"
                  />
                  <SortableHeader
                    label="Failed"
                    sortKey="failed"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-28"
                  />
                  <SortableHeader
                    label="Pending"
                    sortKey="pending"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-28"
                  />
                  <SortableHeader
                    label="Status"
                    sortKey="status"
                    activeKey={sortKey}
                    direction={sortDirection}
                    onSort={handleSort}
                    className="w-36"
                  />
                  <th className="px-4 py-3">Onboarding</th>
                  <th className="w-[360px] px-4 py-3">Action</th>
                </tr>
              </thead>

              <tbody>
                {novels.isLoading ? (
                  <LoadingRows colSpan={11} label="Loading library..." />
                ) : novels.error ? (
                  <EmptyState title="Failed to load novels." colSpan={11} />
                ) : unexpectedPayload ? (
                  <EmptyState title="Unexpected novels payload." colSpan={11} />
                ) : sortedRows.length ? (
                  sortedRows.map((novel) => {
                    const sourceUrl = novel.source_url?.trim();
                    const listedChapters = getCount(novel, "total");
                    const rawChapters = getCount(novel, "scraped");
                    const translatedChapters = getCount(novel, "translated");
                    const failedChapters = getCount(novel, "failed");
                    const pendingChapters = getCount(novel, "pending");
                    const missingSource = !novel.source_key;
                    const onboardingStatus = novel.onboarding_status;
                    const showOnboardingBadge = onboardingStatus != null && onboardingStatus !== "ready_for_translation";

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
                          <div className="font-medium">{novel.source_key || "-"}</div>
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

                        <td className="px-4 py-3 font-medium">{formatCount(listedChapters)}</td>

                        <td className="px-4 py-3">
                          <div className="font-medium">{formatCount(rawChapters)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {formatPercent(rawChapters, listedChapters)} raw
                          </div>
                        </td>

                        <td className="px-4 py-3">
                          <div className="font-medium">{formatCount(translatedChapters)}</div>
                          <div className="mt-1 text-xs text-muted-foreground">
                            {formatPercent(translatedChapters, listedChapters)} translated
                          </div>
                        </td>

                        <td className="px-4 py-3 font-medium text-destructive">
                          {formatCount(failedChapters)}
                        </td>

                        <td className="px-4 py-3 font-medium text-amber-600 dark:text-amber-400">
                          {formatCount(pendingChapters)}
                        </td>

                        <td className="px-4 py-3">{translationBadge(novel)}</td>

                        <td className="px-4 py-3">
                          {showOnboardingBadge ? (
                            <div className="space-y-1">
                              <Badge
                                tone={
                                  onboardingStatus === "failed"
                                    ? "red"
                                    : onboardingStatus === "scraping_chapters" ||
                                        onboardingStatus === "chapters_pending" ||
                                        onboardingStatus === "glossary_pending"
                                      ? "amber"
                                      : "neutral"
                                }
                              >
                                {onboardingStatus === "scraping_chapters"
                                  ? "Scraping"
                                  : onboardingStatus === "chapters_pending"
                                    ? "Scrape pending"
                                    : onboardingStatus === "glossary_pending"
                                      ? "Glossary pending"
                                      : onboardingStatus === "failed"
                                        ? "Failed"
                                        : onboardingStatus === "metadata_discovered"
                                          ? "Metadata ready"
                                          : onboardingStatus === "cancelled"
                                            ? "Cancelled"
                                            : onboardingStatus}
                              </Badge>

                              {onboardingStatus === "failed" && novel.onboarding_error_message ? (
                                <div className="max-w-[200px] truncate text-xs text-destructive" title={novel.onboarding_error_message}>
                                  {novel.onboarding_error_message}
                                </div>
                              ) : null}
                            </div>
                          ) : null}
                        </td>

                        <td className="px-4 py-3">
                          <LibraryRowActions
                            novel={novel}
                            missingSource={missingSource}
                            pending={
                              runLibraryAction.isPending ||
                              publishNovel.isPending ||
                              resumeOnboarding.isPending ||
                              cancelOnboarding.isPending
                            }
                            translationPending={runTranslationDialog.isPending}
                            onTranslate={(row) => runAction("translate", [row])}
                            onRecrawl={(row) => runAction("recrawl", [row])}
                            onDelete={(row) => runAction("delete", [row])}
                            onEditTaxonomy={openTaxonomyDialog}
                            onPublish={(row) => runPublishAction(row, true)}
                            onUnpublish={(row) => runPublishAction(row, false)}
                            onResume={(row) => resumeOnboarding.mutate(row)}
                            onCancel={(row) => cancelOnboarding.mutate(row)}
                            onRetranslateStale={(row) => setRetranslateStaleNovel(row)}
                          />
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <EmptyState title="No novels in the library yet." colSpan={9} />
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
        glossaryStatus={translationMetadata.data?.glossary_status}
        glossaryRevision={translationMetadata.data?.glossary_revision}
        glossaryPendingCount={translationMetadata.data?.glossary_pending_count}
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

      <TaxonomyDialog open={Boolean(taxonomyNovel)} novel={taxonomyNovel} onClose={closeTaxonomyDialog} />

      <RetranslateStaleDialog
        open={Boolean(retranslateStaleNovel)}
        novelId={retranslateStaleNovel?.novel_id ?? ""}
        title={retranslateStaleNovel?.title ?? ""}
        staleCount={0}
        legacyCount={0}
        pending={runRetranslateStale.isPending}
        onCancel={() => setRetranslateStaleNovel(null)}
        onConfirm={(options) => runRetranslateStale.mutate(options)}
      />
    </>
  );
}