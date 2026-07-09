# Tasks: Public Reader Availability

## Overview

Implement configurable public reader behavior for chapters that exist in novel metadata but do not currently have an active translated chapter.

The implementation must preserve current default behavior, add opt-in fallback policies, expose availability metadata, and allow owner-only preview of specific translation versions through the existing public chapter endpoint.

Scope boundaries:

- No database migrations.
- No storage file format changes.
- No new API endpoints.
- No frontend changes required.
- Admin chapter routes remain unchanged.
- Public response changes are additive, except where an opt-in policy intentionally changes unavailable-chapter behavior.

## Task List

- [x] 1. Preflight Current Reader Behavior
  - [x] 1.1 Inspect `backend/src/novelai/api/routers/public.py` and locate public `get_chapter`.
  - [x] 1.2 Locate the public chapter list handler.
  - [x] 1.3 Confirm current missing-translation behavior returns HTTP 404 with detail `"Translated chapter not available."`.
  - [x] 1.4 Inspect how public routes resolve slug, metadata, chapter order, chapter IDs, and published status.
  - [x] 1.5 Inspect how normal chapter responses build `text`, `reader_blocks`, previous/next navigation, and chapter title.
  - [x] 1.6 Inspect `backend/src/novelai/storage/translations.py` for active translation loading, version listing, and translated chapter listing helpers.
  - [x] 1.7 Inspect `backend/src/novelai/config/settings.py` and follow existing settings style.
  - [x] 1.8 Inspect public reader tests and fixtures to reuse local setup.

- [x] 2. Add Global Availability Policy Setting
  - [x] 2.1 Add `PUBLIC_READER_UNAVAILABLE_POLICY: str` to `backend/src/novelai/config/settings.py`.
  - [x] 2.2 Read from environment variable `PUBLIC_READER_UNAVAILABLE_POLICY`.
  - [x] 2.3 Default to `"hard_404"`.
  - [x] 2.4 Do not raise during settings load for invalid values.
  - [x] 2.5 Leave validation to the public router policy resolver.

- [x] 3. Add Specific Version Storage Loader
  - [x] 3.1 Implement `load_translated_chapter_by_version_id(novel_id, chapter_id, version_id)` in `backend/src/novelai/storage/translations.py`.
  - [x] 3.2 Load the existing translated chapter bundle using existing internal helpers.
  - [x] 3.3 Extract versions using the existing version normalization helper when available.
  - [x] 3.4 Match by version `id`.
  - [x] 3.5 Return `None` when the bundle is missing.
  - [x] 3.6 Return `None` when the version ID is unknown.
  - [x] 3.7 Return a normalized dict compatible with public response building, including `id`, `version_id`, `version_kind`, `provider`, `model`, `translated_at`, `created_at`, `text`, `editor`, `note`, `confidence_score`, and `glossary_revision`.
  - [x] 3.8 Keep storage schemas unchanged.

- [x] 4. Add Policy Resolution Helpers
  - [x] 4.1 In `public.py`, define valid policies: `"hard_404"`, `"chapter_shell"`, and `"latest_version"`.
  - [x] 4.2 Implement `_resolve_unavailable_policy(meta: dict[str, Any]) -> str`.
  - [x] 4.3 Check `meta.get("public_reader_unavailable_policy")` first.
  - [x] 4.4 Return valid per-novel policy when present.
  - [x] 4.5 Log a warning for invalid explicit per-novel policy and fall back to `"hard_404"`.
  - [x] 4.6 If no per-novel policy is set, check `settings.PUBLIC_READER_UNAVAILABLE_POLICY`.
  - [x] 4.7 Return valid global policy when configured.
  - [x] 4.8 Log a warning for invalid explicit global policy and fall back to `"hard_404"`.
  - [x] 4.9 Do not warn when policy values are simply missing.

- [x] 5. Add Optional Owner Auth Helper
  - [x] 5.1 Implement `_try_get_owner(request: Request) -> Any | None` in `public.py`.
  - [x] 5.2 Use the existing `require_role("owner")` path if available.
  - [x] 5.3 Make the helper non-raising for unauthenticated public requests.
  - [x] 5.4 Return an owner/auth object only when the caller is authenticated as owner.
  - [x] 5.5 Swallow expected auth failures so public `?version_id=` requests continue normally.
  - [x] 5.6 Do not grant preview access to non-owner roles unless the existing auth model treats them as owner-equivalent.

