"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function RequestsPage() {
  const queryClient = useQueryClient();
  const [title, setTitle] = React.useState("");
  const [sourceUrl, setSourceUrl] = React.useState("");
  const [sourceKey, setSourceKey] = React.useState("syosetu_ncode");
  const [notes, setNotes] = React.useState("");
  const requests = useQuery({ queryKey: ["requests"], queryFn: () => api.requests() });
  const createRequest = useMutation({
    mutationFn: api.createRequest,
    onSuccess: () => {
      setTitle("");
      setSourceUrl("");
      setNotes("");
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
    }
  });

  return (
    <>
      <PageHeading
        title="Requests"
        description="Capture reader-submitted novels, source candidates, votes, and admin review state."
      />

      <div className="grid gap-5 lg:grid-cols-[380px_1fr]">
        <Panel>
          <PanelHeader>
            <PanelTitle>New Request</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3">
            <Input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Novel title" />
            <Input value={sourceKey} onChange={(event) => setSourceKey(event.target.value)} placeholder="Source key" />
            <Input value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="Source URL" />
            <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Notes" />
            <Button
              onClick={() => createRequest.mutate({ title, source_key: sourceKey, source_url: sourceUrl, notes })}
              disabled={!title || createRequest.isPending}
            >
              <Plus className="h-4 w-4" />
              Add request
            </Button>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Request Queue</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Votes</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody>
                {(requests.data?.requests ?? []).map((request) => (
                  <tr key={request.id} className="border-b last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium">{request.title}</div>
                      <div className="text-xs text-muted-foreground">{request.source_candidates.length} source candidate(s)</div>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={request.status} />
                    </td>
                    <td className="px-4 py-3">{request.vote_count}</td>
                    <td className="px-4 py-3 text-muted-foreground">{formatDate(request.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
