"use client";

import { AuthGate } from "@/components/public/auth-gate";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";

export default function AccountSettingsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-normal">Account Settings</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Account controls are scaffolded while backend account-management contracts remain limited.
        </p>
      </header>
      <AuthGate>
        <div className="space-y-4">
          {[
            ["Profile", "Profile editing is not connected yet."],
            ["Linked login methods", "Google OAuth is the current public login path."],
            ["API key contribution settings", "Contribution settings remain gated and unavailable."],
            ["Privacy", "Privacy preferences are pending a public account contract."],
            ["Delete account", "Account deletion requires backend support and confirmation flows before it can be enabled."],
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
