"use client";

import { useQuery } from "@tanstack/react-query";
import { User } from "lucide-react";

import { adminAuth } from "@/lib/api";

/**
 * OwnerSessionIndicator — displays the current authenticated owner identity.
 * Reads from GET /api/auth/me via adminAuth.me().
 * Requirements: 4.5
 */
export function OwnerSessionIndicator() {
  const { data, isLoading } = useQuery({
    queryKey: ["auth", "me"],
    queryFn: () => adminAuth.me(),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <User className="h-4 w-4" />
        <span>…</span>
      </div>
    );
  }

  if (!data?.is_owner || !data?.email) {
    return null;
  }

  return (
    <div className="flex items-center gap-2 text-sm">
      <User className="h-4 w-4 text-muted-foreground" />
      <span className="max-w-[160px] truncate" title={data.email}>
        {data.email}
      </span>
    </div>
  );
}