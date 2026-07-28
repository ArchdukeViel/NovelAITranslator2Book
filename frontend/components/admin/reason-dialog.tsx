"use client";

import { AlertTriangle } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import { DialogShell } from "@/components/admin/dialog-shell";
import { ErrorBanner } from "@/components/admin/error-banner";

export function ReasonDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  pending = false,
  reasonValue = "",
  onReasonChange,
  error,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  pending?: boolean;
  reasonValue?: string;
  onReasonChange?: (value: string) => void;
  error?: unknown;
  onConfirm: (reason: string) => void;
  onCancel: () => void;
}) {
  const [internalReason, setInternalReason] = React.useState("");
  const reason = onReasonChange !== undefined ? reasonValue : internalReason;
  const setReason = onReasonChange ?? setInternalReason;
  const trimmedReason = reason.trim();
  const reasonValid = trimmedReason.length >= 1 && trimmedReason.length <= 500;
  const reasonHint =
    reason.length > 500
      ? `Reason too long (${reason.length}/500)`
      : reason.length > 0 && trimmedReason.length === 0
        ? "Reason must not be only whitespace"
        : reason.length > 0
          ? `${reason.length}/500`
          : null;

  React.useEffect(() => {
    if (open) {
      setInternalReason("");
    }
  }, [open]);

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
          <Button
            variant={destructive ? "destructive" : "default"}
            onClick={() => onConfirm(trimmedReason)}
            disabled={pending || !reasonValid}
          >
            {pending ? `${confirmLabel}...` : confirmLabel}
          </Button>
        </div>
      }
    >
      <div className="space-y-3 p-4">
        <div>
          <label htmlFor="reason-input" className="text-sm font-medium">
            Reason <span className="text-destructive">*</span>
          </label>
          <textarea
            id="reason-input"
            className="mt-1 block w-full rounded-md border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
            rows={3}
            maxLength={500}
            placeholder="Explain why this action is being taken (1-500 characters)"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            disabled={pending}
            aria-describedby={reasonHint ? "reason-hint" : undefined}
          />
          {reasonHint && (
            <p
              id="reason-hint"
              className={`mt-1 text-xs ${
                reason.length > 500 ? "text-destructive" : "text-muted-foreground"
              }`}
            >
              {reasonHint}
            </p>
          )}
        </div>

        <div className="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <p className="text-xs">
            This action will be recorded in the audit log along with the reason. It cannot be undone automatically.
          </p>
        </div>

        {error ? <ErrorBanner error={error} fallback="Action failed." /> : null}
      </div>
    </DialogShell>
  );
}
