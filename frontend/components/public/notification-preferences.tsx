"use client";

import { useState } from "react";
import { Loader2, Mail, Bell } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  useNotificationPreferences,
  useUpdateNotificationPreference,
  channelLabel,
  eventTypeKey,
} from "@/hooks/public/use-notifications";
import type { NotificationPreference, NotificationChannel } from "@/lib/public-types";

interface NotificationPreferencesProps {
  className?: string;
}

const channelIcons: Record<NotificationChannel, React.ComponentType<{ className?: string }>> = {
  in_app: Bell,
  email: Mail,
};

export function NotificationPreferences({ className }: NotificationPreferencesProps) {
  const { data: preferences, isLoading, isError, refetch } = useNotificationPreferences();
  const updatePreference = useUpdateNotificationPreference();
  const [optimisticUpdates, setOptimisticUpdates] = useState<
    Record<string, { enabled: boolean; saving: boolean }>
  >({});

  const getOptimisticValue = (eventType: string, channel: NotificationChannel): boolean => {
    const key = `${eventType}:${channel}`;
    if (optimisticUpdates[key]?.enabled !== undefined) {
      return optimisticUpdates[key].enabled;
    }
    const pref = preferences?.find((p) => p.event_type === eventType && p.channel === channel);
    return pref?.enabled ?? true;
  };

  const isSaving = (eventType: string, channel: NotificationChannel): boolean => {
    const key = `${eventType}:${channel}`;
    return optimisticUpdates[key]?.saving ?? false;
  };

  const handleToggle = async (
    eventType: NotificationPreference["event_type"],
    channel: NotificationChannel,
    newEnabled: boolean
  ) => {
    const key = `${eventType}:${channel}`;
    setOptimisticUpdates((prev) => ({ ...prev, [key]: { enabled: newEnabled, saving: true } }));
    try {
      await updatePreference.mutateAsync({ event_type: eventType, channel, enabled: newEnabled });
      setOptimisticUpdates((prev) => ({ ...prev, [key]: { enabled: newEnabled, saving: false } }));
    } catch {
      const prevEnabled = getOptimisticValue(eventType, channel);
      setOptimisticUpdates((prev) => ({ ...prev, [key]: { enabled: prevEnabled, saving: false } }));
      await refetch();
    }
  };

  const eventTypes: NotificationPreference["event_type"][] = [
    "translation.completed",
    "translation.failed",
    "translation.requires_review",
  ];
  const channels: NotificationChannel[] = ["in_app", "email"];

  if (isLoading) {
    return (
      <div className={cn("space-y-4", className)}>
        {[...Array(3)].map((_, i) => (
          <div key={i} className="flex items-center justify-between p-4 animate-pulse">
            <div className="h-4 bg-muted rounded w-1/4" />
            <div className="h-6 bg-muted rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className={cn("text-center py-8 text-sm text-destructive", className)}>
        Failed to load notification preferences.
      </div>
    );
  }

  if (!preferences || preferences.length === 0) {
    return (
      <div className={cn("text-center py-8 text-sm text-muted-foreground", className)}>
        No notification preferences available.
      </div>
    );
  }

  return (
    <div className={cn("space-y-4", className)}>
      <div className="grid grid-cols-[auto_1fr_1fr] gap-4 text-sm font-medium text-muted-foreground">
        <div className="px-2">Event</div>
        <div>In-app</div>
        <div>Email</div>
      </div>

      {eventTypes.map((eventType) => {
        const prefs = channels.map((channel) =>
          preferences.find((p) => p.event_type === eventType && p.channel === channel)
        );
        const inAppEnabled = getOptimisticValue(eventType, "in_app");
        const emailEnabled = getOptimisticValue(eventType, "email");

        return (
          <div
            key={eventType}
            className="grid grid-cols-[auto_1fr_1fr] gap-4 items-center p-3 rounded-lg border border-border/50 bg-card/50"
          >
            <div className="px-2 text-sm font-medium">{eventTypeKey(eventType)}</div>
            {channels.map((channel, idx) => {
              const pref = prefs[idx];
              const isEnabled = channel === "in_app" ? inAppEnabled : emailEnabled;
              const saving = isSaving(eventType, channel);
              const ChannelIcon = channelIcons[channel];

              return (
                <div key={channel} className="flex items-center justify-center">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isEnabled}
                      disabled={saving}
                      onChange={(e) => handleToggle(eventType, channel, e.target.checked)}
                      className="h-4 w-4 rounded border-input text-primary focus:ring-primary"
                      aria-label={`${channelLabel(channel)} notifications for ${eventTypeKey(eventType)}`}
                    />
                    {saving && (
                      <Loader2
                        className="h-4 w-4 animate-spin text-muted-foreground"
                        data-testid="preference-save-spinner"
                      />
                    )}
                    {!saving && <ChannelIcon className="h-4 w-4 text-muted-foreground" />}
                  </label>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
