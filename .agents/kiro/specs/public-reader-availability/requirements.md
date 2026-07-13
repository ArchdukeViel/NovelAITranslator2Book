# Requirements: Public Reader Availability

## Introduction

The public chapter endpoint, `GET /api/public/novels/{slug}/chapters/{chapter_id}`, currently returns HTTP 404 with `"Translated chapter not available."` when no active translation exists.

That behavior is safe, but too blunt. It does not distinguish between a missing chapter and an existing chapter that has not been translated yet. It also prevents a reader-safe "coming soon" chapter shell, and it cannot fall back to an existing saved translation version when the active version pointer is missing or unset.

The storage layer already exposes the data needed for better availability behavior: translated chapter versions can be listed, active versions can be detected, and existing version metadata can be reused. This spec adds a configurable public availability policy and an owner-only version preview parameter to the public chapter endpoint.

This work is additive and keeps the default behavior unchanged.

## Requirements

### REQ-1: Configurable Availability Policy

Public behavior when no active translation exists must be configurable globally and per novel.

- REQ-1.1: Add `PUBLIC_READER_UNAVAILABLE_POLICY` to `backend/src/novelai/config/settings.py`.
- REQ-1.2: The setting must read from the environment variable `PUBLIC_READER_UNAVAILABLE_POLICY`.
- REQ-1.3: The default value must be `"hard_404"`.
- REQ-1.4: Allowed values are:
  - `"hard_404"`
  - `"chapter_shell"`
  - `"latest_version"`
- REQ-1.5: A per-novel override may be stored in `metadata.json` under `public_reader_unavailable_policy`.
- REQ-1.6: A valid per-novel override must take precedence over the global setting.
- REQ-1.7: Invalid global or per-novel policy values must fall back to `"hard_404"`.
- REQ-1.8: Invalid policy values must log a `WARNING`.

### REQ-2: Preserve Default `hard_404` Behavior

The default policy must preserve current public behavior.

- REQ-2.1: With policy `"hard_404"`, a chapter without an active translated version must return HTTP 404.
- REQ-2.2: The 404 detail should remain compatible with the current response, such as `"Translated chapter not available."`.
- REQ-2.3: Existing deployments must behave the same unless they opt into another policy.
- REQ-2.4: Missing novels, unpublished novels, and chapter IDs not present in metadata must continue returning reader-safe 404 responses.

### REQ-3: `chapter_shell` Policy

When the policy is `"chapter_shell"`, an existing untranslated chapter must return a reader-safe shell response instead of 404.

- REQ-3.1: The response must use HTTP 200.
- REQ-3.2: The response must include:
  - `novel_id`
  - `slug`
  - `chapter_id`
  - `chapter_number`
  - `novel_title`
  - `title`
  - `text: null`
  - `reader_blocks: []`
  - `previous_chapter_id`
  - `next_chapter_id`
  - `previous_chapter_unavailable`
  - `next_chapter_unavailable`
  - `availability_status: "not_translated"`
  - `availability_message: "This chapter has not been translated yet."`
  - `version_id: null`
  - `is_active_version: false`
- REQ-3.3: Previous/next chapter IDs must preserve reader navigation where safe.
- REQ-3.4: Previous/next unavailable flags must indicate whether neighboring chapters exist but lack translated content.
- REQ-3.5: Normal translated chapter responses must include `availability_status: "available"`.
- REQ-3.6: `chapter_shell` must not expose raw source text as translated content.

### REQ-4: `latest_version` Policy

When the policy is `"latest_version"`, the public reader may serve the most recent saved translated version if no active translation is available.

- REQ-4.1: If `load_translated_chapter(novel_id, chapter_id)` returns a valid active translation, the active translation must be served regardless of policy.
- REQ-4.2: If no active translation is available, the endpoint must call `storage.list_translated_chapter_versions(novel_id, chapter_id)`.
- REQ-4.3: The endpoint must select the version with the most recent `created_at` timestamp.
- REQ-4.4: If `created_at` is missing, `translated_at` may be used as a fallback sort key.
- REQ-4.5: The selected version must contain translated text; versions without text must not be served as available reader content.
- REQ-4.6: The selected version must be returned using the normal translated chapter response shape.
- REQ-4.7: The response must include `version_id`.
- REQ-4.8: The response must include `is_active_version: false`.
- REQ-4.9: The response should include `version_kind`, `provider`, `model`, and `translated_at` when available.
- REQ-4.10: If no saved version with text exists, the endpoint must fall back to `chapter_shell` behavior.

### REQ-5: Owner-Only Version Preview

The public chapter endpoint must accept an optional `version_id` query parameter for owner preview.

- REQ-5.1: `GET /api/public/novels/{slug}/chapters/{chapter_id}?version_id={version_id}` must load the specified version only when the caller is authenticated as an owner.
- REQ-5.2: Owner authentication must use the existing owner-role auth mechanism, such as `require_role("owner")`.
- REQ-5.3: For unauthenticated public requests, the `version_id` parameter must be silently ignored.
- REQ-5.4: If optional owner auth fails, normal public behavior must continue.
- REQ-5.5: When an authenticated owner supplies an unknown `version_id`, the endpoint must return HTTP 404 with `"Version not found."`.
- REQ-5.6: When a specific version is served, the response must include:
  - `version_id`
  - `is_active_version`
  - `version_kind`
  - `provider`
  - `model`
  - `translated_at`

