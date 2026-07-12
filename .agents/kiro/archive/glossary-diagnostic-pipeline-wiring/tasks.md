# tasks.md

# Tasks: Glossary Diagnostics Pipeline Wiring

## Task List

* [x] 0. Preflight review

  * [x] 0.1 Inspect `TranslateStage` input/output shape.
  * [x] 0.2 Locate `normalize_glossary_diagnostics()` and review its current behavior.
  * [x] 0.3 Inspect glossary matcher/service output and any raw diagnostic fields.
  * [x] 0.4 Inspect translation activity worker/orchestrator flow.
  * [x] 0.5 Inspect activity metadata update/patch service.
  * [x] 0.6 Inspect activity API response models and metadata whitelisting.
  * [x] 0.7 Inspect existing glossary, translation, and activity tests.
  * [x] 0.8 Inspect existing redaction/logging helpers.
  * [x] 0.9 Identify where chapter ID, novel ID, activity ID, and glossary revision/context are available.

* [x] 1. Define normalized diagnostic schema

  * [x] 1.1 Define schema version. (REQ-2)
  * [x] 1.2 Define summary counters. (REQ-2, REQ-4)
  * [x] 1.3 Define warning entry shape. (REQ-2)
  * [x] 1.4 Define term event entry shape. (REQ-2)
  * [x] 1.5 Define chapter summary shape. (REQ-4)
  * [x] 1.6 Define top warning summary shape. (REQ-4)
  * [x] 1.7 Define truncation fields. (REQ-6)
  * [x] 1.8 Define safe metadata fields. (REQ-8)
  * [x] 1.9 Document fields that must never be stored, such as raw prompts and full chapter text. (REQ-8)

* [x] 2. Stabilize warning codes and event enums

  * [x] 2.1 Define allowed warning codes. (REQ-1, REQ-2)
  * [x] 2.2 Define fallback `unknown` warning code. (REQ-1)
  * [x] 2.3 Define allowed severity values. (REQ-1, REQ-2)
  * [x] 2.4 Define severity fallback behavior. (REQ-1)
  * [x] 2.5 Define allowed term event values. (REQ-2)
  * [x] 2.6 Define match type values if term events include match type. (REQ-2)
  * [x] 2.7 Add tests for unknown warning code, unknown severity, and unknown event normalization. (REQ-1, REQ-11)

* [x] 3. Harden `normalize_glossary_diagnostics()`

  * [x] 3.1 Accept empty or `None` diagnostics. (REQ-1)
  * [x] 3.2 Normalize valid raw diagnostics into stable schema. (REQ-1, REQ-2)
  * [x] 3.3 Handle malformed raw diagnostics without throwing to caller. (REQ-1, REQ-7)
  * [x] 3.4 Normalize summary counts. (REQ-1, REQ-2)
  * [x] 3.5 Normalize warning entries. (REQ-1, REQ-2)
  * [x] 3.6 Normalize term events. (REQ-1, REQ-2)
  * [x] 3.7 Deduplicate duplicate term events where practical. (REQ-1)
  * [x] 3.8 Truncate long strings. (REQ-6, REQ-8)
  * [x] 3.9 Redact unsafe values. (REQ-8)
  * [x] 3.10 Add fallback malformed-diagnostics warning when normalization cannot fully process input. (REQ-1, REQ-7)
  * [x] 3.11 Add unit tests for empty, valid, malformed, unknown, duplicate, truncation, and redaction cases. (REQ-1, REQ-2, REQ-8, REQ-11)

* [x] 4. Add diagnostic limits configuration

  * [x] 4.1 Add max warnings limit. (REQ-6)
  * [x] 4.2 Add max term events limit. (REQ-6)
  * [x] 4.3 Add max chapter summaries limit. (REQ-6)
  * [x] 4.4 Add max term string length. (REQ-6, REQ-8)
  * [x] 4.5 Add max warning message length. (REQ-6, REQ-8)
  * [x] 4.6 Add max serialized metadata bytes if activity metadata has no existing limit. (REQ-6)
  * [x] 4.7 Add tests for configured limits. (REQ-6, REQ-11)

* [x] 5. Wire normalizer into `TranslateStage`

  * [x] 5.1 Identify where raw glossary diagnostics are available inside `TranslateStage`. (REQ-3)
  * [x] 5.2 Call `normalize_glossary_diagnostics()` after raw diagnostics are collected. (REQ-3)
  * [x] 5.3 Attach normalized diagnostics to stage result metadata. (REQ-3)
  * [x] 5.4 Preserve existing translated text/result fields. (REQ-3)
  * [x] 5.5 Preserve existing error behavior for translation failures. (REQ-3, REQ-7)
  * [x] 5.6 Add fallback behavior when normalization fails. (REQ-3, REQ-7)
  * [x] 5.7 Add tests verifying `TranslateStage` invokes normalizer. (REQ-3, REQ-11)
  * [x] 5.8 Add tests verifying translation output is preserved if diagnostic normalization fails. (REQ-3, REQ-7, REQ-11)

