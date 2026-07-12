# tasks.md

# Tasks: Terms DMCA Takedown Workflow

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing contact/support/legal pages and endpoints.
  * [ ] 0.2 Inspect public reader availability and publication checks.
  * [ ] 0.3 Inspect public cache/projection/snapshot behavior.
  * [ ] 0.4 Inspect sitemap and SEO metadata generation.
  * [ ] 0.5 Inspect export/download public access.
  * [ ] 0.6 Inspect admin routing, permissions, and UI patterns.
  * [ ] 0.7 Inspect audit logging service and event schema.
  * [ ] 0.8 Inspect notification/email system if implemented.
  * [ ] 0.9 Inspect maintenance/retention cleanup hooks.
  * [ ] 0.10 Inspect tests for public reader, admin APIs, legal pages, and cache invalidation.

* [ ] 1. Define takedown policy and states

  * [ ] 1.1 Define request statuses. (REQ-7)
  * [ ] 1.2 Define content enforcement states. (REQ-8)
  * [ ] 1.3 Define request types. (REQ-4)
  * [ ] 1.4 Define target types. (REQ-4, REQ-8)
  * [ ] 1.5 Define public status code policy: HTTP 451. (REQ-9)
  * [ ] 1.6 Define cache invalidation policy. (REQ-11)
  * [ ] 1.7 Define sitemap/SEO exclusion policy. (REQ-12)
  * [ ] 1.8 Define export/download blocking policy. (REQ-13)
  * [ ] 1.9 Define redaction/privacy policy. (REQ-16)

* [ ] 2. Add configuration

  * [ ] 2.1 Add `TAKEDOWN_INTAKE_ENABLED`. (REQ-1)
  * [ ] 2.2 Verify HTTP 451 response behavior. (REQ-9)
  * [ ] 2.3 Add `TAKEDOWN_REQUIRE_SIGNATURE`. (REQ-2)
  * [ ] 2.4 Add max URLs per request. (REQ-2)
  * [ ] 2.5 Add max description length. (REQ-2)
  * [ ] 2.6 Add request retention days. (REQ-18)
  * [ ] 2.7 Add notification toggles if needed. (REQ-14)
  * [ ] 2.8 Validate config at startup. (REQ-2, REQ-9, REQ-18)

* [ ] 3. Add takedown request model

  * [ ] 3.1 Create `takedown_requests` table/model. (REQ-4)
  * [ ] 3.2 Add request type field. (REQ-4)
  * [ ] 3.3 Add status field with default `submitted`. (REQ-4, REQ-7)
  * [ ] 3.4 Add submitter/claimant fields. (REQ-4)
  * [ ] 3.5 Add reported URLs fields. (REQ-4)
  * [ ] 3.6 Add original work/description fields. (REQ-4)
  * [ ] 3.7 Add statements/signature fields. (REQ-2, REQ-4)
  * [ ] 3.8 Add target type and `novel_id`/`chapter_id` fields. (REQ-4)
  * [ ] 3.9 Add admin notes/decision fields. (REQ-6, REQ-7)
  * [ ] 3.10 Add timestamps. (REQ-4)
  * [ ] 3.11 Add migration and model tests. (REQ-4, REQ-19)

* [ ] 4. Add content takedown state model

  * [ ] 4.1 Create `content_takedown_states` table/model or equivalent. (REQ-8)
  * [ ] 4.2 Add target type and `novel_id`/`chapter_id`. (REQ-8)
  * [ ] 4.3 Add public URL or URL hash where useful. (REQ-8)
  * [ ] 4.4 Add enforcement state. (REQ-8)
  * [ ] 4.5 Add reason code. (REQ-8)
  * [ ] 4.6 Link request ID. (REQ-8)
  * [ ] 4.7 Add applied/restored admin fields and timestamps. (REQ-8)
  * [ ] 4.8 Add migration and model tests. (REQ-8, REQ-19)

* [ ] 5. Implement public intake endpoint

  * [ ] 5.1 Add or extend `POST /support/takedown`. (REQ-1)
  * [ ] 5.2 Respect intake enabled config. (REQ-1)
  * [ ] 5.3 Validate contact email. (REQ-2)
  * [ ] 5.4 Validate reason/description. (REQ-2)
  * [ ] 5.5 Validate signature/statements where required. (REQ-2)
  * [ ] 5.6 Enforce max URLs and field lengths. (REQ-2)
  * [ ] 5.7 Apply rate limit and body size limits. (REQ-3)
  * [ ] 5.8 Store matched and unmatched URLs. (REQ-1)
  * [ ] 5.9 Return safe confirmation response. (REQ-1)
  * [ ] 5.10 Add endpoint tests for valid, invalid, disabled, rate-limited, oversized, and unmatched URL submissions. (REQ-1, REQ-2, REQ-3, REQ-19)

