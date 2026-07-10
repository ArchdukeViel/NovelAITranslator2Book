# tasks.md

# Tasks: Public Glossary Annotations Setting

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing settings/config system.
  * [ ] 0.2 Inspect public reader chapter API annotation wiring.
  * [ ] 0.3 Inspect `PublicGlossaryAnnotationsService.find_annotations()` call site.
  * [ ] 0.4 Inspect novel/publication settings model.
  * [ ] 0.5 Inspect admin settings API patterns.
  * [ ] 0.6 Inspect admin novel settings UI patterns.
  * [ ] 0.7 Inspect public reader cache behavior.
  * [ ] 0.8 Inspect admin audit logging system.
  * [ ] 0.9 Inspect backend/frontend tests for settings, public reader, and admin pages.

* [ ] 1. Define setting semantics

  * [ ] 1.1 Define global annotation setting key. (REQ-1)
  * [ ] 1.2 Define deployment kill switch behavior. (REQ-1)
  * [ ] 1.3 Define per-novel mode values: inherit, enabled, disabled. (REQ-2)
  * [ ] 1.4 Define effective setting resolution rules. (REQ-3)
  * [ ] 1.5 Define public reader fail-closed behavior. (REQ-3, REQ-10)
  * [ ] 1.6 Define cache invalidation/versioning policy. (REQ-8)
  * [ ] 1.7 Define audit event names and fields. (REQ-9)
  * [ ] 1.8 Document that settings do not bypass glossary visibility rules. (REQ-10)

* [ ] 2. Add global setting storage

  * [ ] 2.1 Add environment/config setting if needed. (REQ-1)
  * [ ] 2.2 Add database-backed global setting if project uses DB settings. (REQ-1, REQ-5)
  * [ ] 2.3 Define default value by environment/rollout policy. (REQ-11)
  * [ ] 2.4 Ensure deployment config can act as hard kill switch. (REQ-1)
  * [ ] 2.5 Add tests for global default and kill switch behavior. (REQ-1, REQ-11, REQ-12)

* [ ] 3. Add per-novel setting storage

  * [ ] 3.1 Add `public_glossary_annotations_mode` or equivalent field. (REQ-2)
  * [ ] 3.2 Use nullable/tri-state value or enum for inherit/enabled/disabled. (REQ-2, REQ-11)
  * [ ] 3.3 Default existing novels to inherit. (REQ-11)
  * [ ] 3.4 Add migration. (REQ-11)
  * [ ] 3.5 Add model validation for allowed values. (REQ-2)
  * [ ] 3.6 Add tests for migration/default behavior. (REQ-11, REQ-12)

* [ ] 4. Implement effective setting service

  * [ ] 4.1 Add `PublicGlossaryAnnotationSettingsService`. (REQ-3)
  * [ ] 4.2 Add method to read global setting. (REQ-1, REQ-3)
  * [ ] 4.3 Add method to read per-novel mode. (REQ-2, REQ-3)
  * [ ] 4.4 Add method to compute effective enabled state. (REQ-3)
  * [ ] 4.5 Add safe reason output for admin context. (REQ-3)
  * [ ] 4.6 Add fail-closed behavior for public reader context. (REQ-3, REQ-10)
  * [ ] 4.7 Add tests for global enabled, global disabled, inherit, enabled, disabled, kill switch, missing setting, and lookup failure. (REQ-1, REQ-2, REQ-3, REQ-12)

* [ ] 5. Wire setting into public chapter API

  * [ ] 5.1 Locate annotation lookup call in public chapter API. (REQ-4)
  * [ ] 5.2 Call effective setting service before annotation lookup. (REQ-4)
  * [ ] 5.3 If disabled, return `glossary_annotations: []`. (REQ-4)
  * [ ] 5.4 If disabled, avoid calling annotation service. (REQ-4)
  * [ ] 5.5 If enabled, preserve existing annotation lookup behavior. (REQ-4)
  * [ ] 5.6 If setting lookup fails, return empty annotations. (REQ-4, REQ-10)
  * [ ] 5.7 Preserve existing unpublished/unavailable chapter behavior. (REQ-4)
  * [ ] 5.8 Add tests for enabled, disabled, lookup failure, unpublished chapter, service-called, and service-not-called paths. (REQ-4, REQ-10, REQ-12)

* [ ] 6. Add admin global settings API

  * [ ] 6.1 Add or extend `GET /admin/settings/public-reader`. (REQ-5)
  * [ ] 6.2 Add or extend `PATCH /admin/settings/public-reader`. (REQ-5)
  * [ ] 6.3 Protect routes with admin auth. (REQ-5)
  * [ ] 6.4 Return global setting. (REQ-5)
  * [ ] 6.5 Return deployment kill switch state. (REQ-5)
  * [ ] 6.6 Validate update payload. (REQ-5)
  * [ ] 6.7 Persist updates. (REQ-5)
  * [ ] 6.8 Trigger cache invalidation/version update. (REQ-5, REQ-8)
  * [ ] 6.9 Record audit event. (REQ-5, REQ-9)
  * [ ] 6.10 Add API tests for admin, non-admin, unauthenticated, valid update, invalid update, kill switch, cache invalidation, and audit. (REQ-5, REQ-8, REQ-9, REQ-12)

