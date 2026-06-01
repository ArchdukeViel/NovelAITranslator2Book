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

export default function TranslationPage() {
  const queryClient = useQueryClient();
  const [novelId, setNovelId] = React.useState("");
  const [sourceKey, setSourceKey] = React.useState("syosetu_ncode");
  const [chapters, setChapters] = React.useState("all");
  const [provider, setProvider] = React.useState("openai");
  const [model, setModel] = React.useState("");
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.jobs() });
  const createJob = useMutation({
    mutationFn: api.createTranslationJob,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });

  return (
    <>
      <PageHeading
        title="Translation"
        description="Queue translation and retranslation runs without blocking the browser or API process."
      />

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>Create Translation Job</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3">
            <Input value={novelId} onChange={(event) => setNovelId(event.target.value)} placeholder="Novel ID" />
            <Input value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="Source key" />
            <Input value={chapters} onChange={(event) => setChapters(event.target.value)} placeholder="Chapters" />
            <Input value={provider} onChange={(event) => setProvider(event.target.value)} placeholder="Provider" />
            <Input value={model} onChange={(event) => setModel(event.target.value)} placeholder="Model" />
            <div className="grid grid-cols-2 gap-2">
              {["translate", "batch_retranslate"].map((kind) => (
                <Button
                  key={kind}
                  variant={kind === "translate" ? "default" : "secondary"}
                  onClick={() =>
                    createJob.mutate({
                      novel_id: novelId,
                      source_key: sourceKey,
                      kind,
                      chapters,
                      provider,
                      model: model || undefined
                    })
                  }
                  disabled={!novelId || createJob.isPending}
                >
                  <Plus className="h-4 w-4" />
                  {kind.replace("_", " ")}
                </Button>
              ))}
            </div>
          </PanelBody>
        </Panel>

        <JobTable jobs={(jobs.data?.jobs ?? []).filter((job) => job.type === "translation")} />
      </div>
    </>
  );
}
