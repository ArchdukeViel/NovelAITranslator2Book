# Tasks: Public Reader Availability

## Overview

Implement configurable public reader behavior for chapters that exist in the novel manifest but do not currently have an active translated chapter. The implementation must preserve the current default behavior, add opt-in fallback policies, expose availability metadata, and allow owner-only preview of specific translation versions.

Scope boundaries:

- No database migrations.
- No storage file format changes.
- No frontend changes required.
- Admin chapter routes remain unchanged.
- Public API response changes are additive, except for opt-in policy behavior.

## Task List

- [ ] 1. Preflight and Current Behavior Review
  - [ ] 1.1 Inspect `backend/src/novelai/api/routers/public.py` and identify the current `get_chapter` and chapter list handlers.
  - [ ] 1.2 Inspect `backend/src/novelai/storage/translations.py` and confirm the existing helpers for active translation loading, version listing, active version selection, and translated chapter listing.
  - [ ] 1.3 Inspect `backend/src/novelai/config/settings.py` and follow the existing settings style before adding the new setting.
  - [ ] 1.4 Inspect existing public reader tests and test fixtures so the new tests reuse local conventions instead of creating duplicate setup code.
  - [ ] 1.5 Confirm the existing missing-translation behavior returns HTTP 404 with detail `"Translated chapter not available."` before making changes. (REQ-1, REQ-6.2)

- [ ] 2. Add Global Availability Policy Setting
  - [ ] 2.1 Add `PUBLIC_READER_UNAVAILABLE_POLICY: str` to `backend/src/novelai/config/settings.py`.
  - [ ] 2.2 Read the value from the `PUBLIC_READER_UNAVAILABLE_POLICY` environment variable.
  - [ ] 2.3 Default the setting to `"hard_404"` to preserve current behavior. (REQ-1.1, REQ-1.2)
  - [ ] 2.4 Do not validate or raise during settings load; invalid values are handled by the public router policy resolver. (REQ-1.4)

- [ ] 3. Add Specific Translation Version Loader
  - [ ] 3.1 Implement `load_translated_chapter_by_version_id(novel_id: str, chapter_id: str, version_id: str)` in `backend/src/novelai/storage/translations.py`. (REQ-4.4)
  - [ ] 3.2 Load the existing chapter bundle with the same internal helper used by other translation loaders.
  - [ ] 3.3 Extract versions using the existing version-normalization helper, if available.
  - [ ] 3.4 Match the requested version by the version `id` field.
  - [ ] 3.5 Return `None` when the bundle is missing or the version ID is unknown.
  - [ ] 3.6 Return a normalized dict compatible with `get_chapter`, including:
    - [ ] 3.6.1 `id`
    - [ ] 3.6.2 `version_id`
    - [ ] 3.6.3 `version_kind`
    - [ ] 3.6.4 `provider`
    - [ ] 3.6.5 `model`
    - [ ] 3.6.6 `translated_at`
    - [ ] 3.6.7 `created_at`
    - [ ] 3.6.8 `text`
    - [ ] 3.6.9 `editor`
    - [ ] 3.6.10 `note`
    - [ ] 3.6.11 `confidence_score`
    - [ ] 3.6.12 `glossary_revision`
  - [ ] 3.7 Keep storage schemas unchanged; this helper only reads the existing translation version list.

- [ ] 4. Add Public Router Policy Helpers
  - [ ] 4.1 In `backend/src/novelai/api/routers/public.py`, add a constant or local set for valid policies: `"hard_404"`, `"chapter_shell"`, and `"latest_version"`.
  - [ ] 4.2 Implement `_resolve_unavailable_policy(meta: dict[str, Any]) -> str`.
  - [ ] 4.3 Check `meta.get("public_reader_unavailable_policy")` first. (REQ-1.3)
  - [ ] 4.4 If the per-novel policy is valid, return it.
  - [ ] 4.5 Otherwise, check `settings.PUBLIC_READER_UNAVAILABLE_POLICY`.
  - [ ] 4.6 If the global policy is valid, return it.
  - [ ] 4.7 If either supplied value is invalid, fall back to `"hard_404"` and log a `WARNING`. (REQ-1.4)
  - [ ] 4.8 Ensure missing policy values do not log warnings; only invalid explicit values should warn.

