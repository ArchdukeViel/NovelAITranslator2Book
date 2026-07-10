"use client";

import { useState, type ComponentType } from "react";
import {
  AlertCircle,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  RefreshCw,
} from "lucide-react";

import { api } from "@/lib/api";
import type {
  ExportManifest,
  ExportManifestFreshness,
  ExportManifestStatus,
} from "@/lib/api-types";
import { formatBytes } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type ExportManifestListResponse = {
  manifests?: ExportManifest[];
  exports?: ExportManifest[];
};

type ApiWithExportManifests = typeof api & {
  listExportManifests?: (
    novelId: string,
  ) => Promise<ExportManifestListResponse>;
};

type BadgeConfig = {
  label: string;
  className?: string;
  icon?: ComponentType<{ className?: string }>;
};

const STATUS_CONFIG: Partial<Record<ExportManifestStatus, BadgeConfig>> = {
  succeeded: {
    label: "Succeeded",
    className: "border-primary/30 bg-primary/10 text-primary",
  },
  failed: {
    label: "Failed",
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
  pending: {
    label: "Pending",
    className: "border-muted-foreground/30 text-muted-foreground",
  },
  running: {
    label: "Running",
    className: "border-muted-foreground/30 text-muted-foreground",
  },
  deleted: {
    label: "Deleted",
    className: "border-muted-foreground/30 text-muted-foreground",
  },
  legacy_unknown: {
    label: "Legacy",
    className: "border-muted-foreground/30 text-muted-foreground",
  },
};

const FRESHNESS_CONFIG: Partial<Record<ExportManifestFreshness, BadgeConfig>> = {
  current: {
    label: "Current",
    icon: CheckCircle,
    className: "border-primary/30 bg-primary/10 text-primary",
  },
  stale: {
    label: "Stale",
    icon: AlertCircle,
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
  unknown_legacy_manifest: {
    label: "Legacy",
    icon: FileText,
    className: "border-muted-foreground/30 text-muted-foreground",
  },
  current_state_unavailable: {
    label: "Unavailable",
    icon: Clock,
    className: "border-muted-foreground/30 text-muted-foreground",
  },
};

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, char => char.toUpperCase());
}

function getStatusConfig(status: ExportManifestStatus): BadgeConfig {
  return (
    STATUS_CONFIG[status] ?? {
      label: titleCase(String(status)),
      className: "border-muted-foreground/30 text-muted-foreground",
    }
  );
}

function getFreshnessConfig(freshness: ExportManifestFreshness): BadgeConfig {
  return (
    FRESHNESS_CONFIG[freshness] ?? {
      label: titleCase(String(freshness)),
      icon: FileText,
      className: "border-muted-foreground/30 text-muted-foreground",
    }
  );
}

function StatusBadge({ status }: { status: ExportManifestStatus }) {
  const config = getStatusConfig(status);

  return <Badge className={config.className}>{config.label}</Badge>;
}

