"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, RotateCcw, Save } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { GlossaryQAPanel } from "@/components/admin/glossary-qa-panel";
import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import type { GlossaryQAIssue, GlossaryQAResult } from "@/lib/api-types";
import { formatDateTime } from "@/lib/format";
import { publicChapterHref } from "@/lib/public-routes";

export default function EditorPage() {
  const queryClient = useQueryClient();
  const [novelId, setNovelId] = React.useState("");
  const [chapterId, setChapterId] = React.useState("");
  const [editorName, setEditorName] = React.useState("admin");
  const [note, setNote] = React.useState("");
  const [draftText, setDraftText] = React.useState("");
  const [qaResult, setQaResult] = React.useState<GlossaryQAResult | null>(null);
  const [overrideReason, setOverrideReason] = React.useState("");
  const [showOverride, setShowOverride] = React.useState(false);

  const novels = useQuery({ queryKey: ["novels"], queryFn: () => api.novels() });
  const chapters = useQuery({
    queryKey: ["chapters", novelId],
    queryFn: () => api.chapters(novelId),
    enabled: Boolean(novelId)
  });
  const rawChapter = useQuery({
    queryKey: ["chapter", novelId, chapterId],
    queryFn: () => api.chapter(novelId, chapterId),
    enabled: Boolean(novelId && chapterId)
  });
  const translated = useQuery({
    queryKey: ["translated", novelId, chapterId],
    queryFn: () => api.translatedChapter(novelId, chapterId),
    enabled: Boolean(novelId && chapterId),
    retry: false
  });
  const versions = useQuery({
    queryKey: ["translation-versions", novelId, chapterId],
    queryFn: () => api.translationVersions(novelId, chapterId),
    enabled: Boolean(novelId && chapterId),
    retry: false
  });
  const history = useQuery({
    queryKey: ["translation-history", novelId, chapterId],
    queryFn: () => api.translationEditHistory(novelId, chapterId),
    enabled: Boolean(novelId && chapterId),
    retry: false
  });

  React.useEffect(() => {
    if (translated.data?.text) {
      setDraftText(translated.data.text);
      return;
    }
    if (rawChapter.data?.text) {
      setDraftText(rawChapter.data.text);
    }
  }, [chapterId, novelId, rawChapter.data?.text, translated.data?.text, translated.data?.version_id]);

  React.useEffect(() => {
    const first = chapters.data?.[0]?.id;
    if (first && !chapterId) {
      setChapterId(first);
    }
  }, [chapterId, chapters.data]);

  const invalidateEditor = () => {
    void queryClient.invalidateQueries({ queryKey: ["translated", novelId, chapterId] });
    void queryClient.invalidateQueries({ queryKey: ["translation-versions", novelId, chapterId] });
    void queryClient.invalidateQueries({ queryKey: ["translation-history", novelId, chapterId] });
    void queryClient.invalidateQueries({ queryKey: ["chapters", novelId] });
  };

  const saveEdit = useMutation({
    mutationFn: () =>
      api.updateTranslatedChapter(novelId, chapterId, {
        text: draftText,
        editor: editorName,
        note,
        lint: true,
        source_text: rawChapter.data?.text,
        glossary_override:
          qaResult?.status === "blocked" && overrideReason.trim()
            ? { reason: overrideReason, issue_ids: qaResult.issues.map((i) => i.issue_id) }
            : undefined,
      }),
    onSuccess: (data) => {
      if (data.glossary_qa) {
        setQaResult(data.glossary_qa);
      } else {
        setQaResult(null);
      }
      setShowOverride(false);
      setOverrideReason("");
      invalidateEditor();
    }
  });

  const lintEdit = useMutation({
    mutationFn: () =>
      api.lintTranslatedChapter(novelId, chapterId, {
        text: draftText,
        source_text: rawChapter.data?.text,
      }),
    onSuccess: (data) => {
      setQaResult(data.glossary_qa);
    }
  });

  const approveChange = useMutation({
    mutationFn: (issue: GlossaryQAIssue) =>
      api.approveTranslationChange(novelId, issue.entry_id!, {
        new_translation: issue.matched_variant || issue.approved_translation || "",
        rationale: `Approved from editor QA issue ${issue.issue_id}`,
      }),
    onSuccess: () => {
      void lintEdit.mutate();
    }
  });
  const rollback = useMutation({
    mutationFn: (versionId: string) => api.rollbackTranslatedChapter(novelId, chapterId, { version_id: versionId, editor: editorName, note }),
    onSuccess: invalidateEditor
  });

  const chapterRows = chapters.data ?? [];
  const versionRows = versions.data?.versions ?? [];
  const historyRows = history.data?.history ?? [];

  return (
    <>
      <PageHeading title="Editor" description="Chapter review, manual edits, version history, and rollback." />

      <div className="grid gap-5 xl:grid-cols-[360px_1fr]">
        <div className="space-y-5">
          <Panel>
            <PanelHeader>
              <PanelTitle>Selection</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={novelId}
                onChange={(event) => {
                  setNovelId(event.target.value);
                  setChapterId("");
                  setDraftText("");
                }}
              >
                <option value="">Select novel</option>
                {(novels.data ?? []).map((novel) => (
                  <option key={novel.novel_id} value={novel.novel_id}>
                    {novel.title || novel.novel_id}
                  </option>
                ))}
              </select>
              <Input
                value={novelId}
                onChange={(event) => {
                  setNovelId(event.target.value);
                  setChapterId("");
                  setDraftText("");
                }}
                placeholder="Novel ID"
              />
              <select
                className="h-9 w-full rounded-md border bg-background px-3 text-sm"
                value={chapterId}
                onChange={(event) => {
                  setChapterId(event.target.value);
                  setDraftText("");
                }}
                disabled={!novelId}
              >
                <option value="">Select chapter</option>
                {chapterRows.map((chapter) => (
                  <option key={chapter.id} value={chapter.id}>
                    {chapter.id} - {chapter.title || "Untitled"}
                  </option>
                ))}
              </select>
              <Input value={chapterId} onChange={(event) => setChapterId(event.target.value)} placeholder="Chapter ID" />
              <Input value={editorName} onChange={(event) => setEditorName(event.target.value)} placeholder="Editor" />
              <Input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Version note" />
              {novelId && chapterId ? (
                <Link
                  className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border text-sm font-medium hover:bg-muted"
                  href={publicChapterHref(novelId, chapterId)}
                >
                  <ExternalLink className="h-4 w-4" />
                  Reader
                </Link>
              ) : null}
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle>Versions</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-2">
              {versionRows.length ? (
                versionRows.map((version) => {
                  const versionId = String(version.version_id || version.id || "");
                  return (
                    <div key={versionId} className="rounded-md border p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium">{versionId}</div>
                        <Badge tone={version.active ? "green" : "neutral"}>{version.active ? "active" : String(version.version_kind || version.kind || "stored")}</Badge>
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatDateTime(version.created_at || version.translated_at)}</div>
                      {version.provider_key || version.provider_model ? (
                        <div className="mt-1 text-xs text-muted-foreground">
                          {version.provider_key}/{version.provider_model}
                        </div>
                      ) : null}
                      <Button className="mt-3 w-full" size="sm" variant="outline" onClick={() => rollback.mutate(versionId)} disabled={!versionId || version.active || rollback.isPending}>
                        <RotateCcw className="h-4 w-4" />
                        Rollback
                      </Button>
                    </div>
                  );
                })
              ) : (
                <div className="text-sm text-muted-foreground">No versions loaded.</div>
              )}
            </PanelBody>
          </Panel>
        </div>

        <div className="space-y-5">
          {translated.data ? (
            <Panel>
              <PanelHeader>
                <PanelTitle>Scheduler Decision</PanelTitle>
              </PanelHeader>
              <PanelBody className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Provider / Model</span>
                  <span className="font-medium">
                    {translated.data.provider_key || "-"} / {translated.data.provider_model || "-"}
                  </span>
                </div>
                {translated.data.confidence_details?.scheduler_policy ? (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Scheduler Policy</span>
                    <Badge tone="blue">{String(translated.data.confidence_details.scheduler_policy)}</Badge>
                  </div>
                ) : null}
                {translated.data.version_kind ? (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Version Kind</span>
                    <span className="font-medium">{translated.data.version_kind}</span>
                  </div>
                ) : null}
              </PanelBody>
            </Panel>
          ) : null}

          <Panel>
            <PanelHeader className="flex flex-row items-center justify-between">
              <PanelTitle>Translated Text</PanelTitle>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => lintEdit.mutate()}
                  disabled={!novelId || !chapterId || !draftText.trim() || lintEdit.isPending}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Check glossary
               </Button>
                <Button onClick={() => saveEdit.mutate()} disabled={!novelId || !chapterId || !draftText.trim() || saveEdit.isPending}>
                  <Save className="h-4 w-4" />
                  Save
               </Button>
             </div>
           </PanelHeader>
            <PanelBody className="space-y-3">
              <Textarea
                className="min-h-[520px] font-serif text-base leading-7"
                value={draftText}
                onChange={(event) => setDraftText(event.target.value)}
                placeholder="Translated chapter text"
              />
              <ErrorBanner error={saveEdit.error} fallback="Failed to save edit." className="rounded-md border border-destructive/40 px-3" />
           </PanelBody>
         </Panel>

          {qaResult ? (
            <Panel>
              <PanelHeader>
                <PanelTitle>Glossary QA</PanelTitle>
             </PanelHeader>
              <PanelBody>
                <GlossaryQAPanel
                  result={qaResult}
                  canApprove
                  canOverride
                  onApproveChange={(issue) => approveChange.mutate(issue)}
                  onOverride={() => setShowOverride(true)}
                />
                {showOverride && qaResult.status === "blocked" ? (
                  <div className="mt-3 space-y-2 rounded-md border border-red-300 bg-red-50 p-3 text-xs">
                    <div className="font-medium text-red-800">Override blocked save</div>
                    <textarea
                      className="w-full rounded-md border bg-background p-2 text-sm"
                      placeholder="Reason for override (required)"
                      value={overrideReason}
                      onChange={(event) => setOverrideReason(event.target.value)}
                      rows={2}
                    />
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => saveEdit.mutate()}
                        disabled={!overrideReason.trim() || saveEdit.isPending}
                      >
                        Submit override
                     </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          setShowOverride(false);
                          setOverrideReason("");
                        }}
                      >
                        Cancel
                     </Button>
                   </div>
                 </div>
                ) : null}
             </PanelBody>
           </Panel>
          ) : null}

          <div className="grid gap-5 lg:grid-cols-2">
            <Panel>
              <PanelHeader>
                <PanelTitle>Source Text</PanelTitle>
              </PanelHeader>
              <PanelBody>
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                  {rawChapter.data?.text || "-"}
                </pre>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <PanelTitle>Edit History</PanelTitle>
              </PanelHeader>
              <PanelBody className="space-y-2">
                {historyRows.length ? (
                  historyRows.map((entry) => (
                    <div key={String(entry.id || `${entry.version_id}-${entry.created_at}`)} className="rounded-md border p-3 text-sm">
                      <div className="font-medium">
                        {entry.action || "edit"}
                        {" -> "}
                        {entry.version_id || "-"}
                      </div>
                      <div className="mt-1 text-xs text-muted-foreground">{formatDateTime(entry.created_at)}</div>
                      {entry.note ? <div className="mt-2 text-muted-foreground">{entry.note}</div> : null}
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-muted-foreground">No edit history loaded.</div>
                )}
              </PanelBody>
            </Panel>
          </div>
        </div>
      </div>
    </>
  );
}
