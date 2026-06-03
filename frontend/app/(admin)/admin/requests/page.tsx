"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, RotateCw, X } from "lucide-react";
import * as React from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api, type NovelRequestRecord } from "@/lib/api";
import { formatDate } from "@/lib/utils";

type RequestSortKey = "title" | "status" | "created";
type SortDirection = "asc" | "desc";

function isHttpUrl(value: string) {
  return /^https?:\/\//i.test(value.trim());
}

function parseUrl(value: string) {
  if (!isHttpUrl(value)) {
    return null;
  }
  try {
    return new URL(value.trim());
  } catch {
    return null;
  }
}

function detectSourceOrigin(value: string) {
  const url = parseUrl(value);
  if (url) {
    const host = url.hostname.toLowerCase();
    if (["novel18.syosetu.com", "noc.syosetu.com", "mnlt.syosetu.com", "mid.syosetu.com"].includes(host)) {
      return "novel18_syosetu";
    }
    if (host === "ncode.syosetu.com") {
      return "syosetu_ncode";
    }
    if (host === "kakuyomu.jp" && url.pathname.includes("/works/")) {
      return "kakuyomu";
    }
  }
  if (/^n\d{4}[a-z]{2}$/i.test(value.trim())) {
    return "novel18_syosetu";
  }
  if (/^\d{12,}$/.test(value.trim())) {
    return "kakuyomu";
  }
  return "generic";
}

