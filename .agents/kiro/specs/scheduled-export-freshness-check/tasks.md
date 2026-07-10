# tasks.md

# Tasks: Scheduled Export Freshness Check

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect export service and export artifact generation flow.
  * [ ] 0.2 Inspect export registry and supported formats.
  * [ ] 0.3 Inspect export manifest structure and storage location.
  * [ ] 0.4 Inspect export artifact database model, if any.
  * [ ] 0.5 Inspect download API behavior for export artifacts.
  * [ ] 0.6 Inspect existing freshness calculation done during API calls.
  * [ ] 0.7 Inspect translation/chapter/novel/glossary revision fields.
  * [ ] 0.8 Inspect export template/profile settings.
  * [ ] 0.9 Inspect scheduler/cron infrastructure.
  * [ ] 0.10 Inspect admin auth/router conventions.
  * [ ] 0.11 Inspect existing export tests.

* [ ] 1. Define freshness status contract

  * [ ] 1.1 Define freshness statuses: fresh, stale, missing, unknown, checking, error. (REQ-2)
  * [ ] 1.2 Define stale reason codes. (REQ-2, REQ-3)
  * [ ] 1.3 Define error categories. (REQ-2, REQ-12)
  * [ ] 1.4 Define freshness metadata response shape. (REQ-8)
  * [ ] 1.5 Define download behavior policy for stale artifacts. (REQ-9)
  * [ ] 1.6 Define old-artifact/no-metadata behavior. (REQ-1, REQ-8)
  * [ ] 1.7 Document fields that must never be stored or exposed. (REQ-12)

* [ ] 2. Add configuration

  * [ ] 2.1 Add export freshness check enabled flag. (REQ-5)
  * [ ] 2.2 Add export freshness check cron schedule. (REQ-5)
  * [ ] 2.3 Add batch size config. (REQ-5)
  * [ ] 2.4 Add max artifacts per run config. (REQ-5)
  * [ ] 2.5 Add lock TTL config. (REQ-6)
  * [ ] 2.6 Add storage check timeout config if missing. (REQ-4)
  * [ ] 2.7 Add dry-run/manual trigger config if endpoint is implemented. (REQ-11)
  * [ ] 2.8 Validate config at startup or scheduler registration. (REQ-5, REQ-15)

* [ ] 3. Extend export artifact/manifest metadata

  * [ ] 3.1 Add freshness status field to artifact DB or manifest. (REQ-1, REQ-2)
  * [ ] 3.2 Add freshness checked timestamp. (REQ-2)
  * [ ] 3.3 Add stale reason field. (REQ-2)
  * [ ] 3.4 Add safe error category/message fields. (REQ-2, REQ-12)
  * [ ] 3.5 Add source/content fingerprint or revision fields. (REQ-1, REQ-3)
  * [ ] 3.6 Add translation revision field where available. (REQ-1, REQ-3)
  * [ ] 3.7 Add glossary revision field where applicable. (REQ-1, REQ-3)
  * [ ] 3.8 Add export template version field. (REQ-1, REQ-3)
  * [ ] 3.9 Add export profile/settings hash field. (REQ-1, REQ-3)
  * [ ] 3.10 Add chapter set/order hash field. (REQ-1, REQ-3)
  * [ ] 3.11 Add publication revision field if relevant. (REQ-1, REQ-3)
  * [ ] 3.12 Add migration if fields are stored in DB. (REQ-1)
  * [ ] 3.13 Add manifest backward-compatibility handling for old exports. (REQ-1, REQ-8)

* [ ] 4. Capture freshness metadata during export generation

  * [ ] 4.1 Compute export-time source/content fingerprint. (REQ-1)
  * [ ] 4.2 Capture current translation revision. (REQ-1)
  * [ ] 4.3 Capture current glossary revision if glossary affects export output. (REQ-1)
  * [ ] 4.4 Capture export template version. (REQ-1)
  * [ ] 4.5 Capture export profile/settings hash. (REQ-1)
  * [ ] 4.6 Capture chapter set/order hash. (REQ-1)
  * [ ] 4.7 Capture publication revision if relevant. (REQ-1)
  * [ ] 4.8 Store initial freshness status as fresh after artifact creation succeeds. (REQ-1, REQ-2)
  * [ ] 4.9 Do not store full source or translated text. (REQ-12)
  * [ ] 4.10 Add tests for metadata captured on new exports. (REQ-1, REQ-12, REQ-14)

