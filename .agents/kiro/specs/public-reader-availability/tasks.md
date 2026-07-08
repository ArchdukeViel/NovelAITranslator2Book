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

- [ ] 1. Preflight Current Reader Behavior
  - [ ] 1.1 Inspect `backend/src/novelai/api/routers/public.py` and locate public `get_chapter`.
  - [ ] 1.2 Locate the public chapter list handler.
  - [ ] 1.3 Confirm current missing-translation behavior returns HTTP 404 with detail `"Translated chapter not available."`.
  - [ ] 1.4 Inspect how public routes resolve slug, metadata, chapter order, chapter IDs, and published status.
  - [ ] 1.5 Inspect how normal chapter responses build `text`, `reader_blocks`, previous/next navigation, and chapter title.
  - [ ] 1.6 Inspect `backend/src/novelai/storage/translations.py` for active translation loading, version listing, and translated chapter listing helpers.
  - [ ] 1.7 Inspect `backend/src/novelai/config/settings.py` and follow existing settings style.
  - [ ] 1.8 Inspect public reader tests and fixtures to reuse local setup.

- [ ] 2. Add Global Availability Policy Setting
  - [ ] 2.1 Add `PUBLIC_READER_UNAVAILABLE_POLICY: str` to `backend/src/novelai/config/settings.py`.
  - [ ] 2.2 Read from environment variable `PUBLIC_READER_UNAVAILABLE_POLICY`.
  - [ ] 2.3 Default to `"hard_404"`.
  - [ ] 2.4 Do not raise during settings load for invalid values.
  - [ ] 2.5 Leave validation to the public router policy resolver.

- [ ] 3. Add Specific Version Storage Loader
  - [ ] 3.1 Implement `load_translated_chapter_by_version_id(novel_id, chapter_id, version_id)` in `backend/src/novelai/storage/translations.py`.
  - [ ] 3.2 Load the existing translated chapter bundle using existing internal helpers.
  - [ ] 3.3 Extract versions using the existing version normalization helper when available.
  - [ ] 3.4 Match by version `id`.
  - [ ] 3.5 Return `None` when the bundle is missing.
  - [ ] 3.6 Return `None` when the version ID is unknown.
  - [ ] 3.7 Return a normalized dict compatible with public response building, including `id`, `version_id`, `version_kind`, `provider`, `model`, `translated_at`, `created_at`, `text`, `editor`, `note`, `confidence_score`, and `glossary_revision`.
  - [ ] 3.8 Keep storage schemas unchanged.

- [ ] 4. Add Policy Resolution Helpers
  - [ ] 4.1 In `public.py`, define valid policies: `"hard_404"`, `"chapter_shell"`, and `"latest_version"`.
  - [ ] 4.2 Implement `_resolve_unavailable_policy(meta: dict[str, Any]) -> str`.
  - [ ] 4.3 Check `meta.get("public_reader_unavailable_policy")` first.
  - [ ] 4.4 Return valid per-novel policy when present.
  - [ ] 4.5 Log a warning for invalid explicit per-novel policy and fall back to `"hard_404"`.
  - [ ] 4.6 If no per-novel policy is set, check `settings.PUBLIC_READER_UNAVAILABLE_POLICY`.
  - [ ] 4.7 Return valid global policy when configured.
  - [ ] 4.8 Log a warning for invalid explicit global policy and fall back to `"hard_404"`.
  - [ ] 4.9 Do not warn when policy values are simply missing.

- [ ] 5. Add Optional Owner Auth Helper
  - [ ] 5.1 Implement `_try_get_owner(request: Request) -> Any | None` in `public.py`.
  - [ ] 5.2 Use the existing `require_role("owner")` path if available.
  - [ ] 5.3 Make the helper non-raising for unauthenticated public requests.
  - [ ] 5.4 Return an owner/auth object only when the caller is authenticated as owner.
  - [ ] 5.5 Swallow expected auth failures so public `?version_id=` requests continue normally.
  - [ ] 5.6 Do not grant preview access to non-owner roles unless the existing auth model treats them as owner-equivalent.

- [ ] 6. Add Chapter Shell Helper
  - [ ] 6.1 Implement `_chapter_shell_response(...)` in `public.py`.
  - [ ] 6.2 Preserve normal identity fields: `novel_id`, `slug`, `chapter_id`, `chapter_number`, `novel_title`, and `title`.
  - [ ] 6.3 Return `text: None`.
  - [ ] 6.4 Return `reader_blocks: []`.
  - [ ] 6.5 Return `availability_status: "not_translated"`.
  - [ ] 6.6 Return `availability_message: "This chapter has not been translated yet."`.
  - [ ] 6.7 Return version fields as unavailable: `version_id: None`, `is_active_version: False`, and optional version metadata as `None`.
  - [ ] 6.8 Compute previous/next IDs from the full chapter order.
  - [ ] 6.9 Use `storage.list_translated_chapters(novel_id)` to determine whether adjacent chapters are translated.
  - [ ] 6.10 Link `previous_chapter_id` and `next_chapter_id` only when the adjacent chapter is translated.
  - [ ] 6.11 Set `previous_chapter_unavailable` or `next_chapter_unavailable` when adjacent chapters exist but are untranslated.
  - [ ] 6.12 Reuse existing title and chapter-number helpers where practical.
  - [ ] 6.13 Do not expose raw source text.

