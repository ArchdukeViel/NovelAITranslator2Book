"use client";

import { AlertTriangle, CheckCircle2, ImageIcon, X } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  readFileHeader,
  validateImageMagicBytes,
  type SupportedImageFormat,
} from "@/lib/cover-magic-bytes";

const ACCEPT = "image/png,image/jpeg,image/webp";
const FORMAT_LABEL: Record<SupportedImageFormat, string> = {
  png: "PNG",
  jpeg: "JPEG",
  webp: "WEBP",
};

type Status =
  | { kind: "idle" }
  | { kind: "validating"; file: File }
  | { kind: "rejected"; reason: string; fileName: string }
  | { kind: "accepted"; file: File; format: SupportedImageFormat; previewUrl: string };

export interface CoverUploaderProps {
  /** Called once per file that passes the magic-byte check. */
  onValidatedFile?: (file: File, format: SupportedImageFormat) => void;
  /** Maximum header bytes to read. Defaults to 16 (covers WEBP marker at offset 8). */
  headerLength?: number;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

/**
 * CoverUploader — client-side cover image uploader with binary-header
 * magic-byte validation (Finding 9.3, REQ-15, AC-15, SEC-2).
 *
 * Boundary contract: a file is NEVER sent to the network until it has
 * passed validateImageMagicBytes. The component is transport-agnostic;
 * callers wire `onValidatedFile` to whatever upload flow they need.
 */
export function CoverUploader({
  onValidatedFile,
  headerLength = 16,
}: CoverUploaderProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function handleFile(file: File | null | undefined) {
    if (!file) return;

    setStatus({ kind: "validating", file });
    try {
      const header = await readFileHeader(file, headerLength);
      const result = validateImageMagicBytes(header);
      if (!result.ok) {
        setStatus({ kind: "rejected", reason: result.reason, fileName: file.name });
        return;
      }
      const previewUrl = URL.createObjectURL(file);
      setStatus({ kind: "accepted", file, format: result.kind, previewUrl });
      onValidatedFile?.(file, result.kind);
    } catch (error) {
      setStatus({
        kind: "rejected",
        reason: error instanceof Error ? error.message : "Failed to read file header.",
        fileName: file.name,
      });
    }
  }

  function handleReset() {
    if (status.kind === "accepted") {
      URL.revokeObjectURL(status.previewUrl);
    }
    setStatus({ kind: "idle" });
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div
      role="group"
      aria-label="Cover image uploader"
      data-testid="cover-uploader"
      className="flex flex-col gap-3"
    >
      <label className="grid gap-1 text-sm font-medium">
        Cover image
        <input
          ref={inputRef}
          data-testid="cover-uploader-input"
          type="file"
          accept={ACCEPT}
          onChange={(event) => {
            void handleFile(event.currentTarget.files?.[0]);
          }}
          aria-describedby="cover-uploader-help"
          className="block w-full cursor-pointer rounded-md border border-border bg-background px-3 py-2 text-sm file:mr-3 file:rounded file:border-0 file:bg-primary file:px-3 file:py-1 file:text-primary-foreground file:hover:bg-primary/90"
        />
        <span id="cover-uploader-help" className="text-xs font-normal text-muted-foreground">
          PNG, JPEG, or WEBP. The file&apos;s binary header is verified before any upload.
        </span>
      </label>

      {status.kind === "validating" ? (
        <p role="status" className="flex items-center gap-2 text-xs text-muted-foreground">
          <ImageIcon className="h-3.5 w-3.5" /> Validating {status.file.name}…
        </p>
      ) : null}

      {status.kind === "rejected" ? (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <div className="flex-1">
            <p className="font-medium">{status.fileName} was rejected.</p>
            <p className="mt-1">{status.reason}</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleReset}
            aria-label="Dismiss rejection"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : null}

      {status.kind === "accepted" ? (
        <div
          role="status"
          className="flex items-start gap-3 rounded-md border border-emerald-300/40 bg-emerald-50 p-3 text-xs dark:border-emerald-900/40 dark:bg-emerald-950/30"
        >
          {/* next/image does not handle blob: URLs, so a transient client-side preview uses <img> directly. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={status.previewUrl}
            alt=""
            className="h-12 w-12 rounded object-cover"
            data-testid="cover-uploader-preview"
          />
          <div className="flex-1 min-w-0">
            <p className="flex items-center gap-1 font-medium text-emerald-900 dark:text-emerald-100">
              <CheckCircle2 className="h-3.5 w-3.5" /> {FORMAT_LABEL[status.format]} signature verified
            </p>
            <p className="mt-0.5 truncate text-emerald-800/80 dark:text-emerald-200/80">
              {status.file.name} · {formatBytes(status.file.size)}
            </p>
            <p className="mt-0.5 text-[10px] text-emerald-800/60 dark:text-emerald-200/60">
              File validated locally. No network upload has been triggered.
            </p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleReset}
            aria-label="Clear selected file"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      ) : null}
    </div>
  );
}
