-- RETIRED HISTORICAL REFERENCE — DO NOT RUN.
-- Alembic revision 3da9f497264c is the canonical, executable RLS policy source.
-- This former Supabase SQL Editor script is intentionally commented out so it
-- cannot drift into a second schema-management path.
/*
-- Row Level Security (RLS) Policies for NovelAI
-- 
-- Role model (backend-enforced):
--   guest - unauthenticated; read public catalog/chapters only
--   user  - authenticated; library, progress, ratings, requests (own data only)
--   owner - authenticated; all operations (admin)
--
-- NOTE: NovelAI uses INTEGER user IDs, but Supabase auth.uid() returns UUID.
-- We need to lookup the user by auth_provider_subject instead.

-- =============================================================================
-- ENABLE RLS ON ALL TABLES
-- =============================================================================

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.novels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.crawl_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.translation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provider_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.library_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reading_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reading_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.novel_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alembic_version ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- HELPER FUNCTIONS (in public schema)
-- =============================================================================

-- Get current user's integer ID by matching auth.uid() to auth_provider_subject
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS integer
LANGUAGE sql
STABLE
AS $$
  SELECT id FROM public.users 
  WHERE auth_provider_subject = auth.uid()::text
  LIMIT 1;
$$;

-- Check if current user is owner
CREATE OR REPLACE FUNCTION public.is_owner()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users 
    WHERE auth_provider_subject = auth.uid()::text
    AND role = 'owner'
  );
$$;

-- =============================================================================
-- NOVELS TABLE
-- Public: read published novels only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Public can read published novels"
ON public.novels
FOR SELECT
TO anon, authenticated
USING (is_published = true);

CREATE POLICY "Owner has full access to novels"
ON public.novels
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- CHAPTERS TABLE
-- Public: read chapters of published novels only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Public can read chapters of published novels"
ON public.chapters
FOR SELECT
TO anon, authenticated
USING (
  EXISTS (
    SELECT 1 FROM public.novels
    WHERE novels.id = chapters.novel_id
    AND novels.is_published = true
  )
);

CREATE POLICY "Owner has full access to chapters"
ON public.chapters
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- USERS TABLE
-- Public: no access
-- User: read/update own row only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Users can read own data"
ON public.users
FOR SELECT
TO authenticated
USING (id = public.current_user_id());

CREATE POLICY "Users can update own data"
ON public.users
FOR UPDATE
TO authenticated
USING (id = public.current_user_id())
WITH CHECK (id = public.current_user_id());

CREATE POLICY "Owner has full access to users"
ON public.users
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- LIBRARY_ITEMS TABLE
-- User: CRUD own library items only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Users can read own library items"
ON public.library_items
FOR SELECT
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Users can insert own library items"
ON public.library_items
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Users can delete own library items"
ON public.library_items
FOR DELETE
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Owner has full access to library_items"
ON public.library_items
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- READING_PROGRESS TABLE
-- User: CRUD own progress only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Users can read own reading progress"
ON public.reading_progress
FOR SELECT
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Users can insert own reading progress"
ON public.reading_progress
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Users can update own reading progress"
ON public.reading_progress
FOR UPDATE
TO authenticated
USING (user_id = public.current_user_id())
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Owner has full access to reading_progress"
ON public.reading_progress
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- READING_HISTORY TABLE
-- User: read/insert own history only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Users can read own reading history"
ON public.reading_history
FOR SELECT
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Users can insert own reading history"
ON public.reading_history
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Owner has full access to reading_history"
ON public.reading_history
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- REVIEWS TABLE
-- Public: read reviews for published novels
-- User: CRUD own reviews only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Public can read reviews for published novels"
ON public.reviews
FOR SELECT
TO anon, authenticated
USING (
  EXISTS (
    SELECT 1 FROM public.novels
    WHERE novels.id = reviews.novel_id
    AND novels.is_published = true
  )
);

CREATE POLICY "Users can insert own reviews"
ON public.reviews
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Users can update own reviews"
ON public.reviews
FOR UPDATE
TO authenticated
USING (user_id = public.current_user_id())
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Users can delete own reviews"
ON public.reviews
FOR DELETE
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Owner has full access to reviews"
ON public.reviews
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- NOVEL_REQUESTS TABLE
-- User: read/insert own requests only
-- Owner: full access
-- =============================================================================

CREATE POLICY "Users can read own novel requests"
ON public.novel_requests
FOR SELECT
TO authenticated
USING (user_id = public.current_user_id());

CREATE POLICY "Users can insert own novel requests"
ON public.novel_requests
FOR INSERT
TO authenticated
WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "Owner has full access to novel_requests"
ON public.novel_requests
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- ADMIN-ONLY TABLES (Owner: full access only)
-- =============================================================================

CREATE POLICY "Owner has full access to crawl_jobs"
ON public.crawl_jobs
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

CREATE POLICY "Owner has full access to translation_jobs"
ON public.translation_jobs
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

CREATE POLICY "Owner has full access to provider_requests"
ON public.provider_requests
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- SYSTEM TABLES (Owner: full access only)
-- =============================================================================

CREATE POLICY "Owner can read audit_logs"
ON public.audit_logs
FOR SELECT
TO authenticated
USING (public.is_owner());

CREATE POLICY "Owner can insert audit_logs"
ON public.audit_logs
FOR INSERT
TO authenticated
WITH CHECK (public.is_owner());

CREATE POLICY "Owner has full access to system_settings"
ON public.system_settings
FOR ALL
TO authenticated
USING (public.is_owner())
WITH CHECK (public.is_owner());

-- =============================================================================
-- ALEMBIC_VERSION TABLE
-- RLS enabled with no policies = no PostgREST access
-- =============================================================================
*/
