"use client";

import { useQuery } from "@tanstack/react-query";
import { Key } from "lucide-react";

import { adminApi } from "@/lib/api";
import type { ProviderCredential } from "@/lib/api-types";

/**
 * CredentialStatusIndicator — summarizes the active Provider_Credential status.
 * Sources from Admin_API via adminApi.providerCredential().
 * Never renders the raw credential value.
 * Requirements: 9.11
 */
export function CredentialStatusIndicator() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "provider-credential"],
    queryFn: () => adminApi.providerCredential(),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground" title="Loading provider status">
        <Key className="h-3.5 w-3.5 animate-pulse" />
        <span>Loading…</span>
      </div>
    );
  }

  if (isError || !data?.configured) {
    return (
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground" title="No active provider credential">
        <Key className="h-3.5 w-3.5 opacity-50" />
        <span>No provider credential</span>
      </div>
    );
  }

  const cred = data as ProviderCredential;
  const statusColor =
    cred.validation_status === "Working"
      ? "text-green-600 dark:text-green-400"
      : cred.validation_status === "Failed"
        ? "text-red-600 dark:text-red-400"
        : cred.validation_status === "Checking"
          ? "text-amber-600 dark:text-amber-400"
          : "text-muted-foreground";

  const statusLabel =
    cred.validation_status === "Working"
      ? "Active"
      : cred.validation_status === "Failed"
        ? "Failed"
        : cred.validation_status === "Checking"
          ? "Checking"
          : "Unchecked";

  return (
    <div className="flex items-center gap-1.5 text-xs" title={cred.masked_token}>
      <Key className={`h-3.5 w-3.5 ${statusColor}`} />
      <span className={statusColor}>
        {cred.provider} ({statusLabel})
      </span>
    </div>
  );
}