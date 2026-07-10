# tasks.md

# Tasks: Export Manifest Admin UI

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing export manifest service and storage model.
  * [ ] 0.2 Inspect existing admin export API endpoints, if any.
  * [ ] 0.3 Inspect export freshness metadata fields from scheduled freshness work.
  * [ ] 0.4 Inspect export artifact download routes.
  * [ ] 0.5 Inspect existing export job/activity creation flow.
  * [ ] 0.6 Inspect admin frontend route/layout/navigation patterns.
  * [ ] 0.7 Inspect frontend API client conventions.
  * [ ] 0.8 Inspect existing admin authorization and scoped permission patterns.
  * [ ] 0.9 Inspect existing frontend/backend test patterns.
  * [ ] 0.10 Identify unsafe manifest fields that must be redacted.

* [ ] 1. Define admin UI contract

  * [ ] 1.1 Define admin route `/admin/exports`. (REQ-1)
  * [ ] 1.2 Decide detail drawer vs detail route. (REQ-7)
  * [ ] 1.3 Define table columns. (REQ-1)
  * [ ] 1.4 Define filters. (REQ-4)
  * [ ] 1.5 Define pagination behavior. (REQ-5)
  * [ ] 1.6 Define freshness badge labels. (REQ-6)
  * [ ] 1.7 Define stale reason labels. (REQ-6)
  * [ ] 1.8 Define re-export confirmation flow. (REQ-10)
  * [ ] 1.9 Define redaction rules for manifest details. (REQ-8)

* [ ] 2. Verify or add backend list endpoint

  * [ ] 2.1 Locate `GET /admin/exports` or equivalent. (REQ-3)
  * [ ] 2.2 Add endpoint if missing. (REQ-3)
  * [ ] 2.3 Protect endpoint with admin auth. (REQ-2)
  * [ ] 2.4 Return export ID, novel, format, export status, freshness status, stale reason, generated time, size, and manifest version. (REQ-3, REQ-6)
  * [ ] 2.5 Support pagination. (REQ-5)
  * [ ] 2.6 Support format filter. (REQ-4)
  * [ ] 2.7 Support freshness status filter. (REQ-4)
  * [ ] 2.8 Support export status filter where available. (REQ-4)
  * [ ] 2.9 Support novel/search filter where available. (REQ-4)
  * [ ] 2.10 Support date range filter. (REQ-4)
  * [ ] 2.11 Support safe sorting. (REQ-4)
  * [ ] 2.12 Add API tests for admin, non-admin, pagination, filters, sorting, and response shape. (REQ-2, REQ-3, REQ-4, REQ-5, REQ-16)

* [ ] 3. Verify or add backend detail endpoint

  * [ ] 3.1 Locate `GET /admin/exports/{export_id}` or equivalent. (REQ-7)
  * [ ] 3.2 Add endpoint if missing. (REQ-7)
  * [ ] 3.3 Protect endpoint with admin auth. (REQ-2)
  * [ ] 3.4 Return basic export identity. (REQ-7)
  * [ ] 3.5 Return safe artifact metadata. (REQ-7, REQ-8)
  * [ ] 3.6 Return freshness metadata and revision comparison where available. (REQ-7, REQ-13)
  * [ ] 3.7 Return safe manifest summary or redacted manifest JSON. (REQ-7, REQ-8)
  * [ ] 3.8 Handle old/incomplete manifests gracefully. (REQ-7, REQ-13)
  * [ ] 3.9 Add API tests for detail, old manifest, redaction, non-admin, and missing export. (REQ-2, REQ-7, REQ-8, REQ-16)