function sanitizeNovelId(value: string) {
  return value
    .toLowerCase()
    .replace(/^https?:\/\//, "")
    .replace(/[^a-z0-9._-]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 120) || "novel";
}

function deriveNovelId(value: string, sourceKey: string) {
  const input = value.trim();
  const url = parseUrl(input);
  if (url) {
    if (sourceKey.includes("syosetu")) {
      const match = url.pathname.match(/\/(n\d{4}[a-z]{2})(?:\/|$)/i);
      if (match) {
        return match[1].toLowerCase();
      }
    }
    if (sourceKey === "kakuyomu") {
      const match = url.pathname.match(/\/works\/([^/?#]+)/i);
      if (match) {
        return match[1];
      }
    }
    return sanitizeNovelId(`${url.hostname}${url.pathname}`);
  }
  if (/^n\d{4}[a-z]{2}$/i.test(input)) {
    return input.toLowerCase();
  }
  return sanitizeNovelId(input);
}

function firstSourceCandidate(request: NovelRequestRecord) {
  return request.source_candidates.find((candidate) => {
    const url = candidate.url;
    const sourceKey = candidate.source_key;
    return (typeof url === "string" && url.trim()) || (typeof sourceKey === "string" && sourceKey.trim());
  });
}

function candidateValue(candidate: Record<string, unknown> | undefined, key: string) {
  const value = candidate?.[key];
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function requestSortValue(request: NovelRequestRecord, key: RequestSortKey) {
  if (key === "title") {
    return request.title.toLowerCase();
  }
  if (key === "status") {
    return request.status.toLowerCase();
  }
  return Date.parse(request.created_at || "") || 0;
}

function sortPointer(key: RequestSortKey, activeKey: RequestSortKey, direction: SortDirection) {
  if (key !== activeKey) {
    return "";
  }
  return direction === "asc" ? " \u25B2" : " \u25BC";
}

export default function RequestsPage() {
  const queryClient = useQueryClient();
  const [selectedRequestIds, setSelectedRequestIds] = React.useState<Set<string>>(new Set());
  const [sortKey, setSortKey] = React.useState<RequestSortKey>("created");
  const [sortDirection, setSortDirection] = React.useState<SortDirection>("desc");
  const requests = useQuery({ queryKey: ["requests"], queryFn: () => api.requests() });
  const rows = requests.data?.requests ?? [];
  const processRequest = useMutation({
    mutationFn: async ({ request, status }: { request: NovelRequestRecord; status: "approved" | "rejected" }) => {
      const updated = await api.updateRequestStatus(request.id, { status, reviewed_by: "admin" });
      if (status === "rejected") {
        return updated;
      }

      const candidate = firstSourceCandidate(request);
      const identifier = candidateValue(candidate, "url") || candidateValue(candidate, "source_url");
      if (!identifier) {
        throw new Error(`Request "${request.title}" has no source URL to crawl.`);
      }
      const sourceKey = candidateValue(candidate, "source_key") || detectSourceOrigin(identifier);
      const novelId = deriveNovelId(identifier, sourceKey);
      const preliminary = await api.preliminaryCrawl(novelId, {
        identifier,
        source_key: sourceKey,
        mode: "update"
      });
      const activity = await api.createCrawlActivity({
        novel_id: preliminary.novel_id,
        source_key: preliminary.source_key,
        kind: "chapters",
        chapters: "all",
        source_url: preliminary.source_url || identifier,
        metadata: {
          approved_request: true,
          request_id: request.id,
          request_title: request.title
        }
      });
      await api.runActivity(activity.id);
      return updated;
    },
    onSuccess: () => {
      setSelectedRequestIds(new Set());
      void queryClient.invalidateQueries({ queryKey: ["requests"] });
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
      void queryClient.invalidateQueries({ queryKey: ["novels"] });
    }
  });

  const sortedRows = React.useMemo(() => {
    return [...rows].sort((left, right) => {
      const leftValue = requestSortValue(left, sortKey);
      const rightValue = requestSortValue(right, sortKey);
      const direction = sortDirection === "asc" ? 1 : -1;
      if (typeof leftValue === "number" && typeof rightValue === "number") {
        return (leftValue - rightValue) * direction;
      }
      return String(leftValue).localeCompare(String(rightValue)) * direction;
    });
  }, [rows, sortDirection, sortKey]);

  const allRowsSelected = rows.length > 0 && rows.every((request) => selectedRequestIds.has(request.id));

  const handleSort = (key: RequestSortKey) => {
    if (sortKey === key) {
      setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection(key === "created" ? "desc" : "asc");
  };

  const toggleAllRows = () => {
    setSelectedRequestIds(allRowsSelected ? new Set() : new Set(rows.map((request) => request.id)));
  };

  const toggleRequest = (requestId: string) => {
    setSelectedRequestIds((current) => {
      const next = new Set(current);
      if (next.has(requestId)) {
        next.delete(requestId);
      } else {
        next.add(requestId);
      }
      return next;
    });
  };

  const header = (label: string, key: RequestSortKey, className = "") => (
    <th className={`px-4 py-3 ${className}`}>
      <button type="button" className="font-semibold uppercase hover:text-foreground" onClick={() => handleSort(key)}>
        {label}
        {sortPointer(key, sortKey, sortDirection)}
      </button>
    </th>
  );

  return (
    <>
      <PageHeading title="Requests" description="Reader novel request queue for admin review." />

      <Panel>
        <PanelHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <PanelTitle>Request Queue</PanelTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {selectedRequestIds.size ? `${selectedRequestIds.size} selected` : `${rows.length} request(s)`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void requests.refetch()} disabled={requests.isFetching}>
            <RotateCw className="h-4 w-4" />
            Refresh
          </Button>
        </PanelHeader>
        {processRequest.error ? (
          <div className="border-t px-4 py-3 text-sm text-destructive">
            {processRequest.error instanceof Error ? processRequest.error.message : "Failed to process request."}
          </div>
        ) : null}
        <PanelBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <input className="table-checkbox" type="checkbox" checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all requests" />
                  </th>
                  {header("Title", "title", "min-w-[320px]")}
                  {header("Status", "status", "w-40")}
                  {header("Time added", "created", "w-48")}
                  <th className="w-48 px-4 py-3">Process</th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.length ? (
                  sortedRows.map((request) => (
                    <tr key={request.id} className="border-b last:border-0">
                      <td className="px-4 py-3">
                        <input
                          className="table-checkbox"
                          type="checkbox"
                          checked={selectedRequestIds.has(request.id)}
                          onChange={() => toggleRequest(request.id)}
                          aria-label={`Select ${request.title}`}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium">{request.title}</div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={request.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(request.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => processRequest.mutate({ request, status: "approved" })}
                            disabled={processRequest.isPending || request.status === "approved"}
                          >
                            <Check className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => processRequest.mutate({ request, status: "rejected" })}
                            disabled={processRequest.isPending || request.status === "rejected"}
                          >
                            <X className="h-4 w-4" />
                            Reject
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td className="px-4 py-8 text-muted-foreground" colSpan={5}>
                      No reader requests yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>
    </>
  );
}
