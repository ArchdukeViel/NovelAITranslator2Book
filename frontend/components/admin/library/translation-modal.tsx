"use client";

import { Languages } from "lucide-react";

import { DialogShell } from "@/components/admin/dialog-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { ChapterSummary } from "@/lib/api";

export type TranslationModalProps = {
  open: boolean;
  novelId: string;
  title: string;
  author: string;
  synopsis: string;
  language: string;
  languages: readonly string[];
  chapters: ChapterSummary[];
  selectedChapterIds: Set<string>;
  selectedCount: number;
  allSelected: boolean;
  loading: boolean;
  loadError: unknown;
  runError: unknown;
  pending: boolean;
  onLanguageChange: (language: string) => void;
  onToggleAll: () => void;
  onToggleChapter: (chapterId: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
};

export function TranslationModal({
  open,
  novelId,
  title,
  author,
  synopsis,
  language,
  languages,
  chapters,
  selectedChapterIds,
  selectedCount,
  allSelected,
  loading,
  loadError,
  runError,
  pending,
  onLanguageChange,
  onToggleAll,
  onToggleChapter,
  onCancel,
  onConfirm
}: TranslationModalProps) {
  return (
    <DialogShell open={open} title="Translate Novel" description={novelId} className="max-w-5xl">
      <div className="seamless-scrollbar flex-1 overflow-auto">
        <div className="grid gap-4 border-b p-5 lg:grid-cols-[1fr_220px]">
          <div className="space-y-3">
            <div>
              <div className="text-xs uppercase text-muted-foreground">Translated Title</div>
              <div className="mt-1 text-base font-semibold">{title}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-muted-foreground">Translated Author</div>
              <div className="mt-1 text-sm">{author}</div>
            </div>
            <div>
              <div className="text-xs uppercase text-muted-foreground">Translated Synopsis</div>
              <p className="seamless-scrollbar mt-1 max-h-28 overflow-auto text-sm leading-6 text-muted-foreground">
                {synopsis}
              </p>
            </div>
          </div>
          <label className="block">
            <span className="text-xs uppercase text-muted-foreground">Language</span>
            <select
              className="mt-2 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              value={language}
              onChange={(event) => onLanguageChange(event.target.value)}
            >
              {languages.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
        </div>

        <ErrorBanner error={loadError} fallback="Failed to load translation form." />
        <ErrorBanner error={runError} fallback="Translation failed." />

        <div className="p-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold">Chapters</div>
              <div className="text-xs text-muted-foreground">
                {selectedCount} selected from {chapters.length} chapter(s)
              </div>
            </div>
          </div>

          <div className="seamless-scrollbar max-h-[360px] overflow-auto rounded-md border border-border">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-[1] border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <TableCheckbox checked={allSelected} onChange={onToggleAll} aria-label="Select all translation chapters" />
                  </th>
                  <th className="w-24 px-4 py-3">Chapter</th>
                  <th className="px-4 py-3">Title</th>
                  <th className="w-40 px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <LoadingRows colSpan={4} label="Loading chapters..." />
                ) : chapters.length ? (
                  chapters.map((chapter) => (
                    <tr className="border-b last:border-0" key={chapter.id}>
                      <td className="px-4 py-3">
                        <TableCheckbox
                          checked={selectedChapterIds.has(chapter.id)}
                          onChange={() => onToggleChapter(chapter.id)}
                          aria-label={`Select chapter ${chapter.id}`}
                        />
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">{chapter.id}</td>
                      <td className="px-4 py-3 font-medium">{chapter.title || `Chapter ${chapter.id}`}</td>
                      <td className="px-4 py-3">
                        {chapter.translated ? <Badge tone="green">Translated</Badge> : <Badge tone="amber">Untranslated</Badge>}
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyState title="No chapters found." colSpan={4} />
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="flex justify-end gap-3 border-t px-5 py-4">
        <Button variant="destructive" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
        <Button onClick={onConfirm} disabled={pending || loading || Boolean(loadError) || selectedCount === 0}>
          <Languages className="h-4 w-4" />
          {pending ? "Translating..." : "Translate"}
        </Button>
      </div>
    </DialogShell>
  );
}