function FreshnessBadge({
  freshness,
}: {
  freshness?: ExportManifestFreshness | null;
}) {
  if (!freshness) return null;

  const config = getFreshnessConfig(freshness);
  const Icon = config.icon ?? FileText;

  return (
    <Badge className={`gap-1 ${config.className ?? ""}`}>
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

function formatDateTime(dateStr?: string | null): string {
  if (!dateStr) return "—";

  try {
    return new Date(dateStr).toLocaleString();
  } catch {
    return dateStr;
  }
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as {
      detail?: unknown;
      message?: unknown;
      error?: unknown;
    };

    const detail = payload.detail ?? payload.message ?? payload.error;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  } catch {
    // Ignore JSON parse errors and fall back to status text.
  }

  return response.statusText || `Request failed with ${response.status}`;
}

async function listExportManifests(
  novelId: string,
): Promise<ExportManifest[]> {
  const client = api as ApiWithExportManifests;

  if (typeof client.listExportManifests === "function") {
    const response = await client.listExportManifests(novelId);
    return response.manifests ?? response.exports ?? [];
  }

  const response = await fetch(
    `/api/admin/novels/${encodeURIComponent(novelId)}/exports`,
    {
      credentials: "include",
    },
  );

  if (!response.ok) {
    throw new Error(await readErrorMessage(response));
  }

  const payload = (await response.json()) as ExportManifestListResponse;
  return payload.manifests ?? payload.exports ?? [];
}

export default function ExportsPage() {
  const [novelId, setNovelId] = useState("");
  const [manifests, setManifests] = useState<ExportManifest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  const fetchManifests = async () => {
    const trimmedNovelId = novelId.trim();
    if (!trimmedNovelId) return;

    setLoading(true);
    setError(null);

    try {
      const nextManifests = await listExportManifests(trimmedNovelId);
      setManifests(nextManifests);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch manifests",
      );
    } finally {
      setLoading(false);
    }
  };

  const toggleExpand = (manifestKey: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);

      if (next.has(manifestKey)) {
        next.delete(manifestKey);
      } else {
        next.add(manifestKey);
      }

      return next;
    });
  };

  const openLatestExport = (format: string) => {
    const trimmedNovelId = novelId.trim();
    if (!trimmedNovelId) return;

    window.open(
      `/api/admin/novels/${encodeURIComponent(trimmedNovelId)}/exports/latest/${encodeURIComponent(format)}`,
      "_blank",
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Export Manifests
          </h1>
          <p className="mt-1 text-muted-foreground">
            View and manage export history for a novel. Manifests track export
            status, freshness, and metadata.
          </p>
        </div>
      </div>

      <div className="rounded-lg border bg-card p-6">
        <h2 className="mb-4 text-lg font-semibold">Select Novel</h2>

        <div className="space-y-4">
          <div className="flex items-end gap-4">
            <div className="max-w-md flex-1">
              <label
                htmlFor="novel-id"
                className="mb-1 block text-sm font-medium"
              >
                Novel ID
              </label>
              <input
                id="novel-id"
                type="text"
                value={novelId}
                onChange={event => setNovelId(event.target.value)}
                placeholder="Enter novel ID or slug"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>

            <Button
              onClick={fetchManifests}
              disabled={loading || !novelId.trim()}
            >
              {loading ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 h-4 w-4" />
              )}
              Fetch Manifests
            </Button>
          </div>

          {error && <div className="text-sm text-destructive">{error}</div>}
        </div>
      </div>

      {manifests.length > 0 && (
        <div className="rounded-lg border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold">
            Manifests for {novelId} ({manifests.length})
          </h2>

          <div className="space-y-4">
            {manifests.map((manifest, index) => {
              const manifestKey =
                manifest.manifest_key || `${manifest.format}-${index}`;
              const isExpanded = expandedKeys.has(manifestKey);

              return (
                <div
                  key={manifestKey}
                  className="rounded-lg border bg-card p-4"
                >
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        <FileText className="h-5 w-5 text-muted-foreground" />
                        <span className="font-mono text-sm text-muted-foreground">
                          {manifest.format.toUpperCase()}
                        </span>
                      </div>

                      <StatusBadge status={manifest.status} />
                      <FreshnessBadge freshness={manifest.freshness} />
                    </div>

                    <select
                      defaultValue=""
                      onChange={event => {
                        const action = event.currentTarget.value;

                        if (action === "download") {
                          openLatestExport(manifest.format);
                        }

                        if (action === "expand") {
                          toggleExpand(manifestKey);
                        }

                        event.currentTarget.value = "";
                      }}
                      className="cursor-pointer border-none bg-transparent text-sm text-muted-foreground hover:text-foreground"
                    >
                      <option value="" disabled>
                        Actions
                      </option>
                      <option value="download">Download</option>
                      <option value="expand">
                        {isExpanded ? "Collapse" : "Expand"}
                      </option>
                    </select>
                  </div>

                  {isExpanded && (
                    <div className="mt-4 grid grid-cols-1 gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                      <div className="space-y-1">
                        <p className="text-muted-foreground">Manifest Key</p>
                        <code className="break-all font-mono text-xs">
                          {manifest.manifest_key}
                        </code>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Status</p>
                        <span className="capitalize">{manifest.status}</span>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Chapters</p>
                        <span>
                          {manifest.chapter_count ?? "—"} /{" "}
                          {manifest.source_chapter_count ?? "—"}
                        </span>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">File Size</p>
                        <span>
                          {typeof manifest.file_size_bytes === "number"
                            ? formatBytes(manifest.file_size_bytes)
                            : "—"}
                        </span>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Checksum</p>
                        <code className="break-all font-mono text-xs">
                          {manifest.checksum ?? "—"}
                        </code>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Glossary Rev</p>
                        <span>{manifest.glossary_revision ?? "—"}</span>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Created</p>
                        <span>{formatDateTime(manifest.created_at)}</span>
                      </div>

                      <div className="space-y-1">
                        <p className="text-muted-foreground">Updated</p>
                        <span>{formatDateTime(manifest.updated_at)}</span>
                      </div>

                      {manifest.failure_code && (
                        <div className="space-y-1 sm:col-span-2">
                          <p className="text-muted-foreground">Failure</p>
                          <div className="flex items-center gap-2">
                            <Badge className="border-destructive/30 bg-destructive/10 text-destructive">
                              {manifest.failure_code}
                            </Badge>
                            {manifest.failure_message && (
                              <span className="text-sm text-destructive">
                                {manifest.failure_message}
                              </span>
                            )}
                          </div>
                        </div>
                      )}

                      {manifest.export_options &&
                        Object.keys(manifest.export_options).length > 0 && (
                          <div className="space-y-1 sm:col-span-2">
                            <p className="text-muted-foreground">
                              Export Options
                            </p>
                            <pre className="max-h-32 overflow-auto rounded bg-muted p-2 text-xs">
                              {JSON.stringify(
                                manifest.export_options,
                                null,
                                2,
                              )}
                            </pre>
                          </div>
                        )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {manifests.length === 0 && novelId && !loading && (
        <div className="rounded-lg border bg-card p-12 text-center">
          <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
          <h3 className="mt-4 text-lg font-medium">No manifests found</h3>
          <p className="mt-2 text-muted-foreground">
            No export manifests exist for this novel yet. Exports will appear
            here after running.
          </p>
        </div>
      )}
    </div>
  );
}