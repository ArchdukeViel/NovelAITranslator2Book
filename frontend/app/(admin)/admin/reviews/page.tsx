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
import { api, type AdminReviewRecord } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { compareSortableValues, useSortableTable } from "@/hooks/use-sortable-table";

type ReviewSortKey = "title" | "status" | "created";

function reviewSortValue(review: AdminReviewRecord, key: ReviewSortKey) {
  if (key === "title") {
    return review.title.toLowerCase();
  }
  if (key === "status") {
    return review.status.toLowerCase();
  }
  return Date.parse(review.created_at || "") || 0;
}

export default function ReviewsPage() {
  const queryClient = useQueryClient();
  const [selectedReviewIds, setSelectedReviewIds] = React.useState<Set<string>>(new Set());
  const [pendingAction, setPendingAction] = React.useState<{ review: AdminReviewRecord; status: "published" | "rejected" } | null>(null);
  const { sortKey, sortDirection, handleSort } = useSortableTable<ReviewSortKey>("created", "desc");
  const reviews = useQuery({ queryKey: ["admin-reviews"], queryFn: () => api.adminReviews() });
  const rows = React.useMemo(() => reviews.data?.items ?? [], [reviews.data?.items]);
  const processReview = useMutation({
    mutationFn: async ({ review, status }: { review: AdminReviewRecord; status: "published" | "rejected" }) => {
      const updated = await api.moderateReview(review.id, { status, reviewer_notes: pendingAction?.review.reviewer_notes ?? undefined });
      return updated;
    },
    onSuccess: () => {
      setSelectedReviewIds(new Set());
      setPendingAction(null);
      void queryClient.invalidateQueries({ queryKey: ["admin-reviews"] });
    },
  });

  const sortedRows = React.useMemo(() => {
    return [...rows].sort((left, right) => {
      const leftValue = reviewSortValue(left, sortKey);
      const rightValue = reviewSortValue(right, sortKey);
      return compareSortableValues(leftValue, rightValue, sortDirection);
    });
  }, [rows, sortDirection, sortKey]);

  const allRowsSelected = rows.length > 0 && rows.every((review) => selectedReviewIds.has(review.id.toString()));

  const toggleAllRows = () => {
    setSelectedReviewIds(allRowsSelected ? new Set() : new Set(rows.map((review) => review.id.toString())));
  };

  const toggleReview = (reviewId: string) => {
    setSelectedReviewIds((current) => {
      const next = new Set(current);
      if (next.has(reviewId)) {
        next.delete(reviewId);
      } else {
        next.add(reviewId);
      }
      return next;
    });
  };

  const confirmPendingAction = () => {
    if (!pendingAction) {
      return;
    }
    processReview.mutate(pendingAction);
  };

  return (
    <>
      <PageHeading title="Reviews" description="Moderate reader reviews before publication." />

      <Panel>
        <PanelHeader className="flex flex-row items-center justify-between gap-3">
          <div>
            <PanelTitle>Review Queue</PanelTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              {selectedReviewIds.size ? `${selectedReviewIds.size} selected` : `${rows.length} review(s)`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => void reviews.refetch()} disabled={reviews.isFetching}>
            <RotateCw className="h-4 w-4" />
            Refresh
          </Button>
        </PanelHeader>
        <ErrorBanner error={processReview.error} fallback="Failed to process review." />
        <ErrorBanner error={reviews.error} fallback="Failed to load reviews." />
        <PanelBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="w-12 px-4 py-3">
                    <TableCheckbox checked={allRowsSelected} onChange={toggleAllRows} aria-label="Select all reviews" />
                  </th>
                  <SortableHeader label="Novel" sortKey="title" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="min-w-[320px]" />
                  <SortableHeader label="Status" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={handleSort} className="w-40" />
                  <SortableHeader label="Rating" sortKey="status" activeKey={sortKey} direction={sortDirection} onSort={(key) => handleSort(key, "desc")} className="w-20" />
                  <SortableHeader label="Time added" sortKey="created" activeKey={sortKey} direction={sortDirection} onSort={(key) => handleSort(key, "desc")} className="w-48" />
                  <th className="w-48 px-4 py-3">Process</th>
                </tr>
              </thead>
              <tbody>
                {reviews.isLoading ? (
                  <LoadingRows colSpan={6} label="Loading reviews..." />
                ) : reviews.error ? (
                  <EmptyState title="Failed to load reviews." colSpan={6} />
                ) : sortedRows.length ? (
                  sortedRows.map((review) => (
                    <tr key={review.id} className="border-b last:border-0">
                      <td className="px-4 py-3">
                        <TableCheckbox
                          checked={selectedReviewIds.has(review.id.toString())}
                          onChange={() => toggleReview(review.id.toString())}
                          aria-label={`Select ${review.title}`}
                        />
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium truncate max-w-[320px]">{review.title}</div>
                        <div className="text-xs text-muted-foreground">by user #{review.user_id}</div>
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={review.status} />
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {review.rating != null ? "★".repeat(review.rating) + "☆".repeat(5 - review.rating) : "—"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDateTime(review.created_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            onClick={() => setPendingAction({ review, status: "published" })}
                            disabled={processReview.isPending || review.status === "published"}
                          >
                            <Check className="h-4 w-4" />
                            Publish
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => setPendingAction({ review, status: "rejected" })}
                            disabled={processReview.isPending || review.status === "rejected"}
                          >
                            <X className="h-4 w-4" />
                            Reject
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyState title="No reader reviews yet." colSpan={6} />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <ConfirmDialog
        open={Boolean(pendingAction)}
        title={pendingAction?.status === "published" ? "Publish review" : "Reject review"}
        description={
          pendingAction
            ? `${pendingAction.status === "published" ? "Publish" : "Reject"} "${pendingAction.review.title}"?`
            : undefined
        }
        confirmLabel={pendingAction?.status === "published" ? "Publish" : "Reject"}
        destructive={pendingAction?.status === "rejected"}
        pending={processReview.isPending}
        onConfirm={confirmPendingAction}
        onCancel={() => setPendingAction(null)}
        auditNotice="This action is recorded in the audit log."
      />
    </>
  );
}