- [x] 6. Add Chapter Shell Helper
  - [x] 6.1 Implement `_chapter_shell_response(...)` in `public.py`.
  - [x] 6.2 Preserve normal identity fields: `novel_id`, `slug`, `chapter_id`, `chapter_number`, `novel_title`, and `title`.
  - [x] 6.3 Return `text: None`.
  - [x] 6.4 Return `reader_blocks: []`.
  - [x] 6.5 Return `availability_status: "not_translated"`.
  - [x] 6.6 Return `availability_message: "This chapter has not been translated yet."`.
  - [x] 6.7 Return version fields as unavailable: `version_id: None`, `is_active_version: False`, and optional version metadata as `None`.
  - [x] 6.8 Compute previous/next IDs from the full chapter order.
  - [x] 6.9 Use `storage.list_translated_chapters(novel_id)` to determine whether adjacent chapters are translated.
  - [x] 6.10 Link `previous_chapter_id` and `next_chapter_id` only when the adjacent chapter is translated.
  - [x] 6.11 Set `previous_chapter_unavailable` or `next_chapter_unavailable` when adjacent chapters exist but are untranslated.
  - [x] 6.12 Reuse existing title and chapter-number helpers where practical.
  - [x] 6.13 Do not expose raw source text.

- [x] 7. Update Public `get_chapter` Signature
  - [x] 7.1 Add `version_id: str | None = Query(default=None)`.
  - [x] 7.2 Add `request: Request` if the handler does not already receive it.
  - [x] 7.3 Keep the existing route path and HTTP method.
  - [x] 7.4 Keep existing storage and DB dependencies unchanged.

- [x] 8. Implement Owner Version Preview
  - [x] 8.1 Initialize `effective_version_id = None`.
  - [x] 8.2 If `version_id` is supplied, call `_try_get_owner(request)`.
  - [x] 8.3 Set `effective_version_id` only when owner auth succeeds.
  - [x] 8.4 If `effective_version_id` is set, call `storage.load_translated_chapter_by_version_id(...)`.
  - [x] 8.5 If owner requested an unknown version, return HTTP 404 with detail `"Version not found."`.
  - [x] 8.6 Load the active translation as well.
  - [x] 8.7 Compare active `version_id` with requested `version_id`.
  - [x] 8.8 Set `is_active_version` accurately.
  - [x] 8.9 Ensure unauthenticated public requests with `?version_id=` ignore the parameter and continue through normal public behavior.

- [x] 9. Preserve Active Translation Behavior
  - [x] 9.1 When no owner preview is active, call existing `storage.load_translated_chapter(novel_id, chapter_id)`.
  - [x] 9.2 If an active translation exists, serve it regardless of unavailable policy.
  - [x] 9.3 Preserve existing response fields and reader block generation.
  - [x] 9.4 Add `availability_status: "available"`.
  - [x] 9.5 Add `availability_message: None` or omit it according to existing response style.
  - [x] 9.6 Add `version_id`.
  - [x] 9.7 Add `is_active_version: True`.
  - [x] 9.8 Add `version_kind`, `provider`, `model`, and `translated_at` when available.

- [x] 10. Implement `hard_404`
  - [x] 10.1 When no active translation is available and policy is `"hard_404"`, preserve current behavior.
  - [x] 10.2 Return HTTP 404 with detail `"Translated chapter not available."`.
  - [x] 10.3 Verify this remains the default with no env var or per-novel override.

- [x] 11. Implement `chapter_shell`
  - [x] 11.1 When no active translation is available and policy is `"chapter_shell"`, return `_chapter_shell_response(...)`.
  - [x] 11.2 Ensure response status is HTTP 200.
  - [x] 11.3 Ensure `text` serializes as JSON `null`.
  - [x] 11.4 Ensure `reader_blocks` is an empty list.
  - [x] 11.5 Ensure `availability_status` is `"not_translated"`.
  - [x] 11.6 Ensure navigation fields and unavailable flags are correct.

