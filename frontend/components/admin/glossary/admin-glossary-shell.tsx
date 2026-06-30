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
import { adminApi, api, ApiError } from "@/lib/api";
import type {
  GlossaryAlias,
  GlossaryAliasAppliesTo,
  GlossaryAliasCreatePayload,
  GlossaryAliasType,
  GlossaryDecisionEvent,
  GlossaryEnforcementLevel,
  GlossaryEntry,
  GlossaryEntryCreatePayload,
  GlossaryEntryStatus,
  GlossaryEntryUpdatePayload,
  GlossaryEvidenceQuality,
  GlossaryMatchingPolicy,
  GlossaryProvenanceCreatePayload,
  GlossaryQaFinding,
  GlossaryQaFindingStatus,
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
const ALIAS_TYPES: GlossaryAliasType[] = ["allowed", "observed", "rejected", "banned", "deprecated", "source_variant"];
const ALIAS_APPLIES_TO: GlossaryAliasAppliesTo[] = ["source_text", "translated_text", "prompt", "qa", "public_display"];
const EVIDENCE_QUALITIES: GlossaryEvidenceQuality[] = [
  "clean_source",
  "mojibake",
  "translated_only",
  "metadata_only",
  "manual_owner_decision",
];
const QA_STATUSES: GlossaryQaFindingStatus[] = ["open", "accepted", "dismissed", "fixed"];

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

type AliasFormValues = {
  alias_text: string;
  alias_type: GlossaryAliasType;
  applies_to: "" | GlossaryAliasAppliesTo;
  matching_policy: "" | GlossaryMatchingPolicy;
  notes: string;
};

type ProvenanceFormValues = {
  source_site: string;
  source_adapter: string;
  source_novel_id: string;
  source_chapter_id: string;
  source_chapter_number: string;
  raw_source_term: string;
  observed_translated_term: string;
  evidence_ref: string;
  local_reference: string;
  evidence_quality: "" | GlossaryEvidenceQuality;
  confidence: string;
};

type PendingAliasDeprecation = {
  alias: GlossaryAlias;
} | null;

type DetailTab = "aliases" | "evidence" | "history" | "qa";

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

function emptyAliasForm(): AliasFormValues {
  return {
    alias_text: "",
    alias_type: "observed",
    applies_to: "",
    matching_policy: "",
    notes: "",
  };
}

function aliasFormFromAlias(alias: GlossaryAlias): AliasFormValues {
  return {
    alias_text: alias.alias_text,
    alias_type: alias.alias_type,
    applies_to: alias.applies_to ?? "",
    matching_policy: alias.matching_policy ?? "",
    notes: alias.notes ?? "",
  };
}

function aliasPayload(values: AliasFormValues): GlossaryAliasCreatePayload {
  return {
    alias_text: values.alias_text.trim(),
    alias_type: values.alias_type,
    applies_to: values.applies_to || null,
    matching_policy: values.matching_policy || null,
    notes: optionalText(values.notes),
  };
}

function emptyProvenanceForm(): ProvenanceFormValues {
  return {
    source_site: "",
    source_adapter: "",
    source_novel_id: "",
    source_chapter_id: "",
    source_chapter_number: "",
    raw_source_term: "",
    observed_translated_term: "",
    evidence_ref: "",
    local_reference: "",
    evidence_quality: "",
    confidence: "",
  };
}

function numberOrNull(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
}

function provenancePayload(values: ProvenanceFormValues): GlossaryProvenanceCreatePayload {
  return {
    source_site: values.source_site.trim(),
    source_adapter: values.source_adapter.trim(),
    source_novel_id: optionalText(values.source_novel_id),
    source_chapter_id: optionalText(values.source_chapter_id),
    source_chapter_number: numberOrNull(values.source_chapter_number),
    raw_source_term: optionalText(values.raw_source_term),
    observed_translated_term: optionalText(values.observed_translated_term),
    evidence_ref: optionalText(values.evidence_ref),
    local_reference: optionalText(values.local_reference),
    evidence_quality: values.evidence_quality || null,
    confidence: numberOrNull(values.confidence),
  };
}

function jsonSummary(value: string | null) {
  if (!value) return null;
  try {
    return JSON.stringify(JSON.parse(value));
  } catch {
    return value;
  }
}

function translationFor(entry: GlossaryEntry) {
  return entry.approved_translation || entry.canonical_term;
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

function FieldLabel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <label className={`space-y-1 text-sm font-medium ${className}`.trim()}>{children}</label>;
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
      description="Entry ownership stays scoped to this novel. Source IDs belong in evidence."
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
            <span>Term</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.canonical_term}
              onChange={(event) => setValue("canonical_term", event.target.value)}
            />
          </FieldLabel>
          <FieldLabel>
            <span>Translation</span>
            <input
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.approved_translation}
              onChange={(event) => setValue("approved_translation", event.target.value)}
            />
          </FieldLabel>
          <SelectField label="Type" value={values.term_type} options={TERM_TYPES} onChange={(value) => setValue("term_type", value)} />
          {mode === "create" ? (
            <SelectField label="Status" value={values.status} options={STATUS_ORDER} onChange={(value) => setValue("status", value)} />
          ) : null}
        </div>

        <details className="rounded-md border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">More options</summary>
          <div className="mt-4 space-y-4">
            <FieldLabel>
              <span>Notes</span>
              <textarea
                className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={values.admin_notes}
                onChange={(event) => setValue("admin_notes", event.target.value)}
              />
            </FieldLabel>
            <div className="grid gap-4 md:grid-cols-2">
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
          </div>
        </details>
      </div>
    </DialogShell>
  );
}