* [ ] 6. Implement URL-to-target matching

  * [ ] 6.1 Parse public novel URLs. (REQ-1, REQ-4)
  * [ ] 6.2 Parse public chapter URLs. (REQ-1, REQ-4)
  * [ ] 6.3 Parse export/public asset URLs if supported. (REQ-13)
  * [ ] 6.4 Reject private/preview tokens from being trusted as public target identity. (REQ-16)
  * [ ] 6.5 Store unmatched URLs safely. (REQ-1)
  * [ ] 6.6 Add tests for matched novel, matched chapter, export URL, malformed URL, external URL, and unmatched URL. (REQ-1, REQ-4, REQ-19)

* [ ] 7. Add takedown service

  * [ ] 7.1 Add `TakedownRequestService`. (REQ-4, REQ-7)
  * [ ] 7.2 Add create request method. (REQ-1)
  * [ ] 7.3 Add list requests method. (REQ-5)
  * [ ] 7.4 Add get request detail method. (REQ-6)
  * [ ] 7.5 Add update status method with transition validation. (REQ-7)
  * [ ] 7.6 Add admin notes method. (REQ-6)
  * [ ] 7.7 Add accept/reject methods. (REQ-7)
  * [ ] 7.8 Add close/reopen methods if needed. (REQ-7)
  * [ ] 7.9 Add tests for service methods and invalid transitions. (REQ-7, REQ-19)

* [ ] 8. Add enforcement service

  * [ ] 8.1 Add `ContentTakedownEnforcementService`. (REQ-8)
  * [ ] 8.2 Add apply temporary hide. (REQ-8)
  * [ ] 8.3 Add apply active takedown. (REQ-8)
  * [ ] 8.4 Add restore content. (REQ-8)
  * [ ] 8.5 Make enforcement actions idempotent where practical. (REQ-8)
  * [ ] 8.6 Add restore behavior that respects publication state. (REQ-9)
  * [ ] 8.7 Add tests for apply, duplicate apply, restore, and restore-unpublished behavior. (REQ-8, REQ-9, REQ-19)

* [ ] 9. Add admin takedown APIs

  * [ ] 9.1 Add `GET /admin/takedowns`. (REQ-5)
  * [ ] 9.2 Add `GET /admin/takedowns/{request_id}`. (REQ-6)
  * [ ] 9.3 Add status transition endpoint. (REQ-7)
  * [ ] 9.4 Add accept/reject endpoints. (REQ-7)
  * [ ] 9.5 Add apply takedown endpoint. (REQ-8)
  * [ ] 9.6 Add restore endpoint. (REQ-8)
  * [ ] 9.7 Add counter-notice record endpoint if in scope. (REQ-7)
  * [ ] 9.8 Protect all endpoints with owner auth. (REQ-17)
  * [ ] 9.9 Add API tests for authorization, list, detail, transitions, enforcement, restore, and invalid actions. (REQ-5, REQ-6, REQ-7, REQ-8, REQ-17, REQ-19)

* [ ] 10. Add admin takedown UI

  * [ ] 10.1 Add `/admin/takedowns` route. (REQ-5)
  * [ ] 10.2 Add admin navigation link if appropriate. (REQ-5)
  * [ ] 10.3 Add takedown list table. (REQ-5)
  * [ ] 10.4 Add filters by status/type/target/date. (REQ-5)
  * [ ] 10.5 Add request detail drawer/page. (REQ-6)
  * [ ] 10.6 Add admin notes section. (REQ-6)
  * [ ] 10.7 Add action buttons for allowed transitions. (REQ-7)
  * [ ] 10.8 Add apply/restore enforcement controls. (REQ-8)
  * [ ] 10.9 Add loading/empty/error states. (REQ-5, REQ-6)
  * [ ] 10.10 Add frontend tests for list, detail, actions, authorization, and states. (REQ-5, REQ-6, REQ-7, REQ-8, REQ-17, REQ-19)

* [ ] 11. Wire public reader availability checks

  * [ ] 11.1 Check takedown state before serving public novel content. (REQ-9, REQ-10)
  * [ ] 11.2 Check takedown state before serving public chapter content. (REQ-9, REQ-10)
  * [ ] 11.3 Return HTTP 451 response. (REQ-9)
  * [ ] 11.4 Ensure chapter text is not returned. (REQ-10)
  * [ ] 11.5 Ensure public fallback/snapshot cannot bypass takedown. (REQ-10)
  * [ ] 11.6 Ensure glossary annotations are not returned. (REQ-10)
  * [ ] 11.7 Add tests for public novel/chapter/API/fallback/annotation blocking. (REQ-9, REQ-10, REQ-19)