* [ ] 5. Implement current export input fingerprint service

  * [ ] 5.1 Compute current novel metadata fingerprint. (REQ-3)
  * [ ] 5.2 Compute current chapter set/order hash. (REQ-3)
  * [ ] 5.3 Compute current translated content fingerprint using hashes/revisions. (REQ-3)
  * [ ] 5.4 Load current glossary revision where applicable. (REQ-3)
  * [ ] 5.5 Load current export template version. (REQ-3)
  * [ ] 5.6 Compute current export profile/settings hash. (REQ-3)
  * [ ] 5.7 Load current publication revision where applicable. (REQ-3)
  * [ ] 5.8 Return unknown/error when required current values cannot be computed. (REQ-3)
  * [ ] 5.9 Add tests for fingerprint changes and dependency failure behavior. (REQ-3, REQ-14)

* [ ] 6. Implement freshness calculation service

  * [ ] 6.1 Compare export metadata with current input fingerprint. (REQ-3)
  * [ ] 6.2 Mark fresh when all required values match and artifact exists. (REQ-3)
  * [ ] 6.3 Mark stale for translation changes. (REQ-3)
  * [ ] 6.4 Mark stale for source/chapter content changes. (REQ-3)
  * [ ] 6.5 Mark stale for chapter order changes. (REQ-3)
  * [ ] 6.6 Mark stale for novel metadata changes. (REQ-3)
  * [ ] 6.7 Mark stale for glossary revision changes when applicable. (REQ-3)
  * [ ] 6.8 Mark stale for template/profile changes. (REQ-3)
  * [ ] 6.9 Mark stale for publication state changes when applicable. (REQ-3)
  * [ ] 6.10 Mark unknown/error when freshness cannot be determined safely. (REQ-2, REQ-3)
  * [ ] 6.11 Add unit tests for every stale reason. (REQ-3, REQ-14)

* [ ] 7. Implement missing artifact detection

  * [ ] 7.1 Add storage exists/head check for local artifacts. (REQ-4)
  * [ ] 7.2 Add storage exists/head check for object storage artifacts. (REQ-4)
  * [ ] 7.3 Mark artifact missing on confirmed not found. (REQ-4)
  * [ ] 7.4 Mark artifact unknown/error on storage timeout or temporary failure. (REQ-4)
  * [ ] 7.5 Do not expose signed URLs or raw storage paths in errors. (REQ-4, REQ-12)
  * [ ] 7.6 Add tests for exists, not found, timeout, and storage error. (REQ-4, REQ-14)

* [ ] 8. Implement freshness persistence repository

  * [ ] 8.1 Add method to list candidate artifacts in batches. (REQ-5)
  * [ ] 8.2 Add method to skip currently generating artifacts. (REQ-5)
  * [ ] 8.3 Add method to update artifact freshness status. (REQ-2, REQ-5)
  * [ ] 8.4 Add method to update artifact checked timestamp. (REQ-2)
  * [ ] 8.5 Add method to update stale reason and safe error fields. (REQ-2, REQ-12)
  * [ ] 8.6 Add method to summarize freshness counts. (REQ-7, REQ-13)
  * [ ] 8.7 Add tests for batch listing, updates, skipping active artifacts, and summaries. (REQ-5, REQ-7, REQ-14)

* [ ] 9. Add freshness run metadata

  * [ ] 9.1 Create `export_freshness_runs` model/table or integrate with existing maintenance run metadata. (REQ-7)
  * [ ] 9.2 Record status, started time, finished time, duration, and trigger. (REQ-7)
  * [ ] 9.3 Record dry-run flag. (REQ-7, REQ-11)
  * [ ] 9.4 Record scanned, fresh, stale, missing, unknown, and error counts. (REQ-7)
  * [ ] 9.5 Record safe error summary. (REQ-7, REQ-12)
  * [ ] 9.6 Add migration if using a new table. (REQ-7)
  * [ ] 9.7 Add tests for run metadata success, partial success, failure, and skipped lock. (REQ-7, REQ-14)

* [ ] 10. Implement freshness check lock

  * [ ] 10.1 Choose lock strategy consistent with existing scheduler/maintenance locks. (REQ-6)
  * [ ] 10.2 Acquire lock before scan. (REQ-6)
  * [ ] 10.3 Skip run if lock is held. (REQ-6)
  * [ ] 10.4 Release lock after run. (REQ-6)
  * [ ] 10.5 Add lock TTL/stale recovery. (REQ-6)
  * [ ] 10.6 Ensure scan does not run if lock acquisition fails unexpectedly. (REQ-6)
  * [ ] 10.7 Add tests for lock acquired, skipped, and stale lock recovery. (REQ-6, REQ-14)

