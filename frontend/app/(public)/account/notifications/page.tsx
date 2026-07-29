"use client";

import Link from "next/link";
import { ArrowLeft, Loader2 } from "lucide-react";

import { AuthGate } from "@/components/public/auth-gate";
import { NotificationList } from "@/components/public/notification-list";
import { NotificationPreferences } from "@/components/public/notification-preferences";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import {
  useArchiveNotification,
  useNotifications,
  useReadAllNotifications,
  useReadNotification,
} from "@/hooks/public";

export default function NotificationsPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8 sm:px-6 lg:px-8">
      <Link
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors"
        href="/home"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Home
      </Link>

      <header className="mt-6 mb-8">
        <h1 className="text-3xl font-semibold tracking-normal font-literary">Notifications</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Translation updates and review requests for your novels.
        </p>
      </header>

      <AuthGate>
        <div className="space-y-6">
          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Activity</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <NotificationsSection />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHeader>
              <PanelTitle className="font-literary">Delivery Preferences</PanelTitle>
            </PanelHeader>
            <PanelBody>
              <NotificationPreferences />
            </PanelBody>
          </Panel>
        </div>
      </AuthGate>
    </main>
  );
}

function NotificationsSection() {
  const { data, isLoading, isError, refetch } = useNotifications({ page_size: 50 });
  const read = useReadNotification();
  const readAll = useReadAllNotifications();
  const archive = useArchiveNotification();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden="true" />
        <span className="sr-only">Loading notifications...</span>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-md border border-destructive/40 bg-destructive/5 p-4">
        <p className="text-sm text-destructive">Could not load notifications.</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="mt-2 text-xs font-medium text-destructive underline"
        >
          Try again
        </button>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <NotificationList
      items={items}
      isReadingAll={readAll.isPending}
      onRead={(id) => read.mutate(id)}
      onArchive={(id) => archive.mutate(id)}
      onReadAll={() => readAll.mutate()}
    />
  );
}