- [ ] 5. Add Owner-Only Optional Version Auth Helper
  - [ ] 5.1 Implement `_try_get_owner(request: Request) -> Any | None` in `public.py`.
  - [ ] 5.2 Use the existing `require_role("owner")` auth path if it is available in the project.
  - [ ] 5.3 Make the helper non-raising for unauthenticated public requests.
  - [ ] 5.4 Return a truthy owner/auth object only when the caller is authenticated as owner.
  - [ ] 5.5 Swallow expected auth failures so public requests with `?version_id=` are silently treated like normal public requests. (REQ-4.2)
  - [ ] 5.6 Do not broaden preview access to non-owner roles unless the existing auth model explicitly treats them as owner-equivalent.

- [ ] 6. Add Chapter Shell Response Helper
  - [ ] 6.1 Implement `_chapter_shell_response(...)` in `public.py`. (REQ-2.1, REQ-2.2)
  - [ ] 6.2 Preserve the normal response identity fields:
    - [ ] 6.2.1 `novel_id`
    - [ ] 6.2.2 `slug`
    - [ ] 6.2.3 `chapter_id`
    - [ ] 6.2.4 `chapter_number`
    - [ ] 6.2.5 `novel_title`
    - [ ] 6.2.6 `title`
  - [ ] 6.3 Return unavailable content fields:
    - [ ] 6.3.1 `text: None`
    - [ ] 6.3.2 `reader_blocks: []`
    - [ ] 6.3.3 `availability_status: "not_translated"`
    - [ ] 6.3.4 `availability_message: "This chapter has not been translated yet."`
  - [ ] 6.4 Preserve navigation shape:
    - [ ] 6.4.1 `previous_chapter_id`
    - [ ] 6.4.2 `next_chapter_id`
    - [ ] 6.4.3 `previous_chapter_unavailable`
    - [ ] 6.4.4 `next_chapter_unavailable`
  - [ ] 6.5 Compute unavailable navigation from the full chapter order and `storage.list_translated_chapters(novel_id)`.
  - [ ] 6.6 Only link `previous_chapter_id` or `next_chapter_id` when that adjacent chapter is translated.
  - [ ] 6.7 Set unavailable flags to `true` when the adjacent chapter exists but is not translated.
  - [ ] 6.8 Include version metadata fields with empty or false values:
    - [ ] 6.8.1 `version_id: None`
    - [ ] 6.8.2 `is_active_version: False`
  - [ ] 6.9 Reuse existing title and chapter-number helpers where possible.

- [ ] 7. Update Public `get_chapter` Endpoint Signature
  - [ ] 7.1 Add `version_id: str | None = Query(default=None)` to the endpoint parameters. (REQ-4.1)
  - [ ] 7.2 Add `request: Request` if the handler does not already receive it. (REQ-4.2)
  - [ ] 7.3 Keep existing dependency injection for storage and DB sessions unchanged.
  - [ ] 7.4 Avoid changing the route path or method.

- [ ] 8. Implement Owner Version Preview Flow
  - [ ] 8.1 Initialize `effective_version_id` to `None`.
  - [ ] 8.2 When `version_id` is supplied, call `_try_get_owner(request)`.
  - [ ] 8.3 Set `effective_version_id` only when owner auth succeeds. (REQ-4.2)
  - [ ] 8.4 When `effective_version_id` is set, call `storage.load_translated_chapter_by_version_id(novel_id, chapter_id, effective_version_id)`. (REQ-4.1, REQ-4.4)
  - [ ] 8.5 If the owner requested an unknown version, return HTTP 404 with detail `"Version not found."`. (REQ-4.3)
  - [ ] 8.6 Load the active translation as well, compare active `version_id` to the requested version, and set `is_active_version` correctly. (REQ-4.5)
  - [ ] 8.7 Ensure unauthenticated public requests with `?version_id=` ignore the parameter and continue through the normal active-version path. (REQ-4.2)

