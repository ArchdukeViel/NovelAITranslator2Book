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
  GlossaryCandidateImportResult,
  GlossaryDecisionEvent,
  GlossaryEnforcementLevel,
  GlossaryEntry,
  GlossaryEntryCreatePayload,
  GlossaryEntryStatus,
  GlossaryEntryUpdatePayload,
  GlossaryEvidenceQuality,
  GlossaryMatchingPolicy,
  GlossaryProvenanceCreatePayload,
  GlossaryProviderCandidateRequest,
  GlossaryProviderCandidateResult,
  GlossaryQaFinding,
  GlossaryQaFindingStatus,
  GlossaryReplacementPolicy,
  GlossaryTermType,
} from "@/lib/api-types";

const STATUS_ORDER: GlossaryEntryStatus[] = ["candidate", "recommended", "approved", "rejected", "deprecated"];
const OWNER_STATUS_OPTIONS: GlossaryEntryStatus[] = ["candidate", "approved"];
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
const DEFAULT_IMPORT_MAX_CANDIDATES = 50;
const DEFAULT_PROVIDER_MAX_CANDIDATES = 5;
const DEFAULT_PROVIDER_MAX_CHAPTERS = 1;
const DEFAULT_PROVIDER_MAX_CHARS = 4000;

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

type ProviderSuggestionValues = {
  maxCandidates: number;
  maxChapters: number;
  maxChars: number;
  provider: string;
  providerModel: string;
};

