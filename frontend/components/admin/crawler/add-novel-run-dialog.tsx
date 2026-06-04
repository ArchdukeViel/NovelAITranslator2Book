"use client";

import { DialogShell } from "@/components/admin/dialog-shell";
import { ProgressBar } from "@/components/admin/progress-bar";
import { Button } from "@/components/ui/button";
import { sourceLabel } from "@/lib/novel-input";

export type AddNovelRunState = "idle" | "running" | "success";

export type AddNovelRunDialogProps = {
  preliminaryPending: boolean;
  runState: AddNovelRunState;
  crawlProgress: number;
  runProgress: number;
  detectedSource: string;
  runLabel: string;
  resultTitle: string;
  addedChapterCount: number;
  selectedChapterCount: number;
  onExitSuccess: () => void;
};

export function AddNovelRunDialog({
  preliminaryPending,
  runState,
  crawlProgress,
  runProgress,
  detectedSource,
  runLabel,
  resultTitle,
  addedChapterCount,
  selectedChapterCount,
  onExitSuccess
}: AddNovelRunDialogProps) {
  if (preliminaryPending) {
    return (
      <DialogShell open title="Preliminary Crawl" description="Detecting metadata, translated title, author, and chapter list.">
        <ProgressBar value={crawlProgress} label={sourceLabel(detectedSource)} />
      </DialogShell>
    );
  }

  if (runState === "running") {
    return (
      <DialogShell
        open
        title="Adding Novel"
        description={`Scraping ${addedChapterCount || selectedChapterCount} selected chapter(s) and saving them into the library.`}
      >
        <ProgressBar value={runProgress} label={runLabel} />
      </DialogShell>
    );
  }

  if (runState === "success") {
    return (
      <DialogShell open title="Novel successfully added" description={`${resultTitle} has been saved into the library with ${addedChapterCount} selected chapter(s).`}>
        <div className="flex justify-end">
          <Button onClick={onExitSuccess}>Exit</Button>
        </div>
      </DialogShell>
    );
  }

  return null;
}