- [ ] 9. Preserve Active Translation Behavior
  - [ ] 9.1 When no effective version ID is being previewed, call the existing `storage.load_translated_chapter(novel_id, chapter_id)`.
  - [ ] 9.2 If an active translation exists, serve it regardless of configured unavailable policy. (REQ-3.5)
  - [ ] 9.3 Set `is_active_version: true` for active translation responses. (REQ-3.5)
  - [ ] 9.4 Add `availability_status: "available"` to normal translated responses. (REQ-2.3)
  - [ ] 9.5 Add response version metadata fields:
    - [ ] 9.5.1 `version_id`
    - [ ] 9.5.2 `is_active_version`
    - [ ] 9.5.3 `version_kind`
    - [ ] 9.5.4 `provider`
    - [ ] 9.5.5 `model`
    - [ ] 9.5.6 `translated_at`
  - [ ] 9.6 Preserve existing response fields and existing reader block generation.

- [ ] 10. Implement `hard_404` Policy
  - [ ] 10.1 When no active translation is available and the resolved policy is `"hard_404"`, preserve current behavior.
  - [ ] 10.2 Return HTTP 404 with detail `"Translated chapter not available."`. (REQ-1.1, REQ-6.2)
  - [ ] 10.3 Verify this remains the default when no environment variable or per-novel override is configured.

- [ ] 11. Implement `chapter_shell` Policy
  - [ ] 11.1 When no active translation is available and the resolved policy is `"chapter_shell"`, return the shell response helper. (REQ-2.1, REQ-2.2)
  - [ ] 11.2 Ensure the shell response uses HTTP 200.
  - [ ] 11.3 Ensure `text` is JSON `null`, not an empty string. (REQ-2.2, REQ-2.4)
  - [ ] 11.4 Ensure `reader_blocks` is an empty list.
  - [ ] 11.5 Ensure frontend clients can distinguish the state using `availability_status: "not_translated"`. (REQ-2.3, REQ-2.4)

- [ ] 12. Implement `latest_version` Policy
  - [ ] 12.1 When no active translation is available and the resolved policy is `"latest_version"`, call `storage.list_translated_chapter_versions(novel_id, chapter_id)`. (REQ-3.1)
  - [ ] 12.2 Select the most recently saved version by `created_at` timestamp descending. (REQ-3.1)
  - [ ] 12.3 Serve the selected version with the normal translated chapter response shape. (REQ-3.2)
  - [ ] 12.4 Include `version_id` from the selected version. (REQ-3.3)
  - [ ] 12.5 Set `is_active_version: false`. (REQ-3.3)
  - [ ] 12.6 Include `availability_status: "available"` because text is being served.
  - [ ] 12.7 If no versions exist, fall back to chapter shell behavior even though the configured policy is `"latest_version"`. (REQ-3.4)
  - [ ] 12.8 If a candidate latest version lacks usable string `text`, fall back to chapter shell behavior rather than returning malformed readable content.

- [ ] 13. Add Availability Status to Public Chapter List
  - [ ] 13.1 In the public chapter list endpoint, call `storage.list_translated_chapters(novel_id)` once and convert the result to a set. (REQ-5.2)
  - [ ] 13.2 Add `availability_status: "available"` for chapter IDs in the translated set. (REQ-5.1)
  - [ ] 13.3 Add `availability_status: "not_translated"` for chapter IDs not in the translated set. (REQ-5.1)
  - [ ] 13.4 Preserve all existing chapter list fields and ordering. (REQ-5.3)
  - [ ] 13.5 Normalize ID comparison consistently, using string IDs if the storage layer returns strings.

