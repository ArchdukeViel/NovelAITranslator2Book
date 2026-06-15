"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, RotateCw, X } from "lucide-react";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { SortableHeader } from "@/components/admin/sortable-header";
import { StatusBadge } from "@/components/admin/status-badge";
import { TableCheckbox } from "@/components/admin/table-checkbox";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api, type NovelRequestRecord } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { deriveNovelId, detectSourceOrigin } from "@/lib/novel-input";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";

type RequestSortKey = "title" | "status" | "created";
type PendingRequestAction = { request: NovelRequestRecord; status: "approved" | "rejected" } | null;

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

export default function RequestsPage() {
  const queryClient = useQueryClient();
  const [selectedRequestIds, setSelectedRequestIds] = React.useState<Set<string>>(new Set());
  const [pendingAction, setPendingAction] = React.useState<PendingRequestAction>(null);
  const { sortKey, sortDirection, handleSort } = useSortableTable<RequestSortKey>("created", "desc");
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
      return compareSortableValues(leftValue, rightValue, sortDirection);
    });
  }, [rows, sortDirection, sortKey]);

  const allRowsSelected = rows.length > 0 && rows.every((request) => selectedRequestIds.has(request.id));

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

  const confirmPendingAction = () => {
    if (!pendingAction) {
      return;
    }
    processRequest.mutate(pendingAction);
    setPendingAction(null);
  };

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
        <ErrorBanner error={processRequest.error} fallback="Failed to process request." />
        <ErrorBanner error={requests.error} fallback="Failed to load requests." />
        <PanelBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <TableCheckbox checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all requests" />
                  </th>
                  <SortableHeader label="Title" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="min-w-[320px]" />
                  <SortableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-40" />
                  <SortableHeader label="Time added" sortKey="created" activeKey={sortKey} direction={sortDirection} onSort={(key) => handleSort(key, "desc")} className="w-48" />
                  <th className="w-48 px-4 py-3">Process</th>
                </tr>
              </thead>
              <tbody>
                {requests.isLoading ? (
                  <LoadingRows colSpan={5} label="Loading requests..." />
                ) : requests.error ? (
                  <EmptyState title="Failed to load requests." colSpan={5} />
                ) : sortedRows.length ? (
                  sortedRows.map((request) => (
                    <tr key={request.id} className="border-b last:border-0">
                      <td className="px-4 py-3">
                        <TableCheckbox
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
                      <td className="px-4 py-3 text-muted-foreground">{formatDateTime(request.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => setPendingAction({ request, status: "approved" })}
                            disabled={processRequest.isPending || request.status === "approved"}
                          >
                            <Check className="h-4 w-4" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setPendingAction({ request, status: "rejected" })}
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
                  <EmptyState title="No reader requests yet." colSpan={5} />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <ConfirmDialog
        open={Boolean(pendingAction)}
        title={pendingAction?.status === "approved" ? "Approve request" : "Reject request"}
        description={
          pendingAction
            ? `${pendingAction.status === "approved" ? "Approve" : "Reject"} "${pendingAction.request.title}"?`
            : undefined
        }
        confirmLabel={pendingAction?.status === "approved" ? "Approve" : "Reject"}
        destructive={pendingAction?.status === "rejected"}
        pending={processRequest.isPending}
        onConfirm={confirmPendingAction}
        onCancel={() => setPendingAction(null)}
        auditNotice="This action is recorded in the audit log."
      />
    </>
  );
}