* [ ] 4. Add manifest redaction helper

  * [ ] 4.1 Identify unsafe fields in manifests. (REQ-8)
  * [ ] 4.2 Redact signed URLs. (REQ-8)
  * [ ] 4.3 Redact credentials and tokens. (REQ-8)
  * [ ] 4.4 Redact absolute private filesystem paths. (REQ-8)
  * [ ] 4.5 Redact raw prompts. (REQ-8)
  * [ ] 4.6 Redact full source chapter text. (REQ-8)
  * [ ] 4.7 Redact full translated chapter text. (REQ-8)
  * [ ] 4.8 Add tests for each redaction category. (REQ-8, REQ-16)

* [ ] 5. Verify or add re-export endpoint

  * [ ] 5.1 Locate existing export/re-export endpoint. (REQ-10, REQ-11)
  * [ ] 5.2 Add `POST /admin/exports/{export_id}/re-export` or project-standard equivalent if missing. (REQ-10, REQ-11)
  * [ ] 5.3 Protect endpoint with admin auth. (REQ-2, REQ-10)
  * [ ] 5.4 Validate export record exists. (REQ-11)
  * [ ] 5.5 Resolve current source/export inputs. (REQ-10, REQ-11)
  * [ ] 5.6 Enqueue export job or call existing export service. (REQ-11)
  * [ ] 5.7 Dedupe or reject if matching export is already running according to policy. (REQ-11)
  * [ ] 5.8 Return job/activity/export identifier where available. (REQ-10, REQ-11)
  * [ ] 5.9 Return structured safe errors. (REQ-10, REQ-11, REQ-14)
  * [ ] 5.10 Add tests for success, non-admin, missing export, duplicate running export, and safe failure. (REQ-10, REQ-11, REQ-16)

* [ ] 6. Verify or add summary endpoint

  * [ ] 6.1 Locate export freshness/status summary endpoint if available. (REQ-12, REQ-13)
  * [ ] 6.2 Add summary data to list endpoint or separate endpoint if missing. (REQ-12)
  * [ ] 6.3 Return total, fresh, stale, missing, unknown, and error counts where available. (REQ-12)
  * [ ] 6.4 Return last freshness check time where available. (REQ-12, REQ-13)
  * [ ] 6.5 Return no-run state if freshness checker has never run. (REQ-13)
  * [ ] 6.6 Protect endpoint with admin auth. (REQ-2)
  * [ ] 6.7 Add tests for summary counts, no-run state, and authorization. (REQ-12, REQ-13, REQ-16)

* [ ] 7. Add frontend API client methods

  * [ ] 7.1 Add `listExportManifests(params)`. (REQ-3)
  * [ ] 7.2 Add `getExportManifest(exportId)`. (REQ-7)
  * [ ] 7.3 Add `reExport(exportId, payload)`. (REQ-10)
  * [ ] 7.4 Add `getExportManifestSummary()` if summary endpoint exists. (REQ-12)
  * [ ] 7.5 Add typed response models if frontend uses types. (REQ-3, REQ-7)
  * [ ] 7.6 Add client tests or mocks according to project convention. (REQ-16)

* [ ] 8. Add admin exports page route

  * [ ] 8.1 Register `/admin/exports` route. (REQ-1)
  * [ ] 8.2 Add route guard requiring admin. (REQ-2)
  * [ ] 8.3 Add admin navigation link if project has admin nav. (REQ-1)
  * [ ] 8.4 Add page layout with header, summary, filters, and table sections. (REQ-1, REQ-12)
  * [ ] 8.5 Add tests for route rendering and access guard. (REQ-1, REQ-2, REQ-16)

* [ ] 9. Implement summary cards

  * [ ] 9.1 Render total exports. (REQ-12)
  * [ ] 9.2 Render fresh count. (REQ-12)
  * [ ] 9.3 Render stale count. (REQ-12)
  * [ ] 9.4 Render missing count. (REQ-12)
  * [ ] 9.5 Render unknown/error count. (REQ-12)
  * [ ] 9.6 Render last freshness check time if available. (REQ-12, REQ-13)
  * [ ] 9.7 Show partial/unavailable state if summary fails. (REQ-12, REQ-14)
  * [ ] 9.8 Avoid labeling current-page counts as global counts unless explicitly scoped. (REQ-12)
  * [ ] 9.9 Add tests for summary rendering, no-run state, and summary failure. (REQ-12, REQ-13, REQ-16)

