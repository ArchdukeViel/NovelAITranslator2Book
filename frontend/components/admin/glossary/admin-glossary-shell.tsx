"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";

import { ConfirmDialog } from "@/components/admin/confirm-dialog";
import { DialogShell } from "@/components/admin/dialog-shell";
import { EmptyState } from "@/components/admin/empty-state";
import { ErrorBanner } from "@/components/admin/error-banner";
import { LoadingRows } from "@/components/admin/loading-rows";
import { PageHeading } from "@/components/admin/page-heading";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader, PanelTitle } from "@/components/ui/panel";
import { adminApi, ApiError } from "@/lib/api";
import type {
  GlossaryEnforcementLevel,
  GlossaryEntry,
  GlossaryEntryCreatePayload,
  GlossaryEntryStatus,
  GlossaryEntryUpdatePayload,
  GlossaryMatchingPolicy,
  GlossaryReplacementPolicy,
  GlossaryTermType,
} from "@/lib/api-types";

const STATUS_ORDER: GlossaryEntryStatus[] = ["candidate", "recommended", "approved", "rejected", "deprecated"];
const TERM_TYPES: GlossaryTermType[] = [
  "character",
  "family_house",
  "place",
  "organization",
  "title",
  "rank",
  "skill",
  "magic",
  "species",
  "item",
  "artifact",
  "concept",
  "phrase",
  "other",
];
const ENFORCEMENT_LEVELS: GlossaryEnforcementLevel[] = ["none", "info", "warning", "error", "blocker"];
const MATCHING_POLICIES: GlossaryMatchingPolicy[] = [
  "exact_phrase",
  "case_insensitive_phrase",
  "word_boundary",
  "source_text_only",
  "translated_text_only",
  "regex_reviewed",
  "manual_only",
  "custom",
];
const REPLACEMENT_POLICIES: GlossaryReplacementPolicy[] = [
  "never_auto_replace",
  "preview_required",
  "manual_only",
  "safe_exact",
  "no_replacement",
];

type EntryFormValues = {
  canonical_term: string;
  term_type: GlossaryTermType;
  approved_translation: string;
  status: GlossaryEntryStatus;
  enforcement_level: GlossaryEnforcementLevel;
  public_visible: boolean;
  public_description: string;
  admin_notes: string;
  matching_policy: GlossaryMatchingPolicy;
  replacement_policy: GlossaryReplacementPolicy;
};

type PendingDecision = {
  entry: GlossaryEntry;
  action: "lock" | "unlock" | "deprecate";
} | null;

function emptyForm(): EntryFormValues {
  return {
    canonical_term: "",
    term_type: "character",
    approved_translation: "",
    status: "candidate",
    enforcement_level: "none",
    public_visible: false,
    public_description: "",
    admin_notes: "",
    matching_policy: "exact_phrase",
    replacement_policy: "preview_required",
  };
}

function formFromEntry(entry: GlossaryEntry): EntryFormValues {
  return {
    canonical_term: entry.canonical_term,
    term_type: entry.term_type,
    approved_translation: entry.approved_translation ?? "",
    status: entry.status,
    enforcement_level: entry.enforcement_level,
    public_visible: entry.public_visible,
    public_description: entry.public_description ?? "",
    admin_notes: entry.admin_notes ?? "",
    matching_policy: entry.matching_policy,
    replacement_policy: entry.replacement_policy,
  };
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function createPayload(values: EntryFormValues): GlossaryEntryCreatePayload {
  return {
    canonical_term: values.canonical_term.trim(),
    term_type: values.term_type,
    approved_translation: optionalText(values.approved_translation),
    status: values.status,
    enforcement_level: values.enforcement_level,
    public_visible: values.public_visible,
    public_description: optionalText(values.public_description),
    admin_notes: optionalText(values.admin_notes),
    matching_policy: values.matching_policy,
    replacement_policy: values.replacement_policy,
  };
}

function updatePayload(values: EntryFormValues): GlossaryEntryUpdatePayload {
  return {
    canonical_term: values.canonical_term.trim(),
    term_type: values.term_type,
    approved_translation: optionalText(values.approved_translation),
    enforcement_level: values.enforcement_level,
    public_visible: values.public_visible,
    public_description: optionalText(values.public_description),
    admin_notes: optionalText(values.admin_notes),
    matching_policy: values.matching_policy,
    replacement_policy: values.replacement_policy,
  };
}

function statusTone(status: GlossaryEntryStatus) {
  if (status === "approved") return "green";
  if (status === "recommended") return "blue";
  if (status === "rejected" || status === "deprecated") return "red";
  return "amber";
}

function formatStatus(status: string) {
  return status.replaceAll("_", " ");
}

function formatDate(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function seenRange(entry: GlossaryEntry) {
  const first = entry.first_seen_chapter_number ?? entry.first_seen_chapter_id;
  const last = entry.last_seen_chapter_number ?? entry.last_seen_chapter_id;
  if (first && last && first !== last) return `${first} to ${last}`;
  if (first || last) return String(first ?? last);
  return "-";
}

function countByStatus(entries: GlossaryEntry[]) {
  return STATUS_ORDER.map((status) => ({
    status,
    count: entries.filter((entry) => entry.status === status).length,
  }));
}

function authorizationMessage(error: unknown) {
  if (error instanceof ApiError && error.status === 401) {
    return "Owner session is required to view this glossary.";
  }
  if (error instanceof ApiError && error.status === 403) {
    return "This owner session is not allowed to view the glossary.";
  }
  return null;
}

function FieldLabel({ children }: { children: React.ReactNode }) {
  return <label className="space-y-1 text-sm font-medium">{children}</label>;
}

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: T[];
  onChange: (value: T) => void;
}) {
  return (
    <FieldLabel>
      <span>{label}</span>
      <select
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value as T)}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {formatStatus(option)}
          </option>
        ))}
      </select>
    </FieldLabel>
  );
}

