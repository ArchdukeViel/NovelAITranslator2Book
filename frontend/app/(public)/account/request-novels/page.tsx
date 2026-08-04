"use client";

import { useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  ExternalLink,
  FilePlus2,
  HelpCircle,
  Info,
  Loader2,
  Search,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { LoginPrompt } from "@/components/public/login-prompt";
import { RequestControl } from "@/components/public/request-control";
import { usePublicAuth, useRequests } from "@/hooks/public";
import { publicNovelHref } from "@/lib/public-routes";
import { cn } from "@/lib/utils";

const SUPPORTED_SOURCES = [
  { name: "Kakuyomu", domain: "kakuyomu.jp", url: "https://kakuyomu.jp" },
  { name: "Syosetu", domain: "ncode.syosetu.com", url: "https://syosetu.com" },
  { name: "Syosetu18", domain: "novel18.syosetu.com", url: "https://novel18.syosetu.com" },
];

function sourceFromUrl(value: string | null): { name: string; domain: string } {
  if (!value) return { name: "Unknown", domain: "—" };
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    if (hostname.includes("kakuyomu")) return { name: "Kakuyomu", domain: "kakuyomu.jp" };
    if (hostname.includes("novel18")) return { name: "Syosetu18", domain: "novel18.syosetu.com" };
    if (hostname.includes("syosetu")) return { name: "Syosetu", domain: "ncode.syosetu.com" };
  } catch {
    return { name: "Unknown", domain: "—" };
  }
  return { name: "Unknown", domain: "—" };
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "pending":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2.5 py-0.5 font-metadata text-xs font-medium text-amber-600 dark:text-amber-400">
          <Clock className="h-3 w-3" />
          Pending Review
        </span>
      );
    case "approved":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 font-metadata text-xs font-medium text-emerald-600 dark:text-emerald-400">
          <CheckCircle2 className="h-3 w-3" />
          Approved
        </span>
      );
    case "rejected":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2.5 py-0.5 font-metadata text-xs font-medium text-rose-600 dark:text-rose-400">
          <XCircle className="h-3 w-3" />
          Rejected
        </span>
      );
    case "completed":
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-0.5 font-metadata text-xs font-medium text-primary">
          <ShieldCheck className="h-3 w-3" />
          Translated
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 font-metadata text-xs font-medium text-muted-foreground capitalize">
          {status}
        </span>
      );
  }
}