* [x] 6. Capture glossary matcher diagnostics

  * [x] 6.1 Inspect glossary matching output for available terms, considered terms, matches, aliases, and conflicts. (REQ-1, REQ-4)
  * [x] 6.2 Add raw diagnostic collection at matcher/service boundary if missing. (REQ-1)
  * [x] 6.3 Include term IDs where safe and available. (REQ-2, REQ-8)
  * [x] 6.4 Include source/display terms only within safe length limits. (REQ-2, REQ-8)
  * [x] 6.5 Include alias match information when available. (REQ-2)
  * [x] 6.6 Include conflict information when available. (REQ-2, REQ-4)
  * [x] 6.7 Do not include full source text or raw prompt sections. (REQ-8)
  * [x] 6.8 Add tests for matcher diagnostic capture if new code is added. (REQ-1, REQ-11)

* [x] 7. Implement diagnostics aggregator

  * [x] 7.1 Add `GlossaryDiagnosticsAggregator` or equivalent helper. (REQ-4)
  * [x] 7.2 Merge summary counters across chapters/batches. (REQ-4)
  * [x] 7.3 Count warning codes. (REQ-4)
  * [x] 7.4 Count conflict warnings. (REQ-4)
  * [x] 7.5 Count chapters with warnings. (REQ-4)
  * [x] 7.6 Produce bounded chapter summaries. (REQ-4, REQ-6)
  * [x] 7.7 Produce top warning summaries. (REQ-4)
  * [x] 7.8 Truncate warning and term event details. (REQ-6)
  * [x] 7.9 Mark metadata as truncated when limits are applied. (REQ-6)
  * [x] 7.10 Handle malformed/empty chapter diagnostics safely. (REQ-4, REQ-7)
  * [x] 7.11 Add aggregation tests for multi-chapter, warnings, conflicts, truncation, and malformed input. (REQ-4, REQ-6, REQ-11)

* [x] 8. Wire aggregation into translation activity flow

  * [x] 8.1 Identify chapter/batch loop in translation worker/orchestrator. (REQ-4, REQ-5)
  * [x] 8.2 Collect normalized diagnostics from each `TranslateStage` result. (REQ-4)
  * [x] 8.3 Add chapter ID and safe context to chapter summary where available. (REQ-4, REQ-8)
  * [x] 8.4 Update aggregator after each chapter/batch. (REQ-4)
  * [x] 8.5 Produce final aggregated diagnostics at activity completion. (REQ-5)
  * [x] 8.6 Preserve partial aggregated diagnostics on activity failure when safe. (REQ-5, REQ-7)
  * [x] 8.7 Add tests for successful multi-chapter aggregation and partial failure aggregation. (REQ-4, REQ-5, REQ-11)

* [x] 9. Persist diagnostics to activity metadata

  * [x] 9.1 Use existing activity metadata patch/update method. (REQ-5)
  * [x] 9.2 Persist diagnostics under `metadata.glossary_diagnostics`. (REQ-5)
  * [x] 9.3 Merge with existing metadata instead of replacing it. (REQ-5)
  * [x] 9.4 Preserve `metadata.progress`. (REQ-5)
  * [x] 9.5 Preserve `metadata.crawl_result`. (REQ-5)
  * [x] 9.6 Persist final diagnostics on translation success. (REQ-5)
  * [x] 9.7 Persist partial diagnostics on translation failure when available. (REQ-5, REQ-7)
  * [x] 9.8 Log safe warning if metadata persistence fails. (REQ-5, REQ-7, REQ-10)
  * [x] 9.9 Ensure metadata persistence failure does not corrupt translated output. (REQ-5, REQ-7)
  * [x] 9.10 Add tests for metadata merge, success persistence, partial persistence, and persistence failure. (REQ-5, REQ-7, REQ-11)

* [x] 10. Update activity response models if needed

  * [x] 10.1 Inspect whether activity APIs expose metadata directly. (REQ-9)
  * [x] 10.2 If metadata is whitelisted, add `glossary_diagnostics` to allowed fields. (REQ-9)
  * [x] 10.3 Ensure old activities without diagnostics still serialize correctly. (REQ-9)
  * [x] 10.4 Ensure diagnostics are JSON-compatible in API responses. (REQ-9)
  * [x] 10.5 Ensure existing activity authorization applies. (REQ-8, REQ-9)
  * [x] 10.6 Add API tests for activity response with and without diagnostics. (REQ-9, REQ-11)

