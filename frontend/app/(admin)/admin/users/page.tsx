"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Search, UsersIcon } from "lucide-react";
import Link from "next/link";
import * as React from "react";

import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { StatusBadge } from "@/components/admin/status-badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";
import { adminApi } from "@/lib/api";
import type { UserListFilters } from "@/lib/api-types";

const ROLE_OPTIONS = [
  { value: "", label: "All roles" },
  { value: "user", label: "User" },
  { value: "guest", label: "Guest" },
  { value: "owner", label: "Owner" },
] as const;

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "active", label: "Active" },
  { value: "disabled", label: "Disabled" },
] as const;

const PAGE_SIZE = 50;

export default function AdminUsersPage() {
  const [search, setSearch] = React.useState("");
  const [role, setRole] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [page, setPage] = React.useState(1);

  const filters: UserListFilters = {
    page,
    page_size: PAGE_SIZE,
  };
  if (role) filters.role = role;
  if (status === "active") filters.is_active = true;
  if (status === "disabled") filters.is_active = false;
  if (search.trim()) filters.search = search.trim();

  const query = useQuery({
    queryKey: ["admin-users", filters],
    queryFn: () => adminApi.listUsers(filters),
  });

  const data = query.data;
  const totalPages = data ? Math.ceil(data.total / data.page_size) : 1;
  const showingFrom = data ? (data.page - 1) * data.page_size + 1 : 0;
  const showingTo = data ? Math.min(data.page * data.page_size, data.total) : 0;

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
  }

  return (
    <>
      <PageHeading
        title="Users"
        description="Manage registered user accounts. Search, filter, and perform account administration."
      />

      {/* Filters */}
      <Panel className="mb-4">
        <PanelBody>
          <form onSubmit={handleSearch} className="flex flex-wrap items-end gap-3">
            <div className="min-w-[200px] flex-1">
              <label htmlFor="user-search" className="text-xs font-medium text-muted-foreground">
                Search
              </label>
              <div className="relative mt-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  id="user-search"
                  className="block w-full rounded-md border bg-background py-2 pl-8 pr-3 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                  placeholder="Email or display name..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
            <div>
              <label htmlFor="role-filter" className="text-xs font-medium text-muted-foreground">
                Role
              </label>
              <select
                id="role-filter"
                className="mt-1 block rounded-md border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                value={role}
                onChange={(e) => {
                  setRole(e.target.value);
                  setPage(1);
                }}
              >
                {ROLE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="status-filter" className="text-xs font-medium text-muted-foreground">
                Status
              </label>
              <select
                id="status-filter"
                className="mt-1 block rounded-md border bg-background px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setPage(1);
                }}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <Button type="submit" variant="secondary" size="sm">
              Search
            </Button>
          </form>
        </PanelBody>
      </Panel>

      {/* Error */}
      {query.isError && (
        <ErrorBanner error={query.error} fallback="Failed to load users." className="mb-4 rounded-md border" />
      )}

      {/* Table */}
      <Panel>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b bg-muted/50">
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Email</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Display Name</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Role</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Auth</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Created</th>
                <th className="px-4 py-3 text-left font-medium text-muted-foreground">Last Login</th>
              </tr>
            </thead>
            <tbody>
              {query.isLoading ? (
                <LoadingRows colSpan={7} label="Loading users..." rows={5} />
              ) : !data || data.items.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <EmptyState
                      title="No users found"
                      description={
                        search.trim() || role || status
                          ? "Try adjusting your search or filters."
                          : "No users have been registered yet."
                      }
                    />
                  </td>
                </tr>
              ) : (
                data.items.map((user) => (
                  <tr key={user.id} className="border-b last:border-0 hover:bg-muted/30">
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/users/${user.id}`}
                        className="font-medium text-primary hover:underline"
                      >
                        {user.email || <span className="italic text-muted-foreground">no email</span>}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {user.display_name || <span className="italic">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={user.role} />
                    </td>
                    <td className="px-4 py-3">
                      {user.is_active ? (
                        <StatusBadge status="active" />
                      ) : (
                        <StatusBadge status="disabled" />
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {user.auth_provider || "local"}
                      {user.email_verified ? " ✓" : ""}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {user.created_at
                        ? new Date(user.created_at).toLocaleDateString()
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {user.last_login_at
                        ? new Date(user.last_login_at).toLocaleDateString()
                        : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
            <span>
              Showing {showingFrom}–{showingTo} of {data.total}
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                aria-label="Previous page"
              >
                <ChevronLeft className="h-4 w-4" />
                Prev
              </Button>
              <span className="px-2 text-xs">
                Page {data.page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
                aria-label="Next page"
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Panel>
    </>
  );
}