- [ ] 7. Update Public `get_chapter` Signature
  - [ ] 7.1 Add `version_id: str | None = Query(default=None)`.
  - [ ] 7.2 Add `request: Request` if the handler does not already receive it.
  - [ ] 7.3 Keep the existing route path and HTTP method.
  - [ ] 7.4 Keep existing storage and DB dependencies unchanged.

- [ ] 8. Implement Owner Version Preview
  - [ ] 8.1 Initialize `effective_version_id = None`.
  - [ ] 8.2 If `version_id` is supplied, call `_try_get_owner(request)`.
  - [ ] 8.3 Set `effective_version_id` only when owner auth succeeds.
  - [ ] 8.4 If `effective_version_id` is set, call `storage.load_translated_chapter_by_version_id(...)`.
  - [ ] 8.5 If owner requested an unknown version, return HTTP 404 with detail `"Version not found."`.
  - [ ] 8.6 Load the active translation as well.
  - [ ] 8.7 Compare active `version_id` with requested `version_id`.
  - [ ] 8.8 Set `is_active_version` accurately.
  - [ ] 8.9 Ensure unauthenticated public requests with `?version_id=` ignore the parameter and continue through normal public behavior.

- [ ] 9. Preserve Active Translation Behavior
  - [ ] 9.1 When no owner preview is active, call existing `storage.load_translated_chapter(novel_id, chapter_id)`.
  - [ ] 9.2 If an active translation exists, serve it regardless of unavailable policy.
  - [ ] 9.3 Preserve existing response fields and reader block generation.
  - [ ] 9.4 Add `availability_status: "available"`.
  - [ ] 9.5 Add `availability_message: None` or omit it according to existing response style.
  - [ ] 9.6 Add `version_id`.
  - [ ] 9.7 Add `is_active_version: True`.
  - [ ] 9.8 Add `version_kind`, `provider`, `model`, and `translated_at` when available.

- [ ] 10. Implement `hard_404`
  - [ ] 10.1 When no active translation is available and policy is `"hard_404"`, preserve current behavior.
  - [ ] 10.2 Return HTTP 404 with detail `"Translated chapter not available."`.
  - [ ] 10.3 Verify this remains the default with no env var or per-novel override.

- [ ] 11. Implement `chapter_shell`
  - [ ] 11.1 When no active translation is available and policy is `"chapter_shell"`, return `_chapter_shell_response(...)`.
  - [ ] 11.2 Ensure response status is HTTP 200.
  - [ ] 11.3 Ensure `text` serializes as JSON `null`.
  - [ ] 11.4 Ensure `reader_blocks` is an empty list.
  - [ ] 11.5 Ensure `availability_status` is `"not_translated"`.
  - [ ] 11.6 Ensure navigation fields and unavailable flags are correct.

- [ ] 12. Implement `latest_version`
  - [ ] 12.1 When no active translation is available and policy is `"latest_version"`, call `storage.list_translated_chapter_versions(novel_id, chapter_id)`.
  - [ ] 12.2 Filter to versions with usable string `text`.
  - [ ] 12.3 Select the newest version by `created_at` descending.
  - [ ] 12.4 Use `translated_at` as fallback sort key when `created_at` is missing.
  - [ ] 12.5 Serve selected version with normal translated response shape.
  - [ ] 12.6 Set `availability_status: "available"`.
  - [ ] 12.7 Set `is_active_version: False`.
  - [ ] 12.8 Include `version_id` and available version metadata.
  - [ ] 12.9 If no saved version has text, fall back to `_chapter_shell_response(...)`.

- [ ] 13. Add Availability to Chapter List
  - [ ] 13.1 In the public chapter list endpoint, call `storage.list_translated_chapters(novel_id)` once.
  - [ ] 13.2 Convert translated IDs to a string set for stable comparison.
  - [ ] 13.3 Add `availability_status: "available"` when chapter ID is translated.
  - [ ] 13.4 Add `availability_status: "not_translated"` when chapter ID is not translated.
  - [ ] 13.5 Preserve existing chapter list fields.
  - [ ] 13.6 Preserve existing chapter ordering.

- [ ] 14. Add Test File and Fixtures
  - [ ] 14.1 Create `backend/tests/test_public_reader_availability.py`.
  - [ ] 14.2 Reuse existing FastAPI client fixtures when available.
  - [ ] 14.3 Reuse existing storage/temp directory fixtures when available.
  - [ ] 14.4 Add setup for a public/published novel with at least two chapters.
  - [ ] 14.5 Add setup for a chapter with no active translation.
  - [ ] 14.6 Add setup for saved translation versions with controlled timestamps.
  - [ ] 14.7 Add setup or dependency override for owner-authenticated requests.
  - [ ] 14.8 Reset environment variables/settings state between tests.

