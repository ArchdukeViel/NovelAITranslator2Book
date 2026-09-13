import * as React from "react";

import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: string;
  helperText?: React.ReactNode;
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, id, error, helperText, "aria-describedby": describedBy, ...props }, ref) => {
    const fallbackId = React.useId();
    const fieldId = id ?? fallbackId;
    const errorId = `${fieldId}-error`;
    const helperId = `${fieldId}-helper`;
    const describedIds =
      [error ? errorId : null, helperText ? helperId : null, describedBy ?? null]
        .filter(Boolean)
        .join(" ") || undefined;

    const textarea = (
      <textarea
        ref={ref}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedIds}
        className={cn(
          "flex min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 text-base outline-none ring-offset-background placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
          error && "border-destructive-text focus-visible:ring-destructive-text",
          className
        )}
        {...props}
      />
    );

    if (!error && !helperText) return textarea;

    return (
      <div className="w-full">
        {textarea}
        {error ? (
          <p id={errorId} className="mt-1.5 text-xs font-medium text-destructive-text">
            {error}
          </p>
        ) : null}
        {helperText ? (
          <p id={helperId} className="mt-1.5 text-xs text-muted-foreground">
            {helperText}
          </p>
        ) : null}
      </div>
    );
  }
);

Textarea.displayName = "Textarea";
