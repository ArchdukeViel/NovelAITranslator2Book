"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import * as React from "react";

import { JobTable } from "@/components/admin/job-table";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

export default function CrawlerPage() {
  const queryClient = useQueryClient();
  const [novelId, setNovelId] = React.useState("");
  const [sourceKey, setSourceKey] = React.useState("syosetu_ncode");
  const [chapters, setChapters] = React.useState("all");
  const [sourceUrl, setSourceUrl] = React.useState("");
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const sourceHealth = useQuery({ queryKey: ["source-health"], queryFn: () => api.sourceHealth() });
  const createJob = useMutation({
    mutationFn: api.createCrawlJob,
    onSuccess: () => {
      setSourceUrl("");
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    }
  });

  return (
    <>
      <PageHeading
        title="Crawler"
        description="Queue metadata crawls, chapter crawls, recrawls, and watch source health across adapters."
      />

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>Create Crawl Job</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3">
            <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
            <Input value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="Source key" />
            <Input value={chapters} onChange={(event) => setChapters(event.target.value)} placeholder="Chapters, e.g. all or 1-5" />
            <Input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="Source URL" />
            <div className="grid grid-cols-3 gap-2">
              {["metadata", "chapters", "recrawl_chapter"].map((kind) => (
                <Button
                  key={kind}
                  variant={kind === "chapters" ? "default" : "outline"}
                  onClick={() =>
                    createJob.mutate({
                      novel_id: novelId,
                      source_key: sourceKey,
                      kind,
                      chapters,
                      source_url: sourceUrl || undefined
                    })
                  }
                  disabled={!novelId || !sourceKey || createJob.isPending}
                >
                  <Plus className="h-4 w-4" />
                  {kind.replace("_", " ")}
                </Button>
              ))}
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Source Health</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Success</th>
                  <th className="px-4 py-3">Failure</th>
                  <th className="px-4 py-3">Last Error</th>
                </tr>
              </thead>
              <tbody>
                {(sourceHealth.data?.sources ?? []).map((source) => (
                  <tr key={source.source_key} className="border-b last:border-0">
                    <td className="px-4 py-3 font-medium">{source.source_key}</td>
                    <td className="px-4 py-3">{source.success_count}</td>
                    <td className="px-4 py-3">{source.failure_count}</td>
                    <td className="px-4 py-3 text-muted-foreground">{source.last_error || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </PanelBody>
        </Panel>
      </div>

      <div className="mt-5">
        <JobTable jobs={(jobs.data?.jobs ?? []).filter((job) => job.type === "crawl")} />
      </div>
    </>
  );
}
