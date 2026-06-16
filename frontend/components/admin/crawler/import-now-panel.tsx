"use client";

import { Upload } from "lucide-react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export type ImportNowPanelProps = {
  novelId: string;
  adapterKey: string;
  source: string;
  maxUnits: string;
  adapters: string[];
  pending: boolean;
  result?: { chapters: number; adapter_key: string } | null;
  error: unknown;
  onNovelIdChange: (value: string) => void;
  onAdapterKeyChange: (value: string) => void;
  onSourceChange: (value: string) => void;
  onMaxUnitsChange: (value: string) => void;
  onSubmit: () => void;
};

export function ImportNowPanel({
  novelId,
  adapterKey,
  source,
  maxUnits,
  adapters,
  pending,
  result,
  error,
  onNovelIdChange,
  onAdapterKeyChange,
  onSourceChange,
  onMaxUnitsChange,
  onSubmit
}: ImportNowPanelProps) {
  const adapterOptions = [adapterKey, ...adapters].filter((value, index, values) => value && values.indexOf(value) === index);

  return (
    <Panel className="flex h-full min-h-0 flex-col">
      <PanelHeader>
        <PanelTitle>Direct Import</PanelTitle>
      </PanelHeader>
      <PanelBody className="flex flex-1 flex-col justify-between gap-3">
        <div className="space-y-3">
          <Input value={novelId} onChange={(event) => onNovelIdChange(event.target.value)} placeholder="Novel ID" />
          <select
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            value={adapterKey}
            onChange={(event) => onAdapterKeyChange(event.target.value)}
          >
            {adapterOptions.map((adapter) => (
              <option key={adapter} value={adapter}>
                {adapter}
              </option>
            ))}
          </select>
          <Input value={source} onChange={(event) => onSourceChange(event.target.value)} placeholder="URL or local source path" />
          <Input value={maxUnits} onChange={(event) => onMaxUnitsChange(event.target.value)} placeholder="Max units" />
          <Button className="w-full" variant="outline" onClick={onSubmit} disabled={!novelId || !adapterKey || !source || pending}>
            <Upload className="h-4 w-4" />
            Import
          </Button>
          {result ? (
            <div className="rounded-md border bg-muted/40 p-3 text-sm">
              {result.chapters} unit(s) imported through {result.adapter_key}
            </div>
          ) : null}
          <ErrorBanner error={error} fallback="Import failed. Verify the adapter, source, and novel ID, then try again." />
        </div>
      </PanelBody>
    </Panel>
  );
}