function GlossaryEntryDialog({
  mode,
  open,
  values,
  pending,
  error,
  validationError,
  onChange,
  onSubmit,
  onClose,
}: {
  mode: "create" | "edit";
  open: boolean;
  values: EntryFormValues;
  pending: boolean;
  error: unknown;
  validationError: string | null;
  onChange: (values: EntryFormValues) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  const setValue = <K extends keyof EntryFormValues>(key: K, value: EntryFormValues[K]) => {
    onChange({ ...values, [key]: value });
  };

  return (
    <DialogShell
      open={open}
      title={mode === "create" ? "Create glossary entry" : "Edit glossary entry"}
      description="Entry ownership stays scoped to this novel. Source IDs belong in provenance later."
      onClose={onClose}
      className="max-w-3xl"
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={pending}>
            {pending ? "Saving..." : mode === "create" ? "Create entry" : "Save entry"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 p-4">
        {validationError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{validationError}</div> : null}
        <ErrorBanner error={error} fallback={mode === "create" ? "Failed to create glossary entry." : "Failed to update glossary entry."} className="border" />

        <div className="grid gap-4 md:grid-cols-2">
          <FieldLabel>
            <span>Canonical term</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.canonical_term}
              onChange={(event) => setValue("canonical_term", event.target.value)}
            />
          </FieldLabel>
          <FieldLabel>
            <span>Approved translation</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.approved_translation}
              onChange={(event) => setValue("approved_translation", event.target.value)}
            />
          </FieldLabel>
          <SelectField label="Term type" value={values.term_type} options={TERM_TYPES} onChange={(value) => setValue("term_type", value)} />
          {mode === "create" ? (
            <SelectField label="Status" value={values.status} options={STATUS_ORDER} onChange={(value) => setValue("status", value)} />
          ) : null}
          <SelectField label="Enforcement level" value={values.enforcement_level} options={ENFORCEMENT_LEVELS} onChange={(value) => setValue("enforcement_level", value)} />
          <SelectField label="Matching policy" value={values.matching_policy} options={MATCHING_POLICIES} onChange={(value) => setValue("matching_policy", value)} />
          <SelectField label="Replacement policy" value={values.replacement_policy} options={REPLACEMENT_POLICIES} onChange={(value) => setValue("replacement_policy", value)} />
          <label className="flex items-center gap-2 self-end text-sm">
            <input
              type="checkbox"
              checked={values.public_visible}
              onChange={(event) => setValue("public_visible", event.target.checked)}
            />
            Public visible
          </label>
        </div>

        <FieldLabel>
          <span>Public description</span>
          <textarea
            className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={values.public_description}
            onChange={(event) => setValue("public_description", event.target.value)}
          />
        </FieldLabel>
        <FieldLabel>
          <span>Admin notes</span>
          <textarea
            className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={values.admin_notes}
            onChange={(event) => setValue("admin_notes", event.target.value)}
          />
        </FieldLabel>
      </div>
    </DialogShell>
  );
}