* [ ] 11. Implement scheduled freshness checker

  * [ ] 11.1 Add `ExportFreshnessScheduler` or scheduler registration. (REQ-5)
  * [ ] 11.2 Register job with configured cron. (REQ-5)
  * [ ] 11.3 Respect enabled/disabled config. (REQ-5)
  * [ ] 11.4 Process artifacts in batches. (REQ-5)
  * [ ] 11.5 Respect max artifacts per run. (REQ-5)
  * [ ] 11.6 Continue after per-artifact failures where safe. (REQ-5)
  * [ ] 11.7 Persist status after each artifact or batch. (REQ-5)
  * [ ] 11.8 Record run summary. (REQ-7)
  * [ ] 11.9 Add tests for scheduling, batch processing, max limit, per-artifact failure, and persisted results. (REQ-5, REQ-7, REQ-14)

* [ ] 12. Add optional event-driven stale hints

  * [ ] 12.1 Identify translation completed/update events. (REQ-10)
  * [ ] 12.2 Identify glossary revision update events. (REQ-10)
  * [ ] 12.3 Identify export template/profile update events. (REQ-10)
  * [ ] 12.4 Identify novel metadata/chapter order update events. (REQ-10)
  * [ ] 12.5 Mark affected exports likely stale when event occurs if implemented. (REQ-10)
  * [ ] 12.6 Ensure scheduled checker remains source of verification. (REQ-10)
  * [ ] 12.7 Add tests for event-driven stale marking if implemented. (REQ-10, REQ-14)

* [ ] 13. Update export API responses

  * [ ] 13.1 Add freshness object to export artifact response models. (REQ-8)
  * [ ] 13.2 Include freshness status. (REQ-8)
  * [ ] 13.3 Include checked timestamp. (REQ-8)
  * [ ] 13.4 Include safe stale reason. (REQ-8)
  * [ ] 13.5 Include missing/unknown/error states safely. (REQ-8)
  * [ ] 13.6 Handle old artifacts without metadata. (REQ-8)
  * [ ] 13.7 Preserve existing response fields. (REQ-8)
  * [ ] 13.8 Add API tests for fresh, stale, missing, unknown, and old artifacts. (REQ-8, REQ-14)

* [ ] 14. Update download behavior

  * [ ] 14.1 Apply product policy for stale downloads. (REQ-9)
  * [ ] 14.2 Return controlled error for missing artifacts. (REQ-9)
  * [ ] 14.3 Return controlled error for storage failures. (REQ-9)
  * [ ] 14.4 Avoid claiming unknown freshness as fresh. (REQ-9)
  * [ ] 14.5 Redact storage paths, signed URLs, credentials, and stack traces from download errors. (REQ-9, REQ-12)
  * [ ] 14.6 Add download tests for fresh, stale, missing, unknown, and storage error cases. (REQ-9, REQ-14)

* [ ] 15. Add optional admin freshness status endpoint

  * [ ] 15.1 Add `GET /admin/exports/freshness/status` if admin ops routes exist. (REQ-13)
  * [ ] 15.2 Protect endpoint with admin auth. (REQ-13)
  * [ ] 15.3 Return enabled state and schedule. (REQ-13)
  * [ ] 15.4 Return last run status and timestamp. (REQ-13)
  * [ ] 15.5 Return summary counts. (REQ-13)
  * [ ] 15.6 Return no-run state safely. (REQ-13)
  * [ ] 15.7 Redact errors. (REQ-13, REQ-12)
  * [ ] 15.8 Add API tests for admin, non-admin, unauthenticated, success, failure, and no-run states. (REQ-13, REQ-14)

* [ ] 16. Add optional manual/dry-run endpoint

  * [ ] 16.1 Add `POST /admin/exports/freshness/check` if manual trigger is in scope. (REQ-11)
  * [ ] 16.2 Protect endpoint with admin auth. (REQ-11)
  * [ ] 16.3 Support dry-run option. (REQ-11)
  * [ ] 16.4 Support optional format filter. (REQ-11)
  * [ ] 16.5 Support optional novel/export filter where safe. (REQ-11)
  * [ ] 16.6 Use same freshness lock. (REQ-11)
  * [ ] 16.7 Ensure dry-run does not mutate artifact statuses. (REQ-11)
  * [ ] 16.8 Add tests for admin auth, dry-run no mutation, filters, invalid filters, and lock conflict. (REQ-11, REQ-14)

