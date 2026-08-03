export type ApiErrorPayload = {
  status: number;
  code: string;
  message: string;
  explanation?: string | null;
  details?: unknown;
  trace_id?: string | null;
  raw?: unknown;
};

export type NovelSummary = {
  novel_id: string;
  title?: string | null;
  source_title?: string | null;
  author?: string | null;
  source_key?: string | null;
  source_url?: string | null;
  publication_status?: string | null;
  chapter_count: number;
  scraped_count?: number;
  translated_count?: number;
  is_published?: boolean;
  latest_chapter_id?: string | null;
  latest_chapter_number?: number | null;
  latest_chapter_title?: string | null;
  glossary_status?: GlossaryReadinessStatus;
  glossary_revision?: number;
  glossary_pending_count?: number;
  onboarding_status?: string | null;
  onboarding_updated_at?: string | null;
  onboarding_error_code?: string | null;
  onboarding_error_message?: string | null;
  body_scrape_required?: boolean | null;
  // Live storage-derived counts (from /api/admin/library/summary)
  total?: number;
  failed?: number;
  pending?: number;
};

export type LibrarySummaryItem = {
  novel_id: string;
  total: number;
  scraped: number;
  translated: number;
  failed: number;
  pending: number;
};

export type LibrarySummaryResponse = {
  generated_at: string;
  cache: {
    hit: boolean;
    ttl_seconds: number;
  };
  totals: LibrarySummaryItem;
  items: LibrarySummaryItem[];
};

export type AnalyticsWindow = "5m" | "15m" | "1h" | "24h" | "7d" | "30d";

export type AnalyticsTimezone =
  | "UTC"
  | "America/New_York"
  | "America/Chicago"
  | "America/Denver"
  | "America/Los_Angeles"
  | "Europe/London"
  | "Europe/Berlin"
  | "Europe/Moscow"
  | "Asia/Tokyo"
  | "Asia/Shanghai"
  | "Asia/Kolkata"
  | "Australia/Sydney"
  | "Pacific/Auckland";

export type AnalyticsEventCounts = Record<string, number>;

export type AnalyticsTopNovel = {
  novel_id: string;
  views: number;
};

export type AnalyticsSummary = {
  enabled: boolean;
  window: AnalyticsWindow;
  timezone: AnalyticsTimezone;
  generated_at: string;
  cutoff_at: string | null;
  status: "ok" | "partial" | "unavailable";
  groups: {
    views: AnalyticsEventCounts;
    search: AnalyticsEventCounts;
    features: AnalyticsEventCounts;
    top_novels: AnalyticsTopNovel[];
  };
  failed_groups: Array<"views" | "search" | "features">;
};

export type AuditEventSummary = {
  id: number;
  created_at: string | null;
  actor_user_id: number | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  status: string | null;
  severity: string | null;
  request_id: string | null;
  correlation_id: string | null;
  summary: string;
};

export type AuditEventDetail = AuditEventSummary & {
  metadata: Record<string, unknown>;
  changes: { before: Record<string, unknown>; after: Record<string, unknown> } | null;
};

