"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { api } from "@/lib/api";
import type { ProviderApiKeyStatus, RuntimeStateItem } from "@/lib/api";
import { useUiStore, type ApiTokenRecord } from "@/lib/store";

function maskToken(token: string) {
  const trimmed = token.trim();
  if (trimmed.length <= 8) {
    return `${trimmed.slice(0, 2)}****`;
  }
  return `${trimmed.slice(0, 4)}****${trimmed.slice(-4)}`;
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleDateString();
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "-";
  }
  return date.toLocaleString();
}

function formatBytes(value: number) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  if (value < 1024) {
    return `${value} B`;
  }
  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function tokenValidation(status: ProviderApiKeyStatus): Partial<ApiTokenRecord> {
  return {
    validationStatus:
      status.validation_status === "working"
        ? "Working"
        : status.validation_status === "failed"
          ? "Failed"
          : "Unchecked",
    validationMessage: status.validation_message ?? null,
    validatedOn: new Date().toISOString(),
    model: status.model
  };
}

function validationTone(status: ApiTokenRecord["validationStatus"] | ProviderApiKeyStatus["validation_status"] | undefined) {
  if (status === "Working" || status === "working") {
    return "green" as const;
  }
  if (status === "Failed" || status === "failed") {
    return "red" as const;
  }
  if (status === "Checking") {
    return "amber" as const;
  }
  return "neutral" as const;
}

