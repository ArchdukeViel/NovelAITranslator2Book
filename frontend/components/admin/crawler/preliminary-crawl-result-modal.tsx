"use client";

import { ErrorBanner } from "@/components/admin/error-banner";
import {
  ChapterSelectionTable,
  chapterRowId
} from "@/components/admin/crawler/chapter-selection-table";
import { Button } from "@/components/ui/button";
import type { PreliminaryCrawlResult } from "@/lib/api";

export type PreliminaryCrawlResultModalProps = {
  open: boolean;
  result: PreliminaryCrawlResult | null | undefined;
  selectedChapterIds: Set<string>;
  selectedCount: number;
  allSelected: boolean;
  pending: boolean;
  error: unknown;
  onToggleAll: () => void;
  onToggleChapter: (chapterId: string) => void;
  onConfirm: () => void;
  onCancel: () => void;
};

export function preliminaryChapterIds(result: PreliminaryCrawlResult | null | undefined) {
  return (result?.chapter_list ?? []).map((chapter, index) => chapterRowId(chapter, index));
}

export function PreliminaryCrawlResultModal({
  open,
  result,
  selectedChapterIds,
  selectedCount,
  allSelected,
  pending,
  error,
  onToggleAll,
  onToggleChapter,
  onConfirm,
  onCancel
}: PreliminaryCrawlResultModalProps) {
  if (!open || !result) {
    return null;
  }

  const resultTitle = result.translated_title || result.title || result.novel_id || "-";
  const resultOriginalTitle =
    result.translated_title && result.title && result.translated_title !== result.title ? result.title : null;
  const resultAuthor = result.translated_author || result.author || "-";
  const resultOriginalAuthor =
    result.translated_author && result.author && result.translated_author !== result.author ? result.author : null;
  const resultSynopsis = result.translated_synopsis || result.synopsis || "";

  return (
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
                <div className="mt-1 text-2xl font-semibold">{result.chapters}</div>
                <div className="mt-1 text-xs text-muted-foreground">{result.source_key}</div>
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
          {result.metadata_translation_status === "failed" ? (
            <div className="mt-3 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
              Metadata translation failed: {result.metadata_translation_error || "check the Gemini key in Settings."}
            </div>
          ) : null}
        </div>

        <div className="seamless-scrollbar min-h-0 flex-1 overflow-auto">
          <ChapterSelectionTable
            chapters={result.chapter_list ?? []}
            selectedChapterIds={selectedChapterIds}
            allSelected={allSelected}
            onToggleAll={onToggleAll}
            onToggleChapter={onToggleChapter}
          />
        </div>

        <ErrorBanner error={error} fallback="Failed to queue selected chapters." />

        {Boolean(error) && (
          <div className="border-t bg-muted/25 p-4 text-sm text-muted-foreground">
            An error occurred while queueing the chapters. Please cancel and restart the process to try again.
          </div>
        )}

        <div className="flex items-center justify-end gap-3 border-t p-4">
          <Button className="min-w-32" onClick={onConfirm} disabled={selectedCount === 0 || pending || !!error}>
            Add novel
          </Button>
          <Button className="min-w-28" variant="destructive" onClick={onCancel} disabled={pending}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
