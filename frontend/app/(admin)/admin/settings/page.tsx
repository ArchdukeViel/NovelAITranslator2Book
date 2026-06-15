"use client";

import { useQuery } from "@tanstack/react-query";

import { ErrorBanner } from "@/components/admin/error-banner";
import { PageHeading } from "@/components/admin/page-heading";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { RuntimeStateItem } from "@/lib/api";
import { formatBytes } from "@/lib/format";

// Note: Client-side API token management removed in Task 4
// Provider credential config will be reimplemented in Task 14 using Admin_API
// Runtime state management is still available

export default function SettingsPage() {
  const runtimeState = useQuery({
    queryKey: ["runtime-state"],
    queryFn: () => api.runtimeState()
  });

  const runtimeStorageError = runtimeState.error;

  return (
    <>
      <PageHeading
        title="Settings"
        description="Configure workspace settings and runtime state."
      />

      <div className="space-y-5">
        {/* Provider Credential Config - Task 14 */}
        <Panel>
          <PanelHeader>
            <PanelTitle>Provider Credential</PanelTitle>
          </PanelHeader>
          <PanelBody>
            <p className="text-sm text-muted-foreground">
              Provider credential configuration will be available in Task 14.
              The credential will be managed server-side via the Admin_API and masked for display.
            </p>
          </PanelBody>
        </Panel>

        {/* Runtime State - still functional */}
        <Panel>
          <PanelHeader>
            <PanelTitle>Runtime State</PanelTitle>
          </PanelHeader>
          <PanelBody>
            <ErrorBanner error={runtimeStorageError} fallback="Failed to load runtime state." />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-4 py-3 font-medium">Key</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Size</th>
                    <th className="px-4 py-3 font-medium">Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {runtimeState.isLoading ? (
                    <tr>
                      <td className="px-4 py-3" colSpan={4}>
                        Loading runtime state...
                      </td>
                    </tr>
                  ) : runtimeState.data?.items.length ? (
                    runtimeState.data.items.map((item: RuntimeStateItem) => (
                      <tr className="border-b last:border-0" key={item.key}>
                        <td className="px-4 py-3 font-mono text-xs">{item.key}</td>
                        <td className="px-4 py-3">{item.label}</td>
                        <td className="px-4 py-3">{formatBytes(item.size_bytes)}</td>
                        <td className="px-4 py-3">
                          {item.updated_at ? new Date(item.updated_at).toLocaleString() : "unknown"}
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-3" colSpan={4}>
                        No runtime state items.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}