- [x] 12. Implement `latest_version`
  - [x] 12.1 When no active translation is available and policy is `"latest_version"`, call `storage.list_translated_chapter_versions(novel_id, chapter_id)`.
  - [x] 12.2 Filter to versions with usable string `text`.
  - [x] 12.3 Select the newest version by `created_at` descending.
  - [x] 12.4 Use `translated_at` as fallback sort key when `created_at` is missing.
  - [x] 12.5 Serve selected version with normal translated response shape.
  - [x] 12.6 Set `availability_status: "available"`.
  - [x] 12.7 Set `is_active_version: False`.
  - [x] 12.8 Include `version_id` and available version metadata.
  - [x] 12.9 If no saved version has text, fall back to `_chapter_shell_response(...)`.

- [x] 13. Add Availability to Chapter List
  - [x] 13.1 In the public chapter list endpoint, call `storage.list_translated_chapters(novel_id)` once.
  - [x] 13.2 Convert translated IDs to a string set for stable comparison.
  - [x] 13.3 Add `availability_status: "available"` when chapter ID is translated.
  - [x] 13.4 Add `availability_status: "not_translated"` when chapter ID is not translated.
  - [x] 13.5 Preserve existing chapter list fields.
  - [x] 13.6 Preserve existing chapter ordering.

- [x] 14. Add Test File and Fixtures
  - [x] 14.1 Create `backend/tests/test_public_reader_availability.py`.
  - [x] 14.2 Reuse existing FastAPI client fixtures when available.
  - [x] 14.3 Reuse existing storage/temp directory fixtures when available.
  - [x] 14.4 Add setup for a public/published novel with at least two chapters.
  - [x] 14.5 Add setup for a chapter with no active translation.
  - [x] 14.6 Add setup for saved translation versions with controlled timestamps.
  - [x] 14.7 Add setup or dependency override for owner-authenticated requests.
  - [x] 14.8 Reset environment variables/settings state between tests.

- [x] 15. Write Policy Tests
  - [x] 15.1 Test default or explicit `"hard_404"` returns HTTP 404 for missing translation.
  - [x] 15.2 Test `"chapter_shell"` returns HTTP 200 for missing translation.
  - [x] 15.3 Assert shell response has `text is None`.
  - [x] 15.4 Assert shell response has `reader_blocks == []`.
  - [x] 15.5 Assert shell response has `availability_status == "not_translated"`.
  - [x] 15.6 Assert shell response has the expected availability message.
  - [x] 15.7 Assert shell navigation fields and unavailable flags are correct.
  - [x] 15.8 Test `"latest_version"` returns newest saved version when no active version exists.
  - [x] 15.9 Assert latest-version response has `is_active_version is False`.
  - [x] 15.10 Test `"latest_version"` falls back to shell when no saved version has text.
  - [x] 15.11 Test active version is served under every policy.
  - [x] 15.12 Assert active-version response has `is_active_version is True`.
  - [x] 15.13 Test invalid policy falls back to `"hard_404"` and logs a warning.

- [x] 16. Write Version Preview Tests
  - [x] 16.1 Test owner auth plus `?version_id=` returns the requested version.
  - [x] 16.2 Assert owner preview response includes `version_id`, `is_active_version`, `version_kind`, `provider`, `model`, and `translated_at`.
  - [x] 16.3 Assert owner preview of a non-active version has `is_active_version is False`.
  - [x] 16.4 Assert owner preview of the active version has `is_active_version is True`.
  - [x] 16.5 Test owner auth plus unknown `?version_id` returns HTTP 404 with `"Version not found."`.
  - [x] 16.6 Test unauthenticated `?version_id=` is ignored.
  - [x] 16.7 Assert unauthenticated request serves normal active-version behavior.
  - [x] 16.8 Assert unauthenticated unknown `version_id` does not return `"Version not found."` when normal public response is available.

- [x] 17. Write Per-Novel and Chapter List Tests
  - [x] 17.1 Test per-novel `public_reader_unavailable_policy` overrides global policy.
  - [x] 17.2 Test global policy applies when no per-novel override exists.
  - [x] 17.3 Test chapter list includes `availability_status` for translated chapters.
  - [x] 17.4 Test chapter list includes `availability_status` for untranslated chapters.
  - [x] 17.5 Assert existing chapter list fields remain present and unchanged.

