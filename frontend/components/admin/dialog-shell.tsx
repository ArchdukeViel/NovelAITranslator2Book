"use client";

import * as React from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function DialogShell({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  className,
  contentClassName,
}: {
  open: boolean;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  onClose?: () => void;
  className?: string;
  contentClassName?: string;
}) {
  const dialogRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose?.();
      }
    };

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose?.();
        }
      }}
    >
      <div
        ref={dialogRef}
        className={cn(
          "flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border bg-card shadow-2xl",
          className,
        )}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="flex items-start justify-between border-b p-4">
          <div className="min-w-0 flex-1">
            <h2 className="text-base font-semibold">{title}</h2>
            {description ? (
              <p className="mt-1 text-sm text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>
          {onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="ml-4 rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-foreground focus:outline-none"
              aria-label="Close dialog"
            >
              <X className="h-4 w-4" />
            </button>
          ) : null}
        </div>
        <div
          className={cn(
            "seamless-scrollbar min-h-0 flex-1 overflow-auto",
            contentClassName,
          )}
        >
          {children}
        </div>
        {footer ? <div className="border-t p-4">{footer}</div> : null}
        {onClose && !footer ? (
          <div className="flex justify-end border-t p-4">
            <Button variant="outline" onClick={onClose}>
              Close
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
