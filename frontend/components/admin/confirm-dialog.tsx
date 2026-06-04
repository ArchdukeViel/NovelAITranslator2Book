"use client";

import * as React from "react";

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
  onCancel
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
      <div className="p-4 text-sm text-muted-foreground">{description || "Confirm this action."}</div>
    </DialogShell>
  );
}