* [ ] 7. Add admin per-novel settings API

  * [ ] 7.1 Add or extend `GET /admin/novels/{novel_id}/public-reader-settings`. (REQ-6)
  * [ ] 7.2 Add or extend `PATCH /admin/novels/{novel_id}/public-reader-settings`. (REQ-6)
  * [ ] 7.3 Protect routes with admin auth. (REQ-6)
  * [ ] 7.4 Return per-novel mode. (REQ-6)
  * [ ] 7.5 Return effective enabled state and safe reason. (REQ-6)
  * [ ] 7.6 Validate mode payload. (REQ-6)
  * [ ] 7.7 Return not found for missing novel. (REQ-6)
  * [ ] 7.8 Persist updates. (REQ-6)
  * [ ] 7.9 Trigger affected novel cache invalidation/version update. (REQ-6, REQ-8)
  * [ ] 7.10 Record audit event. (REQ-6, REQ-9)
  * [ ] 7.11 Add API tests for admin, non-admin, unauthenticated, valid modes, invalid mode, missing novel, cache invalidation, and audit. (REQ-6, REQ-8, REQ-9, REQ-12)

* [ ] 8. Add cache invalidation/versioning

  * [ ] 8.1 Inspect public reader cache keys. (REQ-8)
  * [ ] 8.2 Decide invalidation vs setting-version cache key. (REQ-8)
  * [ ] 8.3 Invalidate all public reader annotation-aware cache on global setting change. (REQ-8)
  * [ ] 8.4 Invalidate affected novel public reader cache on per-novel setting change. (REQ-8)
  * [ ] 8.5 Ensure previously cached annotations are not served after disable. (REQ-8)
  * [ ] 8.6 Log safe warning or fail update if invalidation fails according to policy. (REQ-8)
  * [ ] 8.7 Add tests for cache invalidation/versioning and no stale annotation exposure. (REQ-8, REQ-12)

* [ ] 9. Add audit logging

  * [ ] 9.1 Add global setting update audit event. (REQ-9)
  * [ ] 9.2 Add per-novel setting update audit event. (REQ-9)
  * [ ] 9.3 Include admin user ID. (REQ-9)
  * [ ] 9.4 Include previous and new values. (REQ-9)
  * [ ] 9.5 Include novel ID for per-novel changes. (REQ-9)
  * [ ] 9.6 Avoid logging glossary content, chapter text, prompts, or secrets. (REQ-9, REQ-10)
  * [ ] 9.7 Add audit tests according to project conventions. (REQ-9, REQ-12)

* [ ] 10. Add admin global settings UI

  * [ ] 10.1 Locate admin public reader/settings page. (REQ-7)
  * [ ] 10.2 Add global glossary annotations toggle. (REQ-7)
  * [ ] 10.3 Show deployment kill switch state if applicable. (REQ-7)
  * [ ] 10.4 Load current setting from admin API. (REQ-7)
  * [ ] 10.5 Save setting through admin API. (REQ-7)
  * [ ] 10.6 Show loading state. (REQ-7)
  * [ ] 10.7 Show safe error state. (REQ-7)
  * [ ] 10.8 Show success or updated state. (REQ-7)
  * [ ] 10.9 Add frontend tests for load, toggle, save success, save failure, and kill switch display. (REQ-7, REQ-12)

* [ ] 11. Add admin per-novel settings UI

  * [ ] 11.1 Locate admin novel settings page. (REQ-7)
  * [ ] 11.2 Add per-novel glossary annotation mode select. (REQ-7)
  * [ ] 11.3 Add options: inherit, enabled, disabled. (REQ-7)
  * [ ] 11.4 Show effective state and reason. (REQ-7)
  * [ ] 11.5 Load current mode from admin API. (REQ-7)
  * [ ] 11.6 Save mode through admin API. (REQ-7)
  * [ ] 11.7 Show loading/error/success states. (REQ-7)
  * [ ] 11.8 Add frontend tests for inherit, enabled, disabled, effective state, save success, save failure, and non-admin blocked behavior. (REQ-7, REQ-12)

* [ ] 12. Add security and privacy hardening

  * [ ] 12.1 Verify enabled settings do not bypass term approval. (REQ-10)
  * [ ] 12.2 Verify enabled settings do not expose private/internal terms. (REQ-10)
  * [ ] 12.3 Verify enabled settings do not expose inactive aliases. (REQ-10)
  * [ ] 12.4 Verify disabled settings expose no annotation data. (REQ-10)
  * [ ] 12.5 Verify public reader setting lookup failure fails closed. (REQ-10)
  * [ ] 12.6 Verify admin APIs require admin role. (REQ-10)
  * [ ] 12.7 Verify audit/settings logs contain no glossary definitions or chapter text. (REQ-10)
  * [ ] 12.8 Add missing security tests. (REQ-10, REQ-12)