* [x] 11. Add redaction and safety checks

  * [x] 11.1 Add or reuse redaction helper for diagnostic strings. (REQ-8)
  * [x] 11.2 Ensure raw prompts are never included. (REQ-8)
  * [x] 11.3 Ensure full source text is never included. (REQ-8)
  * [x] 11.4 Ensure full translated text is never included. (REQ-8)
  * [x] 11.5 Ensure provider API keys/tokens are never included. (REQ-8)
  * [x] 11.6 Ensure long warning messages are truncated. (REQ-6, REQ-8)
  * [x] 11.7 Ensure term strings are bounded. (REQ-6, REQ-8)
  * [x] 11.8 Add tests for unsafe values, long strings, and redaction. (REQ-8, REQ-11)

* [x] 12. Add observability logs

  * [x] 12.1 Log safe event when diagnostics normalize successfully. (REQ-10)
  * [x] 12.2 Log safe warning when diagnostics are malformed. (REQ-10)
  * [x] 12.3 Log safe summary when diagnostics aggregate. (REQ-10)
  * [x] 12.4 Log safe event when diagnostics persist. (REQ-10)
  * [x] 12.5 Log safe warning when metadata persistence fails. (REQ-10)
  * [x] 12.6 Include activity ID, novel ID, and chapter ID where available. (REQ-10)
  * [x] 12.7 Ensure logs do not include raw prompts or full text. (REQ-8, REQ-10)
  * [x] 12.8 Add log-related tests only where project conventions support them. (REQ-10, REQ-11)

* [x] 13. Backend test coverage pass

  * [x] 13.1 Add normalizer empty input tests. (REQ-1, REQ-11)
  * [x] 13.2 Add normalizer valid input tests. (REQ-1, REQ-11)
  * [x] 13.3 Add normalizer malformed input tests. (REQ-1, REQ-7, REQ-11)
  * [x] 13.4 Add warning/severity/event normalization tests. (REQ-1, REQ-2, REQ-11)
  * [x] 13.5 Add `TranslateStage` normalizer invocation tests. (REQ-3, REQ-11)
  * [x] 13.6 Add `TranslateStage` diagnostic failure resilience tests. (REQ-3, REQ-7, REQ-11)
  * [x] 13.7 Add aggregator multi-chapter tests. (REQ-4, REQ-11)
  * [x] 13.8 Add aggregator truncation tests. (REQ-6, REQ-11)
  * [x] 13.9 Add activity metadata persistence tests. (REQ-5, REQ-11)
  * [x] 13.10 Add partial diagnostics on failure tests where implemented. (REQ-5, REQ-7, REQ-11)
  * [x] 13.11 Add activity response compatibility tests. (REQ-9, REQ-11)
  * [x] 13.12 Add redaction/security tests. (REQ-8, REQ-11)
  * [x] 13.13 Run existing translation pipeline tests and fix additive-contract regressions. (REQ-3, REQ-11)

* [x] 14. Documentation

  * [x] 14.1 Document normalized glossary diagnostic schema. (REQ-2)
  * [x] 14.2 Document activity metadata location: `metadata.glossary_diagnostics`. (REQ-5)
  * [x] 14.3 Document warning codes and severities. (REQ-1, REQ-2)
  * [x] 14.4 Document metadata limits and truncation behavior. (REQ-6)
  * [x] 14.5 Document diagnostic failure behavior. (REQ-7)
  * [x] 14.6 Document security exclusions: no raw prompts, full text, or secrets. (REQ-8)
  * [x] 14.7 Document how future admin/frontend views can consume diagnostics. (REQ-9)

* [x] 15. Completion verification

  * [x] 15.1 Run a translation with glossary terms and verify activity metadata includes diagnostics. (REQ-12)
  * [x] 15.2 Run a translation with alias matches and verify alias counts appear. (REQ-12)
  * [x] 15.3 Run a translation with conflicting glossary terms and verify warning summary appears. (REQ-12)
  * [x] 15.4 Run a multi-chapter translation and verify aggregated diagnostics appear. (REQ-12)
  * [x] 15.5 Simulate malformed diagnostics and verify translation still completes. (REQ-7, REQ-12)
  * [x] 15.6 Simulate metadata size overflow and verify truncation. (REQ-6, REQ-12)
  * [x] 15.7 Verify activity API returns diagnostics for authorized users. (REQ-9, REQ-12)
  * [x] 15.8 Verify existing translation tests still pass. (REQ-11, REQ-12)
  * [x] 15.9 Mark `glossary-diagnostics-pipeline-wiring` complete only after diagnostics are visible in activity metadata.
