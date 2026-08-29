"use client";

import { Upload } from "lucide-react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export type ImportNowPanelProps = {
  novelId: string;
  sourceUrl: string;
  maxUnits: string;
  pending: boolean;
  result?: { chapters: number; document_type?: string | null } | null;
  error: unknown;
  onNovelIdChange: (value: string) => void;
  onSourceUrlChange: (value: string) => void;
  onMaxUnitsChange: (value: string) => void;
  onSubmit: () => void;
};

export function ImportNowPanel({
  novelId,
  sourceUrl,
  maxUnits,
  pending,
  result,
  error,
  onNovelIdChange,
  onSourceUrlChange,
  onMaxUnitsChange,
  onSubmit
}: ImportNowPanelProps) {
  return (
    <Panel className="flex h-full min-h-0 flex-col">
      <PanelHeader>
        <PanelTitle>Import from URL</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-1 flex-col justify-between gap-3">
        <div className="space-y-3">
          <Input value={novelId} onChange={(event) => onNovelIdChange(event.target.value)} placeholder="Novel ID" />
          <Input value={sourceUrl} onChange={(event) => onSourceUrlChange(event.target.value)} placeholder="Novel source URL" />
          <Input value={maxUnits} onChange={(event) => onMaxUnitsChange(event.target.value)} placeholder="Max units" />
          <Button className="w-full" variant="outline" onClick={onSubmit} disabled={!novelId || !sourceUrl || pending}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
          {result ? (
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              {result.chapters} unit(s) imported from the source URL
            </div>
          ) : null}
          <ErrorBanner error={error} fallback="Import failed. Verify the source URL and novel ID, then try again." />
        </div>
      </PanelBody>
    </Panel>
  );
}