export default function AccountRequestNovelsPage() {
  const { isAuthenticated, isPending: authPending } = usePublicAuth();

  return (
    <main className="mx-auto max-w-7xl">
      <header className="mb-8 border-b border-border/20 pb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <FilePlus2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="font-literary text-3xl font-semibold tracking-normal text-foreground">
              Request Novels
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              Submit web novel or chapter translation requests from supported Japanese raw sources.
            </p>
          </div>
        </div>
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="space-y-8">
          <section aria-label="Request submission form">
            <RequestControl />
          </section>

          {authPending ? (
            <div className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-primary" />
                Checking session...
              </div>
            </div>
          ) : !isAuthenticated ? (
            <LoginPrompt />
          ) : (
            <RequestHistoryList />
          )}
        </div>

        <aside className="space-y-6">
          <div className="rounded-xl bg-card p-5 shadow-card dark:ring-1 dark:ring-white/5">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="font-literary text-base font-semibold text-foreground">
                Supported Sources
              </h2>
              <span className="rounded bg-primary/10 px-2 py-0.5 font-metadata text-[10px] font-medium text-primary">
                3 Active
              </span>
            </div>
            <p className="mb-4 text-xs text-muted-foreground">
              Only novels hosted on official supported raw platforms can be requested.
            </p>
            <ul className="space-y-2.5">
              {SUPPORTED_SOURCES.map((source) => (
                <li key={source.name}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group flex items-center justify-between rounded-lg bg-muted/40 p-2.5 transition-colors hover:bg-muted"
                  >
                    <div>
                      <span className="block text-xs font-semibold text-foreground group-hover:text-primary">
                        {source.name}
                      </span>
                      <span className="block font-metadata text-[11px] text-muted-foreground">
                        {source.domain}
                      </span>
                    </div>
                    <ExternalLink className="h-3.5 w-3.5 text-muted-foreground opacity-60 transition-opacity group-hover:opacity-100" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-xl bg-card p-5 shadow-card dark:ring-1 dark:ring-white/5">
            <h2 className="mb-3 flex items-center gap-2 font-literary text-base font-semibold text-foreground">
              <HelpCircle className="h-4 w-4 text-primary" />
              Request Guidelines
            </h2>
            <ul className="space-y-3 text-xs leading-relaxed text-muted-foreground">
              <li className="flex items-start gap-2">
                <Search className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span>
                  <strong>Check catalog first:</strong> Use search or browse to verify the novel isn&apos;t already available.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span>
                  <strong>Valid URL required:</strong> Provide a direct link to the main table of contents or novel info page.
                </span>
              </li>
              <li className="flex items-start gap-2">
                <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span>
                  <strong>Review Queue:</strong> Requests are processed in order. Approved requests automatically enter translation status.
                </span>
              </li>
            </ul>
          </div>
        </aside>
      </div>
    </main>
  );
}

function RequestHistoryList() {
  const requests = useRequests({ limit: 50 });
  const [statusFilter, setStatusFilter] = useState("all");

  if (requests.isPending) {
    return (
      <div className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          Loading request history...
        </div>
      </div>
    );
  }

  if (requests.isError) {
    return (
      <div className="rounded-xl bg-card p-6 shadow-card dark:ring-1 dark:ring-white/5">
        <p className="text-sm text-destructive">Could not load request history.</p>
      </div>
    );
  }

  const items = requests.data.items ?? [];
  const filteredItems =
    statusFilter === "all"
      ? items
      : items.filter((item) => item.status === statusFilter);

  return (
    <div className="rounded-xl bg-card shadow-card dark:ring-1 dark:ring-white/5">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border/20 p-5">
        <div>
          <h2 className="font-literary text-xl font-semibold text-foreground">My Submissions</h2>
          <p className="font-metadata text-xs text-muted-foreground">
            {items.length} total request{items.length === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter requests by status">
          {["all", "pending", "approved", "rejected", "completed"].map((status) => (
            <button
              key={status}
              type="button"
              onClick={() => setStatusFilter(status)}
              className={cn(
                "rounded-md px-3 py-1 font-metadata text-xs capitalize transition-colors",
                statusFilter === status
                  ? "bg-primary text-primary-foreground font-medium"
                  : "bg-muted/50 text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead className="border-b border-border/20 bg-muted/20 font-metadata text-xs text-muted-foreground">
            <tr>
              <th className="px-5 py-3 font-medium">Requested Novel / URL</th>
              <th className="px-5 py-3 font-medium">Source</th>
              <th className="px-5 py-3 font-medium">Status</th>
              <th className="px-5 py-3 font-medium">Submitted</th>
              <th className="px-5 py-3 font-medium text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/20">
            {filteredItems.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-sm text-muted-foreground">
                  No requests found {statusFilter !== "all" ? `with status "${statusFilter}"` : "yet"}.
                </td>
              </tr>
            ) : (
              filteredItems.map((request) => {
                const source = sourceFromUrl(request.source_url);
                return (
                  <tr key={request.id} className="transition-colors hover:bg-muted/30">
                    <td className="max-w-xs truncate px-5 py-3.5 font-medium text-foreground">
                      {request.slug ?? request.source_url ?? `Request #${request.id}`}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-block rounded bg-muted/60 px-2 py-0.5 font-metadata text-xs text-muted-foreground">
                        {source.name}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={request.status} />
                    </td>
                    <td className="px-5 py-3.5 font-metadata text-xs text-muted-foreground">
                      {formatDate(request.created_at)}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {request.slug ? (
                        <Link
                          href={publicNovelHref(request.slug)}
                          className="inline-flex items-center gap-1 font-metadata text-xs font-medium text-primary hover:underline"
                        >
                          View Novel
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      ) : (
                        <span className="font-metadata text-xs text-muted-foreground">In Review</span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