- [ ] 15. Write Policy Tests
  - [ ] 15.1 Test default or explicit `"hard_404"` returns HTTP 404 for missing translation.
  - [ ] 15.2 Test `"chapter_shell"` returns HTTP 200 for missing translation.
  - [ ] 15.3 Assert shell response has `text is None`.
  - [ ] 15.4 Assert shell response has `reader_blocks == []`.
  - [ ] 15.5 Assert shell response has `availability_status == "not_translated"`.
  - [ ] 15.6 Assert shell response has the expected availability message.
  - [ ] 15.7 Assert shell navigation fields and unavailable flags are correct.
  - [ ] 15.8 Test `"latest_version"` returns newest saved version when no active version exists.
  - [ ] 15.9 Assert latest-version response has `is_active_version is False`.
  - [ ] 15.10 Test `"latest_version"` falls back to shell when no saved version has text.
  - [ ] 15.11 Test active version is served under every policy.
  - [ ] 15.12 Assert active-version response has `is_active_version is True`.
  - [ ] 15.13 Test invalid policy falls back to `"hard_404"` and logs a warning.

- [ ] 16. Write Version Preview Tests
  - [ ] 16.1 Test owner auth plus `?version_id=` returns the requested version.
  - [ ] 16.2 Assert owner preview response includes `version_id`, `is_active_version`, `version_kind`, `provider`, `model`, and `translated_at`.
  - [ ] 16.3 Assert owner preview of a non-active version has `is_active_version is False`.
  - [ ] 16.4 Assert owner preview of the active version has `is_active_version is True`.
  - [ ] 16.5 Test owner auth plus unknown `version_id` returns HTTP 404 with `"Version not found."`.
  - [ ] 16.6 Test unauthenticated `?version_id=` is ignored.
  - [ ] 16.7 Assert unauthenticated request serves normal active-version behavior.
  - [ ] 16.8 Assert unauthenticated unknown `version_id` does not return `"Version not found."` when normal public response is available.

- [ ] 17. Write Per-Novel and Chapter List Tests
  - [ ] 17.1 Test per-novel `public_reader_unavailable_policy` overrides global policy.
  - [ ] 17.2 Test global policy applies when no per-novel override exists.
  - [ ] 17.3 Test chapter list includes `availability_status` for translated chapters.
  - [ ] 17.4 Test chapter list includes `availability_status` for untranslated chapters.
  - [ ] 17.5 Assert existing chapter list fields remain present and unchanged.

- [ ] 18. Backward Compatibility Checks
  - [ ] 18.1 Confirm default setting preserves current `"hard_404"` behavior.
  - [ ] 18.2 Confirm clients checking `text != null` remain compatible with shell responses.
  - [ ] 18.3 Confirm unauthenticated users cannot select arbitrary versions.
  - [ ] 18.4 Confirm no DB migration files are created.
  - [ ] 18.5 Confirm no storage JSON schema changes are introduced.
  - [ ] 18.6 Confirm admin chapter version routes are unchanged.
  - [ ] 18.7 Confirm no new public endpoint is added.

- [ ] 19. Run Verification
  - [ ] 19.1 Run `pytest backend/tests/test_public_reader_availability.py --tb=short -q`.
  - [ ] 19.2 Run existing public reader tests if present.
  - [ ] 19.3 Run `ruff check` on changed backend source and test files.
  - [ ] 19.4 Run configured backend type checker, such as `pyright` or `mypy`, if present.
  - [ ] 19.5 Fix test, lint, and type failures caused by this work.

- [ ] 20. Final Acceptance Review
  - [ ] 20.1 Verify default `"hard_404"` missing translation returns HTTP 404.
  - [ ] 20.2 Verify `"chapter_shell"` missing translation returns HTTP 200 with `text: null` and `availability_status: "not_translated"`.
  - [ ] 20.3 Verify `"latest_version"` returns newest saved version with `is_active_version: false` when active translation is missing.
  - [ ] 20.4 Verify active translations are always preferred when present.
  - [ ] 20.5 Verify authenticated owners can load a specific version via `?version_id=`.
  - [ ] 20.6 Verify public unauthenticated requests ignore `version_id`.
  - [ ] 20.7 Verify chapter list includes `availability_status`.
  - [ ] 20.8 Verify all required tests pass.

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

- [ ] `PUBLIC_READER_UNAVAILABLE_POLICY` exists and defaults to `"hard_404"`.
- [ ] Per-novel `public_reader_unavailable_policy` override is honored.
- [ ] Invalid policy values fall back to `"hard_404"` and log a warning.
- [ ] Missing active translations support `hard_404`, `chapter_shell`, and `latest_version`.
- [ ] Active translations are always served when available.
- [ ] Owner-only `version_id` preview works.
- [ ] Public unauthenticated `version_id` is ignored.
- [ ] Normal translated responses include additive availability and version metadata.
- [ ] Public chapter lists include additive `availability_status`.
- [ ] No DB migrations, storage schema changes, or new endpoints are introduced.
- [ ] Focused tests, lint checks, and configured type checks pass.