"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RotateCw, Upload } from "lucide-react";
import * as React from "react";

import { ActivityTable } from "@/components/admin/activity-table";
import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { ApiError, api, apiErrorInlineMessage, apiErrorKey, describeApiError } from "@/lib/api";
import type { ActivityRecord, PreliminaryCrawlResult } from "@/lib/api";
import { useUiStore } from "@/lib/store";
import { formatDate } from "@/lib/utils";

const SOURCE_LABELS: Record<string, string> = {
  syosetu_ncode: "Syosetu",
  novel18_syosetu: "Novel18",
  kakuyomu: "Kakuyomu",
  generic: "Generic web"
};

function cleanInput(value: string) {
  return value.trim();
}

function isHttpUrl(value: string) {
  return /^https?:\/\//i.test(value.trim());
}

function parseUrl(value: string) {
  if (!isHttpUrl(value)) {
    return null;
  }
  try {
    return new URL(value.trim());
  } catch {
    return null;
  }
}

function detectSourceOrigin(value: string) {
  const input = cleanInput(value);
  if (!input) {
    return "none";
  }

  const url = parseUrl(input);
  if (url) {
    const host = url.hostname.toLowerCase();
    if (["novel18.syosetu.com", "noc.syosetu.com", "mnlt.syosetu.com", "mid.syosetu.com"].includes(host)) {
      return "novel18_syosetu";
    }
    if (host === "ncode.syosetu.com") {
      return "syosetu_ncode";
    }
    if (host === "kakuyomu.jp" && url.pathname.includes("/works/")) {
      return "kakuyomu";
    }
    return "generic";
  }

  if (/^n\d{4}[a-z]{2}$/i.test(input)) {
    return "novel18_syosetu";
  }
  if (/^\d{12,}$/.test(input)) {
    return "kakuyomu";
  }
  return "generic";
}

function sanitizeNovelId(value: string) {
  return value
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/[^a-z0-9._-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120) || "novel";
}

