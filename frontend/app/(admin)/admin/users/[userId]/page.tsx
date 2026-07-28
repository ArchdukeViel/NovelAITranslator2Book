"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Ban, CheckCircle, RefreshCw, ShieldOff, UserCog } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import * as React from "react";

import { ErrorBanner } from "@/components/admin/error-banner";
import { PageHeading } from "@/components/admin/page-heading";
import { ReasonDialog } from "@/components/admin/reason-dialog";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminApi, apiErrorInlineMessage } from "@/lib/api";

const ROLE_OPTIONS = [
  { value: "user", label: "User" },
  { value: "guest", label: "Guest" },
] as const;

export default function AdminUserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const userId = Number(params.userId);
  const queryKey = React.useMemo(() => ["admin-user", userId], [userId]);

  const query = useQuery({
    queryKey,
    queryFn: () => adminApi.getUser(userId),
    enabled: Number.isFinite(userId),
  });

  const invalidate = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey });
  }, [queryClient, queryKey]);

  // ── mutation state ──────────────────────────────────────────────────
  const [activeDialog, setActiveDialog] = React.useState<"disable" | "enable" | "role" | "revoke" | null>(null);
  const [targetRole, setTargetRole] = React.useState<string>("user");
  const [error, setError] = React.useState<unknown>(null);

  const activeMut = useMutation({
    mutationFn: (payload: { is_active: boolean; reason: string }) =>
      adminApi.updateUserActive(userId, payload),
    onSuccess: () => {
      setActiveDialog(null);
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err),
  });

  const roleMut = useMutation({
    mutationFn: (payload: { role: string; reason: string }) =>
      adminApi.updateUserRole(userId, payload),
    onSuccess: () => {
      setActiveDialog(null);
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err),
  });

  const revokeMut = useMutation({
    mutationFn: (payload: { reason: string }) =>
      adminApi.revokeUserSessions(userId, payload),
    onSuccess: () => {
      setActiveDialog(null);
      setError(null);
      invalidate();
    },
    onError: (err) => setError(err),
  });

  // ── derived state ────────────────────────────────────────────────────
  const user = query.data;
  const isOwner = user?.role === "owner";
  const isDisabled = user ? !user.is_active : false;
  const loading = query.isLoading;

  if (!Number.isFinite(userId)) {
    return (
      <>
        <PageHeading title="Invalid User" />
        <p className="text-sm text-muted-foreground">Invalid user ID.</p>
        <Button variant="outline" size="sm" className="mt-4" onClick={() => router.push("/admin/users")}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Users
        </Button>
      </>
    );
  }

  if (query.isError) {
    const errMsg = query.error instanceof Error ? query.error.message : "User not found.";
    return (
      <>
        <PageHeading title="Error" />
        <ErrorBanner error={query.error} fallback="Failed to load user." className="mb-4 rounded-md border" />
        <Button variant="outline" size="sm" onClick={() => router.push("/admin/users")}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Users
        </Button>
      </>
    );
  }

  if (loading || !user) {
    return (
      <>
        <PageHeading title="Loading..." />
        <div className="h-32 animate-pulse rounded-lg bg-muted" />
      </>
    );
  }

  // ── helpers ──────────────────────────────────────────────────────────
  function formatTimestamp(iso: string | null): string {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleString();
  }

  function actionError(): unknown {
    if (activeMut.isError) return activeMut.error;
    if (roleMut.isError) return roleMut.error;
    if (revokeMut.isError) return revokeMut.error;
    return null;
  }

  function actionPending(): boolean {
    return activeMut.isPending || roleMut.isPending || revokeMut.isPending;
  }

  return (
    <>
      <div className="mb-4">
        <Button variant="ghost" size="sm" onClick={() => router.push("/admin/users")}>
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to Users
        </Button>
      </div>

      <PageHeading
        title={user.display_name || user.email || `User #${user.id}`}
        description={`User ID: ${user.id}${user.email ? ` · ${user.email}` : ""}`}
      />

      {/* User info */}
      <div className="grid gap-5 md:grid-cols-2">
        <Panel>
          <PanelHeader>
            <PanelTitle>Account Summary</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Email</span>
              <span>{user.email || <span className="italic text-muted-foreground">none</span>}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Display Name</span>
              <span>{user.display_name || <span className="italic text-muted-foreground">—</span>}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Role</span>
              <StatusBadge status={user.role} />
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Status</span>
              {isDisabled ? <StatusBadge status="disabled" /> : <StatusBadge status="active" />}
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Auth Provider</span>
              <span>{user.auth_provider || "local"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Email Verified</span>
              <span>{user.email_verified ? "Yes" : "No"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Has Password</span>
              <span>{user.has_password ? "Yes" : "No"}</span>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Timestamps</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{formatTimestamp(user.created_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Last Login</span>
              <span>{formatTimestamp(user.last_login_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Session Revoked</span>
              <span>{formatTimestamp(user.session_revoked_at)}</span>
            </div>
          </PanelBody>
        </Panel>
      </div>

      {/* Admin metadata */}
      {isDisabled && (
        <Panel className="mt-5">
          <PanelHeader>
            <PanelTitle>Disabled Metadata</PanelTitle>
          </PanelHeader>
          <PanelBody className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">Disabled At</span>
              <span>{formatTimestamp(user.disabled_at)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Disabled By (User ID)</span>
              <span>{user.disabled_by_user_id ?? "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Disabled Reason</span>
              <span className="max-w-md text-right">{user.disabled_reason || "—"}</span>
            </div>
          </PanelBody>
        </Panel>
      )}

      {/* Actions */}
      <Panel className="mt-5">
        <PanelHeader>
          <PanelTitle>Actions</PanelTitle>
        </PanelHeader>
        <PanelBody>
          {isOwner ? (
            <p className="text-sm text-muted-foreground">
              Owner accounts cannot be modified from this panel.
            </p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {/* Disable / Enable */}
              {isDisabled ? (
                <Button
                  variant="outline"
                  onClick={() => setActiveDialog("enable")}
                  disabled={actionPending()}
                >
                  <CheckCircle className="mr-1 h-4 w-4" />
                  Enable Account
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  onClick={() => setActiveDialog("disable")}
                  disabled={actionPending()}
                >
                  <Ban className="mr-1 h-4 w-4" />
                  Disable Account
                </Button>
              )}

              {/* Role change */}
              <Button
                variant="outline"
                onClick={() => {
                  setTargetRole(user.role === "guest" ? "user" : "guest");
                  setActiveDialog("role");
                }}
                disabled={actionPending()}
              >
                <UserCog className="mr-1 h-4 w-4" />
                Change Role
              </Button>

              {/* Revoke sessions */}
              <Button
                variant="outline"
                onClick={() => setActiveDialog("revoke")}
                disabled={actionPending()}
              >
                <ShieldOff className="mr-1 h-4 w-4" />
                Revoke Sessions
              </Button>
            </div>
          )}

          {/* Audit link */}
          <div className="mt-4">
            <Link
              href={`/admin/audit?target_type=user&target_id=${user.id}`}
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              <RefreshCw className="h-3 w-3" />
              View audit events for this user
            </Link>
          </div>
        </PanelBody>
      </Panel>

      {/* Dialogs */}
      <ReasonDialog
        open={activeDialog === "disable"}
        title="Disable Account"
        description={`Are you sure you want to disable ${user.display_name || user.email || `User #${user.id}`}? They will be unable to log in or use the API.`}
        confirmLabel="Disable Account"
        destructive
        pending={activeMut.isPending}
        error={activeMut.isError ? activeMut.error : null}
        onConfirm={(reason) => activeMut.mutate({ is_active: false, reason })}
        onCancel={() => {
          setActiveDialog(null);
          activeMut.reset();
        }}
      />

      <ReasonDialog
        open={activeDialog === "enable"}
        title="Enable Account"
        description={`Re-enable ${user.display_name || user.email || `User #${user.id}`}? They will regain access to the system.`}
        confirmLabel="Enable Account"
        pending={activeMut.isPending}
        error={activeMut.isError ? activeMut.error : null}
        onConfirm={(reason) => activeMut.mutate({ is_active: true, reason })}
        onCancel={() => {
          setActiveDialog(null);
          activeMut.reset();
        }}
      />

      <ReasonDialog
        open={activeDialog === "role"}
        title="Change Role"
        description={`Change role for ${user.display_name || user.email || `User #${user.id}`} to ${targetRole === "user" ? "User" : "Guest"}.`}
        confirmLabel={`Change to ${targetRole === "user" ? "User" : "Guest"}`}
        pending={roleMut.isPending}
        error={roleMut.isError ? roleMut.error : null}
        onConfirm={(reason) => roleMut.mutate({ role: targetRole, reason })}
        onCancel={() => {
          setActiveDialog(null);
          roleMut.reset();
        }}
      />

      <ReasonDialog
        open={activeDialog === "revoke"}
        title="Revoke Sessions"
        description={`Invalidate all active sessions for ${user.display_name || user.email || `User #${user.id}`}? They will be forced to log in again.`}
        confirmLabel="Revoke Sessions"
        destructive
        pending={revokeMut.isPending}
        error={revokeMut.isError ? revokeMut.error : null}
        onConfirm={(reason) => revokeMut.mutate({ reason })}
        onCancel={() => {
          setActiveDialog(null);
          revokeMut.reset();
        }}
      />
    </>
  );
}
