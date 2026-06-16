"use client";

import { AuthGate } from "@/components/public/auth-gate";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export default function AccountContributionsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-normal">Contribution Dashboard</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Provider key contribution remains unavailable until the secure backend lifecycle exists.
        </p>
      </header>
      <AuthGate>
        <div className="grid gap-4 md:grid-cols-2">
          {[
            ["Key health", "Unavailable until contributed credential validation is implemented."],
            ["Usage stats", "No public usage ledger is connected yet."],
            ["Pause contributed keys", "Pause controls require real credential ownership and revocation APIs."],
            ["Remove contributed keys", "Removal controls are intentionally disabled in this phase."],
          ].map(([title, body]) => (
            <Panel key={title}>
              <PanelHeader>
                <PanelTitle>{title}</PanelTitle>
              </PanelHeader>
              <PanelBody>
                <p className="text-sm text-muted-foreground">{body}</p>
              </PanelBody>
            </Panel>
          ))}
        </div>
      </AuthGate>
    </main>
  );
}
