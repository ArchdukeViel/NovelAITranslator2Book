"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody } from "@/components/ui/panel";
import { api } from "@/lib/api";

export default function HomePage() {
  const novels = useQuery({ queryKey: ["novels"], queryFn: () => api.novels() });

  return (
    <main className="mx-auto max-w-6xl px-5 py-8">
      <header className="mb-6 flex flex-col gap-2">
        <h1 className="text-3xl font-semibold tracking-normal">Novel AI Reader</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Public reader for translated Japanese web novels managed by the crawler and translation pipeline.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {(novels.data ?? []).map((novel) => (
          <Link key={novel.novel_id} href={`/novel/${encodeURIComponent(novel.novel_id)}`}>
            <Panel className="h-full transition-colors hover:border-primary">
              <PanelBody>
                <div className="mb-3 flex items-center justify-between gap-2">
                  <Badge tone="blue">{novel.chapter_count} chapters</Badge>
                </div>
                <h2 className="text-base font-semibold">{novel.title || novel.novel_id}</h2>
                <p className="mt-1 text-sm text-muted-foreground">{novel.author || "Unknown author"}</p>
              </PanelBody>
            </Panel>
          </Link>
        ))}
      </div>
    </main>
  );
}
