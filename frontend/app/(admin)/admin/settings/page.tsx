"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { ErrorBanner } from "@/components/admin/error-banner";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { RuntimeStateItem } from "@/lib/api";
import { formatBytes } from "@/lib/format";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const runtimeState = useQuery({
    queryKey: ["runtime-state"],
    queryFn: () => api.runtimeState()
  });

  const [clearKey, setClearKey] = React.useState<string | null>(null);

  const clearRuntimeState = useMutation({
    mutationFn: (key: string) => api.clearRuntimeState(key),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runtime-state"] });
      setClearKey(null);
    }
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

        {/* Runtime State */}
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
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runtimeState.isLoading ? (
                    <tr>
                      <td className="px-4 py-3" colSpan={5}>
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
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setClearKey(item.key)}
                            disabled={clearRuntimeState.isPending && clearKey === item.key}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="h-4 w-4" />
                            <span className="sr-only">Clear {item.key}</span>
                          </Button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-3" colSpan={5}>
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

      <ConfirmDialog
        open={!!clearKey}
        title="Clear Runtime State"
        description={`Are you sure you want to clear the runtime state for "${clearKey}"? This action cannot be undone and may require the system to rebuild this state.`}
        confirmLabel="Clear State"
        cancelLabel="Cancel"
        destructive
        pending={clearRuntimeState.isPending}
        onConfirm={() => {
          if (clearKey) {
            clearRuntimeState.mutate(clearKey);
          }
        }}
        onCancel={() => setClearKey(null)}
      />
    </>
  );
}