- [x] 18. Backward Compatibility Checks
  - [x] 18.1 Confirm default setting preserves current `"hard_404"` behavior.
  - [x] 18.2 Confirm clients checking `text != null` remain compatible with shell responses.
  - [x] 18.3 Confirm unauthenticated users cannot select arbitrary versions.
  - [x] 18.4 Confirm no DB migration files are created.
  - [x] 18.5 Confirm no storage JSON schema changes are introduced.
  - [x] 18.6 Confirm admin chapter version routes are unchanged.
  - [x] 18.7 Confirm no new public endpoint is added.

- [x] 19. Run Verification
  - [x] 19.1 Run `pytest backend/tests/test_public_reader_availability.py --tb=short -q`.
  - [x] 19.2 Run existing public reader tests if present.
  - [x] 19.3 Run `ruff check` on changed backend source and test files.
  - [x] 19.4 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [x] 19.5 Fix test, lint, and type failures caused by this work.

- [x] 20. Final Acceptance Review
  - [x] 20.1 Verify default `"hard_404"` missing translation returns HTTP 404.
  - [x] 20.2 Verify `"chapter_shell"` missing translation returns HTTP 200 with `text: null` and `availability_status: "not_translated"`.
  - [x] 20.3 Verify `"latest_version"` returns newest saved version with `is_active_version: false` when active translation is missing.
  - [x] 20.4 Verify active translations are always preferred when present.
  - [x] 20.5 Verify authenticated owners can load a specific version via `?version_id=`.
  - [x] 20.6 Verify public unauthenticated requests ignore `version_id`.
  - [x] 20.7 Verify chapter list includes `availability_status`.
  - [x] 20.8 Verify all required tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Configurable Availability Policy | 2, 4, 10, 15, 17, 18, 20 |
| REQ-2 Preserve Default `hard_404` Behavior | 1, 2, 10, 15, 18, 20 |
| REQ-3 `chapter_shell` Policy | 6, 11, 15, 18, 20 |
| REQ-4 `latest_version` Policy | 9, 12, 15, 20 |
| REQ-5 Owner-Only Version Preview | 3, 5, 7, 8, 16, 18, 20 |
| REQ-6 Specific Version Storage Helper | 3, 16 |
| REQ-7 Normal Response Availability Fields | 9, 15, 16, 20 |
| REQ-8 Chapter List Availability | 13, 17, 20 |
| REQ-9 Safety and Compatibility | 6, 8, 18, 19 |
| REQ-10 Tests | 14, 15, 16, 17, 19 |

## Definition of Done

- [x] `PUBLIC_READER_UNAVAILABLE_POLICY` exists and defaults to `"hard_404"`.
- [x] Per-novel `public_reader_unavailable_policy` override is honored.
- [x] Invalid policy values fall back to `"hard_404"` and log a warning.
- [x] Missing active translations support `hard_404`, `chapter_shell`, and `latest_version`.
- [x] Active translations are always served when available.
- [x] Owner-only `version_id` preview works.
- [x] Public unauthenticated `version_id` is ignored.
- [x] Normal translated responses include additive availability and version metadata.
- [x] Public chapter lists include additive `availability_status`.
- [x] No DB migrations, storage schema changes, or new endpoints are introduced.
- [x] Focused tests, lint checks, and configured type checks pass.

### Verification Results

- **Tests:** 22/22 pass in `test_public_reader_availability.py` (3.20s).
- **Existing tests:** 138/139 pass in `test_public_router.py` + `test_public_reader_availability.py` (1 pre-existing failure unrelated to this work).
- **Ruff:** All checks passed on all 5 modified files.
- **Pyright:** 0 errors on all 5 modified files.
- **Files changed:**
  - `backend/src/novelai/config/settings.py` — added `PUBLIC_READER_UNAVAILABLE_POLICY`
  - `backend/src/novelai/storage/translations.py` — added `load_translated_chapter_by_version_id`
  - `backend/src/novelai/storage/service.py` — bound new method to `StorageService`
  - `backend/src/novelai/api/routers/public.py` — added helpers, updated `get_chapter` and `list_chapters`
  - `backend/tests/test_public_reader_availability.py` — new test file (22 tests)