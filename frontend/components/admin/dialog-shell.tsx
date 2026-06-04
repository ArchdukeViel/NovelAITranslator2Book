"use client";

import * as React from "react";

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
  contentClassName
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
  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 px-4 py-6 backdrop-blur-sm">
      <div
        className={cn("flex max-h-full w-full max-w-xl flex-col overflow-hidden rounded-lg border bg-card shadow-2xl", className)}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="border-b p-4">
          <h2 className="text-base font-semibold">{title}</h2>
          {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        </div>
        <div className={cn("seamless-scrollbar min-h-0 flex-1 overflow-auto", contentClassName)}>{children}</div>
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
