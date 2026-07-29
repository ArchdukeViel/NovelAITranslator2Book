"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { userNotificationApi } from "@/lib/public-api";
import type {
  NotificationItem,
  NotificationListParams,
  NotificationListResponse,
  NotificationPreference,
  NotificationPreferenceUpdate,
} from "@/lib/public-types";
import { usePublicAuth } from "./use-auth";

const notificationKeys = {
  all: ["user-notifications"] as const,
  list: (params: NotificationListParams) => [...notificationKeys.all, "list", params] as const,
  unreadCount: ["user-notifications", "unread-count"] as const,
  preferences: ["user-notifications", "preferences"] as const,
};

function useCanUseNotifications() {
  const { isAuthenticated, isPending } = usePublicAuth();
  return {
    canUseNotifications: isAuthenticated,
    authPending: isPending,
  };
}

export function useNotifications(params: NotificationListParams = {}) {
  const { canUseNotifications, authPending } = useCanUseNotifications();
  return useQuery<NotificationListResponse>({
    queryKey: notificationKeys.list(params),
    queryFn: () => userNotificationApi.list(params),
    enabled: canUseNotifications && !authPending,
    staleTime: 30_000,
  });
}

export function useUnreadCount() {
  const { canUseNotifications, authPending } = useCanUseNotifications();
  return useQuery<number>({
    queryKey: notificationKeys.unreadCount,
    queryFn: () => userNotificationApi.unreadCount().then((r) => r.unread_count),
    enabled: canUseNotifications && !authPending,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useNotificationPreferences() {
  const { canUseNotifications, authPending } = useCanUseNotifications();
  return useQuery<NotificationPreference[]>({
    queryKey: notificationKeys.preferences,
    queryFn: () => userNotificationApi.getPreferences(),
    enabled: canUseNotifications && !authPending,
    staleTime: 60_000,
  });
}

export function useReadAllNotifications() {
  const queryClient = useQueryClient();
  const { canUseNotifications } = useCanUseNotifications();
  return useMutation({
    mutationFn: () => {
      if (!canUseNotifications) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userNotificationApi.readAll();
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
      queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount });
      return data.updated;
    },
  });
}

export function useArchiveNotification() {
  const queryClient = useQueryClient();
  const { canUseNotifications } = useCanUseNotifications();
  return useMutation({
    mutationFn: (notificationId: number) => {
      if (!canUseNotifications) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userNotificationApi.archive(notificationId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
      queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount });
    },
  });
}

export function useReadNotification() {
  const queryClient = useQueryClient();
  const { canUseNotifications } = useCanUseNotifications();
  return useMutation({
    mutationFn: (notificationId: number) => {
      if (!canUseNotifications) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userNotificationApi.read(notificationId);
    },
    onMutate: async (notificationId) => {
      await queryClient.cancelQueries({ queryKey: notificationKeys.all });
      const previous = queryClient.getQueryData<NotificationListResponse>(
        notificationKeys.list({})
      );
      queryClient.setQueryData<NotificationListResponse | undefined>(
        notificationKeys.list({}),
        (old) => {
          if (!old) return old;
          return {
            ...old,
            items: old.items.map((n) =>
              n.id === notificationId ? { ...n, status: "read" as const, read_at: new Date().toISOString() } : n
            ),
          };
        }
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(notificationKeys.list({}), context.previous);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.unreadCount });
    },
  });
}

export function useUpdateNotificationPreference() {
  const queryClient = useQueryClient();
  const { canUseNotifications } = useCanUseNotifications();
  return useMutation({
    mutationFn: (update: NotificationPreferenceUpdate) => {
      if (!canUseNotifications) {
        return Promise.reject(new Error("Sign in required."));
      }
      return userNotificationApi.updatePreference(update);
    },
    onMutate: async (update) => {
      await queryClient.cancelQueries({ queryKey: notificationKeys.preferences });
      const previous = queryClient.getQueryData<NotificationPreference[]>(notificationKeys.preferences);
      queryClient.setQueryData<NotificationPreference[] | undefined>(
        notificationKeys.preferences,
        (old) => {
          if (!old) return old;
          return old.map((p) =>
            p.event_type === update.event_type && p.channel === update.channel
              ? { ...p, enabled: update.enabled }
              : p
          );
        }
      );
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(notificationKeys.preferences, context.previous);
      }
    },
  });
}

export function severityBadgeClass(severity: NotificationItem["severity"]): string {
  const base = "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium";
  switch (severity) {
    case "error":
      return `${base} bg-destructive/10 text-destructive border border-destructive/20`;
    case "warning":
      return `${base} bg-yellow/10 text-yellow-700 dark:text-yellow-300 border border-yellow/20`;
    case "success":
      return `${base} bg-green/10 text-green-700 dark:text-green-300 border border-green/20`;
    case "info":
    default:
      return `${base} bg-blue/10 text-blue-700 dark:text-blue-300 border border-blue/20`;
  }
}

export function eventTypeLabel(eventType: NotificationItem["event_type"]): string {
  switch (eventType) {
    case "translation.completed":
      return "Translation Completed";
    case "translation.failed":
      return "Translation Failed";
    case "translation.requires_review":
      return "Translation Requires Review";
    default:
      return eventType;
  }
}

export function formatNotificationDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function isSafeInternalActionUrl(url: string | null): boolean {
  if (!url) return false;
  if (!url.startsWith("/")) return false;
  if (url.startsWith("//")) return false;
  try {
    new URL(url, "http://novelai.local");
    return true;
  } catch {
    return false;
  }
}

export function channelLabel(channel: NotificationPreference["channel"]): string {
  return channel === "email" ? "Email" : "In-app";
}

export function eventTypeKey(eventType: NotificationPreference["event_type"]): string {
  switch (eventType) {
    case "translation.completed":
      return "Translation completed";
    case "translation.failed":
      return "Translation failed";
    case "translation.requires_review":
      return "Translation requires review";
    default:
      return eventType;
  }
}