* [ ] 10. Implement filters and sorting

  * [ ] 10.1 Add format filter. (REQ-4)
  * [ ] 10.2 Add freshness status filter. (REQ-4)
  * [ ] 10.3 Add export status filter where supported. (REQ-4)
  * [ ] 10.4 Add novel/search filter where supported. (REQ-4)
  * [ ] 10.5 Add date range filter where supported. (REQ-4)
  * [ ] 10.6 Add sort selector where supported. (REQ-4)
  * [ ] 10.7 Sync filters with API query params. (REQ-4)
  * [ ] 10.8 Add clear filters action. (REQ-4)
  * [ ] 10.9 Add tests for each supported filter and filtered empty state. (REQ-4, REQ-16)

* [ ] 11. Implement pagination

  * [ ] 11.1 Render pagination controls when total exceeds page size. (REQ-5)
  * [ ] 11.2 Load selected page. (REQ-5)
  * [ ] 11.3 Support page size control if project convention supports it. (REQ-5)
  * [ ] 11.4 Display current page and total where available. (REQ-5)
  * [ ] 11.5 Recover from empty invalid page after filter changes. (REQ-5)
  * [ ] 11.6 Add pagination tests. (REQ-5, REQ-16)

* [ ] 12. Implement export manifest table

  * [ ] 12.1 Render novel title or safe novel identifier. (REQ-1)
  * [ ] 12.2 Render format. (REQ-1)
  * [ ] 12.3 Render export status. (REQ-1)
  * [ ] 12.4 Render freshness badge. (REQ-6)
  * [ ] 12.5 Render stale reason label. (REQ-6)
  * [ ] 12.6 Render generated time. (REQ-1)
  * [ ] 12.7 Render last checked time. (REQ-6, REQ-13)
  * [ ] 12.8 Render artifact size if available. (REQ-1)
  * [ ] 12.9 Render actions column. (REQ-1, REQ-9, REQ-10)
  * [ ] 12.10 Add tests for table rows and old missing fields. (REQ-1, REQ-6, REQ-16)

* [ ] 13. Implement freshness badges

  * [ ] 13.1 Add Fresh badge. (REQ-6)
  * [ ] 13.2 Add Stale badge. (REQ-6)
  * [ ] 13.3 Add Missing badge. (REQ-6)
  * [ ] 13.4 Add Unknown badge. (REQ-6)
  * [ ] 13.5 Add Checking badge if supported. (REQ-6)
  * [ ] 13.6 Add Error badge. (REQ-6)
  * [ ] 13.7 Add human-readable stale reason mapping. (REQ-6)
  * [ ] 13.8 Add fallback label for unknown stale reason. (REQ-6)
  * [ ] 13.9 Add tests for all badge states and reason labels. (REQ-6, REQ-16)

* [ ] 14. Implement manifest detail view

  * [ ] 14.1 Add detail drawer/modal/page. (REQ-7)
  * [ ] 14.2 Load detail data when export is selected. (REQ-7)
  * [ ] 14.3 Render export identity. (REQ-7)
  * [ ] 14.4 Render artifact metadata. (REQ-7)
  * [ ] 14.5 Render freshness metadata. (REQ-7, REQ-13)
  * [ ] 14.6 Render revision comparison. (REQ-7)
  * [ ] 14.7 Render redacted manifest summary/JSON. (REQ-7, REQ-8)
  * [ ] 14.8 Render loading and error states. (REQ-7, REQ-14)
  * [ ] 14.9 Add tests for detail success, loading, error, old manifest, and redaction. (REQ-7, REQ-8, REQ-16)

