"use client";

import * as React from "react";

import { EmptyState } from "@/components/admin/empty-state";
import { SortableHeader } from "@/components/admin/sortable-header";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";
import type { PreliminaryCrawlResult } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export type PreliminaryChapter = PreliminaryCrawlResult["chapter_list"][number];
export type IndexedPreliminaryChapter = { chapter: PreliminaryChapter; index: number };
type ChapterSortKey = "chapter" | "date";

export function chapterRowId(row: PreliminaryChapter, index: number) {
  const rawId = row.id ?? row.num ?? index + 1;
  return String(rawId);
}

export function chapterRowNumber(row: PreliminaryChapter, index: number) {
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

export function chapterRowTitle(row: PreliminaryChapter, index: number) {
  return row.translated_title || row.title || `Chapter ${chapterRowNumber(row, index)}`;
}

export function originalChapterTitle(row: PreliminaryChapter) {
  if (!row.translated_title || !row.title || row.translated_title === row.title) {
    return null;
  }
  return row.title;
}

export function chapterRowDate(row: PreliminaryChapter, fallback?: string | null) {
  return row.date_added || row.updated_at || row.published_at || fallback || null;
}

export function formatSourceDate(value: string | null | undefined) {
  if (!value) {
    return "-";
  }
  if (/^\d{4}\/\d{1,2}\/\d{1,2}/.test(value)) {
    return value;
  }
  return formatDateTime(value);
}

export function chapterRowGroup(row: PreliminaryChapter) {
  const value = row.volume ?? row.part ?? row.arc ?? row.section ?? row.group;
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return String(value);
}

function chapterSortValue(row: IndexedPreliminaryChapter, key: ChapterSortKey) {
  if (key === "date") {
    const parsed = Date.parse(chapterRowDate(row.chapter) || "");
    return Number.isNaN(parsed) ? 0 : parsed;
  }
  return chapterRowNumber(row.chapter, row.index);
}

export type ChapterSelectionTableProps = {
  chapters: PreliminaryChapter[];
  selectedChapterIds: Set<string>;
  allSelected: boolean;
  onToggleAll: () => void;
  onToggleChapter: (chapterId: string) => void;
};

export function ChapterSelectionTable({
  chapters,
  selectedChapterIds,
  allSelected,
  onToggleAll,
  onToggleChapter
}: ChapterSelectionTableProps) {
  const { sortKey, sortDirection, handleSort } = useSortableTable<ChapterSortKey>("chapter", "asc");
  const sortedChapters = React.useMemo(() => {
    return chapters
      .map((chapter, index) => ({ chapter, index }))
      .sort((left, right) => compareSortableValues(chapterSortValue(left, sortKey), chapterSortValue(right, sortKey), sortDirection));
  }, [chapters, sortDirection, sortKey]);

  return (
    <table className="w-full text-left text-sm">
      <thead className="sticky top-0 border-b bg-card text-xs uppercase text-muted-foreground">
        <tr>
          <th className="w-12 px-4 py-3">
            <TableCheckbox checked={allSelected} onChange={onToggleAll} aria-label="Select all chapters" />
          </th>
          <SortableHeader label="Chapter" sortKey="chapter" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-24" />
          <th className="w-36 px-4 py-3">Part / Volume</th>
          <th className="px-4 py-3">Title</th>
          <SortableHeader label="Date added" sortKey="date" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-40" />
        </tr>
      </thead>
      <tbody>
        {chapters.length === 0 ? (
          <EmptyState title="No chapters were detected." colSpan={5} />
        ) : (
          sortedChapters.map(({ chapter, index }) => {
            const rowId = chapterRowId(chapter, index);
            const originalTitle = originalChapterTitle(chapter);
            const dateAdded = chapterRowDate(chapter);
            return (
              <tr className="border-b last:border-0" key={rowId}>
                <td className="px-4 py-3">
                  <TableCheckbox
                    checked={selectedChapterIds.has(rowId)}
                    onChange={() => onToggleChapter(rowId)}
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
  );
}