type PendingAliasDeprecation = {
  alias: GlossaryAlias;
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
    status: ownerStatusFromBackend(entry.status),
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
    status: ownerStatusFromBackend(values.status),
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

function emptyProviderSuggestionValues(): ProviderSuggestionValues {
  return {
    maxCandidates: DEFAULT_PROVIDER_MAX_CANDIDATES,
    maxChapters: DEFAULT_PROVIDER_MAX_CHAPTERS,
    maxChars: DEFAULT_PROVIDER_MAX_CHARS,
    provider: "",
    providerModel: "",
  };
}

function providerSuggestionPayload(values: ProviderSuggestionValues): GlossaryProviderCandidateRequest {
  return {
    max_candidates: values.maxCandidates,
    max_chapters: values.maxChapters,
    max_chars: values.maxChars,
    provider: optionalText(values.provider) ?? undefined,
    provider_model: optionalText(values.providerModel) ?? undefined,
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

function ownerStatusFromBackend(status: GlossaryEntryStatus): GlossaryEntryStatus {
  return status === "approved" ? "approved" : "candidate";
}

function ownerStatusLabel(status: GlossaryEntryStatus) {
  return ownerStatusFromBackend(status) === "approved" ? "Approved" : "Reviewing";
}

function ownerStatusTone(status: GlossaryEntryStatus) {
  return ownerStatusFromBackend(status) === "approved" ? "green" : "amber";
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

function candidateActionLabel(action: string) {
  return formatStatus(action);
}

function formatConfidence(value: number) {
  return `${Math.round(value * 100)}%`;
}

function countByOwnerStatus(entries: GlossaryEntry[]) {
  return OWNER_STATUS_OPTIONS.map((status) => ({
    status,
    count: entries.filter((entry) => ownerStatusFromBackend(entry.status) === status).length,
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

function OwnerStatusSelect({
  value,
  onChange,
}: {
  value: GlossaryEntryStatus;
  onChange: (value: GlossaryEntryStatus) => void;
}) {
  return (
    <FieldLabel>
      <span>Status</span>
      <select
        className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
        value={ownerStatusFromBackend(value)}
        onChange={(event) => onChange(event.target.value as GlossaryEntryStatus)}
      >
        {OWNER_STATUS_OPTIONS.map((status) => (
          <option key={status} value={status}>
            {ownerStatusLabel(status)}
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
          <OwnerStatusSelect value={values.status} onChange={(value) => setValue("status", value)} />
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

function CandidateImportDialog({
  open,
  maxCandidates,
  previewResult,
  applyResult,
  validationError,
  previewPending,
  applyPending,
  previewError,
  applyError,
  onMaxCandidatesChange,
  onPreview,
  onApply,
  onClose,
}: {
  open: boolean;
  maxCandidates: number;
  previewResult: GlossaryCandidateImportResult | null;
  applyResult: GlossaryCandidateImportResult | null;
  validationError: string | null;
  previewPending: boolean;
  applyPending: boolean;
  previewError: unknown;
  applyError: unknown;
  onMaxCandidatesChange: (value: number) => void;
  onPreview: () => void;
  onApply: () => void;
  onClose: () => void;
}) {
  const result = applyResult ?? previewResult;
  const hasPreviewCandidates = Boolean(previewResult && previewResult.candidates.length > 0 && !applyResult);
  const pending = previewPending || applyPending;

  return (
    <DialogShell
      open={open}
      title="Import review candidates"
      description="Find possible terms from saved raw/translated chapters. Imported terms stay Reviewing until approved."
      onClose={onClose}
      className="max-w-5xl"
      footer={
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            This imports the previewed candidate set using the same max candidate limit.
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onClose} disabled={pending}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={onPreview} disabled={pending}>
              {previewPending ? "Previewing..." : "Preview candidates"}
            </Button>
            {hasPreviewCandidates ? (
              <Button onClick={onApply} disabled={pending}>
                {applyPending ? "Importing..." : "Import as Reviewing"}
              </Button>
            ) : null}
          </div>
        </div>
      }
    >
      <div className="space-y-4 p-4">
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
          Imported candidates are Reviewing. Approving is manual. Saved chapter rewriting is a separate future step. This import uses saved chapters only.
        </div>
        <FieldLabel className="max-w-xs">
          <span>Max candidates</span>
          <input
            type="number"
            min={1}
            max={500}
            aria-label="Max candidates"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={maxCandidates}
            onChange={(event) => onMaxCandidatesChange(Number(event.target.value))}
          />
          <span className="block text-xs font-normal text-muted-foreground">
            Limits how many candidate terms are previewed or imported.
          </span>
        </FieldLabel>
        {validationError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {validationError}
          </div>
        ) : null}
        <ErrorBanner error={previewError} fallback="Failed to preview glossary candidates." className="border" />
        <ErrorBanner error={applyError} fallback="Failed to import glossary candidates." className="border" />

        {result ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Found</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_found}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Created</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_created}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Merged</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_merged}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Skipped</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_skipped}</div>
              </div>
            </div>

            {applyResult ? (
              <div className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-900 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
                Import complete. Created {applyResult.candidates_created}, merged {applyResult.candidates_merged}, skipped {applyResult.candidates_skipped}.
              </div>
            ) : null}
            {previewResult && !previewResult.candidates.length ? (
              <EmptyState title="No new review candidates found from saved chapters." description="Try again after more saved raw or translated chapters are available." />
            ) : null}

            {result.warnings.length ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                <div className="font-medium">Warnings</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {result.conflicts.length ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <div className="font-medium">Conflicts</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {result.conflicts.map((conflict) => (
                    <li key={conflict}>{conflict}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {result.candidates.length ? (
              <div className="seamless-scrollbar overflow-auto rounded-md border">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="min-w-[180px] px-3 py-2">Term</th>
                      <th className="min-w-[180px] px-3 py-2">Translation</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Confidence</th>
                      <th className="px-3 py-2">Frequency</th>
                      <th className="px-3 py-2">Action</th>
                      <th className="min-w-[180px] px-3 py-2">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.candidates.map((candidate) => (
                      <tr key={`${candidate.term}-${candidate.translation}`} className="border-b last:border-0">
                        <td className="px-3 py-2 font-medium">{candidate.term}</td>
                        <td className="px-3 py-2">{candidate.translation}</td>
                        <td className="px-3 py-2">{formatStatus(candidate.term_type)}</td>
                        <td className="px-3 py-2">{formatConfidence(candidate.confidence)}</td>
                        <td className="px-3 py-2">{candidate.frequency}</td>
                        <td className="px-3 py-2">{candidateActionLabel(candidate.action)}</td>
                        <td className="px-3 py-2 text-muted-foreground">{candidate.notes ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </DialogShell>
  );
}

function ProviderSuggestionDialog({
  open,
  values,
  previewResult,
  applyResult,
  validationError,
  previewPending,
  applyPending,
  previewError,
  applyError,
  onValuesChange,
  onPreview,
  onApply,
  onClose,
}: {
  open: boolean;
  values: ProviderSuggestionValues;
  previewResult: GlossaryProviderCandidateResult | null;
  applyResult: GlossaryProviderCandidateResult | null;
  validationError: string | null;
  previewPending: boolean;
  applyPending: boolean;
  previewError: unknown;
  applyError: unknown;
  onValuesChange: (values: ProviderSuggestionValues) => void;
  onPreview: () => void;
  onApply: () => void;
  onClose: () => void;
}) {
  const result = applyResult ?? previewResult;
  const hasPreviewCandidates = Boolean(previewResult && previewResult.candidates.length > 0 && !applyResult);
  const pending = previewPending || applyPending;
  const setValue = <K extends keyof ProviderSuggestionValues>(key: K, value: ProviderSuggestionValues[K]) => {
    onValuesChange({ ...values, [key]: value });
  };

  return (
    <DialogShell
      open={open}
      title="Suggest with provider"
      description="Ask the configured translation provider to suggest possible glossary terms from saved chapters. Suggestions stay Reviewing until approved."
      onClose={onClose}
      className="max-w-5xl"
      footer={
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs text-muted-foreground">
            This may call the provider again using the same limits. It will create or merge Reviewing glossary entries only. It will not approve terms or rewrite saved chapters.
          </div>
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={onClose} disabled={pending}>
              Cancel
            </Button>
            <Button variant="secondary" onClick={onPreview} disabled={pending}>
              {previewPending ? "Previewing..." : "Preview suggestions"}
            </Button>
            {hasPreviewCandidates ? (
              <Button onClick={onApply} disabled={pending}>
                {applyPending ? "Importing..." : "Import as Reviewing"}
              </Button>
            ) : null}
          </div>
        </div>
      }
    >
      <div className="space-y-4 p-4">
        <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
          Suggestions stay Reviewing. Approval is manual. Saved chapter rewriting is a separate future step. Provider output can be wrong and should be reviewed.
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <FieldLabel>
            <span>Max candidates</span>
            <input
              type="number"
              min={1}
              max={100}
              aria-label="Max candidates"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.maxCandidates}
              onChange={(event) => setValue("maxCandidates", Number(event.target.value))}
            />
          </FieldLabel>
          <FieldLabel>
            <span>Max chapters</span>
            <input
              type="number"
              min={1}
              max={20}
              aria-label="Max chapters"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.maxChapters}
              onChange={(event) => setValue("maxChapters", Number(event.target.value))}
            />
          </FieldLabel>
          <FieldLabel>
            <span>Max characters</span>
            <input
              type="number"
              min={1000}
              max={50000}
              aria-label="Max characters"
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={values.maxChars}
              onChange={(event) => setValue("maxChars", Number(event.target.value))}
            />
          </FieldLabel>
        </div>

        <details className="rounded-md border px-3 py-2 text-sm">
          <summary className="cursor-pointer font-medium">Advanced</summary>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <FieldLabel>
              <span>Provider</span>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={values.provider}
                onChange={(event) => setValue("provider", event.target.value)}
                placeholder="Use configured default"
              />
            </FieldLabel>
            <FieldLabel>
              <span>Provider model</span>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={values.providerModel}
                onChange={(event) => setValue("providerModel", event.target.value)}
                placeholder="Use provider default"
              />
            </FieldLabel>
          </div>
        </details>

        {validationError ? (
          <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {validationError}
          </div>
        ) : null}
        <ErrorBanner error={previewError} fallback="Failed to preview provider suggestions." className="border" />
        <ErrorBanner error={applyError} fallback="Failed to import provider suggestions." className="border" />

        {result ? (
          <div className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-4">
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Found</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_found}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Created</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_created}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Merged</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_merged}</div>
              </div>
              <div className="rounded-md border px-3 py-2">
                <div className="text-xs uppercase text-muted-foreground">Skipped</div>
                <div className="mt-1 text-xl font-semibold">{result.candidates_skipped}</div>
              </div>
            </div>

            {applyResult ? (
              <div className="rounded-md border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-900 dark:border-green-900 dark:bg-green-950 dark:text-green-200">
                Import complete. Created {applyResult.candidates_created}, merged {applyResult.candidates_merged}, skipped {applyResult.candidates_skipped}.
              </div>
            ) : null}
            {previewResult && !previewResult.candidates.length ? (
              <EmptyState title="No provider suggestions found with these limits." description="Try a larger chapter or character limit after confirming saved chapters are available." />
            ) : null}

            {result.warnings.length ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                <div className="font-medium">Warnings</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {result.provider_warnings.length ? (
              <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
                <div className="font-medium">Provider warnings</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {result.provider_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {result.conflicts.length ? (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                <div className="font-medium">Conflicts</div>
                <ul className="mt-1 list-disc space-y-1 pl-4">
                  {result.conflicts.map((conflict) => (
                    <li key={conflict}>{conflict}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {result.candidates.length ? (
              <div className="seamless-scrollbar overflow-auto rounded-md border">
                <table className="w-full text-left text-sm">
                  <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="min-w-[160px] px-3 py-2">Term</th>
                      <th className="min-w-[160px] px-3 py-2">Translation</th>
                      <th className="px-3 py-2">Type</th>
                      <th className="px-3 py-2">Confidence</th>
                      <th className="min-w-[160px] px-3 py-2">Aliases</th>
                      <th className="px-3 py-2">Action</th>
                      <th className="min-w-[220px] px-3 py-2">Notes</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.candidates.map((candidate) => (
                      <tr key={`${candidate.raw_term}-${candidate.translation}`} className="border-b last:border-0">
                        <td className="px-3 py-2 font-medium">{candidate.term}</td>
                        <td className="px-3 py-2">{candidate.translation}</td>
                        <td className="px-3 py-2">{formatStatus(candidate.term_type)}</td>
                        <td className="px-3 py-2">{formatConfidence(candidate.confidence)}</td>
                        <td className="px-3 py-2 text-muted-foreground">{candidate.aliases.length ? candidate.aliases.join(", ") : "-"}</td>
                        <td className="px-3 py-2">{candidateActionLabel(candidate.action)}</td>
                        <td className="px-3 py-2 text-muted-foreground">{candidate.notes ?? candidate.rationale ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        ) : null}
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
  const [candidateImportOpen, setCandidateImportOpen] = React.useState(false);
  const [candidateImportMax, setCandidateImportMax] = React.useState(DEFAULT_IMPORT_MAX_CANDIDATES);
  const [candidateImportValidationError, setCandidateImportValidationError] = React.useState<string | null>(null);
  const [candidateImportPreview, setCandidateImportPreview] = React.useState<GlossaryCandidateImportResult | null>(null);
  const [candidateImportApply, setCandidateImportApply] = React.useState<GlossaryCandidateImportResult | null>(null);
  const [providerSuggestionOpen, setProviderSuggestionOpen] = React.useState(false);
  const [providerSuggestionValues, setProviderSuggestionValues] = React.useState<ProviderSuggestionValues>(emptyProviderSuggestionValues());
  const [providerSuggestionValidationError, setProviderSuggestionValidationError] = React.useState<string | null>(null);
  const [providerSuggestionPreview, setProviderSuggestionPreview] = React.useState<GlossaryProviderCandidateResult | null>(null);
  const [providerSuggestionApply, setProviderSuggestionApply] = React.useState<GlossaryProviderCandidateResult | null>(null);

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
    enabled: false,
  });

  const provenance = useQuery({
    queryKey: ["admin-glossary-provenance", novelId, selectedEntryId],
    queryFn: () => adminApi.listGlossaryProvenanceForEntry(novelId, selectedEntryId ?? 0),
    enabled: false,
  });

  const decisionEvents = useQuery({
    queryKey: ["admin-glossary-decisions", novelId, selectedEntryId],
    queryFn: () => adminApi.listGlossaryDecisionEvents(novelId, selectedEntryId ?? undefined),
    enabled: false,
  });

  const qaChapterId = qaChapterFilter.trim() ? Number(qaChapterFilter.trim()) : undefined;
  const qaFindings = useQuery({
    queryKey: ["admin-glossary-qa-findings", novelId, qaStatusFilter, qaChapterId],
    queryFn: () =>
      adminApi.listGlossaryQaFindings(novelId, {
        status: qaStatusFilter || undefined,
        chapter_id: typeof qaChapterId === "number" && Number.isFinite(qaChapterId) ? qaChapterId : undefined,
      }),
    enabled: false,
  });
  const normalizedSearch = entrySearch.trim().toLowerCase();
  const visibleEntries = entries.filter((entry) => {
    if (entryTypeFilter && entry.term_type !== entryTypeFilter) return false;
    if (!normalizedSearch) return true;
    return (
      entry.canonical_term.toLowerCase().includes(normalizedSearch)
      || translationFor(entry).toLowerCase().includes(normalizedSearch)
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
    mutationFn: async ({ entryId, payload, status }: { entryId: number; payload: GlossaryEntryUpdatePayload; status?: GlossaryEntryStatus }) => {
      const updated = await adminApi.updateGlossaryEntry(novelId, entryId, payload);
      if (status) {
        return adminApi.changeGlossaryEntryStatus(novelId, entryId, { status });
      }
      return updated;
    },
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

  const previewCandidateImport = useMutation({
    mutationFn: (maxCandidates: number) =>
      adminApi.previewGlossaryCandidateImport(novelId, { max_candidates: maxCandidates }),
    onSuccess: (result) => {
      setCandidateImportPreview(result);
      setCandidateImportApply(null);
    },
  });

  const applyCandidateImport = useMutation({
    mutationFn: (maxCandidates: number) =>
      adminApi.applyGlossaryCandidateImport(novelId, { max_candidates: maxCandidates }),
    onSuccess: (result) => {
      setCandidateImportApply(result);
      invalidateGlossary();
    },
  });

  const previewProviderSuggestions = useMutation({
    mutationFn: (payload: GlossaryProviderCandidateRequest) =>
      adminApi.previewGlossaryProviderCandidates(novelId, payload),
    onSuccess: (result) => {
      setProviderSuggestionPreview(result);
      setProviderSuggestionApply(null);
    },
  });

  const applyProviderSuggestions = useMutation({
    mutationFn: (payload: GlossaryProviderCandidateRequest) =>
      adminApi.applyGlossaryProviderCandidates(novelId, payload),
    onSuccess: (result) => {
      setProviderSuggestionApply(result);
      invalidateGlossary();
    },
  });

  const validateCandidateImportMax = () => {
    if (!Number.isInteger(candidateImportMax) || candidateImportMax < 1 || candidateImportMax > 500) {
      setCandidateImportValidationError("Max candidates must be between 1 and 500.");
      return null;
    }
    setCandidateImportValidationError(null);
    return candidateImportMax;
  };

  const openCandidateImport = () => {
    previewCandidateImport.reset();
    applyCandidateImport.reset();
    setCandidateImportValidationError(null);
    setCandidateImportPreview(null);
    setCandidateImportApply(null);
    setCandidateImportMax(DEFAULT_IMPORT_MAX_CANDIDATES);
    setCandidateImportOpen(true);
  };

  const closeCandidateImport = () => {
    if (previewCandidateImport.isPending || applyCandidateImport.isPending) return;
    setCandidateImportOpen(false);
  };

  const runCandidateImportPreview = () => {
    const maxCandidates = validateCandidateImportMax();
    if (maxCandidates === null) return;
    setCandidateImportApply(null);
    previewCandidateImport.mutate(maxCandidates);
  };

  const runCandidateImportApply = () => {
    const maxCandidates = validateCandidateImportMax();
    if (maxCandidates === null) return;
    applyCandidateImport.mutate(maxCandidates);
  };

  const validateProviderSuggestionValues = () => {
    if (!Number.isInteger(providerSuggestionValues.maxCandidates) || providerSuggestionValues.maxCandidates < 1 || providerSuggestionValues.maxCandidates > 100) {
      setProviderSuggestionValidationError("Max candidates must be between 1 and 100.");
      return null;
    }
    if (!Number.isInteger(providerSuggestionValues.maxChapters) || providerSuggestionValues.maxChapters < 1 || providerSuggestionValues.maxChapters > 20) {
      setProviderSuggestionValidationError("Max chapters must be between 1 and 20.");
      return null;
    }
    if (!Number.isInteger(providerSuggestionValues.maxChars) || providerSuggestionValues.maxChars < 1000 || providerSuggestionValues.maxChars > 50000) {
      setProviderSuggestionValidationError("Max characters must be between 1000 and 50000.");
      return null;
    }
    setProviderSuggestionValidationError(null);
    return providerSuggestionPayload(providerSuggestionValues);
  };

  const openProviderSuggestions = () => {
    previewProviderSuggestions.reset();
    applyProviderSuggestions.reset();
    setProviderSuggestionValidationError(null);
    setProviderSuggestionPreview(null);
    setProviderSuggestionApply(null);
    setProviderSuggestionValues(emptyProviderSuggestionValues());
    setProviderSuggestionOpen(true);
  };

  const closeProviderSuggestions = () => {
    if (previewProviderSuggestions.isPending || applyProviderSuggestions.isPending) return;
    setProviderSuggestionOpen(false);
  };

  const runProviderSuggestionPreview = () => {
    const payload = validateProviderSuggestionValues();
    if (payload === null) return;
    setProviderSuggestionApply(null);
    previewProviderSuggestions.mutate(payload);
  };

  const runProviderSuggestionApply = () => {
    const payload = validateProviderSuggestionValues();
    if (payload === null) return;
    applyProviderSuggestions.mutate(payload);
  };

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
      const nextStatus = ownerStatusFromBackend(formValues.status);
      const currentStatus = ownerStatusFromBackend(editingEntry.status);
      updateEntry.mutate({
        entryId: editingEntry.id,
        payload: updatePayload(formValues),
        status: nextStatus !== currentStatus ? nextStatus : undefined,
      });
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
        title={novelTitle ?? "Glossary"}
        description={novelTitle ? `Glossary - Novel: ${novelId}` : `Novel: ${novelId}`}
      />

      <Panel className="mb-4">
        <PanelBody className="space-y-2 text-sm text-muted-foreground">
          <p>Source IDs are evidence only. No global replace from this page. Saved chapter rewriting is a separate future step.</p>
          <p>Approved means this translation is the default glossary translation for this novel. Imported candidates remain Reviewing until manually approved.</p>
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
            <div className="grid gap-3 sm:grid-cols-2">
              {countByOwnerStatus(entries).map(({ status, count }) => (
                <div key={status} className="rounded-md border px-3 py-2">
                  <div className="text-xs uppercase text-muted-foreground">{ownerStatusLabel(status)}</div>
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
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="outline" onClick={openCandidateImport}>
              Import review candidates
            </Button>
            <Button size="sm" variant="secondary" onClick={openProviderSuggestions}>
              Suggest with provider
            </Button>
            <Button size="sm" onClick={openCreate}>
              Create entry
            </Button>
          </div>
        </PanelHeader>
        <ErrorBanner error={glossary.error} fallback="Failed to load glossary entries." />
        <ErrorBanner error={changeStatus.error} fallback="Failed to update glossary entry status." />
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
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            Find possible terms from saved raw/translated chapters. Imported terms stay Reviewing until approved.
          </div>
          <div className="rounded-md border bg-muted/30 px-3 py-2 text-sm text-muted-foreground">
            Ask the configured translation provider to suggest possible glossary terms from saved chapters. Suggestions stay Reviewing until approved.
          </div>
          <div className="seamless-scrollbar overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b bg-muted/55 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="min-w-[220px] px-4 py-3">Term</th>
                  <th className="min-w-[220px] px-4 py-3">Translation</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="min-w-[180px] px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {glossary.isLoading ? (
                  <LoadingRows colSpan={4} label="Loading glossary entries..." />
                ) : glossary.error ? (
                  <EmptyState title="Failed to load glossary entries." description={authMessage ?? "Try refreshing after confirming the owner session."} colSpan={4} />
                ) : visibleEntries.length ? (
                  visibleEntries.map((entry) => (
                    <tr
                      className={`cursor-pointer border-b transition-colors hover:bg-muted/45 last:border-0 ${selectedEntryId === entry.id ? "bg-muted/55" : ""}`}
                      key={entry.id}
                      tabIndex={0}
                      onClick={() => setSelectedEntryId(entry.id)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          setSelectedEntryId(entry.id);
                        }
                      }}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium">{entry.canonical_term}</div>
                      </td>
                      <td className="px-4 py-3">{translationFor(entry)}</td>
                      <td className="px-4 py-3">
                        <Badge tone={ownerStatusTone(entry.status)}>{ownerStatusLabel(entry.status)}</Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2">
                          <Button size="sm" variant="outline" onClick={(event) => {
                            event.stopPropagation();
                            openEdit(entry);
                          }}>
                            Edit
                          </Button>
                          {ownerStatusFromBackend(entry.status) === "approved" ? (
                            <Button size="sm" variant="secondary" disabled>Approved</Button>
                          ) : (
                            <Button
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                changeStatus.mutate({ entryId: entry.id, status: "approved" });
                              }}
                              disabled={changeStatus.isPending}
                            >
                              Approve
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <EmptyState
                    title={entries.length ? "No glossary entries match your filters." : "No glossary entries yet."}
                    description={entries.length ? "Try another term, translation, or type." : "Add terms manually or import review candidates from saved raw/translated chapters."}
                    colSpan={4}
                  />
                )}
              </tbody>
            </table>
          </div>
        </PanelBody>
      </Panel>

      <CandidateImportDialog
        open={candidateImportOpen}
        maxCandidates={candidateImportMax}
        previewResult={candidateImportPreview}
        applyResult={candidateImportApply}
        validationError={candidateImportValidationError}
        previewPending={previewCandidateImport.isPending}
        applyPending={applyCandidateImport.isPending}
        previewError={previewCandidateImport.error}
        applyError={applyCandidateImport.error}
        onMaxCandidatesChange={(value) => {
          setCandidateImportMax(value);
          setCandidateImportValidationError(null);
          setCandidateImportPreview(null);
          setCandidateImportApply(null);
        }}
        onPreview={runCandidateImportPreview}
        onApply={runCandidateImportApply}
        onClose={closeCandidateImport}
      />

      <ProviderSuggestionDialog
        open={providerSuggestionOpen}
        values={providerSuggestionValues}
        previewResult={providerSuggestionPreview}
        applyResult={providerSuggestionApply}
        validationError={providerSuggestionValidationError}
        previewPending={previewProviderSuggestions.isPending}
        applyPending={applyProviderSuggestions.isPending}
        previewError={previewProviderSuggestions.error}
        applyError={applyProviderSuggestions.error}
        onValuesChange={(values) => {
          setProviderSuggestionValues(values);
          setProviderSuggestionValidationError(null);
          setProviderSuggestionPreview(null);
          setProviderSuggestionApply(null);
        }}
        onPreview={runProviderSuggestionPreview}
        onApply={runProviderSuggestionApply}
        onClose={closeProviderSuggestions}
      />

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