- [ ] 14. Add Test File and Shared Test Setup
  - [ ] 14.1 Create `backend/tests/test_public_reader_availability.py`. (REQ-6.1)
  - [ ] 14.2 Reuse existing FastAPI app/client fixtures when available.
  - [ ] 14.3 Reuse existing storage/temp directory fixtures when available.
  - [ ] 14.4 Add helper setup for a public novel with at least two chapters so navigation fields can be tested.
  - [ ] 14.5 Add helper setup for chapter metadata without an active translation.
  - [ ] 14.6 Add helper setup for saved translation versions with controlled `created_at` values.
  - [ ] 14.7 Add helper setup or dependency override for owner-authenticated requests.
  - [ ] 14.8 Ensure tests reset environment variables and settings state between cases.

- [ ] 15. Write Policy Tests
  - [ ] 15.1 Write `test_hard_404_policy_returns_404`: default or explicit `"hard_404"`, no translation, expect HTTP 404. (REQ-6.2)
  - [ ] 15.2 Write `test_chapter_shell_policy_returns_200_with_null_text`: policy `"chapter_shell"`, no translation, expect HTTP 200, `text is None`, `reader_blocks == []`, `availability_status == "not_translated"`. (REQ-6.3)
  - [ ] 15.3 In the shell test, assert `availability_message == "This chapter has not been translated yet."`. (REQ-2.2)
  - [ ] 15.4 In the shell test, assert adjacent translated/untranslated navigation fields are correct. (REQ-2.2)
  - [ ] 15.5 Write `test_latest_version_policy_returns_newest_saved_version`: policy `"latest_version"`, no active version, multiple saved versions, expect newest version text and `is_active_version is False`. (REQ-6.4)
  - [ ] 15.6 Write `test_latest_version_policy_falls_back_to_shell_when_no_versions`: policy `"latest_version"`, zero versions, expect shell response. (REQ-6.5)
  - [ ] 15.7 Write `test_active_version_always_served_regardless_of_policy`: active version exists under each policy, expect active version text and `is_active_version is True`. (REQ-6.6)
  - [ ] 15.8 Write a test or assertion for invalid policy values falling back to `"hard_404"` and logging a warning. (REQ-1.4)

- [ ] 16. Write Version Selection Tests
  - [ ] 16.1 Write `test_version_id_param_honored_for_owner`: owner auth plus `?version_id=` returns the requested version. (REQ-6.7)
  - [ ] 16.2 Assert the owner preview response includes `version_id`, `is_active_version`, `version_kind`, `provider`, `model`, and `translated_at`. (REQ-4.5)
  - [ ] 16.3 Assert `is_active_version` is `false` when the requested owner-preview version is not the active version. (REQ-4.5)
  - [ ] 16.4 Assert `is_active_version` is `true` when the requested owner-preview version is the active version.
  - [ ] 16.5 Write an owner-only unknown version assertion: owner auth plus unknown `version_id` returns HTTP 404 with detail `"Version not found."`. (REQ-4.3)
  - [ ] 16.6 Write `test_version_id_param_ignored_for_public`: unauthenticated request with `?version_id=` returns the normal active version, not the requested non-active version. (REQ-6.8)
  - [ ] 16.7 Assert unauthenticated unknown `version_id` does not return `"Version not found."` if a normal active response is available. (REQ-4.2)

- [ ] 17. Write Per-Novel Override and Chapter List Tests
  - [ ] 17.1 Write `test_per_novel_policy_override`: metadata has `public_reader_unavailable_policy: "chapter_shell"` while global policy is `"hard_404"`, expect shell response. (REQ-6.9)
  - [ ] 17.2 Add a complementary assertion that a valid global policy applies when no per-novel override is present. (REQ-1.1, REQ-1.3)
  - [ ] 17.3 Write `test_chapter_list_includes_availability_status`: public chapter list includes both available and not-translated statuses. (REQ-6.10)
  - [ ] 17.4 Assert chapter list response shape is additive by checking an existing field still appears unchanged. (REQ-5.3)

