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
  author?: string | null;
  source?: string | null;
  source_url?: string | null;
  chapter_count: number;
  scraped_count?: number;
  translated_count?: number;
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
};

export type ChapterDetail = {
  novel_id: string;
  chapter_id: string;
  text: string;
};

export type TranslatedChapter = {
  novel_id: string;
  chapter_id: string;
  id?: string;
  version_id?: string | null;
  version_kind?: string | null;
  provider?: string | null;
  model?: string | null;
  provider_key?: string | null;
  provider_model?: string | null;
  translated_at?: string | null;
  created_at?: string | null;
  text: string;
  editor?: string | null;
  note?: string | null;
  confidence_score?: number | null;
  polish_needed?: boolean | null;
};

export type TranslationVersion = Record<string, unknown> & {
  id?: string;
  version_id?: string;
  version_kind?: string;
  kind?: string;
  text?: string;
  active?: boolean;
  provider?: string | null;
  model?: string | null;
  provider_key?: string | null;
  provider_model?: string | null;
  created_at?: string | null;
  translated_at?: string | null;
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

export type NovelProgress = {
  novel_id: string;
  total: number;
  scraped: number;
  translated: number;
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
  id: string;
  activity_id?: string;
  job_id?: string;
  type: "crawl" | "translation";
  kind: string;
  novel_id: string;
  source_key?: string | null;
  source_url?: string | null;
  chapters?: string | null;
  provider?: string | null;
  model?: string | null;
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
  last_job_id?: string | null;
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

export type ReaderNovel = {
  novel_id: string;
  title?: string | null;
  source_title?: string | null;
  author?: string | null;
  source?: string | null;
  source_url?: string | null;
  chapter_count: number;
  translated_count: number;
  chapters: Array<{
    id: string;
    num?: number | null;
    title?: string | null;
    source_title?: string | null;
    translated: boolean;
  }>;
};

export type ReaderChapter = {
  novel_id: string;
  chapter_id: string;
  novel_title?: string | null;
  title?: string | null;
  source_title?: string | null;
  text: string;
  version_id?: string | null;
  version_kind?: string | null;
  previous_chapter_id?: string | null;
  next_chapter_id?: string | null;
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
  activity_log_job_id?: string | null;
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

export type CreateTranslationActivityPayload = {
  novel_id: string;
  source_key?: string;
  kind: string;
  chapters: string;
  provider_key?: string;
  provider_model?: string;
  provider?: string;
  model?: string;
  metadata?: Record<string, unknown>;
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