* [ ] 15. Implement download/open action

  * [ ] 15.1 Show download/open action when artifact exists and route is available. (REQ-9)
  * [ ] 15.2 Hide or disable action when artifact is missing. (REQ-9)
  * [ ] 15.3 Show stale warning when artifact is stale and download is allowed. (REQ-9)
  * [ ] 15.4 Use existing authorized download route. (REQ-9)
  * [ ] 15.5 Avoid exposing raw signed URLs or storage keys in UI. (REQ-9)
  * [ ] 15.6 Show safe error when download fails. (REQ-9, REQ-14)
  * [ ] 15.7 Add tests for exists, missing, stale warning, and failure states. (REQ-9, REQ-16)

* [ ] 16. Implement re-export action

  * [ ] 16.1 Add Re-export button where supported. (REQ-10)
  * [ ] 16.2 Add confirmation dialog. (REQ-10)
  * [ ] 16.3 Call re-export API on confirm. (REQ-10)
  * [ ] 16.4 Show success state. (REQ-10)
  * [ ] 16.5 Show job/activity link if returned. (REQ-10)
  * [ ] 16.6 Refresh list/detail after accepted re-export where practical. (REQ-10)
  * [ ] 16.7 Show validation/server error states safely. (REQ-10, REQ-14)
  * [ ] 16.8 Disable repeated clicks while request is pending. (REQ-10)
  * [ ] 16.9 Add tests for confirmation, success, failure, and pending state. (REQ-10, REQ-16)

* [ ] 17. Add page state handling

  * [ ] 17.1 Add list loading state. (REQ-1, REQ-14)
  * [ ] 17.2 Add list empty state. (REQ-1)
  * [ ] 17.3 Add filtered empty state. (REQ-4)
  * [ ] 17.4 Add list error state. (REQ-14)
  * [ ] 17.5 Add summary partial failure state. (REQ-12, REQ-14)
  * [ ] 17.6 Add detail error state. (REQ-14)
  * [ ] 17.7 Ensure all errors are public/admin-safe and do not expose internals. (REQ-14)
  * [ ] 17.8 Add tests for page states. (REQ-14, REQ-16)

* [ ] 18. Add compatibility handling

  * [ ] 18.1 Handle manifests without freshness metadata. (REQ-13)
  * [ ] 18.2 Handle exports without size/checksum. (REQ-7)
  * [ ] 18.3 Handle exports without artifact-exists status. (REQ-7)
  * [ ] 18.4 Handle scheduled freshness never-run state. (REQ-13)
  * [ ] 18.5 Handle backend without summary endpoint by hiding/limiting summary cards. (REQ-12)
  * [ ] 18.6 Add tests for old/incomplete export records. (REQ-13, REQ-16)

* [ ] 19. Add observability and audit logs

  * [ ] 19.1 Log safe re-export requested event. (REQ-15)
  * [ ] 19.2 Log safe re-export failure event. (REQ-15)
  * [ ] 19.3 Optionally log list/detail view events if project audit policy requires them. (REQ-15)
  * [ ] 19.4 Redact raw manifest JSON, credentials, signed URLs, and private content from logs. (REQ-15)
  * [ ] 19.5 Add backend tests for re-export audit/log behavior where project conventions support it. (REQ-15, REQ-16)

* [ ] 20. Security review

  * [ ] 20.1 Verify admin page route is protected. (REQ-2)
  * [ ] 20.2 Verify list API is admin-only. (REQ-2)
  * [ ] 20.3 Verify detail API is admin-only. (REQ-2)
  * [ ] 20.4 Verify re-export API is admin-only. (REQ-2, REQ-10)
  * [ ] 20.5 Verify manifest redaction. (REQ-8)
  * [ ] 20.6 Verify download action uses authorized route. (REQ-9)
  * [ ] 20.7 Verify arbitrary storage keys cannot be read from UI/API. (REQ-8, REQ-9)
  * [ ] 20.8 Add missing security tests. (REQ-2, REQ-8, REQ-9, REQ-16)

