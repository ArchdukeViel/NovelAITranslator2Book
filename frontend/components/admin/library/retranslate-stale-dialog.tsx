"use client";

import { RotateCw } from "lucide-react";
import * as React from "react";

import { DialogShell } from "@/components/admin/dialog-shell";
import { Button } from "@/components/ui/button";

export type RetranslateStaleDialogProps = {
  open: boolean;
  novelId: string;
  title: string;
  staleCount: number;
  legacyCount: number;
  pending: boolean;
  onCancel: () => void;
  onConfirm: (options: { includeLegacy: boolean; activate: boolean }) => void;
};

export function RetranslateStaleDialog({
  open,
  novelId,
  title,
  staleCount,
  legacyCount,
  pending,
  onCancel,
  onConfirm,
}: RetranslateStaleDialogProps) {
  const [includeLegacy, setIncludeLegacy] = React.useState(false);
  const [activate, setActivate] = React.useState(false);

  React.useEffect(() => {
    if (open) {
      setIncludeLegacy(false);
      setActivate(false);
    }
  }, [open]);

  const totalToRetranslate = staleCount + (includeLegacy ? legacyCount : 0);

  if (staleCount === 0 && legacyCount === 0) {
    return (
      <DialogShell open={open} onClose={onCancel} title="Retranslate Stale">
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            No stale or legacy translations found for <strong>{title}</strong>.
          </p>
          <div className="flex justify-end">
            <Button onClick={onCancel}>Close</Button>
          </div>
        </div>
      </DialogShell>
    );
  }

  return (
    <DialogShell open={open} onClose={onCancel} title="Retranslate Stale">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Retranslate chapters with stale glossary for <strong>{title}</strong>.
        </p>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span>Stale chapters (glossary changed)</span>
            <span className="font-mono">{staleCount}</span>
          </div>
          {legacyCount > 0 && (
            <label className="flex items-center justify-between text-sm cursor-pointer">
              <span className="flex items-center gap-2">
                Include legacy/unknown chapters
                <span className="text-muted-foreground">({legacyCount} without revision data)</span>
              </span>
              <input
                type="checkbox"
                checked={includeLegacy}
                onChange={(e) => setIncludeLegacy(e.target.checked)}
                className="rounded"
              />
            </label>
          )}
          <label className="flex items-center justify-between text-sm cursor-pointer">
            <span>Activate new translations immediately</span>
            <input
              type="checkbox"
              checked={activate}
              onChange={(e) => setActivate(e.target.checked)}
              className="rounded"
            />
          </label>
        </div>

        {totalToRetranslate > 0 && (
          <p className="text-xs text-muted-foreground">
            {totalToRetranslate} chapter{totalToRetranslate !== 1 ? "s" : ""} will be retranslated.
          </p>
        )}

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm({ includeLegacy, activate })}
            disabled={totalToRetranslate === 0 || pending}
          >
            <RotateCw className="h-4 w-4 mr-2" />
            {pending ? "Scheduling..." : `Retranslate ${totalToRetranslate} chapter${totalToRetranslate !== 1 ? "s" : ""}`}
          </Button>
        </div>
      </div>
    </DialogShell>
  );
}