export type AuditEventListResponse = {
  items: AuditEventSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type AuditEventListFilters = {
  action?: string;
  actor_user_id?: number;
  target_type?: string;
  target_id?: string;
  status?: string;
  severity?: string;
  request_id?: string;
  correlation_id?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
};

export type NovelPublicationSummary = {
  novel_id: string;
  title: string;
  source_title?: string | null;
  is_published: boolean;
  chapter_count: number;
  translated_count: number;
  latest_chapter_id?: string | null;
  latest_chapter_number?: number | null;
  latest_chapter_title?: string | null;
  publication_status: string;
  visibility_warnings: string[];
};

export type ChapterSummary = {
  id: string;
  title?: string | null;
  translated: boolean;
};

export type NovelMetadata = Record<string, unknown> & {
  novel_id?: string;
  title?: string | null;
  translated_title?: string | null;
  author?: string | null;
  translated_author?: string | null;
  chapters?: Array<Record<string, unknown>>;
  glossary_status?: GlossaryReadinessStatus;
  glossary_revision?: number;
  glossary_pending_count?: number;
};

export type ChapterDetail = {
  novel_id: string;
  chapter_id: string;
  text: string;
};

export type TranslatedChapter = {
  novel_id: string;
  chapter_id: string;
  version_id?: string | null;
  version_kind?: string | null;
  provider_key?: string | null;
  provider_model?: string | null;
  translated_at?: string | null;
  created_at?: string | null;
  text: string;
  editor?: string | null;
  note?: string | null;
  confidence_score?: number | null;
  polish_needed?: boolean | null;
  glossary_freshness?: string | null;
  glossary_stale?: boolean | null;
  glossary_stale_reason?: string | null;
  current_glossary_revision?: number | null;
  current_glossary_hash?: string | null;
  confidence_details?: Record<string, unknown>;
};

export type TranslationVersion = Record<string, unknown> & {
  version_id?: string;
  version_kind?: string;
  text?: string;
  active?: boolean;
  provider_key?: string | null;
  provider_model?: string | null;
  created_at?: string | null;
  translated_at?: string | null;
  glossary_freshness?: string | null;
  glossary_stale?: boolean | null;
  glossary_stale_reason?: string | null;
  current_glossary_revision?: number | null;
  current_glossary_hash?: string | null;
};

export type TranslationEditHistory = Record<string, unknown> & {
  id?: string;
  action?: string;
  version_id?: string;
  previous_version_id?: string | null;
  created_at?: string | null;
  editor?: string | null;
  note?: string | null;
};

export type ModelState = {
  provider_key: string;
  provider_model: string;
  status: string;
  priority_order?: number | null;
  rpm_limit?: number | null;
  rpd_limit?: number | null;
  requests_this_minute?: number | null;
  requests_today?: number | null;
  window_started_at?: string | null;
  day_started_at?: string | null;
  cooldown_until?: string | null;
  exhausted_until?: string | null;
  last_error_code?: string | null;
  last_error_message?: string | null;
  selection_reason?: string | null;
};

export type JobProgress = {
  status: string;
  provider_key?: string | null;
  provider_model?: string | null;
  current_stage?: string | null;
  current_label?: string | null;
  completed?: number | null;
  total?: number | null;
  paused_reason?: string | null;
  resume_after?: string | null;
  selection_reason?: string | null;
  errors?: unknown[];
  warnings?: unknown[];
  model_states?: ModelState[];
};

export type ActivityRecord = {
  activity_id: string;
  type: "crawl" | "translation";
  kind: string;
  novel_id: string;
  source_key?: string | null;
  source_url?: string | null;
  chapters?: string | null;
  provider_key?: string | null;
  provider_model?: string | null;
  status: string;
  created_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  retry_count: number;
  error?: string | null;
  metadata?: Record<string, unknown>;
} & Partial<JobProgress>;

export type WorkerStatus = {
  running: boolean;
  poll_seconds: number;
  last_tick_at?: string | null;
  last_activity_id?: string | null;
  last_error?: string | null;
  activity_processed: number;
  idle_ticks: number;
  error_count: number;
};

export type SourceHealth = {
  source_key: string;
  success_count: number;
  failure_count: number;
  last_success_at?: string | null;
  last_failure_at?: string | null;
  last_error?: string | null;
};

export type AdminReviewRecord = {
  id: number;
  user_id: number;
  slug: string;
  title: string;
  rating: number | null;
  body: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  moderated_at: string | null;
  reviewer_notes: string | null;
  reviewed_by_user_id: number | null;
};

export type NovelRequestRecord = {
  id: string;
  request_id?: string;
  title: string;
  status: string;
  requested_by?: string | null;
  vote_count: number;
  created_at?: string | null;
  source_candidates: Array<
    Record<string, unknown> & {
      id?: string;
      source_key?: string | null;
      url?: string | null;
      source_url?: string | null;
      submitted_by?: string | null;
      status?: string | null;
      created_at?: string | null;
      reviewed_at?: string | null;
      reviewed_by?: string | null;
      notes?: string | null;
    }
  >;
};
export type PreliminaryCrawlResult = {
  novel_id: string;
  source_key: string;
  source_url?: string | null;
  title?: string | null;
  translated_title?: string | null;
  author?: string | null;
  translated_author?: string | null;
  synopsis?: string | null;
  translated_synopsis?: string | null;
  metadata_translation_status?: string | null;
  metadata_translation_error?: string | null;
  bootstrap_candidate_count?: number;
  activity_log_activity_id?: string | null;
  detected_at?: string | null;
  chapters: number;
  chapter_list: Array<{
    id?: string | number | null;
    num?: number | null;
    title?: string | null;
    translated_title?: string | null;
    date_added?: string | null;
    published_at?: string | null;
    updated_at?: string | null;
    volume?: string | number | null;
    part?: string | number | null;
    arc?: string | number | null;
    section?: string | number | null;
    group?: string | number | null;
    url?: string | null;
  } & Record<string, unknown>>;
};

export type ProviderApiKeyStatus = {
  provider: string;
  provider_key?: string;
  configured: boolean;
  preferred_provider: string;
  preferred_provider_key?: string;
  model: string;
  provider_model?: string;
  fallback_models?: string[];
  validation_status: "unchecked" | "working" | "failed";
  validation_message?: string | null;
};

export type ProviderApiKeyValidationPayload = {
  provider?: string;
  provider_key?: string;
  api_key?: string | null;
  model?: string | null;
  provider_model?: string | null;
};

export type RuntimeStateItem = {
  key: string;
  label: string;
  filename: string;
  path: string;
  exists: boolean;
  size_bytes: number;
  updated_at?: string | null;
  description: string;
  affects_process: boolean;
};

export type MaintenanceTaskStatus = {
  task_key: string;
  schedule: string;
  timezone: string;
  enabled: boolean;
  state: string;
  last_started_at: string | null;
  last_finished_at: string | null;
  result: string | null;
  failure_summary: string | null;
  next_eligible_at: string | null;
};

export type MaintenanceStatusResponse = {
  status: "healthy" | "degraded";
  tasks: MaintenanceTaskStatus[];
};

export type CreateTranslationActivityPayload = {
  novel_id: string;
  source_key?: string;
  kind: string;
  chapters: string;
  provider_key?: string;
  provider_model?: string;
  skip_glossary_gate?: boolean;
  metadata?: Record<string, unknown>;
};

export type SchedulerHealthModel = {
  provider_key: string;
  provider_model: string;
  priority_order: number;
  configured: boolean;
  credential_active: boolean | null;
  rpm_limit: number | null;
  rpd_limit: number | null;
};

export type SchedulerHealthResponse = {
  policy: {
    default_provider_key: string;
    default_provider_model: string;
    allow_cross_provider_fallback: boolean;
    fallback_on_qa_failure: boolean;
  };
  models: SchedulerHealthModel[];
};

export type SchedulerSummary = {
  chapters_with_decisions: number;
  fallback_count: number;
  no_capacity_count: number;
  checkpoint_blocked_count: number;
  memory_pressure_count: number;
  peak_exact_memory_bytes: number;
  skip_reason_counts: Record<string, number>;
  selected_provider_model_counts: Record<string, number>;
  provider_key_counts: Record<string, number>;
};

// ===========================================
// Glossary Editor QA
// ===========================================

export type GlossaryQAIssue = {
  issue_id: string;
  entry_id: number | null;
  canonical_term: string;
  approved_translation: string | null;
  matched_variant: string | null;
  severity: "error" | "warning" | "advisory";
  code: string;
  owner_locked: boolean;
  context_hint: string;
};

export type GlossaryQAResult = {
  status: "passed" | "advisory" | "warning" | "blocked" | "overridden";
  novel_id: string;
  platform_novel_id: number | null;
  chapter_id: string;
  glossary_revision: number | null;
  checked_terms: number;
  issue_count: number;
  has_errors: boolean;
  has_warnings: boolean;
  source_context: "provided" | "missing";
  notes: string[];
  issues: GlossaryQAIssue[];
  cap_reached: boolean;
  cap_limit: number | null;
};

export type GlossaryQAResponse = {
  glossary_qa: GlossaryQAResult;
};

export type GlossaryOverride = {
  reason: string;
  issue_ids?: string[];
};

export type ApproveTranslationChangeRequest = {
  new_translation: string;
  rationale?: string;
};

export type ApproveTranslationChangeResponse = {
  entry_id: number;
  canonical_term: string;
  approved_translation: string;
  glossary_revision: number | null;
  updated_at: string | null;
};

// ===========================================
// Admin UI Rework - Active Data Models
// ===========================================

// Auth (Req 4) — mirrors backend UserResponse
export type AuthUser = {
  user_id: number | null;
  email: string | null;
  role: "guest" | "user" | "owner";
  is_authenticated: boolean;
  is_owner: boolean;
};

// Masking and validation for active owner provider credential status.
export type TokenValidationStatus = "Unchecked" | "Checking" | "Working" | "Failed";
export type MaskedToken = string;

export type NovelTaxonomyResponse = {
  novel_id: string;
  genres: string[];
  tags: string[];
};

export type NovelTaxonomyRequest = {
  genre_slugs: string[];
  tags: string[];
};

// ===========================================
// Admin User Management
// ===========================================

export type UserListItem = {
  id: number;
  email: string | null;
  display_name: string | null;
  role: string;
  is_active: boolean;
  auth_provider: string | null;
  has_password: boolean;
  email_verified: boolean;
  created_at: string | null;
  last_login_at: string | null;
};

export type UserDetail = UserListItem & {
  auth_provider_subject: string | null;
  disabled_at: string | null;
  disabled_reason: string | null;
  disabled_by_user_id: number | null;
  session_revoked_at: string | null;
};

export type UserListResponse = {
  items: UserListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type UserListFilters = {
  role?: string;
  is_active?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
};

export type ActiveUpdatePayload = {
  is_active: boolean;
  reason: string;
};

export type RoleUpdatePayload = {
  role: string;
  reason: string;
};

export type RevokeSessionsPayload = {
  reason: string;
};

export type ProviderCredential = {
  id: string;
  provider: string;
  masked_token: MaskedToken;
  configured: boolean;
  is_active: boolean;
  validation_status: TokenValidationStatus;
  validation_message?: string | null;
  model?: string | null;
};

// DEBT-023: Admin provider credential list/CRUD shapes (DB-backed).
export type ProviderCredentialRow = {
  id: number;
  provider_key: string;
  label: string;
  is_active: boolean;
  validation_status: string;
  validation_message: string | null;
  model: string | null;
  key_fingerprint: string;
  last4: string;
  created_at: string;
  updated_at: string;
  last_validated_at: string | null;
  notes: string | null;
};

export type ProviderCredentialListResponse = {
  rows: ProviderCredentialRow[];
};

export type ProviderCredentialCreatePayload = {
  provider_key: string;
  api_key: string;
  label: string;
  provider_model?: string | null;
  is_active?: boolean;
  notes?: string | null;
  apply_globally?: boolean;
};

export type ProviderCredentialUpdatePayload = {
  label?: string | null;
  provider_model?: string | null;
  is_active?: boolean | null;
  notes?: string | null;
};

export type ProviderCredentialValidationResult = {
  ok: boolean;
  status: string;
  message?: string | null;
};


export type GlossaryEntryStatus = "candidate" | "recommended" | "approved" | "rejected" | "deprecated";
export type GlossaryReadinessStatus = "glossary_pending" | "glossary_ready" | "glossary_skipped";
export type GlossaryStatusTransitionPayload = {
  target_status: GlossaryReadinessStatus;
};
export type GlossaryStatusTransitionResult = {
  novel_id: string;
  glossary_status: GlossaryReadinessStatus;
  glossary_revision: number;
};
export type GlossaryBatchApproveResult = GlossaryStatusTransitionResult & {
  approved_count: number;
};
export type GlossaryTermType =
  | "character"
  | "family_house"
  | "place"
  | "organization"
  | "title"
  | "rank"
  | "skill"
  | "magic"
  | "species"
  | "item"
  | "artifact"
  | "concept"
  | "phrase"
  | "other";
export type GlossaryEnforcementLevel = "none" | "info" | "warning" | "error" | "blocker";
export type GlossaryReplacementPolicy =
  | "never_auto_replace"
  | "preview_required"
  | "manual_only"
  | "safe_exact"
  | "no_replacement";
export type GlossaryMatchingPolicy =
  | "exact_phrase"
  | "case_insensitive_phrase"
  | "word_boundary"
  | "source_text_only"
  | "translated_text_only"
  | "regex_reviewed"
  | "manual_only"
  | "custom";
export type GlossaryAliasType = "allowed" | "rejected" | "banned" | "deprecated" | "observed" | "source_variant";
export type GlossaryAliasAppliesTo = "source_text" | "translated_text" | "prompt" | "qa" | "public_display";
export type GlossaryEvidenceQuality =
  | "clean_source"
  | "mojibake"
  | "translated_only"
  | "metadata_only"
  | "manual_owner_decision";
export type GlossaryQaSeverity = "info" | "warning" | "error" | "blocker";
export type GlossaryQaFindingStatus = "open" | "accepted" | "dismissed" | "fixed";
export type GlossaryQaFindingType =
  | "banned_alias"
  | "inconsistent_alias"
  | "missing_canonical"
  | "unresolved_term"
  | "source_mismatch"
  | "replacement_risk";
export type GlossaryCandidateImportMode = "preview" | "apply";
export type GlossaryCandidateImportAction = "preview" | "created" | "merged" | "skipped" | "conflict";
export type GlossaryProviderCandidateMode = "preview" | "apply";
export type GlossaryProviderCandidateAction = "preview" | "created" | "merged" | "skipped" | "conflict";

export type GlossaryEntry = {
  id: number;
  novel_id: number | null;
  scope: "global" | "novel";
  canonical_term: string;
  term_type: GlossaryTermType;
  approved_translation: string | null;
  status: GlossaryEntryStatus;
  enforcement_level: GlossaryEnforcementLevel;
  owner_locked: boolean;
  public_visible: boolean;
  public_description: string | null;
  admin_notes: string | null;
  confidence: number | null;
  replacement_policy: GlossaryReplacementPolicy;
  matching_policy: GlossaryMatchingPolicy;
  first_seen_chapter_id: number | null;
  first_seen_chapter_number: number | null;
  last_seen_chapter_id: number | null;
  last_seen_chapter_number: number | null;
  created_by_user_id: number | null;
  updated_by_user_id: number | null;
  created_at: string;
  updated_at: string;
  deprecated_at: string | null;
};

export type GlossaryEntryCreatePayload = {
  canonical_term: string;
  term_type: GlossaryTermType;
  approved_translation?: string | null;
  status?: GlossaryEntryStatus;
  scope?: "global" | "novel";
  enforcement_level?: GlossaryEnforcementLevel;
  owner_locked?: boolean;
  public_visible?: boolean;
  public_description?: string | null;
  admin_notes?: string | null;
  confidence?: number | null;
  replacement_policy?: GlossaryReplacementPolicy;
  matching_policy?: GlossaryMatchingPolicy;
  first_seen_chapter_id?: number | null;
  first_seen_chapter_number?: number | null;
  last_seen_chapter_id?: number | null;
  last_seen_chapter_number?: number | null;
  rationale?: string | null;
};

export type GlossaryEntryUpdatePayload = Partial<
  Omit<
    GlossaryEntryCreatePayload,
    "status" | "owner_locked" | "rationale"
  >
>;

export type GlossaryEntryStatusPayload = {
  status: GlossaryEntryStatus;
  rationale?: string | null;
};

export type GlossaryDecisionPayload = {
  rationale?: string | null;
};

export type GlossaryEntryListFilters = {
  status?: GlossaryEntryStatus;
  term_type?: GlossaryTermType;
  public_visible?: boolean;
};

export type GlossaryAlias = {
  id: number;
  glossary_entry_id: number;
  novel_id: number;
  alias_text: string;
  alias_type: GlossaryAliasType;
  language: string | null;
  text_origin: string | null;
  applies_to: GlossaryAliasAppliesTo | null;
  matching_policy: GlossaryMatchingPolicy | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type GlossaryAliasCreatePayload = {
  alias_text: string;
  alias_type?: GlossaryAliasType;
  language?: string | null;
  text_origin?: string | null;
  applies_to?: GlossaryAliasAppliesTo | null;
  matching_policy?: GlossaryMatchingPolicy | null;
  notes?: string | null;
  rationale?: string | null;
};

export type GlossaryAliasUpdatePayload = Partial<GlossaryAliasCreatePayload>;

export type GlossaryProvenance = {
  id: number;
  glossary_entry_id: number | null;
  novel_id: number;
  source_site: string;
  source_adapter: string;
  source_novel_id: string | null;
  source_url: string | null;
  source_chapter_id: string | null;
  source_chapter_number: number | null;
  chapter_id: number | null;
  raw_source_term: string | null;
  observed_translated_term: string | null;
  evidence_ref: string | null;
  local_reference: string | null;
  evidence_quality: GlossaryEvidenceQuality | null;
  confidence: number | null;
  first_seen_at: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
};

export type GlossaryProvenanceCreatePayload = {
  source_site: string;
  source_adapter: string;
  source_novel_id?: string | null;
  source_url?: string | null;
  source_chapter_id?: string | null;
  source_chapter_number?: number | null;
  chapter_id?: number | null;
  raw_source_term?: string | null;
  observed_translated_term?: string | null;
  evidence_ref?: string | null;
  local_reference?: string | null;
  evidence_quality?: GlossaryEvidenceQuality | null;
  confidence?: number | null;
};

export type GlossaryDecisionEvent = {
  id: number;
  novel_id: number;
  glossary_entry_id: number | null;
  alias_id: number | null;
  actor_user_id: number | null;
  event_type: string;
  old_value_json: string | null;
  new_value_json: string | null;
  rationale: string | null;
  decision_source: string;
  created_at: string;
};

export type GlossaryQaFinding = {
  id: number;
  novel_id: number;
  chapter_id: number | null;
  glossary_entry_id: number | null;
  finding_type: GlossaryQaFindingType;
  severity: GlossaryQaSeverity;
  matched_text: string | null;
  suggested_text: string | null;
  context_ref: string | null;
  status: GlossaryQaFindingStatus;
  reviewer_user_id: number | null;
  reviewer_notes: string | null;
  created_at: string;
  resolved_at: string | null;
};

export type GlossaryQaFindingCreatePayload = {
  finding_type: GlossaryQaFindingType;
  severity?: GlossaryQaSeverity;
  status?: GlossaryQaFindingStatus;
  chapter_id?: number | null;
  glossary_entry_id?: number | null;
  matched_text?: string | null;
  suggested_text?: string | null;
  context_ref?: string | null;
};

export type GlossaryQaFindingStatusPayload = {
  status: GlossaryQaFindingStatus;
  reviewer_notes?: string | null;
};

export type GlossaryQaFindingListFilters = {
  chapter_id?: number;
  status?: GlossaryQaFindingStatus;
};

export type GlossaryCandidateImportRequest = {
  max_candidates?: number;
};

export type GlossaryCandidateSummary = {
  term: string;
  translation: string;
  term_type: GlossaryTermType;
  confidence: number;
  frequency: number;
  chapter_count: number;
  chapter_numbers: number[];
  chapter_refs: string[];
  action: GlossaryCandidateImportAction;
  notes: string | null;
};

export type GlossaryCandidateImportResult = {
  novel_id: number;
  mode: GlossaryCandidateImportMode;
  candidates_found: number;
  candidates_created: number;
  candidates_merged: number;
  candidates_skipped: number;
  conflicts: string[];
  warnings: string[];
  candidates: GlossaryCandidateSummary[];
};

export type GlossaryProviderCandidateRequest = {
  max_candidates?: number;
  max_chapters?: number;
  max_chars?: number;
  chapter_scope?: "latest" | "all" | "range";
  chapter_start?: number | null;
  chapter_end?: number | null;
  provider_key?: string;
  provider_model?: string;
};

export type GlossaryProviderCandidateSummary = {
  raw_term: string;
  term: string;
  translation: string;
  term_type: GlossaryTermType;
  confidence: number;
  aliases: string[];
  alias_count: number;
  chapter_refs: string[];
  action: GlossaryProviderCandidateAction;
  rationale: string | null;
  notes: string | null;
};

export type GlossaryProviderCandidateResult = {
  novel_id: number;
  mode: GlossaryProviderCandidateMode;
  provider_mode: string;
  provider_label: string;
  candidates_found: number;
  candidates_created: number;
  candidates_merged: number;
  candidates_skipped: number;
  conflicts: string[];
  warnings: string[];
  provider_warnings: string[];
  scanned_chapter_count: number;
  highest_scanned_chapter_number: number | null;
  candidates: GlossaryProviderCandidateSummary[];
};

export interface TakedownRequestSummary {
  id: number;
  created_at: string | null;
  complainant_name: string;
  complainant_email: string;
  infringing_url: string;
  description: string;
  status: string;
  reviewer_notes: string | null;
  reviewed_at: string | null;
}

export interface TakedownListResponse {
  items: TakedownRequestSummary[];
  total: number;
  page: number;
  page_size: number;
}
