"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Play, Plus, RotateCw } from "lucide-react";
import * as React from "react";

import { JobTable } from "@/components/admin/job-table";
import { Metric } from "@/components/admin/metric";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";

const translationKinds = ["translate", "retranslate", "batch_retranslate"];
const exportFormats = ["epub", "html", "txt"];

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export default function TranslationPage() {
  const queryClient = useQueryClient();
  const [novelId, setNovelId] = React.useState("");
  const [sourceKey, setSourceKey] = React.useState("syosetu_ncode");
  const [chapters, setChapters] = React.useState("all");
  const [provider, setProvider] = React.useState("gemini");
  const [model, setModel] = React.useState("");
  const [kind, setKind] = React.useState("translate");
  const [force, setForce] = React.useState(false);
  const [exportFormat, setExportFormat] = React.useState("epub");

  const jobs = useQuery({ queryKey: ["jobs", "translation"], queryFn: () => api.jobs({ job_type: "translation", limit: 50 }) });
  const progress = useQuery({
    queryKey: ["progress", novelId],
    queryFn: () => api.progress(novelId),
    enabled: Boolean(novelId)
  });

  const invalidateTranslation = () => {
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["progress", novelId] });
    void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
  };

  const createJob = useMutation({ mutationFn: api.createTranslationJob, onSuccess: invalidateTranslation });
  const translateNow = useMutation({
    mutationFn: () =>
      api.translateNow(novelId, {
        source_key: sourceKey,
        chapters,
        provider_key: provider || undefined,
        provider_model: model || undefined,
        force
      }),
    onSuccess: invalidateTranslation
  });
  const exportNovel = useMutation({
    mutationFn: () => api.exportNovel(novelId, { format: exportFormat, chapters }),
    onSuccess: (blob) => downloadBlob(blob, `${novelId}.${exportFormat}`)
  });

  const progressData = progress.data;
  const total = progressData?.total ?? 0;
  const translated = progressData?.translated ?? 0;

  return (
    <>
      <PageHeading title="Translation" description="Translation queueing, direct runs, progress, and export downloads." />

      <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader>
              <PanelTitle>Translation Scope</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
              <Input value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="Source key" />
              <Input value={chapters} onChange={(event) => setChapters(event.target.value)} placeholder="Chapters" />
              <div className="grid gap-3 sm:grid-cols-2">
                <Input value={provider} onChange={(event) => setProvider(event.target.value)} placeholder="Provider" />
                <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Model" />
              </div>
              <select className="h-9 w-full rounded-md border bg-background px-3 text-sm" value={kind} onChange={(event) => setKind(event.target.value)}>
                {translationKinds.map((item) => (
                  <option key={item} value={item}>
                    {item.replace("_", " ")}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-2 text-sm">
                <input className="h-4 w-4" type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
                Force retranslate
              </label>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  onClick={() =>
                    createJob.mutate({
                      novel_id: novelId,
                      source_key: sourceKey,
                      kind,
                      chapters,
                      provider: provider || undefined,
                      model: model || undefined,
                      metadata: { force }
                    })
                  }
                  disabled={!novelId || createJob.isPending}
                >
                  <Plus className="h-4 w-4" />
                  Queue
                </Button>
                <Button variant="secondary" onClick={() => translateNow.mutate()} disabled={!novelId || !sourceKey || translateNow.isPending}>
                  <Play className="h-4 w-4" />
                  Run now
                </Button>
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Export</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={exportFormat}
                onChange={(event) => setExportFormat(event.target.value)}
              >
                {exportFormats.map((format) => (
                  <option key={format} value={format}>
                    {format}
                  </option>
                ))}
              </select>
              <Button className="w-full" variant="outline" onClick={() => exportNovel.mutate()} disabled={!novelId || exportNovel.isPending}>
                <Download className="h-4 w-4" />
                Download export
              </Button>
            </PanelBody>
          </Panel>
        </div>

        <div className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <Metric label="Total chapters" value={total} />
            <Metric label="Translated" value={translated} accent="violet" />
            <Metric label="Remaining" value={Math.max(0, total - translated)} accent="amber" />
          </div>
          <Panel>
            <PanelHeader className="flex flex-row items-center justify-between">
              <PanelTitle>Progress</PanelTitle>
              <Button variant="outline" size="sm" onClick={() => void progress.refetch()} disabled={!novelId}>
                <RotateCw className="h-4 w-4" />
                Refresh
              </Button>
            </PanelHeader>
            <PanelBody>
              <div className="h-3 overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full bg-primary transition-[width]"
                  style={{ width: `${total ? Math.round((translated / total) * 100) : 0}%` }}
                />
              </div>
            </PanelBody>
          </Panel>
          <JobTable jobs={jobs.data?.jobs ?? []} />
        </div>
      </div>
    </>
  );
}
