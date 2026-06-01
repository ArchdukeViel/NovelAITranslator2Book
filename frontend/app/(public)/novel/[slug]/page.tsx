"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

export default function NovelPage() {
  const params = useParams<{ slug: string }>();
  const novelId = decodeURIComponent(params.slug);
  const novel = useQuery({ queryKey: ["reader-novel", novelId], queryFn: () => api.readerNovel(novelId) });

  const data = novel.data;

  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <Link className="text-sm text-muted-foreground hover:text-foreground" href="/">
        Back to library
      </Link>
      <header className="my-6">
        <h1 className="text-3xl font-semibold tracking-normal">{data?.title || novelId}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{data?.author || "Unknown author"}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Badge tone="blue">{data?.translated_count ?? 0} translated</Badge>
          <Badge tone="neutral">{data?.chapter_count ?? 0} listed</Badge>
          {data?.source ? <Badge tone="violet">{data.source}</Badge> : null}
        </div>
      </header>

      <Panel>
        <PanelHeader>
          <PanelTitle>Chapters</PanelTitle>
        </PanelHeader>
        <PanelBody className="p-0">
          <div className="divide-y">
            {(data?.chapters ?? []).map((chapter) => (
              <div className="flex items-center justify-between gap-3 px-4 py-3" key={chapter.id}>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{chapter.title || `Chapter ${chapter.id}`}</div>
                  <div className="text-xs text-muted-foreground">Chapter {chapter.id}</div>
                </div>
                {chapter.translated ? (
                  <Link
                    className="inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium hover:bg-muted"
                    href={`/novel/${encodeURIComponent(novelId)}/chapter/${encodeURIComponent(chapter.id)}`}
                  >
                    Read
                  </Link>
                ) : (
                  <Badge tone="amber">pending</Badge>
                )}
              </div>
            ))}
          </div>
        </PanelBody>
      </Panel>
    </main>
  );
}
