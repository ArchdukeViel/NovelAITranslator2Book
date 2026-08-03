"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { EmptyState, ErrorState, LoadingState } from "@/components/ui/page-state";
import { Button } from "@/components/ui/button";
import { adminApi } from "@/lib/api";

export default function TakedownsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState("");
  const [notes, setNotes] = useState<Record<number, string>>({});
  const requests = useQuery({
    queryKey: ["admin", "takedowns", status],
    queryFn: () => adminApi.listTakedowns(status || undefined),
  });
  const review = useMutation({
    mutationFn: ({ id, decision }: { id: number; decision: "approved" | "rejected" }) =>
      adminApi.reviewTakedown(id, { status: decision, reviewer_notes: notes[id]?.trim() || undefined }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["admin", "takedowns"] }),
  });

  return (
    <main className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-semibold">DMCA takedown requests</h1>
        <p className="mt-1 text-sm text-muted-foreground">Review notices before approving legal removal.</p>
      </div>
      <label className="block max-w-xs text-sm font-medium">
        Status
        <select className="mt-1 w-full rounded-md border bg-background px-3 py-2" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">All</option>
          {['pending', 'reviewing', 'approved', 'rejected', 'expired'].map((value) => <option key={value}>{value}</option>)}
        </select>
      </label>
      {requests.isPending ? <LoadingState label="Loading takedown requests" /> : null}
      {requests.isError ? <ErrorState title="Could not load takedown requests" description="Try again." action={<Button onClick={() => requests.refetch()}>Retry</Button>} /> : null}
      {requests.data?.items.length === 0 ? <EmptyState title="No takedown requests" description="No notices match this status." /> : null}
      <div className="space-y-4">
        {requests.data?.items.map((item) => (
          <article className="rounded-lg border bg-card p-5" key={item.id}>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h2 className="font-semibold">Request #{item.id}</h2>
              <span className="text-sm capitalize text-muted-foreground">{item.status}</span>
            </div>
            <p className="mt-3 break-all text-sm">{item.infringing_url}</p>
            <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{item.description}</p>
            <label className="mt-4 block text-sm font-medium">
              Reviewer notes
              <textarea className="mt-1 min-h-20 w-full rounded-md border bg-background p-2" value={notes[item.id] ?? ""} onChange={(event) => setNotes((current) => ({ ...current, [item.id]: event.target.value }))} />
            </label>
            <div className="mt-3 flex gap-2">
              <Button disabled={review.isPending} onClick={() => review.mutate({ id: item.id, decision: "approved" })}>Approve</Button>
              <Button disabled={review.isPending} variant="outline" onClick={() => review.mutate({ id: item.id, decision: "rejected" })}>Reject</Button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
