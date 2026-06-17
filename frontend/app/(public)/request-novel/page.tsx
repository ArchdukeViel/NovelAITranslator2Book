"use client";

import Link from "next/link";
import { Loader2 } from "lucide-react";

import { AuthGate } from "@/components/public/auth-gate";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { useRequests } from "@/hooks/public";

const SUPPORTED_SOURCES = ["Kakuyomu", "Syosetu", "Syosetu18"];

function sourceFromUrl(value: string | null): string {
  if (!value) return "Unknown";
  try {
    const hostname = new URL(value).hostname.toLowerCase();
    if (hostname.includes("kakuyomu")) return "Kakuyomu";
    if (hostname.includes("novel18")) return "Syosetu18";
    if (hostname.includes("syosetu")) return "Syosetu";
  } catch {
    return "Unknown";
  }
  return "Unknown";
}

export default function RequestNovelPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">Request Novel</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Sign in to request a novel from a supported source. Requests are reviewed by the owner and may be accepted, rejected, or queued based on catalog priorities.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <AuthGate>
          <RequestHistory />
        </AuthGate>

        <aside className="space-y-4">
          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Supported Sources</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <ul className="space-y-2 text-sm text-muted-foreground">
                {SUPPORTED_SOURCES.map((source) => (
                  <li key={source} className="font-metadata">{source}</li>
                ))}
              </ul>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Request URL</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <label className="block text-xs font-medium text-muted-foreground">
                Supported source URL
              </label>
              <input
                className="h-9 w-full rounded-md border border-border bg-background px-3 text-sm disabled:opacity-50"
                disabled
                placeholder="https://kakuyomu.jp/..."
                type="url"
                aria-label="Supported source URL (disabled pending backend support)"
              />
              <p className="text-xs text-muted-foreground">
                URL validation and submission controls will be enabled against the existing request API in a dedicated behavior phase.
              </p>
            </PanelBody>
          </Panel>
        </aside>
      </div>
    </main>
  );
}

function RequestHistory() {
  const requests = useRequests({ limit: 50 });

  if (requests.isPending) {
    return (
      <Panel>
        <PanelBody>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading request history
          </div>
        </PanelBody>
      </Panel>
    );
  }

  if (requests.isError) {
    return (
      <Panel>
        <PanelBody>
          <p className="text-sm text-destructive">Could not load request history.</p>
        </PanelBody>
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader>
        <PanelTitle className="font-literary">Request History</PanelTitle>
      </PanelHeader>
      <PanelBody className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b text-xs text-muted-foreground">
            <tr>
              {[
                "Requested Novel / URL",
                "Source",
                "Status",
                "Rejection Reason",
                "Requested At",
                "Updated At",
                "Action",
              ].map((heading) => (
                <th className="px-4 py-3 font-medium font-metadata" key={heading}>
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y">
            {requests.data.items.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-center text-muted-foreground" colSpan={7}>
                  No requests yet.
                </td>
              </tr>
            ) : (
              requests.data.items.map((request) => (
                <tr key={request.id}>
                  <td className="px-4 py-3">
                    {request.slug ?? request.source_url ?? "Request"}
                  </td>
                  <td className="px-4 py-3 font-metadata">{sourceFromUrl(request.source_url)}</td>
                  <td className="px-4 py-3 font-metadata capitalize">{request.status}</td>
                  <td className="px-4 py-3 text-muted-foreground">Not provided by current API</td>
                  <td className="px-4 py-3 font-metadata">{request.created_at}</td>
                  <td className="px-4 py-3 text-muted-foreground">Not provided by current API</td>
                  <td className="px-4 py-3">
                    {request.slug ? (
                      <Link className="text-accent underline hover:text-foreground" href={`/novel/${encodeURIComponent(request.slug)}`}>
                        Open
                      </Link>
                    ) : (
                      <span className="text-muted-foreground">Pending</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </PanelBody>
    </Panel>
  );
}