* [ ] 12. Wire search and discovery exclusion

  * [ ] 12.1 Exclude active takedown novels from public search. (REQ-10)
  * [ ] 12.2 Exclude active takedown chapters from public discovery. (REQ-10)
  * [ ] 12.3 Exclude active takedown content from public lists where appropriate. (REQ-10)
  * [ ] 12.4 Add tests for search/list exclusion. (REQ-10, REQ-19)

* [ ] 13. Wire cache invalidation

  * [ ] 13.1 Invalidate public reader cache on takedown apply. (REQ-11)
  * [ ] 13.2 Invalidate public projection/snapshot cache on takedown apply. (REQ-11)
  * [ ] 13.3 Invalidate public API cache on takedown apply. (REQ-11)
  * [ ] 13.4 Invalidate sitemap cache on takedown apply. (REQ-11)
  * [ ] 13.5 Invalidate SEO metadata cache on takedown apply. (REQ-11)
  * [ ] 13.6 Invalidate/rebuild caches on restore. (REQ-11)
  * [ ] 13.7 Decide fail action vs critical warning on cache invalidation failure. (REQ-11)
  * [ ] 13.8 Add tests proving cached content is not served after takedown. (REQ-11, REQ-19)

* [ ] 14. Wire sitemap and SEO behavior

  * [ ] 14.1 Exclude active takedown content from sitemap. (REQ-12)
  * [ ] 14.2 Add noindex/nofollow to tombstone page. (REQ-12)
  * [ ] 14.3 Ensure OG/Twitter metadata does not expose private content. (REQ-12)
  * [ ] 14.4 Restore sitemap eligibility only when restored and published. (REQ-12)
  * [ ] 14.5 Add tests for sitemap exclusion, noindex, metadata safety, and restore behavior. (REQ-12, REQ-19)

* [ ] 15. Wire export/download blocking

  * [ ] 15.1 Check takedown state before public export list/download. (REQ-13)
  * [ ] 15.2 Return safe unavailable response for blocked export. (REQ-13)
  * [ ] 15.3 Exclude blocked exports from public export lists. (REQ-13)
  * [ ] 15.4 Preserve admin export metadata access according to policy. (REQ-13)
  * [ ] 15.5 Restore export access only if content is restored, published, and policy allows. (REQ-13)
  * [ ] 15.6 Add tests for public download blocked, list exclusion, admin access, and restore. (REQ-13, REQ-19)

* [ ] 16. Add notifications

  * [ ] 16.1 Notify admins on takedown submission if notification system exists. (REQ-14)
  * [ ] 16.2 Send submitter confirmation if email exists and policy allows. (REQ-14)
  * [ ] 16.3 Notify content owner on accepted/applied takedown if owner model exists. (REQ-14)
  * [ ] 16.4 Notify submitter on rejection if policy allows. (REQ-14)
  * [ ] 16.5 Redact admin notes/private details from notifications. (REQ-14)
  * [ ] 16.6 Add tests for implemented notifications and failure isolation. (REQ-14, REQ-19)

* [ ] 17. Add audit logging

  * [ ] 17.1 Log request submitted. (REQ-15)
  * [ ] 17.2 Log status changes. (REQ-15)
  * [ ] 17.3 Log accepted/rejected decisions. (REQ-15)
  * [ ] 17.4 Log takedown applied. (REQ-15)
  * [ ] 17.5 Log content restored. (REQ-15)
  * [ ] 17.6 Log counter-notice recorded if implemented. (REQ-15)
  * [ ] 17.7 Redact sensitive legal/request details from audit event. (REQ-15, REQ-16)
  * [ ] 17.8 Add tests for audit events and redaction. (REQ-15, REQ-19)

* [ ] 18. Add redaction and privacy safeguards

  * [ ] 18.1 Ensure public responses never include submitter contact details. (REQ-16)
  * [ ] 18.2 Ensure public responses never include claimant private details. (REQ-16)
  * [ ] 18.3 Ensure public responses never include admin notes. (REQ-16)
  * [ ] 18.4 Ensure public responses do not expose internal target IDs unnecessarily. (REQ-16)
  * [ ] 18.5 Ensure admin APIs are admin-only. (REQ-16, REQ-17)
  * [ ] 18.6 Redact logs. (REQ-16)
  * [ ] 18.7 Add tests using sensitive request data. (REQ-16, REQ-19)

* [ ] 19. Add retention support

  * [ ] 19.1 Add retention config. (REQ-18)
  * [ ] 19.2 Integrate takedown request cleanup/archive with maintenance cron if in scope. (REQ-18)
  * [ ] 19.3 Ensure active enforcement states are not deleted. (REQ-18)
  * [ ] 19.4 Preserve audit history according to audit policy. (REQ-18)
  * [ ] 19.5 Add tests for retention eligibility if cleanup is implemented. (REQ-18, REQ-19)