* [ ] 21. Frontend test coverage pass

  * [ ] 21.1 Test admin page rendering. (REQ-1, REQ-16)
  * [ ] 21.2 Test non-admin blocked state. (REQ-2, REQ-16)
  * [ ] 21.3 Test loading/empty/error states. (REQ-1, REQ-14, REQ-16)
  * [ ] 21.4 Test filter behavior. (REQ-4, REQ-16)
  * [ ] 21.5 Test pagination behavior. (REQ-5, REQ-16)
  * [ ] 21.6 Test table rendering. (REQ-1, REQ-16)
  * [ ] 21.7 Test freshness badges and stale reason labels. (REQ-6, REQ-16)
  * [ ] 21.8 Test detail view rendering. (REQ-7, REQ-16)
  * [ ] 21.9 Test redacted manifest display. (REQ-8, REQ-16)
  * [ ] 21.10 Test download action states. (REQ-9, REQ-16)
  * [ ] 21.11 Test re-export confirmation/success/failure. (REQ-10, REQ-16)
  * [ ] 21.12 Test old/incomplete manifest compatibility. (REQ-13, REQ-16)

* [ ] 22. Backend test coverage pass

  * [ ] 22.1 Test list API authorization. (REQ-2, REQ-16)
  * [ ] 22.2 Test list API pagination. (REQ-5, REQ-16)
  * [ ] 22.3 Test list API filters. (REQ-4, REQ-16)
  * [ ] 22.4 Test detail API authorization. (REQ-2, REQ-16)
  * [ ] 22.5 Test detail API redaction. (REQ-8, REQ-16)
  * [ ] 22.6 Test detail API old manifest handling. (REQ-13, REQ-16)
  * [ ] 22.7 Test summary API if added. (REQ-12, REQ-16)
  * [ ] 22.8 Test re-export API success. (REQ-10, REQ-11, REQ-16)
  * [ ] 22.9 Test re-export API safe failures. (REQ-10, REQ-11, REQ-16)
  * [ ] 22.10 Test non-admin re-export blocked. (REQ-2, REQ-10, REQ-16)

* [ ] 23. Documentation

  * [ ] 23.1 Document admin exports page. (REQ-1)
  * [ ] 23.2 Document freshness badges and stale reasons. (REQ-6)
  * [ ] 23.3 Document manifest detail fields. (REQ-7)
  * [ ] 23.4 Document redacted fields. (REQ-8)
  * [ ] 23.5 Document re-export behavior. (REQ-10, REQ-11)
  * [ ] 23.6 Document compatibility with scheduled freshness. (REQ-13)
  * [ ] 23.7 Document operator workflow for stale/missing exports. (REQ-17)

* [ ] 24. Completion verification

  * [ ] 24.1 Log in as admin and open `/admin/exports`. (REQ-1, REQ-17)
  * [ ] 24.2 Verify export history is visible. (REQ-1, REQ-17)
  * [ ] 24.3 Verify stale export shows Stale badge and reason. (REQ-6, REQ-17)
  * [ ] 24.4 Verify missing export shows Missing badge. (REQ-6, REQ-17)
  * [ ] 24.5 Open manifest detail and verify safe metadata appears. (REQ-7, REQ-17)
  * [ ] 24.6 Verify unsafe manifest values are redacted. (REQ-8, REQ-17)
  * [ ] 24.7 Trigger re-export and verify job/activity starts or controlled error appears. (REQ-10, REQ-17)
  * [ ] 24.8 Verify non-admin cannot access page or APIs. (REQ-2, REQ-17)
  * [ ] 24.9 Verify old export without freshness metadata renders as unknown/incomplete safely. (REQ-13, REQ-17)
  * [ ] 24.10 Mark `export-manifest-admin-ui` complete only after stale/missing exports are visible and re-export is admin-only.
