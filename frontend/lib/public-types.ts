// Public-scoped data types for the public reader surface.
// This module is separate from lib/api-types.ts (admin/owner-scoped).
// Shapes mirror the backend Pydantic responses from routers/public.py,
// routers/auth.py, and routers/user_data.py.

// ---- Catalog / Novel / Chapter (from routers/public.py) ----

export interface PublicNovelSummary {
  novel_id: string;
  slug: string;
  title: string | null;
  author: string | null; // null -> render "Unknown author" (Req 2.4)
  language: string | null;
  status: string | null;
  chapter_count: number;
  translated_count: number;
  added_at?: string | null;
  genres?: string[];
  tags?: string[];
}

export interface PublicCatalogResponse {
  novels: PublicNovelSummary[];
  total: number; // total > page_size -> show next-page control (Req 3.6)
  page: number;
  page_size: number;
}

export type CatalogSortField = "added_at" | "title" | "chapter_count";
export type CatalogOrder = "asc" | "desc";

export interface CatalogParams {
  q?: string;
  status?: string;
  sort_by?: CatalogSortField;
  order?: CatalogOrder;
  min_chapters?: number;
  max_chapters?: number;
  genre_include?: string;
  genre_exclude?: string;
  tag_include?: string;
  tag_exclude?: string;
  page?: number;
  page_size?: number;
}

export interface PublicChapterSummary {
  chapter_id: string;
  title: string | null;
  chapter_number: number | null; // sort ascending (Req 4.3)
  translated: boolean; // false -> pending indicator (Req 4.5)
}

export interface PublicChapterDetail {
  novel_id: string;
  chapter_id: string;
  chapter_number: number | null;
  novel_title: string | null;
  title: string | null;
  text: string;
  previous_chapter_id: string | null; // Req 5.4
  next_chapter_id: string | null; // Req 5.5
}

// ---- Auth (from routers/auth.py) ----

export type ReaderRole = "guest" | "user" | "owner";

export interface AuthUser {
  user_id: number | null;
  email: string | null;
  role: ReaderRole;
  is_authenticated: boolean;
  is_owner: boolean;
}

export type PublicAuthStatus = "guest" | "authenticated";

export interface PublicAuthState {
  status: PublicAuthStatus;
  user: AuthUser;
}

// ---- Reading State (from routers/user_data.py) ----

export type LibraryStatus = "reading" | "completed" | "paused";

export interface LibraryItem {
  slug: string;
  status: LibraryStatus;
  added_at: string;
}

export interface ProgressInput {
  chapter_id?: string | null;
  progress_percent: number;
}

export interface ProgressResponse {
  slug: string;
  chapter_id: string | null;
  chapter_number: number | null;
  progress_percent: number;
  updated_at: string;
}

export interface HistoryEntry {
  id: number;
  slug: string;
  chapter_id: string | null;
  chapter_number: number | null;
  read_at: string;
}

export interface HistoryListParams {
  limit?: number;
}

export interface HistoryListResponse {
  items: HistoryEntry[];
  next_cursor: string | null;
}

export interface HistoryRecordInput {
  slug: string;
  chapter_id?: string | null;
}

// ---- Engagement (reviews/ratings and public requests) ----

export interface ReviewInput {
  rating?: number | null;
  body?: string | null;
}

export interface ReviewResponse {
  slug: string;
  rating: number | null;
  body: string | null;
  status: "pending" | "published" | "rejected" | string;
  updated_at: string;
}

export interface PublicRequestInput {
  request_type: "novel" | "chapter";
  source_url?: string | null;
  slug?: string | null;
  chapter_id?: string | null;
  details?: string | null;
}

export interface PublicRequest {
  id: number;
  request_type: string;
  status: "pending" | "approved" | "rejected" | "completed" | string;
  source_url: string | null;
  slug: string | null;
  chapter_id: string | null;
  created_at: string;
}

export interface RequestListParams {
  limit?: number;
}

export interface RequestListResponse {
  items: PublicRequest[];
  next_cursor: string | null;
}

// ---- Contribution (frontend-designed; backend dependency) ----

export type ContributionStatus = "Unchecked" | "Checking" | "Working" | "Failed";

export interface ContributionStatusResponse {
  present: boolean; // whether a credential exists
  status: ContributionStatus; // Req 17.9
  masked_value: string | null; // Masked_Credential_Display value, e.g. "AIza…7Bx" (Req 17.7)
  provider?: string | null;
  updated_at?: string | null;
}
// NOTE: raw credential is request-only input; never stored client-side (Req 17.6).

// ---- Taxonomy (from routers/public.py) ----

export interface PublicGenreResponse {
  slug: string;
  name_ja: string;
  name_en: string | null;
  is_adult: boolean;
}

export interface PublicTagSearchResult {
  name: string;
  name_ja: string | null;
  is_adult: boolean;
}

export interface TagSearchParams {
  q: string;
  include_adult?: boolean;
  limit?: number;
}