* [ ] 17. Add security and privacy hardening

  * [ ] 17.1 Ensure freshness metadata stores only hashes/revisions, not full text. (REQ-12)
  * [ ] 17.2 Ensure raw prompts are not stored. (REQ-12)
  * [ ] 17.3 Ensure provider responses are not stored. (REQ-12)
  * [ ] 17.4 Ensure API keys/tokens/signed URLs are not stored. (REQ-12)
  * [ ] 17.5 Redact freshness errors in APIs. (REQ-12)
  * [ ] 17.6 Redact artifact paths and signed URLs in logs. (REQ-12)
  * [ ] 17.7 Ensure admin endpoints require admin authorization. (REQ-12, REQ-13)
  * [ ] 17.8 Add tests for metadata safety and redaction. (REQ-12, REQ-14)

* [ ] 18. Add observability logs

  * [ ] 18.1 Log freshness run started. (REQ-7)
  * [ ] 18.2 Log freshness run finished. (REQ-7)
  * [ ] 18.3 Log artifact checked. (REQ-7)
  * [ ] 18.4 Log artifact stale. (REQ-2, REQ-3)
  * [ ] 18.5 Log artifact missing. (REQ-4)
  * [ ] 18.6 Log artifact error. (REQ-2)
  * [ ] 18.7 Log skipped lock. (REQ-6)
  * [ ] 18.8 Use safe fields only. (REQ-12)
  * [ ] 18.9 Add log tests only where project conventions support them. (REQ-14)

* [ ] 19. Backend test coverage pass

  * [ ] 19.1 Add freshness metadata capture tests. (REQ-1, REQ-14)
  * [ ] 19.2 Add freshness status model tests. (REQ-2, REQ-14)
  * [ ] 19.3 Add stale reason tests for translation/content/order/metadata/glossary/template/profile/publication changes. (REQ-3, REQ-14)
  * [ ] 19.4 Add missing artifact tests. (REQ-4, REQ-14)
  * [ ] 19.5 Add scheduled checker tests. (REQ-5, REQ-14)
  * [ ] 19.6 Add locking tests. (REQ-6, REQ-14)
  * [ ] 19.7 Add run metadata tests. (REQ-7, REQ-14)
  * [ ] 19.8 Add export API freshness tests. (REQ-8, REQ-14)
  * [ ] 19.9 Add download behavior tests. (REQ-9, REQ-14)
  * [ ] 19.10 Add event-driven stale hint tests if implemented. (REQ-10, REQ-14)
  * [ ] 19.11 Add manual/dry-run endpoint tests if implemented. (REQ-11, REQ-14)
  * [ ] 19.12 Add security/redaction tests. (REQ-12, REQ-14)
  * [ ] 19.13 Add admin status tests if implemented. (REQ-13, REQ-14)

* [ ] 20. Documentation

  * [ ] 20.1 Document freshness statuses and stale reasons. (REQ-2)
  * [ ] 20.2 Document freshness metadata fields. (REQ-1)
  * [ ] 20.3 Document scheduled checker configuration. (REQ-5)
  * [ ] 20.4 Document missing artifact behavior. (REQ-4)
  * [ ] 20.5 Document API freshness fields. (REQ-8)
  * [ ] 20.6 Document stale download policy. (REQ-9)
  * [ ] 20.7 Document optional event-driven stale hints. (REQ-10)
  * [ ] 20.8 Document admin status/manual endpoints if implemented. (REQ-11, REQ-13)
  * [ ] 20.9 Document security rule: hashes/revisions only, no full content. (REQ-12)

* [ ] 21. Completion verification

  * [ ] 21.1 Generate an export and verify freshness metadata is stored. (REQ-1, REQ-15)
  * [ ] 21.2 Run scheduled checker with no source changes and verify export remains fresh. (REQ-3, REQ-15)
  * [ ] 21.3 Change translation content and run scheduled checker. (REQ-3, REQ-15)
  * [ ] 21.4 Verify changed translation marks export stale before export API is called. (REQ-5, REQ-15)
  * [ ] 21.5 Delete or hide artifact file and run scheduled checker. (REQ-4, REQ-15)
  * [ ] 21.6 Verify missing artifact is marked missing before download is requested. (REQ-4, REQ-15)
  * [ ] 21.7 Change export template/profile and verify stale status. (REQ-3, REQ-15)
  * [ ] 21.8 Simulate dependency failure and verify artifact is not incorrectly marked fresh. (REQ-3, REQ-15)
  * [ ] 21.9 Call export API and verify persisted freshness status is returned. (REQ-8, REQ-15)
  * [ ] 21.10 Inspect freshness metadata and verify no full text, prompts, signed URLs, or secrets are stored. (REQ-12, REQ-15)
  * [ ] 21.11 Mark `scheduled-export-freshness-check` complete only after stale/missing exports are detected by the background job before API access.
