"use client";

import Link from "next/link";
import { AlertCircle, ArrowRight, Shield } from "lucide-react";

import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export default function ContributePage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">Contribute</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Help support the translation capacity of this platform.
          Public provider/API key contribution is intentionally gated until the secure backend lifecycle exists.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="space-y-6">
          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">What Contribution Means</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3 text-sm text-muted-foreground">
              <p>
                By contributing a provider API key, you help the platform translate more chapters for the community.
                Your key will be used exclusively for translation tasks, respecting rate limits and usage quotas.
              </p>
              <p>
                <strong className="text-foreground">Important:</strong> This feature requires a future gated backend.
                Do not submit API keys here. Real credential handling must happen through secure backend support.
              </p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Security & Privacy</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <div className="flex items-start gap-3">
                <Shield className="mt-0.5 h-5 w-5 shrink-0 text-accent" />
                <div className="space-y-2 text-sm text-muted-foreground">
                  <p>
                    The platform takes credential security seriously. When the backend contribution lifecycle is implemented,
                    keys will be encrypted at rest and masked in all UI displays.
                  </p>
                  <p>
                    The goal is for you to retain full control to pause or remove contributed keys at any time from your account dashboard.
                  </p>
                </div>
              </div>
            </PanelBody>
          </Panel>
        </div>

        <aside className="space-y-4">
          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Provider Selection</PanelTitle>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <select
                className="h-9 w-full rounded-md border border-border bg-muted px-3 text-sm disabled:opacity-50"
                disabled
                aria-label="Provider selection (disabled pending backend support)"
              >
                <option>Select a provider...</option>
                <option>Gemini</option>
                <option>OpenAI</option>
              </select>
              <p className="text-xs text-muted-foreground">
                Provider selection and key submission are disabled until backend support is available.
              </p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelBody className="p-4">
              <Link
                href="/account/contributions"
                className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                View Contribution Dashboard
                <ArrowRight className="h-4 w-4" />
              </Link>
            </PanelBody>
          </Panel>
        </aside>
      </div>
    </main>
  );
}