- [ ] 18. Backward Compatibility Checks
  - [ ] 18.1 Confirm default `PUBLIC_READER_UNAVAILABLE_POLICY` keeps existing public behavior as `"hard_404"`. (REQ-1.1)
  - [ ] 18.2 Confirm clients that only check `text != null` still behave correctly for shell responses. (REQ-2.4)
  - [ ] 18.3 Confirm public unauthenticated users cannot browse arbitrary versions via `version_id`. (REQ-4.2)
  - [ ] 18.4 Confirm there are no DB migration files created.
  - [ ] 18.5 Confirm no storage JSON schema changes are introduced.
  - [ ] 18.6 Confirm admin chapter version list behavior is unchanged.

- [ ] 19. Run Focused Verification
  - [ ] 19.1 Run `pytest backend/tests/test_public_reader_availability.py --tb=short -q`.
  - [ ] 19.2 If existing public reader tests exist, run them as well.
  - [ ] 19.3 Run `ruff check backend/src/novelai/api/routers/public.py backend/src/novelai/storage/translations.py backend/src/novelai/config/settings.py backend/tests/test_public_reader_availability.py`.
  - [ ] 19.4 Run the repository's normal backend type checker if configured, such as `pyright`, `mypy`, or the project's existing test command.
  - [ ] 19.5 Fix any lint, type, or test failures caused by the new work.

- [ ] 20. Final Review and Acceptance Mapping
  - [ ] 20.1 Verify acceptance criterion 1: default `"hard_404"` missing translation still returns HTTP 404.
  - [ ] 20.2 Verify acceptance criterion 2: `"chapter_shell"` missing translation returns HTTP 200 with `text: null` and `availability_status: "not_translated"`.
  - [ ] 20.3 Verify acceptance criterion 3: `"latest_version"` missing active translation but saved version exists returns that version with `is_active_version: false`.
  - [ ] 20.4 Verify acceptance criterion 4: authenticated owner can load any specific version via `?version_id=`.
  - [ ] 20.5 Verify acceptance criterion 5: public unauthenticated requests ignore `version_id`.
  - [ ] 20.6 Verify acceptance criterion 6: public chapter list includes `availability_status` per chapter.
  - [ ] 20.7 Verify acceptance criterion 7: all required tests pass.

## Requirement Coverage Matrix

| Requirement | Covered By Tasks |
|---|---|
| REQ-1 Configurable Availability Policy | 2, 4, 10, 15, 17, 18, 20 |
| REQ-2 `chapter_shell` Policy | 6, 11, 15, 18, 20 |
| REQ-3 `latest_version` Policy | 9, 12, 15, 20 |
| REQ-4 Version Selection Parameter | 3, 5, 7, 8, 16, 18, 20 |
| REQ-5 Chapter List Availability | 13, 17, 20 |
| REQ-6 Tests | 14, 15, 16, 17, 19, 20 |

## Definition of Done

- [ ] `PUBLIC_READER_UNAVAILABLE_POLICY` exists and defaults to `"hard_404"`.
- [ ] Per-novel `metadata.json` override is honored through `public_reader_unavailable_policy`.
- [ ] Invalid policy values fall back to `"hard_404"` and log a warning.
- [ ] Missing active translations support `hard_404`, `chapter_shell`, and `latest_version` behavior.
- [ ] Owner-only `version_id` preview works and public unauthenticated `version_id` is ignored.
- [ ] Normal translated responses include additive availability and version metadata.
- [ ] Public chapter lists include additive `availability_status`.
- [ ] No DB migrations or storage schema changes are introduced.
- [ ] Required tests in `backend/tests/test_public_reader_availability.py` pass.
- [ ] Relevant linting and type checks pass, or any unavailable tooling is documented.
