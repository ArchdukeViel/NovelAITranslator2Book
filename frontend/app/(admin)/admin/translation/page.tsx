"use client";

import { useQuery } from "@tanstack/react-query";
import { Gauge, ShieldAlert } from "lucide-react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { SchedulerHealthModel } from "@/lib/api-types";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

function modelTone(configured: boolean, active: boolean | null) {
  if (!configured) return "neutral" as const;
  if (active === false) return "red" as const;
  return "green" as const;
}

function modelLabel(configured: boolean, active: boolean | null) {
  if (!configured) return "Not Configured";
  if (active === false) return "Inactive";
  return "Configured";
}

export default function SchedulerHealthPage() {
  const health = useQuery({
    queryKey: ["scheduler-health"],
    queryFn: () => api.schedulerHealth(),
    refetchInterval: 30000,
  });

  return (
    <>
      <PageHeading title="Scheduler Health" description="Provider/model configuration and status overview" />
      <ErrorBanner error={health.error} fallback="Failed to load scheduler health." className="mb-4 rounded-md border" />

      {health.isLoading ? (
        <LoadingRows colSpan={5} label="Loading scheduler health..." />
      ) : health.data ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <Panel>
            <PanelHeader>
              <PanelTitle>Model Configurations</PanelTitle>
            </PanelHeader>
            <PanelBody className="p-0">
              <table className="w-full text-left text-sm">
                <thead className="border-b text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">Provider / Model</th>
                    <th className="px-4 py-3">Priority</th>
                    <th className="px-4 py-3">RPM Limit</th>
                    <th className="px-4 py-3">RPD Limit</th>
                    <th className="px-4 py-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {health.data.models.length === 0 ? (
                    <tr>
                      <td className="px-4 py-8 text-center text-muted-foreground" colSpan={5}>
                        No models configured.
                      </td>
                    </tr>
                  ) : (
                    health.data.models.map((model: SchedulerHealthModel) => (
                      <tr key={`${model.provider_key}:${model.provider_model}`} className="border-b last:border-0">
                        <td className="px-4 py-3">
                          <div className="font-medium">{model.provider_key}</div>
                          <div className="text-xs text-muted-foreground">{model.provider_model}</div>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">{model.priority_order}</td>
                        <td className="px-4 py-3 text-muted-foreground">{model.rpm_limit ?? "-"}</td>
                        <td className="px-4 py-3 text-muted-foreground">{model.rpd_limit ?? "-"}</td>
                        <td className="px-4 py-3">
                          <Badge tone={modelTone(model.configured, model.credential_active)}>
                            {modelLabel(model.configured, model.credential_active)}
                          </Badge>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </PanelBody>
          </Panel>

          <div className="space-y-4">
            <Panel>
              <PanelHeader>
                <PanelTitle>Fallback Policy</PanelTitle>
              </PanelHeader>
              <PanelBody className="space-y-3 text-sm">
                <div>
                  <div className="text-muted-foreground">Default Provider</div>
                  <div className="font-medium">{health.data.policy.default_provider_key}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Default Model</div>
                  <div className="font-medium">{health.data.policy.default_provider_model}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Cross-Provider Fallback</div>
                  <Badge tone={health.data.policy.allow_cross_provider_fallback ? "green" : "neutral"}>
                    {health.data.policy.allow_cross_provider_fallback ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <div>
                  <div className="text-muted-foreground">Fallback on QA Failure</div>
                  <Badge tone={health.data.policy.fallback_on_qa_failure ? "green" : "neutral"}>
                    {health.data.policy.fallback_on_qa_failure ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
              </PanelBody>
            </Panel>
          </div>
        </div>
      ) : null}
    </>
  );
}
