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
}

export interface PublicCatalogResponse {
  novels: PublicNovelSummary[];
  total: number; // total > page_size -> show next-page control (Req 3.6)
  page: number;
  page_size: number;
}

export interface CatalogParams {
  q?: string;
  status?: string;
  language?: string; // genre/facet mapped here
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