function deriveNovelId(value: string, sourceKey: string) {
  const input = cleanInput(value);
  const url = parseUrl(input);

  if (url) {
    if (sourceKey.includes("syosetu")) {
      const match = url.pathname.match(/\/(n\d{4}[a-z]{2})(?:\/|$)/i);
      if (match) {
        return match[1].toLowerCase();
      }
    }
    if (sourceKey === "kakuyomu") {
      const match = url.pathname.match(/\/works\/([^/?#]+)/i);
      if (match) {
        return match[1];
      }
    }
    return sanitizeNovelId(`${url.hostname}${url.pathname}`);
  }

  if (/^n\d{4}[a-z]{2}$/i.test(input)) {
    return input.toLowerCase();
  }
  return sanitizeNovelId(input);
}

function sourceLabel(sourceKey: string, input = "") {
  if (sourceKey === "none") {
    return "None";
  }
  if (sourceKey === "novel18_syosetu") {
    return "Novel18 -> Syosetu fallback (auto)";
  }
  if (sourceKey === "syosetu_ncode") {
    return "Syosetu -> Novel18 fallback (auto)";
  }
  return SOURCE_LABELS[sourceKey] ? `${SOURCE_LABELS[sourceKey]} (${sourceKey})` : sourceKey;
}

function chapterRowId(row: PreliminaryCrawlResult["chapter_list"][number], index: number) {
  const rawId = row.id ?? row.num ?? index + 1;
  return String(rawId);
}

function chapterRowNumber(row: PreliminaryCrawlResult["chapter_list"][number], index: number) {
  if (typeof row.num === "number") {
    return row.num;
  }
  const id = row.id;
  if (typeof id === "number") {
    return id;
  }
  if (typeof id === "string" && /^\d+$/.test(id)) {
    return Number(id);
  }
  return index + 1;
}

function chapterRowTitle(row: PreliminaryCrawlResult["chapter_list"][number], index: number) {
  return row.translated_title || row.title || `Chapter ${chapterRowNumber(row, index)}`;
}

function originalChapterTitle(row: PreliminaryCrawlResult["chapter_list"][number]) {
  if (!row.translated_title || !row.title || row.translated_title === row.title) {
    return null;
  }
  return row.title;
}

function chapterRowDate(row: PreliminaryCrawlResult["chapter_list"][number], fallback?: string | null) {
  return row.date_added || row.updated_at || row.published_at || fallback || null;
}

function formatSourceDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  if (/^\d{4}\/\d{1,2}\/\d{1,2}/.test(value)) {
    return value;
  }
  return formatDate(value);
}

function chapterRowGroup(row: PreliminaryCrawlResult["chapter_list"][number]) {
  const value = row.volume ?? row.part ?? row.arc ?? row.section ?? row.group;
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

type ChapterSortKey = "chapter" | "date";
type ChapterSortDirection = "asc" | "desc";
type AddNovelRunState = "idle" | "running" | "success";

const ADD_NOVEL_JOB_POLL_INTERVAL_MS = 2000;
const ADD_NOVEL_JOB_POLL_ATTEMPTS = 180;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function serializableError(error: unknown) {
  if (error instanceof ApiError) {
    return {
      status: error.status,
      code: error.code,
      message: error.message,
      explanation: error.explanation,
      details: error.details
    };
  }
  if (error instanceof Error) {
    return { name: error.name, message: error.message };
  }
  return error;
}

function scrapeActivityFailure(activity: ActivityRecord, originalError: unknown) {
  return new ApiError({
    status: 424,
    code: "SCRAPE_ACTIVITY_FAILED",
    message: activity.error || `Scrape activity ended with status ${activity.status}.`,
    explanation: "The chapter scrape activity did not complete successfully. Open Activity Log details for the stored payload.",
    details: {
      activity,
      original_error: serializableError(originalError)
    }
  });
}

function scrapeActivityStillRunning(activity: ActivityRecord, originalError: unknown) {
  return new ApiError({
    status: 504,
    code: "SCRAPE_ACTIVITY_STILL_RUNNING",
    message: "The scrape request timed out while the activity was still running.",
    explanation:
      "The backend may still be scraping chapters. Check Activity Log for this novel; the activity can finish after the browser request times out.",
    details: {
      activity,
      original_error: serializableError(originalError)
    }
  });
}

async function recoverScrapeActivityAfterRunError(activityId: string, originalError: unknown) {
  let lastActivity: ActivityRecord | null = null;
  let sawRunning = false;

  for (let attempt = 0; attempt < ADD_NOVEL_JOB_POLL_ATTEMPTS; attempt += 1) {
    lastActivity = await api.activityItem(activityId);
    if (lastActivity.status === "completed") {
      return lastActivity;
    }
    if (lastActivity.status === "failed" || lastActivity.status === "cancelled") {
      throw scrapeActivityFailure(lastActivity, originalError);
    }
    if (lastActivity.status === "running") {
      sawRunning = true;
    }
    if (lastActivity.status === "pending" && !sawRunning && attempt >= 5) {
      break;
    }
    await sleep(ADD_NOVEL_JOB_POLL_INTERVAL_MS);
  }

  if (lastActivity?.status === "running") {
    throw scrapeActivityStillRunning(lastActivity, originalError);
  }
  throw originalError;
}

export default function CrawlerPage() {
  const queryClient = useQueryClient();
  const [novelInput, setNovelInput] = React.useState("");
  const [crawlProgress, setCrawlProgress] = React.useState(0);
  const [resultModalOpen, setResultModalOpen] = React.useState(false);
  const [selectedChapterIds, setSelectedChapterIds] = React.useState<Set<string>>(new Set());
  const [chapterSortKey, setChapterSortKey] = React.useState<ChapterSortKey>("chapter");
  const [chapterSortDirection, setChapterSortDirection] = React.useState<ChapterSortDirection>("asc");
  const [adapterKey, setAdapterKey] = React.useState("web");
  const [importNovelId, setImportNovelId] = React.useState("");
  const [importSource, setImportSource] = React.useState("");
  const [maxUnits, setMaxUnits] = React.useState("");
  const [dismissedErrorKey, setDismissedErrorKey] = React.useState<string | null>(null);
  const [addNovelRunState, setAddNovelRunState] = React.useState<AddNovelRunState>("idle");
  const [addNovelRunProgress, setAddNovelRunProgress] = React.useState(0);
  const [addedChapterCount, setAddedChapterCount] = React.useState(0);
  const activeGeminiToken = useUiStore((state) => state.apiTokens.find((entry) => entry.status === "Active")?.token);

  const activity = useQuery({ queryKey: ["activity", "crawl"], queryFn: () => api.activity({ activity_type: "crawl", limit: 50 }) });
  const sourceHealth = useQuery({ queryKey: ["source-health"], queryFn: () => api.sourceHealth() });
  const adapters = useQuery({ queryKey: ["input-adapters"], queryFn: () => api.inputAdapters() });

  const detectedSource = React.useMemo(() => detectSourceOrigin(novelInput), [novelInput]);
  const derivedNovelId = React.useMemo(
    () => deriveNovelId(novelInput, detectedSource),
    [detectedSource, novelInput]
  );

  const invalidateCrawler = () => {
    void queryClient.invalidateQueries({ queryKey: ["activity"] });
    void queryClient.invalidateQueries({ queryKey: ["source-health"] });
    void queryClient.invalidateQueries({ queryKey: ["novels"] });
  };

  const addNovel = useMutation({
    mutationFn: async () => {
      if (activeGeminiToken?.trim()) {
        await api.setProviderApiKey({
          provider: "gemini",
          api_key: activeGeminiToken,
          apply_globally: true,
          validate_connection: false
        });
      }
      return api.preliminaryCrawl(derivedNovelId, {
        source_key: detectedSource === "none" ? undefined : detectedSource,
        identifier: cleanInput(novelInput),
        mode: "update"
      });
    },
    onSuccess: invalidateCrawler
  });

  const resultChapters = React.useMemo(() => addNovel.data?.chapter_list ?? [], [addNovel.data]);
  const sortedResultChapters = React.useMemo(() => {
    return resultChapters
      .map((chapter, index) => ({ chapter, index }))
      .sort((left, right) => {
        const direction = chapterSortDirection === "asc" ? 1 : -1;
        if (chapterSortKey === "date") {
          const leftDate = Date.parse(chapterRowDate(left.chapter) || "");
          const rightDate = Date.parse(chapterRowDate(right.chapter) || "");
          const leftValue = Number.isNaN(leftDate) ? 0 : leftDate;
          const rightValue = Number.isNaN(rightDate) ? 0 : rightDate;
          if (leftValue !== rightValue) {
            return (leftValue - rightValue) * direction;
          }
        }
        return (chapterRowNumber(left.chapter, left.index) - chapterRowNumber(right.chapter, right.index)) * direction;
      });
  }, [chapterSortDirection, chapterSortKey, resultChapters]);
  const resultChapterIds = React.useMemo(
    () => resultChapters.map((chapter, index) => chapterRowId(chapter, index)),
    [resultChapters]
  );
  const selectedChapterSelection = React.useMemo(() => {
    if (resultChapterIds.length > 0 && resultChapterIds.every((id) => selectedChapterIds.has(id))) {
      return "all";
    }
    return resultChapterIds.filter((id) => selectedChapterIds.has(id)).join(";");
  }, [resultChapterIds, selectedChapterIds]);
  const allChaptersSelected = resultChapterIds.length > 0 && resultChapterIds.every((id) => selectedChapterIds.has(id));
  const selectedChapterCount = resultChapterIds.filter((id) => selectedChapterIds.has(id)).length;

  const queueSelectedChapters = useMutation({
    mutationFn: async () => {
      if (!addNovel.data) {
        throw new Error("Preliminary crawl result is missing.");
      }
      const activity = await api.createCrawlActivity({
        novel_id: addNovel.data.novel_id,
        source_key: addNovel.data.source_key,
        kind: "chapters",
        chapters: selectedChapterSelection,
        source_url: addNovel.data.source_url || undefined,
        metadata: {
          activity_subtype: "scraping",
          activity_phase: "add_novel_chapter_scrape",
          from_preliminary_crawl: true,
          preliminary_activity_log_job_id: addNovel.data.activity_log_job_id || null,
          selected_chapter_count: selectedChapterCount,
          selected_chapters: selectedChapterSelection,
          source_url: addNovel.data.source_url || null,
          title: addNovel.data.title || null,
          translated_title: addNovel.data.translated_title || null
        }
      });
      try {
        return await api.runActivity(activity.id);
      } catch (error) {
        return recoverScrapeActivityAfterRunError(activity.id, error);
      }
    },
    onMutate: () => {
      setDismissedErrorKey(null);
      setResultModalOpen(false);
      setAddedChapterCount(selectedChapterCount);
      setAddNovelRunState("running");
      setAddNovelRunProgress(8);
    },
    onSuccess: () => {
      invalidateCrawler();
      setSelectedChapterIds(new Set());
      setAddNovelRunProgress(100);
      setAddNovelRunState("success");
    },
    onError: () => {
      setAddNovelRunState("idle");
      setAddNovelRunProgress(0);
      if (addNovel.data) {
        setResultModalOpen(true);
      }
    }
  });

  const importNow = useMutation({
    mutationFn: () =>
      api.importNow(importNovelId, {
        adapter_key: adapterKey,
        source: importSource,
        max_units: maxUnits ? Number(maxUnits) : null
      }),
    onSuccess: invalidateCrawler
  });

  React.useEffect(() => {
    if (!addNovel.isPending) {
      return;
    }

    setCrawlProgress(8);
    const timer = window.setInterval(() => {
      setCrawlProgress((current) => {
        if (current >= 92) {
          return current;
        }
        return Math.min(92, current + Math.max(3, Math.round((92 - current) / 8)));
      });
    }, 350);

    return () => window.clearInterval(timer);
  }, [addNovel.isPending]);

  React.useEffect(() => {
    if (!queueSelectedChapters.isPending || addNovelRunState !== "running") {
      return;
    }

    setAddNovelRunProgress((current) => Math.max(current, 8));
    const timer = window.setInterval(() => {
      setAddNovelRunProgress((current) => {
        if (current >= 95) {
          return current;
        }
        return Math.min(95, current + Math.max(2, Math.round((95 - current) / 10)));
      });
    }, 450);

    return () => window.clearInterval(timer);
  }, [addNovelRunState, queueSelectedChapters.isPending]);

  React.useEffect(() => {
    if (addNovel.isSuccess) {
      setCrawlProgress(0);
    }
    if (addNovel.isError) {
      setCrawlProgress(0);
    }
  }, [addNovel.isError, addNovel.isSuccess]);

  React.useEffect(() => {
    if (!addNovel.isSuccess || !addNovel.data) {
      return;
    }
    const ids = (addNovel.data.chapter_list ?? []).map((chapter, index) => chapterRowId(chapter, index));
    setSelectedChapterIds(new Set(ids));
    setResultModalOpen(true);
  }, [addNovel.data, addNovel.isSuccess]);

  const canAddNovel = cleanInput(novelInput).length > 0 && detectedSource !== "none" && !addNovel.isPending;

  const handleNovelInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setNovelInput(event.target.value);
    if (!addNovel.isPending) {
      addNovel.reset();
      queueSelectedChapters.reset();
      setResultModalOpen(false);
      setSelectedChapterIds(new Set());
      setCrawlProgress(0);
      setAddNovelRunState("idle");
      setAddNovelRunProgress(0);
      setAddedChapterCount(0);
      setDismissedErrorKey(null);
    }
  };

  const handleStartPreliminaryCrawl = () => {
    setResultModalOpen(false);
    setSelectedChapterIds(new Set());
    queueSelectedChapters.reset();
    setAddNovelRunState("idle");
    setAddNovelRunProgress(0);
    setAddedChapterCount(0);
    setDismissedErrorKey(null);
    addNovel.mutate();
  };

  const handleToggleAllChapters = () => {
    setSelectedChapterIds(allChaptersSelected ? new Set() : new Set(resultChapterIds));
  };

  const handleToggleChapter = (chapterId: string) => {
    setSelectedChapterIds((current) => {
      const next = new Set(current);
      if (next.has(chapterId)) {
        next.delete(chapterId);
      } else {
        next.add(chapterId);
      }
      return next;
    });
  };

  const handleCancelResult = () => {
    setResultModalOpen(false);
    setSelectedChapterIds(new Set());
    queueSelectedChapters.reset();
    addNovel.reset();
    setAddNovelRunState("idle");
    setAddNovelRunProgress(0);
    setAddedChapterCount(0);
    setDismissedErrorKey(null);
  };

  const handleExitAddSuccess = () => {
    setAddNovelRunState("idle");
    setAddNovelRunProgress(0);
    setSelectedChapterIds(new Set());
    setNovelInput("");
    setAddedChapterCount(0);
    queueSelectedChapters.reset();
    addNovel.reset();
  };

  const handleSortChapters = (key: ChapterSortKey) => {
    if (chapterSortKey === key) {
      setChapterSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      return;
    }
    setChapterSortKey(key);
    setChapterSortDirection("asc");
  };

  const sortLabel = (key: ChapterSortKey) => {
    if (chapterSortKey !== key) {
      return "";
    }
    return chapterSortDirection === "asc" ? " \u25B2" : " \u25BC";
  };

  const resultTitle = addNovel.data?.translated_title || addNovel.data?.title || addNovel.data?.novel_id || "-";
  const resultOriginalTitle =
    addNovel.data?.translated_title && addNovel.data?.title && addNovel.data.translated_title !== addNovel.data.title
      ? addNovel.data.title
      : null;
  const resultAuthor = addNovel.data?.translated_author || addNovel.data?.author || "-";
  const resultOriginalAuthor =
    addNovel.data?.translated_author && addNovel.data?.author && addNovel.data.translated_author !== addNovel.data.author
      ? addNovel.data.author
      : null;
  const resultSynopsis = addNovel.data?.translated_synopsis || addNovel.data?.synopsis || "";
  const activeError = queueSelectedChapters.error || addNovel.error || importNow.error;
  const activeErrorKey = activeError ? apiErrorKey(activeError) : null;
  const activeErrorDescription = activeError ? describeApiError(activeError) : null;
  const showErrorDialog = Boolean(activeError && activeErrorKey && activeErrorKey !== dismissedErrorKey);

  return (
    <>
      <PageHeading
        title="Crawler"
        description="Add new Japanese novels by link or source ID, detect the source, and discover chapter counts before deeper crawling."
      />

      <div className="grid gap-5 xl:grid-cols-[420px_1fr] xl:items-stretch">
        <div className="grid gap-5 xl:grid-rows-[306px_306px]">
          <Panel className="flex h-full min-h-0 flex-col">
            <PanelHeader>
              <PanelTitle>Add New Novel</PanelTitle>
            </PanelHeader>
            <PanelBody className="flex flex-1 flex-col justify-between gap-4">
              <div className="space-y-4">
              <Input
                value={novelInput}
                onChange={handleNovelInputChange}
                placeholder="Novel link or novel ID"
              />

              <div className="rounded-md border bg-muted/25 px-3 py-2 text-sm">
                <span className="text-muted-foreground">Source:</span>
                <span className="ml-2 font-medium">{sourceLabel(detectedSource, novelInput)}</span>
              </div>

              {addNovel.error ? (
                <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                  {apiErrorInlineMessage(addNovel.error)}
                </div>
              ) : null}
              </div>

              <Button
                className="w-full"
                onClick={handleStartPreliminaryCrawl}
                disabled={!canAddNovel}
              >
                <Plus className="h-4 w-4" />
                Add novel
              </Button>
            </PanelBody>
          </Panel>

          <Panel className="flex h-full min-h-0 flex-col">
            <PanelHeader>
              <PanelTitle>Direct Import</PanelTitle>
            </PanelHeader>
            <PanelBody className="flex flex-1 flex-col justify-between gap-3">
              <div className="space-y-3">
              <Input value={importNovelId} onChange={(event) => setImportNovelId(event.target.value)} placeholder="Novel ID" />
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={adapterKey}
                onChange={(event) => setAdapterKey(event.target.value)}
              >
                {[adapterKey, ...(adapters.data ?? [])]
                  .filter((value, index, values) => value && values.indexOf(value) === index)
                  .map((adapter) => (
                    <option key={adapter} value={adapter}>
                      {adapter}
                    </option>
                  ))}
              </select>
              <Input value={importSource} onChange={(event) => setImportSource(event.target.value)} placeholder="URL or local source path" />
              <Input value={maxUnits} onChange={(event) => setMaxUnits(event.target.value)} placeholder="Max units" />
              <Button
                className="w-full"
                variant="outline"
                onClick={() => {
                  setDismissedErrorKey(null);
                  importNow.mutate();
                }}
                disabled={!importNovelId || !adapterKey || !importSource || importNow.isPending}
              >
                <Upload className="h-4 w-4" />
                Import
              </Button>
              {importNow.data ? (
                <div className="rounded-md border bg-muted/40 p-3 text-sm">
                  {importNow.data.chapters} unit(s) imported through {importNow.data.adapter_key}
                </div>
              ) : null}
              </div>
            </PanelBody>
          </Panel>
        </div>

        <div className="grid gap-5 xl:grid-rows-[306px_306px]">
          <Panel className="flex h-full min-h-0 flex-col">
            <PanelHeader className="flex flex-row items-center justify-between">
              <PanelTitle>Source Health</PanelTitle>
              <Button variant="outline" size="sm" onClick={() => void sourceHealth.refetch()}>
                <RotateCw className="h-4 w-4" />
                Refresh
              </Button>
            </PanelHeader>
            <PanelBody className="min-h-0 flex-1 p-0">
              <div className="seamless-scrollbar h-full overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">Source</th>
                      <th className="px-4 py-3">Health</th>
                      <th className="px-4 py-3">Success</th>
                      <th className="px-4 py-3">Failure</th>
                      <th className="px-4 py-3">Last Seen</th>
                      <th className="px-4 py-3">Last Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sourceHealth.data?.sources ?? []).map((source) => (
                      <tr key={source.source_key} className="border-b last:border-0">
                        <td className="px-4 py-3 font-medium">{source.source_key}</td>
                        <td className="px-4 py-3">
                          <StatusBadge status={source.failure_count > 0 ? "failed" : "ok"} />
                        </td>
                        <td className="px-4 py-3">{source.success_count}</td>
                        <td className="px-4 py-3">{source.failure_count}</td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDate(source.last_success_at || source.last_failure_at)}
                        </td>
                        <td className="max-w-[280px] truncate px-4 py-3 text-muted-foreground">{source.last_error || "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </PanelBody>
          </Panel>

          <ActivityTable
            activity={activity.data?.activity ?? []}
            className="flex h-full min-h-0 flex-col"
            bodyClassName="min-h-0 flex-1"
            tableContainerClassName="seamless-scrollbar h-full overflow-auto"
          />
        </div>
      </div>

      {addNovel.isPending ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-lg border bg-card p-5 shadow-2xl">
            <div className="mb-4">
              <h2 className="text-base font-semibold">Preliminary Crawl</h2>
              <p className="mt-1 text-sm text-muted-foreground">Detecting metadata, translated title, author, and chapter list.</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{sourceLabel(detectedSource, novelInput)}</span>
                <span>{crawlProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${crawlProgress}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {resultModalOpen && addNovel.data ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
          <div className="flex max-h-full w-full max-w-5xl flex-col overflow-hidden rounded-lg border bg-card shadow-2xl">
            <div className="border-b p-4">
              <h2 className="text-base font-semibold">Confirm Novel Chapters</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Select the chapters to queue for crawling before adding this novel to the workspace.
              </p>
            </div>

            <div className="border-b bg-muted/25 p-4">
              <div className="rounded-md border bg-background p-3">
                <div className="grid gap-4 md:grid-cols-[200px_1fr]">
                  <div>
                    <div className="text-xs uppercase text-muted-foreground">Chapters detected</div>
                    <div className="mt-1 text-2xl font-semibold">{addNovel.data.chapters}</div>
                    <div className="mt-1 text-xs text-muted-foreground">{addNovel.data.source_key}</div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs uppercase text-muted-foreground">Title</div>
                      <div className="mt-1 text-sm font-semibold">{resultTitle}</div>
                      {resultOriginalTitle ? <div className="mt-1 text-xs text-muted-foreground">{resultOriginalTitle}</div> : null}
                    </div>
                    <div>
                      <div className="text-xs uppercase text-muted-foreground">Author</div>
                      <div className="mt-1 text-sm font-semibold">{resultAuthor}</div>
                      {resultOriginalAuthor ? <div className="mt-1 text-xs text-muted-foreground">{resultOriginalAuthor}</div> : null}
                    </div>
                    <div className="md:col-span-2">
                      <div className="text-xs uppercase text-muted-foreground">Synopsis</div>
                      <div className="seamless-scrollbar mt-1 max-h-24 overflow-auto pr-2 text-sm leading-6 text-muted-foreground">
                        {resultSynopsis || "-"}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              {addNovel.data.metadata_translation_status === "failed" ? (
                <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
                  Metadata translation failed: {addNovel.data.metadata_translation_error || "check the Gemini key in Settings."}
                </div>
              ) : null}
            </div>

            <div className="seamless-scrollbar min-h-0 flex-1 overflow-auto">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 border-b bg-card text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="w-12 px-4 py-3">
                      <input
                        className="table-checkbox"
                        type="checkbox"
                        checked={allChaptersSelected}
                        onChange={handleToggleAllChapters}
                        aria-label="Select all chapters"
                      />
                    </th>
                    <th className="w-24 px-4 py-3">
                      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => handleSortChapters("chapter")}>
                        Chapter{sortLabel("chapter")}
                      </button>
                    </th>
                    <th className="w-36 px-4 py-3">Part / Volume</th>
                    <th className="px-4 py-3">Title</th>
                    <th className="w-40 px-4 py-3">
                      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => handleSortChapters("date")}>
                        Date added{sortLabel("date")}
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {resultChapters.length === 0 ? (
                    <tr>
                      <td className="px-4 py-8 text-muted-foreground" colSpan={5}>
                        No chapters were detected.
                      </td>
                    </tr>
                  ) : (
                    sortedResultChapters.map(({ chapter, index }) => {
                      const rowId = chapterRowId(chapter, index);
                      const originalTitle = originalChapterTitle(chapter);
                      const dateAdded = chapterRowDate(chapter);
                      return (
                        <tr className="border-b last:border-0" key={rowId}>
                          <td className="px-4 py-3">
                            <input
                              className="table-checkbox"
                              type="checkbox"
                              checked={selectedChapterIds.has(rowId)}
                              onChange={() => handleToggleChapter(rowId)}
                              aria-label={`Select chapter ${rowId}`}
                            />
                          </td>
                          <td className="px-4 py-3 font-medium">{chapterRowNumber(chapter, index)}</td>
                          <td className="px-4 py-3 text-muted-foreground">{chapterRowGroup(chapter)}</td>
                          <td className="px-4 py-3">
                            <div className="font-medium">{chapterRowTitle(chapter, index)}</div>
                            {originalTitle ? <div className="mt-1 text-xs text-muted-foreground">{originalTitle}</div> : null}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">{formatSourceDate(dateAdded)}</td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {queueSelectedChapters.error ? (
              <div className="border-t px-4 py-3 text-sm text-destructive">{apiErrorInlineMessage(queueSelectedChapters.error)}</div>
            ) : null}

            <div className="flex items-center justify-end gap-3 border-t p-4">
              <Button
                className="min-w-32"
                onClick={() => {
                  setDismissedErrorKey(null);
                  queueSelectedChapters.mutate();
                }}
                disabled={selectedChapterCount === 0 || queueSelectedChapters.isPending}
              >
                Add novel
              </Button>
              <Button className="min-w-28" variant="destructive" onClick={handleCancelResult} disabled={queueSelectedChapters.isPending}>
                Cancel
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {addNovelRunState === "running" ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-lg border bg-card p-5 shadow-2xl">
            <div className="mb-4">
              <h2 className="text-base font-semibold">Adding Novel</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Scraping {addedChapterCount || selectedChapterCount} selected chapter(s) and saving them into the library.
              </p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>{addNovel.data?.novel_id || derivedNovelId}</span>
                <span>{addNovelRunProgress}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary transition-[width] duration-300"
                  style={{ width: `${addNovelRunProgress}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {addNovelRunState === "success" ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-md overflow-hidden rounded-lg border bg-card shadow-2xl">
            <div className="border-b p-5">
              <div className="text-xs uppercase text-muted-foreground">Completed</div>
              <h2 className="mt-1 text-base font-semibold">Novel successfully added</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                {resultTitle} has been saved into the library with {addedChapterCount} selected chapter(s).
              </p>
            </div>
            <div className="flex justify-end p-4">
              <Button onClick={handleExitAddSuccess}>Exit</Button>
            </div>
          </div>
        </div>
      ) : null}

      {showErrorDialog && activeErrorDescription && activeErrorKey ? (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 px-4 backdrop-blur-sm">
          <div className="w-full max-w-xl overflow-hidden rounded-lg border bg-card shadow-2xl">
            <div className="border-b p-4">
              <div className="text-xs uppercase text-muted-foreground">Error</div>
              <h2 className="mt-1 text-base font-semibold text-destructive">{activeErrorDescription.title}</h2>
            </div>
            <div className="space-y-4 p-4">
              <div>
                <div className="text-xs uppercase text-muted-foreground">Explanation</div>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">{activeErrorDescription.explanation}</p>
              </div>
              {activeErrorDescription.details !== undefined ? (
                <div>
                  <div className="text-xs uppercase text-muted-foreground">Details</div>
                  <pre className="seamless-scrollbar mt-2 max-h-56 overflow-auto rounded-md border bg-muted/35 p-3 text-xs leading-5 text-muted-foreground">
                    {JSON.stringify(activeErrorDescription.details, null, 2)}
                  </pre>
                </div>
              ) : null}
            </div>
            <div className="flex justify-end border-t p-4">
              <Button variant="outline" onClick={() => setDismissedErrorKey(activeErrorKey)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
