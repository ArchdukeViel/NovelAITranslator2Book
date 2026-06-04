"use client";

import { Plus } from "lucide-react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { sourceLabel } from "@/lib/novel-input";

export type AddNovelFormProps = {
  value: string;
  detectedSource: string;
  canSubmit: boolean;
  pending: boolean;
  error: unknown;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function AddNovelForm({ value, detectedSource, canSubmit, pending, error, onChange, onSubmit }: AddNovelFormProps) {
  return (
    <Panel className="flex h-full min-h-0 flex-col">
      <PanelHeader>
        <PanelTitle>Add New Novel</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-1 flex-col justify-between gap-4">
        <div className="space-y-4">
          <Input value={value} onChange={(event) => onChange(event.target.value)} placeholder="Novel link or novel ID" />

          <div className="rounded-md border bg-muted/25 px-3 py-2 text-sm">
            <span className="text-muted-foreground">Source:</span>
            <span className="ml-2 font-medium">{sourceLabel(detectedSource)}</span>
          </div>

          <ErrorBanner error={error} fallback="Failed to add novel." />
        </div>

        <Button className="w-full" onClick={onSubmit} disabled={!canSubmit || pending}>
          <Plus className="h-4 w-4" />
          Add novel
        </Button>
      </PanelBody>
    </Panel>
  );
}
