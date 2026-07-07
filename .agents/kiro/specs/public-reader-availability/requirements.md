# Requirements: Public Reader Availability

## Introduction

The public chapter endpoint (`GET /api/public/novels/{slug}/chapters/{chapter_id}`) returns HTTP 404 with `"Translated chapter not available."` when no active translation exists. There is no fallback to a previous approved version, no "coming soon" shell that preserves navigation, and no way for a reader to distinguish "this chapter doesn't exist" from "this chapter exists but isn't translated yet." The hard 404 removes chapters from public consumption even when older approved versions exist, and it breaks client navigation by making `previous_chapter_unavailable` / `next_chapter_unavailable` logic unreliable when the reader suddenly disappears mid-novel.

The storage layer already has everything needed: `list_translated_chapter_versions` returns all versions with an `active: bool` flag, and `activate_translated_chapter_version` can promote any version. This spec adds a configurable availability policy and a version selection parameter to the public chapter endpoint.

## Requirements

### REQ-1: Configurable Availability Policy

The behavior when no active translation exists must be configurable per-novel and globally.

- REQ-1.1: A new setting `PUBLIC_READER_UNAVAILABLE_POLICY` must be added to `backend/src/novelai/config/settings.py`. Allowed values: `"hard_404"` (current behavior, default), `"chapter_shell"` (return a 200 with availability metadata and no text), `"latest_version"` (return the most recently saved translation version even if not activated).
- REQ-1.2: The setting must be readable from the environment variable `PUBLIC_READER_UNAVAILABLE_POLICY` with default `"hard_404"`.
- REQ-1.3: A per-novel override must be storable in the novel's `metadata.json` under the key `public_reader_unavailable_policy`. When present, it overrides the global setting for that novel.
- REQ-1.4: Invalid policy values (neither `"hard_404"`, `"chapter_shell"`, nor `"latest_version"`) must fall back to `"hard_404"` and log a `WARNING`.

### REQ-2: `chapter_shell` Policy

When the policy is `"chapter_shell"`, the endpoint must return a 200 response with availability metadata instead of a 404.

- REQ-2.1: The response must have HTTP status 200.
- REQ-2.2: The response body must include: `novel_id`, `slug`, `chapter_id`, `chapter_number`, `novel_title`, `title`, `text: null`, `reader_blocks: []`, `previous_chapter_id`, `next_chapter_id`, `previous_chapter_unavailable`, `next_chapter_unavailable`, `availability_status: "not_translated"`, `availability_message: "This chapter has not been translated yet."`.
- REQ-2.3: The `availability_status` field must also be present in normal translated responses with value `"available"`.
- REQ-2.4: Frontend code that checks for `text != null` will continue to work correctly; the new `availability_status` field is additive.

### REQ-3: `latest_version` Policy

When the policy is `"latest_version"`, the endpoint must serve the most recently saved translation version even if it is not the active version.

- REQ-3.1: When `load_translated_chapter` returns `None` (no active version), the endpoint must call `storage.list_translated_chapter_versions(novel_id, chapter_id)` and select the version with the most recent `created_at` timestamp.
- REQ-3.2: The selected version must be served with the normal response shape, including `text`, `reader_blocks`, and all standard fields.
- REQ-3.3: The response must include `version_id: str` and `is_active_version: false` in the response body to signal to clients that this is not the official active version.
- REQ-3.4: When no versions exist at all, the endpoint must fall back to `chapter_shell` behavior (200 with `availability_status: "not_translated"`), regardless of the policy setting.
- REQ-3.5: When `load_translated_chapter` returns a result (an active version exists), `is_active_version: true` must be returned and the normal active version is served — no change from today's behavior.

### REQ-4: Version Selection Parameter (Admin Preview)

The public chapter endpoint must accept an optional `version_id` query parameter for previewing specific versions.

- REQ-4.1: `GET /api/public/novels/{slug}/chapters/{chapter_id}?version_id={version_id}` must load and serve the specified version when supplied.
- REQ-4.2: This parameter must only be honored when the caller is authenticated as owner (via `require_role("owner")`). For unauthenticated public requests, the `version_id` parameter must be silently ignored.
- REQ-4.3: When an authenticated owner supplies an unknown `version_id`, return HTTP 404 with `"Version not found."`.
- REQ-4.4: A new storage helper `load_translated_chapter_by_version_id(novel_id, chapter_id, version_id)` must be added to `storage/translations.py` that loads a specific version from `translation_versions` list by `id` field.
- REQ-4.5: The response when loading a specific version must include `version_id`, `is_active_version`, `version_kind`, `provider`, `model`, `translated_at`.

### REQ-5: Availability Status in Chapter List

The chapter list endpoint must expose per-chapter availability status.

- REQ-5.1: `GET /api/public/novels/{slug}/chapters` must include an `availability_status` field per chapter: `"available"` when a translation exists, `"not_translated"` when none exists.
- REQ-5.2: This is computed from `storage.list_translated_chapters(novel_id)` which already returns the set of translated chapter IDs.
- REQ-5.3: The chapter list response shape must be additive — existing fields are unchanged.

### REQ-6: Tests

- REQ-6.1: A new test file `backend/tests/test_public_reader_availability.py` must be created.
- REQ-6.2: `test_hard_404_policy_returns_404` — active policy `"hard_404"`, no translation → HTTP 404.
- REQ-6.3: `test_chapter_shell_policy_returns_200_with_null_text` — policy `"chapter_shell"`, no translation → HTTP 200, `text=null`, `availability_status="not_translated"`.
- REQ-6.4: `test_latest_version_policy_returns_newest_saved_version` — policy `"latest_version"`, no active version but one saved version → HTTP 200 with that version's text, `is_active_version=false`.
- REQ-6.5: `test_latest_version_policy_falls_back_to_shell_when_no_versions` — policy `"latest_version"`, zero versions → 200 with `availability_status="not_translated"`.
- REQ-6.6: `test_active_version_always_served_regardless_of_policy` — any policy, active version exists → that version is served, `is_active_version=true`.
- REQ-6.7: `test_version_id_param_honored_for_owner` — owner auth + `version_id` param → specific version returned.
- REQ-6.8: `test_version_id_param_ignored_for_public` — no auth + `version_id` param → active version returned (param silently ignored).
- REQ-6.9: `test_per_novel_policy_override` — metadata has `public_reader_unavailable_policy="chapter_shell"`, global is `"hard_404"` → chapter_shell behavior used.
- REQ-6.10: `test_chapter_list_includes_availability_status` — assert `availability_status` present in chapter list response.

## Non-Goals

- This spec does not add full public version browsing (all versions visible to public readers).
- This spec does not change how active versions are set or published.
- This spec does not add a "vote for re-translation" or user feedback mechanism.
- This spec does not change the admin chapter version list endpoint.
