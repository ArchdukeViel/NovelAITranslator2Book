"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

export default function EditorPage() {
  const [novelId, setNovelId] = React.useState("");
  const chapters = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => api.chapters(novelId),
    enabled: Boolean(novelId)
  });

  return (
    <>
      <PageHeading
        title="Editor"
        description="Jump into translated chapters for review, version history, and manual polish workflow."
      />

      <Panel>
        <PanelHeader>
          <PanelTitle>Find Chapters</PanelTitle>
        </PanelHeader>
        <PanelBody className="space-y-4">
          <div className="flex max-w-xl gap-2">
            <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
            <Button variant="outline" onClick={() => void chapters.refetch()} disabled={!novelId}>
              Load
            </Button>
          </div>
          <div className="divide-y rounded-md border">
            {(chapters.data ?? []).map((chapter) => (
              <div key={chapter.id} className="flex items-center justify-between gap-3 px-4 py-3">
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{chapter.title || `Chapter ${chapter.id}`}</div>
                  <div className="text-xs text-muted-foreground">Chapter {chapter.id}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={chapter.translated ? "green" : "amber"}>
                    {chapter.translated ? "translated" : "pending"}
                  </Badge>
                  {chapter.translated ? (
                    <Link
                      className="inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium hover:bg-muted"
                      href={`/novel/${encodeURIComponent(novelId)}/chapter/${encodeURIComponent(chapter.id)}`}
                    >
                      Open
                    </Link>
                  ) : null}
                </div>
              </div>
            ))}
            {novelId && chapters.data?.length === 0 ? (
              <div className="px-4 py-6 text-sm text-muted-foreground">No chapters found.</div>
            ) : null}
          </div>
        </PanelBody>
      </Panel>
    </>
  );
}
