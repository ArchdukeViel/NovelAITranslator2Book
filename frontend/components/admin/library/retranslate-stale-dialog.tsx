"use client";

import { RotateCw } from "lucide-react";
import { DialogShell } from "@/components/admin/dialog-shell";
import { Button } from "@/components/ui/button";

export type RetranslateStaleDialogProps = {
  open: boolean;
  title: string;
  pending: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function RetranslateStaleDialog({
  open,
  title,
  pending,
  onCancel,
  onConfirm,
}: RetranslateStaleDialogProps) {
  return (
    <DialogShell open={open} onClose={onCancel} title="Retranslate Stale">
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          Find and retranslate every chapter whose translation uses an older
          glossary revision for <strong>{title}</strong>.
        </p>
        <p className="text-xs text-muted-foreground">
          Current translations remain active until each replacement passes the
          normal confidence policy.
        </p>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button onClick={onConfirm} disabled={pending}>
            <RotateCw className="h-4 w-4 mr-2" />
            {pending ? "Scheduling..." : "Retranslate stale chapters"}
          </Button>
        </div>
      </div>
    </DialogShell>
  );
}