* [ ] 20. Backend test coverage pass

  * [ ] 20.1 Test intake validation. (REQ-1, REQ-2, REQ-19)
  * [ ] 20.2 Test intake abuse protection. (REQ-3, REQ-19)
  * [ ] 20.3 Test request persistence. (REQ-4, REQ-19)
  * [ ] 20.4 Test admin authorization. (REQ-5, REQ-6, REQ-17, REQ-19)
  * [ ] 20.5 Test workflow transitions. (REQ-7, REQ-19)
  * [ ] 20.6 Test enforcement states. (REQ-8, REQ-19)
  * [ ] 20.7 Test tombstone behavior. (REQ-9, REQ-19)
  * [ ] 20.8 Test public API blocking. (REQ-10, REQ-19)
  * [ ] 20.9 Test cache invalidation. (REQ-11, REQ-19)
  * [ ] 20.10 Test sitemap/SEO exclusion. (REQ-12, REQ-19)
  * [ ] 20.11 Test export/download blocking. (REQ-13, REQ-19)
  * [ ] 20.12 Test notifications where implemented. (REQ-14, REQ-19)
  * [ ] 20.13 Test audit logging. (REQ-15, REQ-19)
  * [ ] 20.14 Test redaction/privacy. (REQ-16, REQ-19)
  * [ ] 20.15 Test retention if implemented. (REQ-18, REQ-19)

* [ ] 21. Frontend test coverage pass

  * [ ] 21.1 Test admin takedown list. (REQ-5, REQ-19)
  * [ ] 21.2 Test admin takedown detail. (REQ-6, REQ-19)
  * [ ] 21.3 Test action buttons and status transitions. (REQ-7, REQ-19)
  * [ ] 21.4 Test apply/restore controls. (REQ-8, REQ-19)
  * [ ] 21.5 Test loading/empty/error states. (REQ-5, REQ-6, REQ-19)
  * [ ] 21.6 Test unauthorized/non-admin blocked states. (REQ-17, REQ-19)
  * [ ] 21.7 Test public tombstone UI if frontend renders it. (REQ-9, REQ-19)
  * [ ] 21.8 Test no private legal data appears in public UI. (REQ-16, REQ-19)

* [ ] 22. Documentation

  * [ ] 22.1 Document public takedown intake fields. (REQ-1, REQ-2)
  * [ ] 22.2 Document request statuses. (REQ-7)
  * [ ] 22.3 Document enforcement states. (REQ-8)
  * [ ] 22.4 Document public tombstone/status-code policy. (REQ-9)
  * [ ] 22.5 Document public blocking surfaces. (REQ-10)
  * [ ] 22.6 Document cache/sitemap/SEO invalidation. (REQ-11, REQ-12)
  * [ ] 22.7 Document export/download behavior. (REQ-13)
  * [ ] 22.8 Document notification behavior. (REQ-14)
  * [ ] 22.9 Document audit/redaction/privacy rules. (REQ-15, REQ-16)
  * [ ] 22.10 Document admin operating procedure. (REQ-20)

* [ ] 23. Completion verification

  * [ ] 23.1 Submit a public takedown request. (REQ-20)
  * [ ] 23.2 Verify admin can see it in takedown queue. (REQ-5, REQ-20)
  * [ ] 23.3 Accept and apply takedown to a public chapter. (REQ-7, REQ-8, REQ-20)
  * [ ] 23.4 Request public chapter and verify text is not served. (REQ-10, REQ-20)
  * [ ] 23.5 Request public route and verify tombstone/unavailable behavior. (REQ-9, REQ-20)
  * [ ] 23.6 Request sitemap and verify taken-down URL is absent. (REQ-12, REQ-20)
  * [ ] 23.7 Inspect SEO metadata and verify noindex/unavailable behavior. (REQ-12, REQ-20)
  * [ ] 23.8 Verify previously cached public response no longer serves content. (REQ-11, REQ-20)
  * [ ] 23.9 Request public export/download and verify it is disabled. (REQ-13, REQ-20)
  * [ ] 23.10 Restore content and verify public access resumes only if still published. (REQ-8, REQ-9, REQ-20)
  * [ ] 23.11 Inspect audit logs and verify safe takedown events. (REQ-15, REQ-20)
  * [ ] 23.12 Inspect public responses/logs and verify private legal details are not exposed. (REQ-16, REQ-20)
  * [ ] 23.13 Mark `terms-dmca-takedown-workflow` complete only after public takedown enforcement, cache invalidation, sitemap exclusion, and redaction are verified.