export function AdminGlossaryShell({ novelId }: { novelId: string }) {
  const queryClient = useQueryClient();
  const [dialogMode, setDialogMode] = React.useState<"create" | "edit" | null>(null);
  const [editingEntry, setEditingEntry] = React.useState<GlossaryEntry | null>(null);
  const [formValues, setFormValues] = React.useState<EntryFormValues>(emptyForm());
  const [formValidationError, setFormValidationError] = React.useState<string | null>(null);
  const [pendingDecision, setPendingDecision] = React.useState<PendingDecision>(null);
  const [decisionError, setDecisionError] = React.useState<unknown>(null);

  const glossary = useQuery({
    queryKey: ["admin-glossary", novelId],
    queryFn: () => adminApi.listGlossaryEntries(novelId),
  });
  const entries = glossary.data ?? [];
  const authMessage = authorizationMessage(glossary.error);
  const invalidateGlossary = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-glossary", novelId] });
  };

  const createEntry = useMutation({
    mutationFn: (payload: GlossaryEntryCreatePayload) => adminApi.createGlossaryEntry(novelId, payload),
    onSuccess: () => {
      setDialogMode(null);
      setFormValues(emptyForm());
      invalidateGlossary();
    },
  });

  const updateEntry = useMutation({
    mutationFn: ({ entryId, payload }: { entryId: number; payload: GlossaryEntryUpdatePayload }) =>
      adminApi.updateGlossaryEntry(novelId, entryId, payload),
    onSuccess: () => {
      setDialogMode(null);
      setEditingEntry(null);
      invalidateGlossary();
    },
  });

  const changeStatus = useMutation({
    mutationFn: ({ entryId, status }: { entryId: number; status: GlossaryEntryStatus }) =>
      adminApi.changeGlossaryEntryStatus(novelId, entryId, { status }),
    onSuccess: invalidateGlossary,
  });

  const runDecision = useMutation({
    mutationFn: async ({ entry, action }: Exclude<PendingDecision, null>) => {
      if (action === "lock") return adminApi.lockGlossaryEntry(novelId, entry.id);
      if (action === "unlock") return adminApi.unlockGlossaryEntry(novelId, entry.id);
      return adminApi.deprecateGlossaryEntry(novelId, entry.id);
    },
    onSuccess: () => {
      setPendingDecision(null);
      setDecisionError(null);
      invalidateGlossary();
    },
    onError: (error) => setDecisionError(error),
  });

  const openCreate = () => {
    createEntry.reset();
    updateEntry.reset();
    setFormValidationError(null);
    setEditingEntry(null);
    setFormValues(emptyForm());
    setDialogMode("create");
  };

  const openEdit = (entry: GlossaryEntry) => {
    createEntry.reset();
    updateEntry.reset();
    setFormValidationError(null);
    setEditingEntry(entry);
    setFormValues(formFromEntry(entry));
    setDialogMode("edit");
  };

  const closeDialog = () => {
    if (createEntry.isPending || updateEntry.isPending) return;
    setDialogMode(null);
    setEditingEntry(null);
    setFormValidationError(null);
  };

  const submitEntry = () => {
    if (!formValues.canonical_term.trim()) {
      setFormValidationError("Canonical term is required.");
      return;
    }
    setFormValidationError(null);
    if (dialogMode === "create") {
      createEntry.mutate(createPayload(formValues));
      return;
    }
    if (editingEntry) {
      updateEntry.mutate({ entryId: editingEntry.id, payload: updatePayload(formValues) });
    }
  };

  const decisionTitle = pendingDecision
    ? `${pendingDecision.action === "deprecate" ? "Deprecate" : pendingDecision.action === "lock" ? "Lock" : "Unlock"} glossary entry`
    : "Glossary entry action";
  const decisionDescription = pendingDecision
    ? `${pendingDecision.action === "deprecate" ? "Deprecate" : pendingDecision.action === "lock" ? "Lock" : "Unlock"} "${pendingDecision.entry.canonical_term}"?`
    : undefined;

  return (
    <>
      <PageHeading
        title="Glossary"
        description={`Novel ID: ${novelId}`}
      />

      <Panel className="mb-4">
        <PanelBody className="space-y-2 text-sm text-muted-foreground">
          <p>Glossary terms are owned by this novel. Source IDs are provenance only.</p>
          <p>No global find/replace or chapter repair runs from this page. Prompt injection and QA enforcement are later phases.</p>
        </PanelBody>
      </Panel>

      <Panel className="mb-4">
        <PanelHeader>
          <PanelTitle>Status summary</PanelTitle>
        </PanelHeader>
        <PanelBody>
          {glossary.isLoading ? (
            <div className="text-sm text-muted-foreground">Loading glossary summary...</div>
          ) : glossary.error ? (
            <div className="text-sm text-muted-foreground">Summary unavailable.</div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {countByStatus(entries).map(({ status, count }) => (
                <div key={status} className="rounded-md border px-3 py-2">
                  <div className="text-xs uppercase text-muted-foreground">{formatStatus(status)}</div>
                  <div className="mt-1 text-2xl font-semibold">{count}</div>
                </div>
              ))}
            </div>
          )}
        </PanelBody>
      </Panel>

      <Panel>
        <PanelHeader className="flex flex-row items-center justify-between gap-3">
          <PanelTitle>Entries</PanelTitle>
          <Button size="sm" onClick={openCreate}>
            Create entry
          </Button>
        </PanelHeader>
        <ErrorBanner error={glossary.error} fallback="Failed to load glossary entries." />
        <ErrorBanner error={changeStatus.error} fallback="Failed to update glossary entry status." />
        <ErrorBanner error={decisionError} fallback="Failed to update glossary entry." />
        {authMessage ? (
          <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            {authMessage}
          </div>
        ) : null}
        <PanelBody className="p-0">
          <div className="seamless-scrollbar overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="min-w-[220px] px-4 py-3">Canonical term</th>
                  <th className="px-4 py-3">Term type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Enforcement</th>
                  <th className="px-4 py-3">Owner locked</th>
                  <th className="px-4 py-3">Public visible</th>
                  <th className="px-4 py-3">First/last seen</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="min-w-[300px] px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {glossary.isLoading ? (
                  <LoadingRows colSpan={9} label="Loading glossary entries..." />
                ) : glossary.error ? (
                  <EmptyState title="Failed to load glossary entries." description={authMessage ?? "Try refreshing after confirming the owner session."} colSpan={9} />
                ) : entries.length ? (
                  entries.map((entry) => (
                    <tr className="border-b last:border-0" key={entry.id}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{entry.canonical_term}</div>
                        {entry.approved_translation ? (
                          <div className="mt-1 text-xs text-muted-foreground">{entry.approved_translation}</div>
                        ) : null}
                      </td>
                      <td className="px-4 py-3">{formatStatus(entry.term_type)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(entry.status)}>{formatStatus(entry.status)}</Badge>
                      </td>
                      <td className="px-4 py-3">{formatStatus(entry.enforcement_level)}</td>
                      <td className="px-4 py-3">{entry.owner_locked ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">{entry.public_visible ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">{seenRange(entry)}</td>
                      <td className="px-4 py-3">{formatDate(entry.updated_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={() => openEdit(entry)}>
                            Edit
                          </Button>
                          <select
                            aria-label={`Change status for ${entry.canonical_term}`}
                            className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                            value={entry.status}
                            onChange={(event) => changeStatus.mutate({ entryId: entry.id, status: event.target.value as GlossaryEntryStatus })}
                            disabled={changeStatus.isPending}
                          >
                            {STATUS_ORDER.map((status) => (
                              <option key={status} value={status}>
                                {formatStatus(status)}
                              </option>
                            ))}
                          </select>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setDecisionError(null);
                              setPendingDecision({ entry, action: entry.owner_locked ? "unlock" : "lock" });
                            }}
                          >
                            {entry.owner_locked ? "Unlock" : "Lock"}
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => {
                              setDecisionError(null);
                              setPendingDecision({ entry, action: "deprecate" });
                            }}
                            disabled={entry.status === "deprecated"}
                          >
                            Deprecate
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyState
                    title="No glossary entries yet."
                    description="Additions and decision workflows will arrive in later admin glossary phases."
                    colSpan={9}
                  />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <GlossaryEntryDialog
        mode={dialogMode ?? "create"}
        open={dialogMode !== null}
        values={formValues}
        pending={createEntry.isPending || updateEntry.isPending}
        error={dialogMode === "create" ? createEntry.error : updateEntry.error}
        validationError={formValidationError}
        onChange={setFormValues}
        onSubmit={submitEntry}
        onClose={closeDialog}
      />

      <ConfirmDialog
        open={pendingDecision !== null}
        title={decisionTitle}
        description={decisionDescription}
        confirmLabel={pendingDecision?.action === "deprecate" ? "Deprecate" : "Confirm"}
        destructive={pendingDecision?.action === "deprecate"}
        pending={runDecision.isPending}
        onConfirm={() => {
          if (pendingDecision) runDecision.mutate(pendingDecision);
        }}
        onCancel={() => {
          if (!runDecision.isPending) setPendingDecision(null);
        }}
        auditNotice="This changes owner/admin glossary state for this novel only."
      />
    </>
  );
}
