"use client";

import { useQuery } from "@tanstack/react-query";
import * as React from "react";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminApi, ApiError } from "@/lib/api";
import type { GlossaryEntry, GlossaryEntryStatus } from "@/lib/api-types";

const STATUS_ORDER: GlossaryEntryStatus[] = ["candidate", "recommended", "approved", "rejected", "deprecated"];

function statusTone(status: GlossaryEntryStatus) {
  if (status === "approved") return "green";
  if (status === "recommended") return "blue";
  if (status === "rejected" || status === "deprecated") return "red";
  return "amber";
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function seenRange(entry: GlossaryEntry) {
  const first = entry.first_seen_chapter_number ?? entry.first_seen_chapter_id;
  const last = entry.last_seen_chapter_number ?? entry.last_seen_chapter_id;
  if (first && last && first !== last) return `${first} to ${last}`;
  if (first || last) return String(first ?? last);
  return "-";
}

function countByStatus(entries: GlossaryEntry[]) {
  return STATUS_ORDER.map((status) => ({
    status,
    count: entries.filter((entry) => entry.status === status).length,
  }));
}

function authorizationMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    return "Owner session is required to view this glossary.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "This owner session is not allowed to view the glossary.";
  }
  return null;
}

export function AdminGlossaryShell({ novelId }: { novelId: string }) {
  const glossary = useQuery({
    queryKey: ["admin-glossary", novelId],
    queryFn: () => adminApi.listGlossaryEntries(novelId),
  });
  const entries = glossary.data ?? [];
  const authMessage = authorizationMessage(glossary.error);

  return (
    <>
      <PageHeading
        title="Glossary"
        description={`Novel ID: ${novelId}`}
      />

      <Panel className="mb-4">
        <PanelBody className="space-y-2 text-sm text-muted-foreground">
          <p>Glossary terms are owned by this novel. Source IDs are provenance only.</p>
          <p>No global find/replace or chapter repair runs from this page. Prompt injection and QA enforcement are later phases.</p>
        </PanelBody>
      </Panel>

      <Panel className="mb-4">
        <PanelHeader>
          <PanelTitle>Status summary</PanelTitle>
        </PanelHeader>
        <PanelBody>
          {glossary.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading glossary summary...</div>
          ) : glossary.error ? (
            <div className="text-sm text-muted-foreground">Summary unavailable.</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {countByStatus(entries).map(({ status, count }) => (
                <div key={status} className="rounded-md border px-3 py-2">
                  <div className="text-xs uppercase text-muted-foreground">{formatStatus(status)}</div>
                  <div className="mt-1 text-2xl font-semibold">{count}</div>
                </div>
              ))}
            </div>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle>Entries</PanelTitle>
        </PanelHeader>
        <ErrorBanner error={glossary.error} fallback="Failed to load glossary entries." />
        {authMessage ? (
          <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {authMessage}
          </div>
        ) : null}
        <PanelBody className="p-0">
          <div className="seamless-scrollbar overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="min-w-[220px] px-4 py-3">Canonical term</th>
                  <th className="px-4 py-3">Term type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Enforcement</th>
                  <th className="px-4 py-3">Owner locked</th>
                  <th className="px-4 py-3">Public visible</th>
                  <th className="px-4 py-3">First/last seen</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody>
                {glossary.isLoading ? (
                  <LoadingRows colSpan={8} label="Loading glossary entries..." />
                ) : glossary.error ? (
                  <EmptyState title="Failed to load glossary entries." description={authMessage ?? "Try refreshing after confirming the owner session."} colSpan={8} />
                ) : entries.length ? (
                  entries.map((entry) => (
                    <tr className="border-b last:border-0" key={entry.id}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{entry.canonical_term}</div>
                        {entry.approved_translation ? (
                          <div className="mt-1 text-xs text-muted-foreground">{entry.approved_translation}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">{formatStatus(entry.term_type)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(entry.status)}>{formatStatus(entry.status)}</Badge>
                      </td>
                      <td className="px-4 py-3">{formatStatus(entry.enforcement_level)}</td>
                      <td className="px-4 py-3">{entry.owner_locked ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">{entry.public_visible ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">{seenRange(entry)}</td>
                      <td className="px-4 py-3">{formatDate(entry.updated_at)}</td>
                    </tr>
                  ))
                ) : (
                  <EmptyState
                    title="No glossary entries yet."
                    description="Additions and decision workflows will arrive in later admin glossary phases."
                    colSpan={8}
                  />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>
    </>
  );
}