function OptionalSelectField<T extends string>({
  label,
  value,
  options,
  emptyLabel,
  onChange,
}: {
  label: string;
  value: "" | T;
  options: T[];
  emptyLabel: string;
  onChange: (value: "" | T) => void;
}) {
  return (
    <FieldLabel>
      <span>{label}</span>
      <select
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value as "" | T)}
      >
        <option value="">{emptyLabel}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {formatStatus(option)}
          </option>
        ))}
      </select>
    </FieldLabel>
  );
}

function AliasDialog({
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
  mode: "add" | "edit";
  open: boolean;
  values: AliasFormValues;
  pending: boolean;
  error: unknown;
  validationError: string | null;
  onChange: (values: AliasFormValues) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  const setValue = <K extends keyof AliasFormValues>(key: K, value: AliasFormValues[K]) => {
    onChange({ ...values, [key]: value });
  };
  const caution = values.alias_type === "banned" || values.alias_type === "rejected";

  return (
    <DialogShell
      open={open}
      title={mode === "add" ? "Add alias" : "Edit alias"}
      description="Aliases guide owner decisions and future QA. They do not rewrite chapters."
      onClose={onClose}
      className="max-w-2xl"
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={pending}>
            {pending ? "Saving..." : mode === "add" ? "Add alias" : "Save alias"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 p-4">
        {validationError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{validationError}</div> : null}
        <ErrorBanner error={error} fallback={mode === "add" ? "Failed to add alias." : "Failed to update alias."} className="border" />
        {caution ? (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Rejected and banned aliases mark risky or forbidden variants. They are not replacement instructions.
          </div>
        ) : null}
        <FieldLabel>
          <span>Alias text</span>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={values.alias_text}
            onChange={(event) => setValue("alias_text", event.target.value)}
          />
        </FieldLabel>
        <div className="grid gap-4 md:grid-cols-2">
          <SelectField label="Alias type" value={values.alias_type} options={ALIAS_TYPES} onChange={(value) => setValue("alias_type", value)} />
          <OptionalSelectField label="Applies to" value={values.applies_to} options={ALIAS_APPLIES_TO} emptyLabel="No scope" onChange={(value) => setValue("applies_to", value)} />
          <OptionalSelectField label="Matching policy override" value={values.matching_policy} options={MATCHING_POLICIES} emptyLabel="Use entry policy" onChange={(value) => setValue("matching_policy", value)} />
        </div>
        <FieldLabel>
          <span>Notes</span>
          <textarea
            className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={values.notes}
            onChange={(event) => setValue("notes", event.target.value)}
          />
        </FieldLabel>
      </div>
    </DialogShell>
  );
}

function ProvenanceDialog({
  open,
  values,
  pending,
  error,
  validationError,
  onChange,
  onSubmit,
  onClose,
}: {
  open: boolean;
  values: ProvenanceFormValues;
  pending: boolean;
  error: unknown;
  validationError: string | null;
  onChange: (values: ProvenanceFormValues) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  const setValue = <K extends keyof ProvenanceFormValues>(key: K, value: ProvenanceFormValues[K]) => {
    onChange({ ...values, [key]: value });
  };

  return (
    <DialogShell
      open={open}
      title="Add evidence"
      description="Source metadata is evidence only. Glossary ownership remains per novel."
      onClose={onClose}
      className="max-w-3xl"
      footer={
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={pending}>
            Cancel
          </Button>
          <Button onClick={onSubmit} disabled={pending}>
            {pending ? "Saving..." : "Add evidence"}
          </Button>
        </div>
      }
    >
      <div className="space-y-4 p-4">
        {validationError ? <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{validationError}</div> : null}
        <ErrorBanner error={error} fallback="Failed to add evidence." className="border" />
        <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Keep evidence compact. Do not paste large source excerpts here.
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <FieldLabel>
            <span>Source site</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.source_site} onChange={(event) => setValue("source_site", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Source adapter</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.source_adapter} onChange={(event) => setValue("source_adapter", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Source novel ID</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.source_novel_id} onChange={(event) => setValue("source_novel_id", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Source chapter ID</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.source_chapter_id} onChange={(event) => setValue("source_chapter_id", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Source chapter number</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.source_chapter_number} onChange={(event) => setValue("source_chapter_number", event.target.value)} />
          </FieldLabel>
          <OptionalSelectField label="Evidence quality" value={values.evidence_quality} options={EVIDENCE_QUALITIES} emptyLabel="Unknown quality" onChange={(value) => setValue("evidence_quality", value)} />
          <FieldLabel>
            <span>Raw source term</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.raw_source_term} onChange={(event) => setValue("raw_source_term", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Observed translated term</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.observed_translated_term} onChange={(event) => setValue("observed_translated_term", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Evidence reference</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.evidence_ref} onChange={(event) => setValue("evidence_ref", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Local reference</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.local_reference} onChange={(event) => setValue("local_reference", event.target.value)} />
          </FieldLabel>
          <FieldLabel>
            <span>Confidence</span>
            <input className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm" value={values.confidence} onChange={(event) => setValue("confidence", event.target.value)} />
          </FieldLabel>
        </div>
      </div>
    </DialogShell>
  );
}

export function AdminGlossaryShell({ novelId }: { novelId: string }) {
  const queryClient = useQueryClient();
  const [selectedEntryId, setSelectedEntryId] = React.useState<number | null>(null);
  const [dialogMode, setDialogMode] = React.useState<"create" | "edit" | null>(null);
  const [editingEntry, setEditingEntry] = React.useState<GlossaryEntry | null>(null);
  const [formValues, setFormValues] = React.useState<EntryFormValues>(emptyForm());
  const [formValidationError, setFormValidationError] = React.useState<string | null>(null);
  const [pendingDecision, setPendingDecision] = React.useState<PendingDecision>(null);
  const [decisionError, setDecisionError] = React.useState<unknown>(null);
  const [aliasDialogMode, setAliasDialogMode] = React.useState<"add" | "edit" | null>(null);
  const [editingAlias, setEditingAlias] = React.useState<GlossaryAlias | null>(null);
  const [aliasValues, setAliasValues] = React.useState<AliasFormValues>(emptyAliasForm());
  const [aliasValidationError, setAliasValidationError] = React.useState<string | null>(null);
  const [pendingAliasDeprecation, setPendingAliasDeprecation] = React.useState<PendingAliasDeprecation>(null);
  const [provenanceDialogOpen, setProvenanceDialogOpen] = React.useState(false);
  const [provenanceValues, setProvenanceValues] = React.useState<ProvenanceFormValues>(emptyProvenanceForm());
  const [provenanceValidationError, setProvenanceValidationError] = React.useState<string | null>(null);
  const [qaStatusFilter, setQaStatusFilter] = React.useState<"" | GlossaryQaFindingStatus>("");
  const [qaChapterFilter, setQaChapterFilter] = React.useState("");
  const [entrySearch, setEntrySearch] = React.useState("");
  const [entryTypeFilter, setEntryTypeFilter] = React.useState<"" | GlossaryTermType>("");
  const [activeDetailTab, setActiveDetailTab] = React.useState<DetailTab>("aliases");

  const novel = useQuery({
    queryKey: ["admin-novel", novelId],
    queryFn: () => api.novel(novelId),
  });

  const glossary = useQuery({
    queryKey: ["admin-glossary", novelId],
    queryFn: () => adminApi.listGlossaryEntries(novelId),
  });
  const entries = glossary.data ?? [];
  const selectedEntry = entries.find((entry) => entry.id === selectedEntryId) ?? null;
  const authMessage = authorizationMessage(glossary.error);
  const invalidateGlossary = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin-glossary", novelId] });
  };
  const invalidateSelectedEntryResources = () => {
    if (selectedEntryId !== null) {
      void queryClient.invalidateQueries({ queryKey: ["admin-glossary-aliases", novelId, selectedEntryId] });
      void queryClient.invalidateQueries({ queryKey: ["admin-glossary-provenance", novelId, selectedEntryId] });
    }
  };

  const aliases = useQuery({
    queryKey: ["admin-glossary-aliases", novelId, selectedEntryId],
    queryFn: () => adminApi.listGlossaryAliases(novelId, selectedEntryId ?? 0),
    enabled: selectedEntryId !== null,
  });

  const provenance = useQuery({
    queryKey: ["admin-glossary-provenance", novelId, selectedEntryId],
    queryFn: () => adminApi.listGlossaryProvenanceForEntry(novelId, selectedEntryId ?? 0),
    enabled: selectedEntryId !== null,
  });

  const decisionEvents = useQuery({
    queryKey: ["admin-glossary-decisions", novelId, selectedEntryId],
    queryFn: () => adminApi.listGlossaryDecisionEvents(novelId, selectedEntryId ?? undefined),
    enabled: selectedEntryId !== null,
  });

  const qaChapterId = qaChapterFilter.trim() ? Number(qaChapterFilter.trim()) : undefined;
  const qaFindings = useQuery({
    queryKey: ["admin-glossary-qa-findings", novelId, qaStatusFilter, qaChapterId],
    queryFn: () =>
      adminApi.listGlossaryQaFindings(novelId, {
        status: qaStatusFilter || undefined,
        chapter_id: typeof qaChapterId === "number" && Number.isFinite(qaChapterId) ? qaChapterId : undefined,
      }),
  });
  const normalizedSearch = entrySearch.trim().toLowerCase();
  const visibleEntries = entries.filter((entry) => {
    if (entryTypeFilter && entry.term_type !== entryTypeFilter) return false;
    if (!normalizedSearch) return true;
    const aliasHit = selectedEntryId === entry.id
      ? aliases.data?.some((alias) => alias.alias_text.toLowerCase().includes(normalizedSearch))
      : false;
    return (
      entry.canonical_term.toLowerCase().includes(normalizedSearch)
      || translationFor(entry).toLowerCase().includes(normalizedSearch)
      || Boolean(aliasHit)
    );
  });
  const novelTitle =
    typeof novel.data?.translated_title === "string" && novel.data.translated_title.trim()
      ? novel.data.translated_title
      : typeof novel.data?.title === "string" && novel.data.title.trim()
        ? novel.data.title
        : null;

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

  const addAlias = useMutation({
    mutationFn: ({ entryId, payload }: { entryId: number; payload: GlossaryAliasCreatePayload }) =>
      adminApi.addGlossaryAlias(novelId, entryId, payload),
    onSuccess: () => {
      setAliasDialogMode(null);
      setAliasValues(emptyAliasForm());
      invalidateSelectedEntryResources();
    },
  });

  const updateAlias = useMutation({
    mutationFn: ({ aliasId, payload }: { aliasId: number; payload: GlossaryAliasCreatePayload }) =>
      adminApi.updateGlossaryAlias(novelId, aliasId, payload),
    onSuccess: () => {
      setAliasDialogMode(null);
      setEditingAlias(null);
      invalidateSelectedEntryResources();
    },
  });

  const deprecateAlias = useMutation({
    mutationFn: (alias: GlossaryAlias) => adminApi.deprecateGlossaryAlias(novelId, alias.id),
    onSuccess: () => {
      setPendingAliasDeprecation(null);
      invalidateSelectedEntryResources();
    },
  });

  const addProvenance = useMutation({
    mutationFn: ({ entryId, payload }: { entryId: number; payload: GlossaryProvenanceCreatePayload }) =>
      adminApi.addGlossaryProvenance(novelId, entryId, payload),
    onSuccess: () => {
      setProvenanceDialogOpen(false);
      setProvenanceValues(emptyProvenanceForm());
      invalidateSelectedEntryResources();
    },
  });

  const updateQaStatus = useMutation({
    mutationFn: ({ findingId, status }: { findingId: number; status: GlossaryQaFindingStatus }) =>
      adminApi.updateGlossaryQaFindingStatus(novelId, findingId, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin-glossary-qa-findings", novelId] });
    },
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

  const openAddAlias = () => {
    addAlias.reset();
    updateAlias.reset();
    setAliasValidationError(null);
    setEditingAlias(null);
    setAliasValues(emptyAliasForm());
    setAliasDialogMode("add");
  };

  const openEditAlias = (alias: GlossaryAlias) => {
    addAlias.reset();
    updateAlias.reset();
    setAliasValidationError(null);
    setEditingAlias(alias);
    setAliasValues(aliasFormFromAlias(alias));
    setAliasDialogMode("edit");
  };

  const closeAliasDialog = () => {
    if (addAlias.isPending || updateAlias.isPending) return;
    setAliasDialogMode(null);
    setEditingAlias(null);
    setAliasValidationError(null);
  };

  const submitAlias = () => {
    if (!aliasValues.alias_text.trim()) {
      setAliasValidationError("Alias text is required.");
      return;
    }
    if (!selectedEntry) return;
    setAliasValidationError(null);
    if (aliasDialogMode === "add") {
      addAlias.mutate({ entryId: selectedEntry.id, payload: aliasPayload(aliasValues) });
      return;
    }
    if (editingAlias) {
      updateAlias.mutate({ aliasId: editingAlias.id, payload: aliasPayload(aliasValues) });
    }
  };

  const openAddProvenance = () => {
    addProvenance.reset();
    setProvenanceValidationError(null);
    setProvenanceValues(emptyProvenanceForm());
    setProvenanceDialogOpen(true);
  };

  const closeProvenanceDialog = () => {
    if (addProvenance.isPending) return;
    setProvenanceDialogOpen(false);
    setProvenanceValidationError(null);
  };

  const submitProvenance = () => {
    if (!selectedEntry) return;
    if (!provenanceValues.source_site.trim() || !provenanceValues.source_adapter.trim()) {
      setProvenanceValidationError("Source site and source adapter are required evidence fields.");
      return;
    }
    setProvenanceValidationError(null);
    addProvenance.mutate({ entryId: selectedEntry.id, payload: provenancePayload(provenanceValues) });
  };

  const closeDialog = () => {
    if (createEntry.isPending || updateEntry.isPending) return;
    setDialogMode(null);
    setEditingEntry(null);
    setFormValidationError(null);
  };

  const submitEntry = () => {
    if (!formValues.canonical_term.trim()) {
      setFormValidationError("Term is required.");
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
  const detailTabs: Array<{ id: DetailTab; label: string }> = [
    { id: "aliases", label: "Aliases" },
    { id: "evidence", label: "Evidence" },
    { id: "history", label: "History" },
    { id: "qa", label: "QA findings" },
  ];

  return (
    <>
      <PageHeading
        title={novelTitle ?? "Glossary"}
        description={novelTitle ? `Glossary - Novel: ${novelId}` : `Novel: ${novelId}`}
      />

      <Panel className="mb-4">
        <PanelBody className="space-y-2 text-sm text-muted-foreground">
          <p>Source IDs are evidence only. No global replace from this page. Saved chapter repair is a later explicit step.</p>
          <p>Approved means this translation is the default glossary translation for this novel. Applying it to saved chapters will be handled by a separate repair step.</p>
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
        <PanelBody className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
            <FieldLabel className="lg:flex-1">
              <span>Search term or translation</span>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={entrySearch}
                onChange={(event) => setEntrySearch(event.target.value)}
                placeholder="Search term or translation"
              />
            </FieldLabel>
            <OptionalSelectField
              label="Type"
              value={entryTypeFilter}
              options={TERM_TYPES}
              emptyLabel="All types"
              onChange={setEntryTypeFilter}
            />
          </div>
          <div className="seamless-scrollbar overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="min-w-[220px] px-4 py-3">Term</th>
                  <th className="min-w-[220px] px-4 py-3">Translation</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Locked</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="min-w-[300px] px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {glossary.isLoading ? (
                  <LoadingRows colSpan={6} label="Loading glossary entries..." />
                ) : glossary.error ? (
                  <EmptyState title="Failed to load glossary entries." description={authMessage ?? "Try refreshing after confirming the owner session."} colSpan={6} />
                ) : visibleEntries.length ? (
                  visibleEntries.map((entry) => (
                    <tr className="border-b last:border-0" key={entry.id}>
                      <td className="px-4 py-3">
                        <div className="font-medium">{entry.canonical_term}</div>
                      </td>
                      <td className="px-4 py-3">{translationFor(entry)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={statusTone(entry.status)}>{formatStatus(entry.status)}</Badge>
                      </td>
                      <td className="px-4 py-3">{entry.owner_locked ? "Yes" : "No"}</td>
                      <td className="px-4 py-3">{formatDate(entry.updated_at)}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            variant={selectedEntryId === entry.id ? "secondary" : "outline"}
                            onClick={() => {
                              setSelectedEntryId(entry.id);
                              setActiveDetailTab("aliases");
                            }}
                          >
                            {selectedEntryId === entry.id ? "Selected" : "Select"}
                          </Button>
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
                    title={entries.length ? "No glossary entries match your filters." : "No glossary entries yet."}
                    description={entries.length ? "Try another term, translation, or type." : "Add terms and translations for this novel."}
                    colSpan={6}
                  />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <Panel className="mt-4">
        <PanelHeader>
          <PanelTitle>{selectedEntry ? `Entry details: ${selectedEntry.canonical_term}` : "Entry details"}</PanelTitle>
        </PanelHeader>
        <PanelBody className="space-y-4">
          {selectedEntry ? (
            <>
              <div className="rounded-md border bg-muted/30 p-4">
                <div className="grid gap-3 md:grid-cols-4">
                  <div>
                    <div className="text-xs text-muted-foreground">Term</div>
                    <div className="font-medium">{selectedEntry.canonical_term}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Translation</div>
                    <div className="font-medium">{translationFor(selectedEntry)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Type</div>
                    <div>{formatStatus(selectedEntry.term_type)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Status</div>
                    <Badge tone={statusTone(selectedEntry.status)}>{formatStatus(selectedEntry.status)}</Badge>
                  </div>
                </div>
                {selectedEntry.admin_notes ? <div className="mt-3 text-sm text-muted-foreground">{selectedEntry.admin_notes}</div> : null}
              </div>

              <div className="flex flex-wrap gap-2">
                {detailTabs.map((tabItem) => (
                  <Button
                    key={tabItem.id}
                    size="sm"
                    variant={activeDetailTab === tabItem.id ? "secondary" : "outline"}
                    onClick={() => setActiveDetailTab(tabItem.id)}
                  >
                    {tabItem.label}
                  </Button>
                ))}
              </div>

              {activeDetailTab === "aliases" ? (
                <section className="rounded-md border">
                  <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Aliases</h3>
                    <Button size="sm" onClick={openAddAlias}>Add alias</Button>
                  </div>
                  <ErrorBanner error={aliases.error} fallback="Failed to load aliases." />
                  <ErrorBanner error={deprecateAlias.error} fallback="Failed to deprecate alias." />
                  <div className="p-4">
                    {aliases.isLoading ? (
                      <div className="text-sm text-muted-foreground">Loading aliases...</div>
                    ) : aliases.error ? (
                      <EmptyState title="Failed to load aliases." />
                    ) : aliases.data?.length ? (
                      <div className="space-y-3">
                        {aliases.data.map((alias) => (
                          <div key={alias.id} className="rounded-md border px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div>
                                <div className="font-medium">{alias.alias_text}</div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                  {formatStatus(alias.alias_type)}
                                  {alias.applies_to ? ` - ${formatStatus(alias.applies_to)}` : ""}
                                  {alias.matching_policy ? ` - ${formatStatus(alias.matching_policy)}` : ""}
                                </div>
                              </div>
                              <div className="flex gap-2">
                                <Button size="sm" variant="outline" onClick={() => openEditAlias(alias)}>Edit alias</Button>
                                <Button size="sm" variant="destructive" onClick={() => setPendingAliasDeprecation({ alias })} disabled={alias.alias_type === "deprecated"}>
                                  Deprecate alias
                                </Button>
                              </div>
                            </div>
                            {alias.alias_type === "banned" || alias.alias_type === "rejected" ? (
                              <div className="mt-2 rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-200">
                                Caution: this alias marks a risky or forbidden variant.
                              </div>
                            ) : null}
                            {alias.notes ? <div className="mt-2 text-xs text-muted-foreground">{alias.notes}</div> : null}
                            <div className="mt-2 text-xs text-muted-foreground">Updated {formatDate(alias.updated_at)}</div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No aliases yet." description="Add observed, allowed, rejected, banned, or source-variant aliases for this selected entry." />
                    )}
                  </div>
                </section>
              ) : null}

              {activeDetailTab === "evidence" ? (
                <section className="rounded-md border">
                  <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">Evidence</h3>
                    <Button size="sm" onClick={openAddProvenance}>Add evidence</Button>
                  </div>
                  <ErrorBanner error={provenance.error} fallback="Failed to load evidence." />
                  <div className="p-4">
                    {provenance.isLoading ? (
                      <div className="text-sm text-muted-foreground">Loading evidence...</div>
                    ) : provenance.error ? (
                      <EmptyState title="Failed to load evidence." />
                    ) : provenance.data?.length ? (
                      <div className="space-y-3">
                        {provenance.data.map((item) => (
                          <div key={item.id} className="rounded-md border px-3 py-2">
                            <div className="font-medium">{item.source_site} / {item.source_adapter}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {item.source_novel_id ? `Novel ${item.source_novel_id}` : "No source novel ID"}
                              {item.source_chapter_id ? ` - Chapter ID ${item.source_chapter_id}` : ""}
                              {item.source_chapter_number ? ` - Ch. ${item.source_chapter_number}` : ""}
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                              {item.raw_source_term ? <div>Raw: {item.raw_source_term}</div> : null}
                              {item.observed_translated_term ? <div>Observed: {item.observed_translated_term}</div> : null}
                              {item.evidence_quality ? <div>Quality: {formatStatus(item.evidence_quality)}</div> : null}
                              {typeof item.confidence === "number" ? <div>Confidence: {item.confidence}</div> : null}
                              {item.evidence_ref ? <div>Evidence: {item.evidence_ref}</div> : null}
                              {item.local_reference ? <div>Reference: {item.local_reference}</div> : null}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No evidence yet." description="Add compact evidence rows for this selected entry." />
                    )}
                  </div>
                </section>
              ) : null}

              {activeDetailTab === "history" ? (
                <section className="rounded-md border">
                  <div className="border-b px-4 py-3">
                    <h3 className="text-sm font-semibold">History</h3>
                  </div>
                  <ErrorBanner error={decisionEvents.error} fallback="Failed to load history." />
                  <div className="p-4">
                    {decisionEvents.isLoading ? (
                      <div className="text-sm text-muted-foreground">Loading history...</div>
                    ) : decisionEvents.error ? (
                      <EmptyState title="Failed to load history." />
                    ) : decisionEvents.data?.length ? (
                      <div className="space-y-3">
                        {decisionEvents.data.map((event: GlossaryDecisionEvent) => (
                          <div key={event.id} className="rounded-md border px-3 py-2 text-sm">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <div className="font-medium">{formatStatus(event.event_type)}</div>
                              <div className="text-xs text-muted-foreground">{formatDate(event.created_at)}</div>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              Actor: {event.actor_user_id ?? "unknown"} - Source: {event.decision_source}
                            </div>
                            <div className="mt-2 text-sm">{event.rationale || "No rationale recorded."}</div>
                            {jsonSummary(event.old_value_json) || jsonSummary(event.new_value_json) ? (
                              <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                                {jsonSummary(event.old_value_json) ? <div>Previous: {jsonSummary(event.old_value_json)}</div> : null}
                                {jsonSummary(event.new_value_json) ? <div>New: {jsonSummary(event.new_value_json)}</div> : null}
                              </div>
                            ) : null}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No history yet." description="Meaningful owner/admin glossary changes will appear here when recorded by the backend." />
                    )}
                  </div>
                </section>
              ) : null}

              {activeDetailTab === "qa" ? (
                <section className="rounded-md border">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3">
                    <div>
                      <h3 className="text-sm font-semibold">QA findings</h3>
                      <p className="mt-1 text-xs text-muted-foreground">Data access only. No QA scan or automatic repair runs here.</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <select
                        aria-label="Filter QA findings by status"
                        className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                        value={qaStatusFilter}
                        onChange={(event) => setQaStatusFilter(event.target.value as "" | GlossaryQaFindingStatus)}
                      >
                        <option value="">All statuses</option>
                        {QA_STATUSES.map((status) => (
                          <option key={status} value={status}>{formatStatus(status)}</option>
                        ))}
                      </select>
                      <input
                        aria-label="Filter QA findings by chapter id"
                        className="h-8 w-32 rounded-md border border-border bg-background px-2 text-xs"
                        placeholder="Chapter ID"
                        value={qaChapterFilter}
                        onChange={(event) => setQaChapterFilter(event.target.value)}
                      />
                    </div>
                  </div>
                  <ErrorBanner error={qaFindings.error} fallback="Failed to load QA findings." />
                  <ErrorBanner error={updateQaStatus.error} fallback="Failed to update QA finding status." />
                  <div className="p-4">
                    {qaFindings.isLoading ? (
                      <div className="text-sm text-muted-foreground">Loading QA findings...</div>
                    ) : qaFindings.error ? (
                      <EmptyState title="Failed to load QA findings." />
                    ) : qaFindings.data?.length ? (
                      <div className="space-y-3">
                        {qaFindings.data.map((finding: GlossaryQaFinding) => (
                          <div key={finding.id} className="rounded-md border px-3 py-2 text-sm">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <div className="font-medium">{formatStatus(finding.finding_type)}</div>
                                <div className="mt-1 text-xs text-muted-foreground">
                                  Severity: {formatStatus(finding.severity)}
                                  {finding.chapter_id ? ` - Chapter ${finding.chapter_id}` : ""}
                                  {finding.glossary_entry_id ? ` - Entry ${finding.glossary_entry_id}` : ""}
                                </div>
                              </div>
                              <select
                                aria-label={`Update QA finding ${finding.id} status`}
                                className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                                value={finding.status}
                                onChange={(event) => updateQaStatus.mutate({ findingId: finding.id, status: event.target.value as GlossaryQaFindingStatus })}
                                disabled={updateQaStatus.isPending}
                              >
                                {QA_STATUSES.map((status) => (
                                  <option key={status} value={status}>{formatStatus(status)}</option>
                                ))}
                              </select>
                            </div>
                            <div className="mt-2 grid gap-1 text-xs text-muted-foreground">
                              {finding.matched_text ? <div>Matched: {finding.matched_text}</div> : null}
                              {finding.suggested_text ? <div>Suggested: {finding.suggested_text}</div> : null}
                              {finding.context_ref ? <div>Context: {finding.context_ref}</div> : null}
                              {finding.reviewer_notes ? <div>Reviewer notes: {finding.reviewer_notes}</div> : null}
                              <div>Created {formatDate(finding.created_at)}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <EmptyState title="No QA findings yet." description="Existing findings will appear here after backend data exists. This page does not run QA scans." />
                    )}
                  </div>
                </section>
              ) : null}
            </>
          ) : (
            <EmptyState title="Select an entry to manage details." description="Aliases, evidence, history, and QA findings stay tucked away until an entry is selected." />
          )}
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

      <AliasDialog
        mode={aliasDialogMode ?? "add"}
        open={aliasDialogMode !== null}
        values={aliasValues}
        pending={addAlias.isPending || updateAlias.isPending}
        error={aliasDialogMode === "add" ? addAlias.error : updateAlias.error}
        validationError={aliasValidationError}
        onChange={setAliasValues}
        onSubmit={submitAlias}
        onClose={closeAliasDialog}
      />

      <ProvenanceDialog
        open={provenanceDialogOpen}
        values={provenanceValues}
        pending={addProvenance.isPending}
        error={addProvenance.error}
        validationError={provenanceValidationError}
        onChange={setProvenanceValues}
        onSubmit={submitProvenance}
        onClose={closeProvenanceDialog}
      />

      <ConfirmDialog
        open={pendingAliasDeprecation !== null}
        title="Deprecate alias"
        description={pendingAliasDeprecation ? `Deprecate alias "${pendingAliasDeprecation.alias.alias_text}"?` : undefined}
        confirmLabel="Deprecate alias"
        destructive
        pending={deprecateAlias.isPending}
        onConfirm={() => {
          if (pendingAliasDeprecation) deprecateAlias.mutate(pendingAliasDeprecation.alias);
        }}
        onCancel={() => {
          if (!deprecateAlias.isPending) setPendingAliasDeprecation(null);
        }}
        auditNotice="This changes alias state for the selected novel-scoped glossary entry."
      />
    </>
  );
}
