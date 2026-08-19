"use client";

import Link from "next/link";
import {
  Bell,
  BookOpen,
  HeartHandshake,
  Lock,
  Palette,
  Shield,
  User,
} from "lucide-react";

import { AuthGate } from "@/components/public/auth-gate";
import {
  Panel,
  PanelBody,
  PanelHeader,
  PanelTitle,
} from "@/components/ui/panel";
import { PublicThemeSegmentedControl } from "@/components/public/public-theme-toggle";
import { usePublicAuth } from "@/hooks/public/use-auth";

export default function AccountSettingsPage() {
  const { user } = usePublicAuth();

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">
          Account Settings
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Manage your reader preferences, appearance, notification channels, and
          contributions.
        </p>
      </header>

      <AuthGate>
        <div className="space-y-6">
          {/* Profile Overview */}
          <Panel>
            <PanelHeader>
              <div className="flex items-center gap-2">
                <User className="h-4 w-4 text-primary" />
                <PanelTitle className="font-literary">Profile</PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-border/40 pb-3">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    Email Address
                  </p>
                  <p className="text-sm font-semibold text-foreground">
                    {user?.email ?? "Reader Account"}
                  </p>
                </div>
                <span className="inline-flex items-center rounded-full bg-muted px-2.5 py-0.5 text-xs font-medium text-foreground">
                  Role: {user?.role ?? "user"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Profile editing is not available yet. Account identity is
                managed via authenticated sessions.
              </p>
            </PanelBody>
          </Panel>

          {/* Appearance & Display */}
          <Panel>
            <PanelHeader>
              <div className="flex items-center gap-2">
                <Palette className="h-4 w-4 text-primary" />
                <PanelTitle className="font-literary">
                  Appearance & Theme
                </PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Choose your default interface theme mode across all pages.
              </p>
              <div className="max-w-xs">
                <PublicThemeSegmentedControl />
              </div>
            </PanelBody>
          </Panel>

          {/* Reading Preferences Shortcut */}
          <Panel>
            <PanelHeader>
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                <PanelTitle className="font-literary">
                  Reading Defaults
                </PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody className="space-y-2">
              <p className="text-xs text-muted-foreground">
                Reader typography (font size, serif style, line spacing,
                margins, paper tints) is saved per-device directly in the
                chapter reader drawer.
              </p>
              <Link
                href="/browse-novels"
                className="inline-flex items-center gap-1.5 text-xs font-medium text-primary underline hover:text-foreground"
              >
                Open a novel to adjust reading settings
              </Link>
            </PanelBody>
          </Panel>

          {/* Notifications & API Contributions */}
          <div className="grid gap-4 sm:grid-cols-2">
            <Panel>
              <PanelHeader>
                <div className="flex items-center gap-2">
                  <Bell className="h-4 w-4 text-primary" />
                  <PanelTitle className="font-literary text-sm">
                    Notifications
                  </PanelTitle>
                </div>
              </PanelHeader>
              <PanelBody className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Configure in-app and email delivery options for chapter
                  updates.
                </p>
                <Link
                  href="/account/notifications"
                  className="inline-block text-xs font-medium text-primary underline hover:text-foreground"
                >
                  Manage notifications →
                </Link>
              </PanelBody>
            </Panel>

            <Panel>
              <PanelHeader>
                <div className="flex items-center gap-2">
                  <HeartHandshake className="h-4 w-4 text-primary" />
                  <PanelTitle className="font-literary text-sm">
                    API Key Contributions
                  </PanelTitle>
                </div>
              </PanelHeader>
              <PanelBody className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  Contribute Google Gemini API keys to increase translation
                  speeds.
                </p>
                <Link
                  href="/account/contributions"
                  className="inline-block text-xs font-medium text-primary underline hover:text-foreground"
                >
                  View Dashboard →
                </Link>
              </PanelBody>
            </Panel>
          </div>

          {/* Security & Danger Zone */}
          <Panel className="border-destructive/30">
            <PanelHeader>
              <div className="flex items-center gap-2">
                <Shield className="h-4 w-4 text-destructive" />
                <PanelTitle className="font-literary text-destructive">
                  Account Security
                </PanelTitle>
              </div>
            </PanelHeader>
            <PanelBody className="space-y-3">
              <p className="text-xs text-muted-foreground">
                Account deletion is not available yet. This action is permanent
                and cannot be undone.
              </p>
              <button
                type="button"
                disabled
                className="inline-flex h-8 items-center justify-center rounded-md border border-destructive/40 bg-destructive/10 px-3 text-xs font-medium text-destructive opacity-50 cursor-not-allowed"
                aria-label="Delete account (disabled)"
              >
                Delete Account (Unavailable)
              </button>
            </PanelBody>
          </Panel>
        </div>
      </AuthGate>
    </main>
  );
}