* [ ] 13. Backend test coverage pass

  * [ ] 13.1 Test global enabled. (REQ-1, REQ-12)
  * [ ] 13.2 Test global disabled. (REQ-1, REQ-12)
  * [ ] 13.3 Test per-novel inherit. (REQ-2, REQ-12)
  * [ ] 13.4 Test per-novel enabled. (REQ-2, REQ-12)
  * [ ] 13.5 Test per-novel disabled. (REQ-2, REQ-12)
  * [ ] 13.6 Test global kill switch overriding per-novel enabled. (REQ-1, REQ-2, REQ-12)
  * [ ] 13.7 Test setting lookup failure returns empty annotations. (REQ-3, REQ-4, REQ-12)
  * [ ] 13.8 Test annotation service called only when enabled. (REQ-4, REQ-12)
  * [ ] 13.9 Test admin global only when enabled. (REQ-4, REQ-12)
  * [ ] 13.9 Test admin global API authorization and validation. (REQ-5, REQ-12)
  * [ ] 13.10 Test admin per-novel API authorization and validation. (REQ-6, REQ-12)
  * [ ] 13.11 Test cache invalidation/versioning. (REQ-8, REQ-12)
  * [ ] 13.12 Test audit creation. (REQ-9, REQ-12)
  * [ ] 13.13 Test migration/default behavior. (REQ-11, REQ-12)

* [ ] 14. Frontend test coverage pass

  * [ ] 14.1 Test global settings control renders. (REQ-7, REQ-12)
  * [ ] 14.2 Test global setting load success. (REQ-7, REQ-12)
  * [ ] 14.3 Test global setting load failure. (REQ-7, REQ-12)
  * [ ] 14.4 Test global setting update success. (REQ-7, REQ-12)
  * [ ] 14.5 Test global setting update failure. (REQ-7, REQ-12)
  * [ ] 14.6 Test deployment kill switch display. (REQ-7, REQ-12)
  * [ ] 14.7 Test per-novel settings control renders. (REQ-7, REQ-12)
  * [ ] 14.8 Test inherit/enabled/disabled modes. (REQ-7, REQ-12)
  * [ ] 14.9 Test effective state display. (REQ-7, REQ-12)
  * [ ] 14.10 Test per-novel setting update success/failure. (REQ-7, REQ-12)
  * [ ] 14.11 Test non-admin blocked behavior where frontend route guards are tested. (REQ-7, REQ-12)

* [ ] 15. Documentation

  * [ ] 15.1 Document global public glossary annotations setting. (REQ-1)
  * [ ] 15.2 Document per-novel annotation mode. (REQ-2)
  * [ ] 15.3 Document effective setting logic. (REQ-3)
  * [ ] 15.4 Document public reader disabled behavior. (REQ-4)
  * [ ] 15.5 Document admin APIs. (REQ-5, REQ-6)
  * [ ] 15.6 Document admin UI controls. (REQ-7)
  * [ ] 15.7 Document cache invalidation/versioning. (REQ-8)
  * [ ] 15.8 Document audit behavior. (REQ-9)
  * [ ] 15.9 Document security rule: enabled setting does not bypass glossary visibility. (REQ-10)

* [ ] 16. Completion verification

  * [ ] 16.1 Disable global setting and request a public chapter with matching glossary terms. (REQ-13)
  * [ ] 16.2 Verify response contains `glossary_annotations: []`. (REQ-13)
  * [ ] 16.3 Enable global setting and set novel mode to inherit. (REQ-13)
  * [ ] 16.4 Verify response contains annotations for approved active terms. (REQ-13)
  * [ ] 16.5 Set novel mode to disabled. (REQ-13)
  * [ ] 16.6 Verify response returns empty annotations. (REQ-13)
  * [ ] 16.7 Set novel mode to enabled while global setting is disabled. (REQ-13)
  * [ ] 16.8 Verify global kill switch still returns empty annotations. (REQ-13)
  * [ ] 16.9 Simulate settings lookup failure and verify fail-closed empty annotations. (REQ-13)
  * [ ] 16.10 Verify public reader cache does not serve stale annotations after disable. (REQ-8, REQ-13)
  * [ ] 16.11 Verify admin setting change creates audit log. (REQ-9, REQ-13)
  * [ ] 16.12 Verify non-admin cannot change settings. (REQ-10, REQ-13)
  * [ ] 16.13 Mark `public-glossary-annotations-setting` complete only after global/per-novel controls safely affect public reader responses.
