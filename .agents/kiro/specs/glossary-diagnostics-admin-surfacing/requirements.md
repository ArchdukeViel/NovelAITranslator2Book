# Requirements: Glossary Diagnostics Admin Surfacing

## Introduction

The translation pipeline already uses glossary data during prompt generation. The deep research reports found that `TranslateStage` records useful glossary-related diagnostics such as injected term counts, glossary prompt blocks, truncation, conflict warnings, glossary hash, and approved term metadata. However, those diagnostics are not clearly surfaced through activity logs, admin APIs, or editor/review screens.

This spec makes glossary prompt-injection diagnostics visible to admins and reviewers. The goal is to explain whether glossary terms were injected, whether the prompt glossary block was truncated, whether conflicts occurred, and which glossary revision/hash was used for a translation.

## Requirements

### REQ-1: Persist Glossary Diagnostics

Glossary diagnostics produced during translation must be persisted in backend-accessible metadata.

- REQ-1.1: Persist per-chapter glossary diagnostics when a chapter translation completes.
- REQ-1.2: Persist diagnostics in translation activity metadata, translation version metadata, or both, depending on existing storage boundaries.
- REQ-1.3: Diagnostics must include `glossary_revision` when available.
- REQ-1.4: Diagnostics must include `glossary_hash` when available.
- REQ-1.5: Diagnostics must include injected term counts when available.
- REQ-1.6: Diagnostics must include prompt block truncation status when available.
- REQ-1.7: Diagnostics must include conflict/warning counts when available.
- REQ-1.8: Diagnostics must not store full prompt text by default.
- REQ-1.9: Diagnostics must not store full source chapter text or full translated chapter text.

### REQ-2: Normalize Diagnostic Shape

Glossary diagnostics must use a stable, documented shape.

- REQ-2.1: Add a normalizer/helper that converts raw translation context metadata into a compact diagnostics dict.
- REQ-2.2: The compact diagnostics dict must support missing fields without raising.
- REQ-2.3: The dict must include `term_count_injected`.
- REQ-2.4: The dict must include `term_count_available`.
- REQ-2.5: The dict must include `prompt_block_truncated`.
- REQ-2.6: The dict must include `conflict_count`.
- REQ-2.7: The dict must include `warning_count`.
- REQ-2.8: The dict must include `glossary_revision`.
- REQ-2.9: The dict must include `glossary_hash`.
- REQ-2.10: The dict may include a bounded list of safe warning/conflict codes.

### REQ-3: Expose Diagnostics in Admin APIs

Admin APIs must expose glossary diagnostics additively.

- REQ-3.1: Translation activity detail responses must include glossary diagnostics when available.
- REQ-3.2: Chapter translation/version detail responses must include glossary diagnostics when available.
- REQ-3.3: Novel translation summary responses should include aggregate counts of glossary warnings/conflicts when practical.
- REQ-3.4: Response changes must be additive and must not remove existing fields.
- REQ-3.5: Strict response models must be updated if they would otherwise drop diagnostics fields.
- REQ-3.6: Public reader APIs must not expose admin glossary diagnostics.

### REQ-4: Admin UI Visibility

Admin UI must make glossary diagnostics visible and actionable.

- REQ-4.1: Translation activity detail UI must show whether glossary terms were injected.
- REQ-4.2: Chapter/version UI must show glossary revision/hash used by the translation when available.
- REQ-4.3: UI must show a warning when glossary prompt block was truncated.
- REQ-4.4: UI must show warning/conflict counts.
- REQ-4.5: UI should expose a bounded list of safe conflict/warning codes or short messages.
- REQ-4.6: UI should link to glossary management/review screens when diagnostics indicate conflict or truncation.
- REQ-4.7: UI must avoid rendering full prompt text unless an explicit admin-debug mode already exists.

### REQ-5: Filtering and Review Workflow

Admins should be able to find translations with glossary issues.

- REQ-5.1: Add or extend admin filtering to find activities/chapters with glossary conflicts.
- REQ-5.2: Add or extend admin filtering to find activities/chapters with truncated glossary prompt blocks.
- REQ-5.3: Add or extend admin filtering to find translations with zero injected glossary terms when approved terms existed.
- REQ-5.4: If existing APIs cannot support filtering efficiently, expose aggregate fields first and document filtering as a follow-up.
- REQ-5.5: Filters must not require scanning full chapter text in the frontend.

### REQ-6: Diagnostics Aggregation

Novel-level and activity-level summaries should expose useful aggregate diagnostics.

- REQ-6.1: Activity metadata should include total translated chapters with glossary diagnostics.
- REQ-6.2: Activity metadata should include count of chapters with glossary conflicts.
- REQ-6.3: Activity metadata should include count of chapters with truncated glossary blocks.
- REQ-6.4: Activity metadata should include count of chapters where approved terms existed but zero terms were injected.
- REQ-6.5: Aggregates must be computed from compact diagnostics, not full prompt text.

### REQ-7: Security and Privacy

Diagnostics must not leak sensitive or oversized data.

- REQ-7.1: Do not persist full provider prompts by default.
- REQ-7.2: Do not persist raw source text or translated chapter text inside diagnostics.
- REQ-7.3: Do not persist provider API keys, account state, or hidden model configuration.
- REQ-7.4: Bound any stored warning/conflict list to a safe maximum length.
- REQ-7.5: Redact or omit free-form strings that could contain source content unless they are already safe diagnostic codes.

### REQ-8: Backward Compatibility

Existing translations and activities must continue to work.

- REQ-8.1: Translation versions without glossary diagnostics must still load.
- REQ-8.2: Activity records without glossary diagnostics must still load.
- REQ-8.3: Admin UI must gracefully show "not available" for older translations.
- REQ-8.4: Existing glossary prompt injection behavior must remain unchanged.
- REQ-8.5: Existing translation version schemas may receive additive diagnostics fields only.

### REQ-9: Tests

Focused tests must prove diagnostics are persisted, exposed, and safe.

- REQ-9.1: Test diagnostics normalizer handles full raw metadata.
- REQ-9.2: Test diagnostics normalizer handles missing fields.
- REQ-9.3: Test translation completion persists per-chapter diagnostics.
- REQ-9.4: Test translation activity metadata includes aggregate diagnostics.
- REQ-9.5: Test admin version/detail API includes diagnostics fields.
- REQ-9.6: Test public reader API does not expose diagnostics.
- REQ-9.7: Test warning/conflict lists are bounded and safe.
- REQ-9.8: Test admin UI displays truncation/conflict indicators if frontend is changed.
- REQ-9.9: Test old translations without diagnostics still load.

## Non-Goals

- This spec does not change glossary prompt injection rules.
- This spec does not change glossary review workflows.
- This spec does not implement glossary revision invalidation; that belongs to `glossary-revision-translation-invalidation`.
- This spec does not implement glossary-aware manual editor linting; that belongs to `glossary-aware-editor-qa`.
- This spec does not expose diagnostics in the public reader.
- This spec does not store full prompts by default.

