"use client";

import Link from "next/link";
import { AlertTriangle, ArrowRight, Lock, User } from "lucide-react";

import { AuthGate } from "@/components/public/auth-gate";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { Button } from "@/components/ui/button";

export default function AccountSettingsPage() {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">Account Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Manage your account preferences. Some settings are not yet connected to the backend.
        </p>
      </header>

      <AuthGate>
        <div className="space-y-6">
          <Panel>
            <PanelHeader>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-muted-foreground" />
                <PanelTitle className="font-literary">Profile</PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody>
              <p className="text-sm text-muted-foreground">Profile editing is not available yet.</p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Linked Login Methods</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <p className="text-sm text-muted-foreground">Google OAuth is the current login method for public accounts.</p>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">API Key Contribution Settings</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">Contribution settings remain gated and unavailable.</p>
                <Link
                  href="/account/contributions"
                  className="inline-flex items-center gap-2 text-sm text-accent hover:text-foreground"
                >
                  View Dashboard
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Privacy</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <p className="text-sm text-muted-foreground">Privacy preferences are not yet available.</p>
            </PanelBody>
          </Panel>

          <Panel className="border-destructive/30">
            <PanelHeader>
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-4 w-4 text-destructive" />
                <PanelTitle className="font-literary text-destructive">Delete Account</PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <p className="text-sm text-muted-foreground">
                Account deletion requires backend support and confirmation flows before it can be enabled.
                This action is permanent and cannot be undone.
              </p>
              <Button variant="destructive" disabled aria-label="Delete account (disabled pending backend support)">
                <Lock className="mr-2 h-4 w-4" />
                Delete Account (Unavailable)
              </Button>
            </PanelBody>
          </Panel>
        </div>
      </AuthGate>
    </main>
  );
}
