"use client";

import * as React from "react";

import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/admin/dialog-shell";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  onConfirm,
  onCancel,
  auditNotice,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  auditNotice?: string;
}) {
  return (
    <DialogShell
      open={open}
      title={title}
      description={description}
      onClose={onCancel}
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel} disabled={pending}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} disabled={pending}>
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="p-4 text-sm text-muted-foreground">
        {description || "Confirm this action."}
        {auditNotice && (
          <div className="mt-3 flex items-start gap-2 rounded-md bg-amber-50 p-3 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <p className="text-xs">{auditNotice}</p>
          </div>
        )}
      </div>
    </DialogShell>
  );
}
