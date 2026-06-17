"use client";

import Link from "next/link";
import { ArrowRight, Lock, ShieldAlert } from "lucide-react";

import { AuthGate } from "@/components/public/auth-gate";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export default function AccountContributionsPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">Contribution Dashboard</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Manage your provider key contributions. Credential handling features are not yet available.
        </p>
      </header>

      <AuthGate>
        <div className="space-y-6">
          <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4">
            <div className="flex items-start gap-3">
              <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
              <div className="space-y-1 text-sm text-amber-800 dark:text-amber-200">
                <p className="font-medium">Coming Soon</p>
                <p>
                  API key contribution features require additional security infrastructure and are not yet available.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {[
              {
                title: "Key Health",
                body: "Credential validation tracking is not yet available.",
                icon: null,
              },
              {
                title: "Usage Stats",
                body: "Usage tracking is not connected yet.",
                icon: null,
              },
              {
                title: "Pause Contributed Keys",
                body: "Pause controls require credential ownership support that is not yet available.",
                icon: <Lock className="h-4 w-4 text-muted-foreground" />,
              },
              {
                title: "Remove Contributed Keys",
                body: "Removal controls are not yet available.",
                icon: <Lock className="h-4 w-4 text-muted-foreground" />,
              },
            ].map(({ title, body, icon }) => (
              <Panel key={title}>
                <PanelHeader>
                  <div className="flex items-center gap-2">
                    {icon}
                    <PanelTitle className="font-literary">{title}</PanelTitle>
                  </div>
                </PanelHeader>
                <PanelBody>
                  <p className="text-sm text-muted-foreground">{body}</p>
                </PanelBody>
              </Panel>
            ))}
          </div>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Learn More About Contributing</PanelTitle>
            </PanelHeader>
            <PanelBody className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Visit the main contribution page to understand how provider keys help the platform.
              </p>
              <Link
                href="/contribute"
                className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                View Contribution Info
                <ArrowRight className="h-4 w-4" />
              </Link>
            </PanelBody>
          </Panel>
        </div>
      </AuthGate>
    </main>
  );
}
