"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

export default function ChapterPage() {
  const params = useParams<{ slug: string; chapterId: string }>();
  const novelId = decodeURIComponent(params.slug);
  const chapterId = decodeURIComponent(params.chapterId);
  const chapter = useQuery({
    queryKey: ["reader-chapter", novelId, chapterId],
    queryFn: () => api.readerChapter(novelId, chapterId)
  });
  const data = chapter.data;

  return (
    <main className="mx-auto max-w-3xl px-5 py-8">
      <Link className="text-sm text-muted-foreground hover:text-foreground" href={`/novel/${encodeURIComponent(novelId)}`}>
        Back to chapters
      </Link>
      <header className="my-6">
        <div className="mb-3 flex flex-wrap gap-2">
          <Badge tone="blue">Chapter {chapterId}</Badge>
          {data?.version_kind ? <Badge tone="violet">{data.version_kind}</Badge> : null}
        </div>
        <h1 className="text-3xl font-semibold tracking-normal">{data?.title || `Chapter ${chapterId}`}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{data?.novel_title || novelId}</p>
      </header>

      <article className="whitespace-pre-wrap text-[17px] leading-8">
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
    </main>
  );
}
