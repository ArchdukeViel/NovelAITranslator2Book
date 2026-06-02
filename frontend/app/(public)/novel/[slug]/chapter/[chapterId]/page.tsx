"use client";

import { useQuery } from "@tanstack/react-query";
import { Minus, Moon, Plus, Sun, Type } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useUiStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const widthClass = {
  compact: "max-w-2xl",
  comfortable: "max-w-3xl",
  wide: "max-w-5xl"
};

export default function ChapterPage() {
  const params = useParams<{ slug: string; chapterId: string }>();
  const novelId = decodeURIComponent(params.slug);
  const chapterId = decodeURIComponent(params.chapterId);
  const {
    readerFontSize,
    readerTheme,
    readerWidth,
    setReaderFontSize,
    setReaderTheme,
    setReaderWidth
  } = useUiStore();
  const chapter = useQuery({
    queryKey: ["reader-chapter", novelId, chapterId],
    queryFn: () => api.readerChapter(novelId, chapterId)
  });
  const data = chapter.data;
  const dark = readerTheme === "dark";
  const sepia = readerTheme === "sepia";

  return (
    <main
      className={cn(
        "min-h-screen transition-colors",
        dark && "bg-[#101418] text-slate-100",
        sepia && "bg-[#f4ecd8] text-[#251b12]",
        !dark && !sepia && "bg-background text-foreground"
      )}
    >
      <div className={cn("mx-auto px-5 py-8", widthClass[readerWidth])}>
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link className="text-sm opacity-75 hover:opacity-100" href={`/novel/${encodeURIComponent(novelId)}`}>
            Back to chapters
          </Link>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="outline" size="icon" onClick={() => setReaderTheme(readerTheme === "dark" ? "light" : "dark")} aria-label="Toggle reader theme">
              {dark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
            </Button>
            <Button variant="outline" size="icon" onClick={() => setReaderFontSize(readerFontSize - 1)} aria-label="Decrease reader font size">
              <Minus className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="icon" onClick={() => setReaderFontSize(readerFontSize + 1)} aria-label="Increase reader font size">
              <Plus className="h-4 w-4" />
            </Button>
            <select
              className="h-9 rounded-md border bg-background px-3 text-sm text-foreground"
              value={readerWidth}
              onChange={(event) => setReaderWidth(event.target.value as typeof readerWidth)}
              aria-label="Reader width"
            >
              <option value="compact">compact</option>
              <option value="comfortable">comfortable</option>
              <option value="wide">wide</option>
            </select>
            <Button variant="outline" size="icon" onClick={() => setReaderTheme("sepia")} aria-label="Sepia reader theme">
              <Type className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <header className="my-6">
          <div className="mb-3 flex flex-wrap gap-2">
            <Badge tone="blue">Chapter {chapterId}</Badge>
            {data?.version_kind ? <Badge tone="violet">{data.version_kind}</Badge> : null}
          </div>
          <h1 className="text-3xl font-semibold tracking-normal">{data?.title || `Chapter ${chapterId}`}</h1>
          <p className="mt-2 text-sm opacity-70">{data?.novel_title || novelId}</p>
        </header>

        <article
          className="whitespace-pre-wrap font-serif leading-[1.9]"
          style={{ fontSize: `${readerFontSize}px` }}
        >
          {data?.text || "Loading..."}
        </article>

        <nav className="mt-10 flex justify-between gap-3 border-t pt-5">
          {data?.previous_chapter_id ? (
            <Link
              className="inline-flex h-9 items-center rounded-md border px-3 text-sm hover:bg-muted"
              href={`/novel/${encodeURIComponent(novelId)}/chapter/${encodeURIComponent(data.previous_chapter_id)}`}
            >
              Previous
            </Link>
          ) : (
            <span />
          )}
          {data?.next_chapter_id ? (
            <Link
              className="inline-flex h-9 items-center rounded-md border px-3 text-sm hover:bg-muted"
              href={`/novel/${encodeURIComponent(novelId)}/chapter/${encodeURIComponent(data.next_chapter_id)}`}
            >
              Next
            </Link>
          ) : null}
        </nav>
      </div>
    </main>
  );
}