### REQ-6: Specific Version Storage Helper

Storage must expose a helper for loading a translated chapter by version ID.

- REQ-6.1: Add `load_translated_chapter_by_version_id(novel_id, chapter_id, version_id)` to `backend/src/novelai/storage/translations.py`.
- REQ-6.2: The helper must load the existing translated chapter bundle.
- REQ-6.3: The helper must search the existing `translation_versions` list by version `id`.
- REQ-6.4: The helper must return `None` if the bundle or version does not exist.
- REQ-6.5: The helper must not modify storage.
- REQ-6.6: The helper must return normalized fields compatible with public chapter response construction, including:
  - `version_id`
  - `version_kind`
  - `provider`
  - `model`
  - `translated_at`
  - `created_at`
  - `text`
  - `glossary_revision` when available

### REQ-7: Availability Fields in Normal Chapter Responses

Normal translated chapter responses must include additive availability/version fields.

- REQ-7.1: Successful translated responses must include `availability_status: "available"`.
- REQ-7.2: Successful translated responses must include `availability_message: null` or omit it according to existing response style.
- REQ-7.3: Successful translated responses must include `version_id` when available.
- REQ-7.4: Successful translated responses must include `is_active_version: true` for active translations.
- REQ-7.5: Successful translated responses should include `version_kind`, `provider`, `model`, and `translated_at` when available.
- REQ-7.6: New fields must be additive and must not remove or rename existing response fields.

### REQ-8: Availability Status in Chapter List

The public chapter list endpoint must expose per-chapter availability status.

- REQ-8.1: `GET /api/public/novels/{slug}/chapters` must include `availability_status` for each chapter.
- REQ-8.2: `availability_status` must be `"available"` when a translated chapter exists.
- REQ-8.3: `availability_status` must be `"not_translated"` when no translated chapter exists.
- REQ-8.4: Availability must be computed from `storage.list_translated_chapters(novel_id)` or the local equivalent.
- REQ-8.5: The chapter list response shape must remain additive; existing fields must be unchanged.

### REQ-9: Safety and Compatibility

Availability behavior must remain reader-safe and backward compatible.

- REQ-9.1: No database migration is required.
- REQ-9.2: No storage file format change is required.
- REQ-9.3: No new API endpoint is required.
- REQ-9.4: Public readers must not be able to browse arbitrary historical versions.
- REQ-9.5: Public unauthenticated requests must not be able to force a specific version with `version_id`.
- REQ-9.6: Raw source text must never be returned as translated content.
- REQ-9.7: Existing clients that ignore the new fields must continue working.
- REQ-9.8: Default `"hard_404"` behavior must preserve current deployment behavior.

### REQ-10: Tests

Create `backend/tests/test_public_reader_availability.py`.

- REQ-10.1: `test_hard_404_policy_returns_404` must assert policy `"hard_404"` with no translation returns HTTP 404.
- REQ-10.2: `test_chapter_shell_policy_returns_200_with_null_text` must assert policy `"chapter_shell"` with no translation returns HTTP 200, `text=null`, and `availability_status="not_translated"`.
- REQ-10.3: `test_latest_version_policy_returns_newest_saved_version` must assert policy `"latest_version"` with no active version but saved versions returns the newest version with text.
- REQ-10.4: `test_latest_version_policy_sets_inactive_flag` must assert latest-version fallback returns `is_active_version=false`.
- REQ-10.5: `test_latest_version_policy_falls_back_to_shell_when_no_versions` must assert zero versions returns chapter shell.
- REQ-10.6: `test_active_version_always_served_regardless_of_policy` must assert an active version is served with `is_active_version=true` under all policies.
- REQ-10.7: `test_version_id_param_honored_for_owner` must assert owner auth plus `version_id` returns the requested version.
- REQ-10.8: `test_version_id_param_ignored_for_public` must assert unauthenticated `version_id` is ignored.
- REQ-10.9: `test_unknown_version_id_for_owner_returns_404` must assert owner preview of unknown version returns HTTP 404.
- REQ-10.10: `test_per_novel_policy_override` must assert `metadata.json` policy overrides global policy.
- REQ-10.11: `test_invalid_policy_falls_back_to_hard_404` must assert invalid policy logs a warning and uses `hard_404`.
- REQ-10.12: `test_chapter_list_includes_availability_status` must assert chapter list includes availability for translated and untranslated chapters.
- REQ-10.13: Tests must confirm existing response fields remain present.

## Non-Goals

- This spec does not add public version browsing.
- This spec does not expose all historical versions to unauthenticated users.
- This spec does not change how active versions are set.
- This spec does not change publishing rules.
- This spec does not change the admin chapter version list endpoint.
- This spec does not add reader feedback, voting, or retranslation requests.
- This spec does not change crawl, translation, or export behavior.