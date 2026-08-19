"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Activity,
  KeyRound,
  LogIn,
  Pause,
  Play,
  ShieldCheck,
  Trash2,
  Zap,
} from "lucide-react";

import { usePublicAuth } from "@/hooks/public/use-auth";
import {
  useContributionUsage,
  useContributions,
  useDeleteContribution,
  useReplaceContribution,
  useUpdateContributionStatus,
} from "@/hooks/public";
import {
  Panel,
  PanelBody,
  PanelHeader,
  PanelTitle,
} from "@/components/ui/panel";
import { Button } from "@/components/ui/button";

function dateLabel(value: string | null | undefined): string {
  if (!value) return "Not yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not yet" : date.toLocaleString();
}

function statusLabel(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export default function AccountContributionsPage() {
  const { isAuthenticated, isPending: isAuthPending } = usePublicAuth();
  const contributions = useContributions(isAuthenticated);
  const replace = useReplaceContribution();
  const updateStatus = useUpdateContributionStatus();
  const remove = useDeleteContribution();
  const [apiKey, setApiKey] = useState("");
  const [consentAccepted, setConsentAccepted] = useState(false);
  const credential = contributions.data?.credentials[0] ?? null;
  const usage = useContributionUsage(credential?.credential_id ?? null);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKey.trim() || !consentAccepted || !contributions.data) return;
    await replace.mutateAsync({
      provider_key: "gemini",
      api_key: apiKey,
      consent_version: contributions.data.consent_version,
    });
    setApiKey("");
    setConsentAccepted(false);
  };

  const handleRemove = async () => {
    if (!credential || !window.confirm("Permanently delete this contributor credential?")) return;
    await remove.mutateAsync(credential.credential_id);
  };

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
      <header className="mb-8">
        <h1 className="font-literary text-3xl font-semibold tracking-normal">
          Contributions
        </h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">
          Share a Google Gemini API key to increase community translation capacity.
          The key is validated before it can be selected for contributor work.
        </p>
      </header>

      {!isAuthPending && !isAuthenticated ? (
        <div className="rounded-lg border border-border/80 bg-card p-8 text-center shadow-xs">
          <KeyRound className="mx-auto h-10 w-10 text-muted-foreground/60" />
          <p className="mt-3 text-base font-semibold text-foreground">
            You need to sign in to contribute an API key.
          </p>
          <p className="mx-auto mt-1 max-w-md text-xs text-muted-foreground">
            Contributor credentials belong to the authenticated account that added them.
          </p>
          <div className="mt-5">
            <Link
              href="/login?mode=signin&callbackUrl=%2Faccount%2Fcontributions"
              className="inline-flex h-9 items-center justify-center gap-2 rounded-md bg-primary px-4 text-xs font-medium text-primary-foreground shadow-xs transition-colors hover:bg-primary/90"
            >
              <LogIn className="h-4 w-4" />
              Sign in to continue
            </Link>
          </div>
        </div>
      ) : contributions.isPending ? (
        <div className="rounded-lg border border-border bg-card p-8 text-sm text-muted-foreground">
          Loading contributor credential status…
        </div>
      ) : contributions.isError ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-6 text-sm text-destructive">
          The contributor service could not be reached. No credential state was changed.
        </div>
      ) : contributions.data ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
          <div className="space-y-6">
            {!contributions.data.enabled || !contributions.data.encryption_ready ? (
              <div className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
                Contributor intake is temporarily unavailable because the service
                is disabled or its encryption boundary is unavailable. Existing
                credentials are not selected until the service reports them as
                active.
              </div>
            ) : null}

            <Panel>
              <PanelHeader>
                <div className="flex items-center gap-2">
                  <KeyRound className="h-4 w-4 text-primary" />
                  <PanelTitle className="font-literary">
                    {credential ? "Replace Gemini API Key" : "Contribute Gemini API Key"}
                  </PanelTitle>
                </div>
              </PanelHeader>
              <PanelBody className="space-y-4">
                {replace.data && !replace.data.validation_ok ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                    The key was stored as invalid and is not eligible for translation work.
                    Review it and replace it with a valid Gemini key.
                  </div>
                ) : null}
                {replace.isError ? (
                  <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
                    The key could not be submitted. The existing credential was not replaced.
                  </div>
                ) : null}
                <form onSubmit={handleSubmit} className="space-y-3">
                  <div>
                    <label htmlFor="gemini-key" className="mb-1 block text-xs font-medium text-foreground">
                      Google AI Studio API Key (Gemini)
                    </label>
                    <input
                      id="gemini-key"
                      type="password"
                      required
                      value={apiKey}
                      onChange={(event) => setApiKey(event.target.value)}
                      placeholder="AIzaSy…"
                      disabled={!contributions.data.enabled || !contributions.data.encryption_ready || replace.isPending}
                      className="h-9 w-full rounded-md border border-border bg-background px-3 font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
                    />
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      The full key is accepted only in this request and is never returned to the browser. Get a key at{" "}
                      <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" className="text-primary underline">
                        Google AI Studio
                      </a>
                      .
                    </p>
                  </div>
                  <label className="flex items-start gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={consentAccepted}
                      onChange={(event) => setConsentAccepted(event.target.checked)}
                      disabled={replace.isPending}
                      className="mt-0.5"
                    />
                    <span>
                      I consent to encrypted storage, contributor translation use,
                      quota accounting, and owner emergency pause/revocation under
                      consent version {contributions.data.consent_version}.
                    </span>
                  </label>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={!apiKey.trim() || !consentAccepted || replace.isPending || !contributions.data.enabled || !contributions.data.encryption_ready}
                  >
                    {replace.isPending ? "Validating key…" : credential ? "Validate replacement" : "Validate and activate"}
                  </Button>
                </form>
              </PanelBody>
            </Panel>

            {credential ? (
              <div className="grid gap-4 sm:grid-cols-2">
                <Panel>
                  <PanelHeader>
                    <div className="flex items-center gap-2">
                      <Activity className="h-4 w-4 text-accent" />
                      <PanelTitle className="font-literary text-sm">Credential status</PanelTitle>
                    </div>
                  </PanelHeader>
                  <PanelBody>
                    <div className="flex items-center gap-2 text-xs font-medium text-foreground">
                      <span className="h-2 w-2 rounded-full bg-primary" />
                      {statusLabel(credential.status)} · ending {credential.last4}
                    </div>
                    <p className="mt-2 text-[11px] text-muted-foreground">
                      {credential.validation_message ?? "No validation message."}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Last validated: {dateLabel(credential.last_validated_at)}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      {credential.status === "active" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={updateStatus.isPending}
                          onClick={() => updateStatus.mutate({ credentialId: credential.credential_id, status: "paused" })}
                        >
                          <Pause className="h-3.5 w-3.5" /> Pause
                        </Button>
                      ) : credential.status === "paused" && credential.validation_status === "valid" ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={updateStatus.isPending}
                          onClick={() => updateStatus.mutate({ credentialId: credential.credential_id, status: "active" })}
                        >
                          <Play className="h-3.5 w-3.5" /> Resume
                        </Button>
                      ) : null}
                      <Button size="sm" variant="destructive" disabled={remove.isPending} onClick={handleRemove}>
                        <Trash2 className="h-3.5 w-3.5" /> Delete permanently
                      </Button>
                    </div>
                  </PanelBody>
                </Panel>

                <Panel>
                  <PanelHeader>
                    <div className="flex items-center gap-2">
                      <Zap className="h-4 w-4 text-primary" />
                      <PanelTitle className="font-literary text-sm">Usage</PanelTitle>
                    </div>
                  </PanelHeader>
                  <PanelBody>
                    {usage.isPending ? (
                      <p className="text-xs text-muted-foreground">Loading usage…</p>
                    ) : usage.isError || !usage.data ? (
                      <p className="text-xs text-muted-foreground">Usage is unavailable right now.</p>
                    ) : (
                      <div className="space-y-2 text-xs text-muted-foreground">
                        <p>Last minute: {usage.data.current_minute.requests} / {usage.data.limits.requests_per_minute} requests</p>
                        <p>Last 24 hours: {usage.data.today.requests} / {usage.data.limits.requests_per_day} requests</p>
                        <p>Last 24 hours: {usage.data.today.tokens.toLocaleString()} tokens</p>
                      </div>
                    )}
                  </PanelBody>
                </Panel>
              </div>
            ) : null}
          </div>

          <aside className="space-y-4">
            <Panel>
              <PanelHeader>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-primary" />
                  <PanelTitle className="font-literary">Security & Privacy</PanelTitle>
                </div>
              </PanelHeader>
              <PanelBody className="space-y-2.5 text-xs text-muted-foreground">
                <p><strong className="text-foreground">Encrypted at rest:</strong> the key is encrypted with the configured credential encryption key.</p>
                <p><strong className="text-foreground">No readback:</strong> the full key is never returned after submission; only the last four characters and fingerprint are shown.</p>
                <p><strong className="text-foreground">Isolated use:</strong> contributor keys are selected only for explicitly marked contributor translation work, never owner-only jobs.</p>
              </PanelBody>
            </Panel>
          </aside>
        </div>
      ) : null}
    </main>
  );
}
