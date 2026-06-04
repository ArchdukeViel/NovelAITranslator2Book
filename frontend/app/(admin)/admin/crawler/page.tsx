"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { ActivityTable } from "@/components/admin/activity-table";
import { AddNovelForm } from "@/components/admin/crawler/add-novel-form";
import { AddNovelRunDialog, type AddNovelRunState } from "@/components/admin/crawler/add-novel-run-dialog";
import { ImportNowPanel } from "@/components/admin/crawler/import-now-panel";
import {
  PreliminaryCrawlResultModal,
  preliminaryChapterIds
} from "@/components/admin/crawler/preliminary-crawl-result-modal";
import { SourceHealthPanel } from "@/components/admin/crawler/source-health-panel";
import { DialogShell } from "@/components/admin/dialog-shell";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { ApiError, api, apiErrorKey, describeApiError } from "@/lib/api";
import type { ActivityRecord } from "@/lib/api";
import { cleanNovelInput, deriveNovelId, detectSourceOrigin } from "@/lib/novel-input";
import { useUiStore } from "@/lib/store";

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
        identifier: cleanNovelInput(novelInput),
        mode: "update"
      });
    },
    onSuccess: invalidateCrawler
  });

  const resultChapterIds = React.useMemo(
    () => preliminaryChapterIds(addNovel.data),
    [addNovel.data]
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
    const ids = preliminaryChapterIds(addNovel.data);
    setSelectedChapterIds(new Set(ids));
    setResultModalOpen(true);
  }, [addNovel.data, addNovel.isSuccess]);

  const canAddNovel = cleanNovelInput(novelInput).length > 0 && detectedSource !== "none" && !addNovel.isPending;

  const handleNovelInputChange = (value: string) => {
    setNovelInput(value);
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

  const resultTitle = addNovel.data?.translated_title || addNovel.data?.title || addNovel.data?.novel_id || "-";
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
          <AddNovelForm
            value={novelInput}
            detectedSource={detectedSource}
            canSubmit={canAddNovel}
            pending={addNovel.isPending}
            error={addNovel.error}
            onChange={handleNovelInputChange}
            onSubmit={handleStartPreliminaryCrawl}
          />

          <ImportNowPanel
            novelId={importNovelId}
            adapterKey={adapterKey}
            source={importSource}
            maxUnits={maxUnits}
            adapters={adapters.data ?? []}
            pending={importNow.isPending}
            result={importNow.data}
            error={importNow.error}
            onNovelIdChange={setImportNovelId}
            onAdapterKeyChange={setAdapterKey}
            onSourceChange={setImportSource}
            onMaxUnitsChange={setMaxUnits}
            onSubmit={() => {
              setDismissedErrorKey(null);
              importNow.mutate();
            }}
          />
        </div>

        <div className="grid gap-5 xl:grid-rows-[306px_306px]">
          <SourceHealthPanel
            sources={sourceHealth.data?.sources ?? []}
            loading={sourceHealth.isLoading}
            fetching={sourceHealth.isFetching}
            error={sourceHealth.error}
            onRefresh={() => void sourceHealth.refetch()}
          />

          <ActivityTable
            activity={activity.data?.activity ?? []}
            className="flex h-full min-h-0 flex-col"
            bodyClassName="min-h-0 flex-1"
            tableContainerClassName="seamless-scrollbar h-full overflow-auto"
          />
        </div>
      </div>

      <AddNovelRunDialog
        preliminaryPending={addNovel.isPending}
        runState={addNovelRunState}
        crawlProgress={crawlProgress}
        runProgress={addNovelRunProgress}
        detectedSource={detectedSource}
        runLabel={addNovel.data?.novel_id || derivedNovelId}
        resultTitle={resultTitle}
        addedChapterCount={addedChapterCount}
        selectedChapterCount={selectedChapterCount}
        onExitSuccess={handleExitAddSuccess}
      />

      <PreliminaryCrawlResultModal
        open={resultModalOpen}
        result={addNovel.data}
        selectedChapterIds={selectedChapterIds}
        selectedCount={selectedChapterCount}
        allSelected={allChaptersSelected}
        pending={queueSelectedChapters.isPending}
        error={queueSelectedChapters.error}
        onToggleAll={handleToggleAllChapters}
        onToggleChapter={handleToggleChapter}
        onConfirm={() => {
          setDismissedErrorKey(null);
          queueSelectedChapters.mutate();
        }}
        onCancel={handleCancelResult}
      />

      {showErrorDialog && activeErrorDescription && activeErrorKey ? (
        <DialogShell
          open
          title={activeErrorDescription.title}
          description={activeErrorDescription.explanation}
          className="z-[60] max-w-xl"
          footer={
            <div className="flex justify-end">
              <Button variant="outline" onClick={() => setDismissedErrorKey(activeErrorKey)}>
                Close
              </Button>
            </div>
          }
        >
          {activeErrorDescription.details !== undefined ? (
            <div>
              <div className="text-xs uppercase text-muted-foreground">Details</div>
              <pre className="seamless-scrollbar mt-2 max-h-56 overflow-auto rounded-md border bg-muted/35 p-3 text-xs leading-5 text-muted-foreground">
                {JSON.stringify(activeErrorDescription.details, null, 2)}
              </pre>
            </div>
          ) : null}
        </DialogShell>
      ) : null}
    </>
  );
}
