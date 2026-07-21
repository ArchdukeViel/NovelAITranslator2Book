"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Suspense } from "react";

import { OwnerLoginView } from "@/components/admin/owner-login-view";
import { adminAuth } from "@/lib/api";
import { ApiError } from "@/lib/api";

interface AdminAuthGuardProps {
  children: React.ReactNode;
}

/**
 * AdminAuthGuard — presentation-only auth gate for the Admin_Workspace.
 * - Probes GET /api/auth/me via adminAuth.me()
 * - If unauthenticated or not owner: renders OwnerLoginView
 * - On 401/403 from any adminApi call: treats session as ended, shows OwnerLoginView
 * - Does NOT read/delete cookies directly (browser/backend manages Session_Cookie)
 * - Backend require_role("owner") is the actual security boundary (Req 4.8)
 */
export function AdminAuthGuard({ children }: AdminAuthGuardProps) {
  const router = useRouter();
  const [showLogin, setShowLogin] = useState(true);
  const [authChecked, setAuthChecked] = useState(false);
  const [isOwner, setIsOwner] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function checkAuth() {
      try {
        const user = await adminAuth.me();
        if (mounted) {
          setIsOwner(user.is_owner === true);
          setShowLogin(!user.is_owner);
        }
      } catch (error) {
        if (mounted) {
          // 401/403 or network error -> treat as unauthenticated
          setIsOwner(false);
          setShowLogin(true);
        }
      } finally {
        if (mounted) {
          setAuthChecked(true);
        }
      }
    }

    checkAuth();

    return () => {
      mounted = false;
    };
  }, []);

  // Expose a function to trigger re-auth check (called on 401/403 from adminApi)
  const triggerReauth = useCallback(() => {
    setShowLogin(true);
    setIsOwner(false);
    setAuthChecked(false);
  }, []);

  // Make triggerReauth globally accessible for adminApi error handling
  useEffect(() => {
    (window as Window & { __adminReauth?: () => void }).__adminReauth = triggerReauth;
    return () => {
      delete (window as Window & { __adminReauth?: () => void }).__adminReauth;
    };
  }, [triggerReauth]);

  if (!authChecked) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  if (showLogin || !isOwner) {
    return (
      <OwnerLoginView onSuccess={() => {
        setIsOwner(true);
        setShowLogin(false);
        router.refresh();
      }} />
    );
  }

  return <>{children}</>;
}

/**
 * Hook for admin pages to detect 401/403 and trigger re-auth.
 * Use in mutation onError handlers.
 */
export function useAdminReauth() {
  return () => {
    const reauth = (window as Window & { __adminReauth?: () => void }).__adminReauth;
    if (reauth) reauth();
  };
}

/**
 * Wrapper to make adminApi calls that auto-handle 401/403.
 * Not currently used but available for future.
 */
export function withReauth<T extends (...args: unknown[]) => Promise<unknown>>(
  fn: T
): T {
  return (async (...args: unknown[]) => {
    try {
      return await fn(...args);
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        const reauth = (window as Window & { __adminReauth?: () => void }).__adminReauth;
        if (reauth) reauth();
      }
      throw error;
    }
  }) as T;
}
