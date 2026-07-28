"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Eye, EyeOff, KeyRound, RefreshCw, Trash2 } from "lucide-react";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminApi } from "@/lib/api";
import type { ProviderCredentialRow } from "@/lib/api-types";
import { maskToken } from "@/lib/mask-token";

type FormState = {
  provider_key: string;
  api_key: string;
  label: string;
  provider_model: string;
  is_active: boolean;
  notes: string;
};

const EMPTY_FORM: FormState = {
  provider_key: "gemini",
  api_key: "",
  label: "",
  provider_model: "gemini-3.1-flash-lite",
  is_active: true,
  notes: "",
};

function fingerprintLabel(row: ProviderCredentialRow): string {
  return `${row.key_fingerprint}…${row.last4}`;
}

export default function CredentialsPage() {
  const queryClient = useQueryClient();
  const [showSecrets, setShowSecrets] = React.useState<Record<number, boolean>>({});
  const [deleteId, setDeleteId] = React.useState<number | null>(null);
  const [createForm, setCreateForm] = React.useState<FormState>(EMPTY_FORM);

  const list = useQuery({
    queryKey: ["admin", "credentials", "list"],
    queryFn: () => adminApi.listProviderCredentialRows(),
  });
  const rows = list.data?.rows ?? [];

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "credentials"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "provider-credential"] });
  };

  const create = useMutation({
    mutationFn: (payload: typeof EMPTY_FORM) =>
      adminApi.createProviderCredential({
        provider_key: payload.provider_key,
        api_key: payload.api_key,
        label: payload.label,
        provider_model: payload.provider_model || null,
        is_active: payload.is_active,
        notes: payload.notes || null,
        apply_globally: false,
      }),
    onSuccess: () => {
      setCreateForm(EMPTY_FORM);
      invalidate();
    },
  });

  const deleteCred = useMutation({
    mutationFn: (id: number) => adminApi.deleteProviderCredential(String(id)),
    onSuccess: () => {
      setDeleteId(null);
      invalidate();
    },
  });

  const testCred = useMutation({
    mutationFn: (id: number) => adminApi.testProviderCredential(String(id)),
  });

  const toggleActive = useMutation({
    mutationFn: (row: ProviderCredentialRow) =>
      adminApi.updateProviderCredential(String(row.id), { is_active: !row.is_active }),
    onSuccess: invalidate,
  });

  return (
    <>
      <PageHeading
        title="Provider credentials"
        description="Manage encrypted provider API keys. Stored values are never displayed in full; only fingerprint and last4."
      />

      {list.isError && (
        <ErrorBanner
          error={list.error}
          fallback="Could not load credentials."
          className="mb-4 rounded-md border"
        />
      )}
      {create.error && (
        <ErrorBanner
          error={create.error}
          fallback="Could not create credential."
          className="mb-4 rounded-md border"
        />
      )}
      {deleteCred.error && (
        <ErrorBanner
          error={deleteCred.error}
          fallback="Could not delete credential."
          className="mb-4 rounded-md border"
        />
      )}

      <Panel className="mb-4">
        <PanelHeader>
          <PanelTitle>Existing credentials</PanelTitle>
        </PanelHeader>
        <PanelBody className="p-0">
          <table className="w-full table-auto text-sm">
            <thead>
              <tr className="border-b text-left text-xs uppercase text-muted-foreground">
                <th className="px-4 py-2">Provider</th>
                <th className="px-4 py-2">Label</th>
                <th className="px-4 py-2">Model</th>
                <th className="px-4 py-2">Fingerprint</th>
                <th className="px-4 py-2">Status</th>
                <th className="px-4 py-2">Active</th>
                <th className="px-4 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.isLoading ? (
                <LoadingRows colSpan={7} />
              ) : rows.length === 0 ? (
                <EmptyState
                  colSpan={7}
                  title="No credentials configured"
                  description="Add a credential below to translate novels."
                />
              ) : rows.map((row) => {
                const isShown = Boolean(showSecrets[row.id]);
                const masked = maskToken(fingerprintLabel(row));
                return (
                  <tr key={row.id} className="border-b last:border-b-0">
                    <td className="px-4 py-2 align-top font-mono text-xs">{row.provider_key}</td>
                    <td className="px-4 py-2 align-top text-xs">{row.label || "—"}</td>
                    <td className="px-4 py-2 align-top font-mono text-xs">{row.model ?? "—"}</td>
                    <td className="px-4 py-2 align-top font-mono text-xs">
                      {isShown ? `${masked} (revealed)` : masked}
                    </td>
                    <td className="px-4 py-2 align-top text-xs">
                      {row.validation_status}
                      {row.validation_message ? (
                        <div className="text-muted-foreground">{row.validation_message}</div>
                      ) : null}
                    </td>
                    <td className="px-4 py-2 align-top text-xs">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => toggleActive.mutate(row)}
                        disabled={toggleActive.isPending}
                      >
                        {row.is_active ? "Deactivate" : "Activate"}
                      </Button>
                    </td>
                    <td className="px-4 py-2 align-top">
                      <div className="flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setShowSecrets((state) => ({ ...state, [row.id]: !state[row.id] }))
                          }
                          title={isShown ? "Hide" : "Reveal fingerprint"}
                        >
                          {isShown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => testCred.mutate(row.id)}
                          disabled={testCred.isPending}
                          title="Test connection"
                        >
                          <RefreshCw className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeleteId(row.id)}
                          title="Delete credential"
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader>
          <PanelTitle>
            <span className="flex items-center gap-2">
              <KeyRound className="h-4 w-4" /> Add credential
            </span>
          </PanelTitle>
        </PanelHeader>
        <PanelBody>
          <form
            className="grid gap-3 sm:grid-cols-2"
            onSubmit={(event) => {
              event.preventDefault();
              if (!createForm.api_key.trim() || !createForm.label.trim()) return;
              create.mutate(createForm);
            }}
          >
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="cred-provider">Provider</label>
              <Input
                id="cred-provider"
                value={createForm.provider_key}
                onChange={(event) => setCreateForm((state) => ({ ...state, provider_key: event.target.value }))}
                placeholder="gemini"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="cred-label">Label</label>
              <Input
                id="cred-label"
                value={createForm.label}
                onChange={(event) => setCreateForm((state) => ({ ...state, label: event.target.value }))}
                placeholder="Production"
                required
              />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="cred-key">API key</label>
              <Input
                id="cred-key"
                type="password"
                value={createForm.api_key}
                onChange={(event) => setCreateForm((state) => ({ ...state, api_key: event.target.value }))}
                placeholder="api-key"
                required
                autoComplete="off"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="cred-model">Model</label>
              <Input
                id="cred-model"
                value={createForm.provider_model}
                onChange={(event) => setCreateForm((state) => ({ ...state, provider_model: event.target.value }))}
                placeholder="gemini-3.1-flash-lite"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground" htmlFor="cred-notes">Notes</label>
              <Input
                id="cred-notes"
                value={createForm.notes}
                onChange={(event) => setCreateForm((state) => ({ ...state, notes: event.target.value }))}
                placeholder="optional"
              />
            </div>
            <div className="flex items-end">
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? "Saving…" : "Save credential"}
              </Button>
            </div>
          </form>
        </PanelBody>
      </Panel>

      <ConfirmDialog
        open={deleteId !== null}
        title="Delete credential?"
        description="This removes the encrypted credential row from the database. Connections using this credential will fail until a new credential is configured."
        confirmLabel="Delete"
        destructive
        onCancel={() => setDeleteId(null)}
        onConfirm={() => {
          if (deleteId !== null) deleteCred.mutate(deleteId);
        }}
        pending={deleteCred.isPending}
      />
    </>
  );
}