export default function SettingsPage() {
  const [draftToken, setDraftToken] = useState("");
  const queryClient = useQueryClient();
  const geminiStatus = useQuery({
    queryKey: ["provider-api-key", "gemini"],
    queryFn: () => api.providerApiKeyStatus("gemini")
  });
  const runtimeState = useQuery({
    queryKey: ["runtime-state"],
    queryFn: () => api.runtimeState()
  });
  const {
    addApiToken,
    apiTokens,
    applyDummyApiToken,
    removeApiToken,
    setActiveApiToken,
    updateApiTokenValidation
  } = useUiStore();
  const addToken = useMutation({
    mutationFn: (token: string) =>
      api.setProviderApiKey({
        provider: "gemini",
        api_key: token,
        apply_globally: true
      }),
    onSuccess: (status, token) => {
      addApiToken(token, tokenValidation(status));
      setDraftToken("");
      queryClient.setQueryData(["provider-api-key", "gemini"], status);
    }
  });
  const checkToken = useMutation({
    mutationFn: (entry: ApiTokenRecord) =>
      api.validateProviderApiKey({
        provider: "gemini",
        api_key: entry.token
      }),
    onMutate: (entry) => {
      updateApiTokenValidation(entry.id, {
        validationStatus: "Checking",
        validationMessage: null
      });
    },
    onSuccess: (status, entry) => {
      updateApiTokenValidation(entry.id, tokenValidation(status));
    },
    onError: (error, entry) => {
      updateApiTokenValidation(entry.id, {
        validationStatus: "Failed",
        validationMessage: error instanceof Error ? error.message : "Validation failed.",
        validatedOn: new Date().toISOString()
      });
    }
  });
  const useToken = useMutation({
    mutationFn: (entry: ApiTokenRecord) =>
      api.setProviderApiKey({
        provider: "gemini",
        api_key: entry.token,
        apply_globally: true,
        validate_connection: true
      }),
    onMutate: (entry) => {
      updateApiTokenValidation(entry.id, {
        validationStatus: "Checking",
        validationMessage: null
      });
    },
    onSuccess: (status, entry) => {
      setActiveApiToken(entry.id);
      updateApiTokenValidation(entry.id, tokenValidation(status));
      queryClient.setQueryData(["provider-api-key", "gemini"], status);
    },
    onError: (error, entry) => {
      updateApiTokenValidation(entry.id, {
        validationStatus: "Failed",
        validationMessage: error instanceof Error ? error.message : "Failed to sync token.",
        validatedOn: new Date().toISOString()
      });
    }
  });
  const refreshState = useMutation({
    mutationFn: (item: RuntimeStateItem) => api.refreshRuntimeState(item.key),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runtime-state"] });
    }
  });
  const clearState = useMutation({
    mutationFn: (item: RuntimeStateItem) => api.clearRuntimeState(item.key),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["runtime-state"] });
      void queryClient.invalidateQueries({ queryKey: ["provider-api-key"] });
    }
  });
  const activeToken = useMemo(
    () => apiTokens.find((entry) => entry.status === "Active" && entry.token.trim()),
    [apiTokens]
  );
  const runtimeStorageError = runtimeState.error ?? refreshState.error ?? clearState.error;

  useEffect(() => {
    if (!geminiStatus.isSuccess || geminiStatus.data.configured || !activeToken || useToken.isPending) {
      return;
    }
    useToken.mutate(activeToken);
  }, [activeToken, geminiStatus.data?.configured, geminiStatus.isSuccess, useToken]);

  function handleAddToken(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const token = draftToken.trim();
    if (!token) {
      return;
    }
    addToken.mutate(token);
  }

  return (
    <>
      <PageHeading title="Settings" description="Manage API token access for the admin workspace." />

      <div className="space-y-5">
        <Panel>
          <PanelHeader>
            <PanelTitle>API Token</PanelTitle>
          </PanelHeader>
          <PanelBody>
            <form className="space-y-4" onSubmit={handleAddToken}>
              <div className="space-y-2">
                <label className="block text-sm font-medium" htmlFor="api-token">
                  Add API Token
                </label>
                <Input
                  id="api-token"
                  type="password"
                  value={draftToken}
                  onChange={(event) => setDraftToken(event.target.value)}
                  placeholder="Enter your API token here..."
                />
                <p className="text-sm text-muted-foreground">
                  Stored in this browser and sent to the backend Gemini provider for translation activity.
                </p>
              </div>

              {addToken.error ? (
                <p className="text-sm text-destructive">
                  {addToken.error instanceof Error ? addToken.error.message : "Failed to sync API key."}
                </p>
              ) : null}

              <div className="flex flex-col gap-2 sm:flex-row">
                <Button className="flex-1" type="submit" disabled={!draftToken.trim() || addToken.isPending}>
                  {addToken.isPending ? "Adding..." : "Add API Key"}
                </Button>
                <Button className="sm:w-48" type="button" variant="secondary" onClick={applyDummyApiToken}>
                  Apply Dummy API
                </Button>
              </div>
            </form>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Your API Tokens</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Token</th>
                    <th className="px-4 py-3 font-medium">Added On</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Key Check</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {apiTokens.length ? (
                    apiTokens.map((entry) => (
                      <tr className="border-b last:border-0" key={entry.id}>
                        <td className="px-4 py-3">{entry.type}</td>
                        <td className="px-4 py-3 font-mono text-xs">{maskToken(entry.token)}</td>
                        <td className="px-4 py-3">{formatDate(entry.addedOn)}</td>
                        <td className="px-4 py-3">
                          <Badge tone={entry.status === "Active" ? "green" : "neutral"}>{entry.status}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="space-y-1">
                            <Badge tone={validationTone(entry.validationStatus)}>
                              {entry.validationStatus ?? "Unchecked"}
                            </Badge>
                            {entry.validationMessage ? (
                              <div className="max-w-[340px] truncate text-xs text-muted-foreground" title={entry.validationMessage}>
                                {entry.validationMessage}
                              </div>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex flex-wrap gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => useToken.mutate(entry)}
                              disabled={useToken.isPending && useToken.variables?.id === entry.id}
                            >
                              Use
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => checkToken.mutate(entry)}
                              disabled={checkToken.isPending && checkToken.variables?.id === entry.id}
                            >
                              Check
                            </Button>
                            <Button
                              type="button"
                              variant="destructive"
                              size="sm"
                              onClick={() => removeApiToken(entry.id)}
                            >
                              Remove
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={6}>
                        No API tokens added.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </PanelBody>
        </Panel>

        <Panel>
          <PanelHeader>
            <PanelTitle>Runtime Storage</PanelTitle>
          </PanelHeader>
          <PanelBody className="p-0">
            <div className="seamless-scrollbar overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b bg-muted/40">
                  <tr>
                    <th className="px-4 py-3 font-medium">File</th>
                    <th className="px-4 py-3 font-medium">Used For</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Updated</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {(runtimeState.data?.items ?? []).map((item) => (
                    <tr className="border-b last:border-0" key={item.key}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{item.label}</div>
                        <div className="mt-1 font-mono text-xs text-muted-foreground">{item.filename}</div>
                      </td>
                      <td className="max-w-[460px] px-4 py-3 text-muted-foreground">
                        {item.description}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Badge tone={item.exists ? "green" : "neutral"}>{item.exists ? formatBytes(item.size_bytes) : "Missing"}</Badge>
                          <Badge tone={item.affects_process ? "amber" : "neutral"}>
                            {item.affects_process ? "Affects process" : "Report only"}
                          </Badge>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDateTime(item.updated_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => refreshState.mutate(item)}
                            disabled={refreshState.isPending && refreshState.variables?.key === item.key}
                          >
                            <RefreshCw className="h-4 w-4" />
                            Refresh
                          </Button>
                          <Button
                            type="button"
                            variant="destructive"
                            size="sm"
                            onClick={() => clearState.mutate(item)}
                            disabled={clearState.isPending && clearState.variables?.key === item.key}
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {runtimeState.isLoading ? (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={5}>
                        Loading runtime storage...
                      </td>
                    </tr>
                  ) : null}
                  {!runtimeState.isLoading && (runtimeState.data?.items ?? []).length === 0 ? (
                    <tr>
                      <td className="px-4 py-6 text-center text-muted-foreground" colSpan={5}>
                        No runtime state files found.
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
            {runtimeStorageError ? (
              <div className="border-t px-4 py-3 text-sm text-destructive">
                {runtimeStorageError instanceof Error
                  ? runtimeStorageError.message
                  : "Failed to update runtime storage."}
              </div>
            ) : null}
          </PanelBody>
        </Panel>
      </div>
    </>
  );
}
