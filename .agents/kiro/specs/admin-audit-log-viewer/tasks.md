# tasks.md

# Tasks: Admin Audit Log Viewer

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing audit log model/table.
  * [ ] 0.2 Inspect existing audit event writer/service.
  * [ ] 0.3 Inspect existing admin audit API, if any.
  * [ ] 0.4 Inspect admin routing/layout/navigation patterns.
  * [ ] 0.5 Inspect admin authorization and scoped permission patterns.
  * [ ] 0.6 Inspect existing audit events from user management, settings, exports, backups, maintenance, and notifications.
  * [ ] 0.7 Inspect current redaction helpers.
  * [ ] 0.8 Inspect frontend table/filter/pagination components.
  * [ ] 0.9 Inspect frontend error/empty state components.
  * [ ] 0.10 Inspect tests for admin pages and backend admin APIs.

* [ ] 1. Define audit viewer contract

  * [ ] 1.1 Define audit list item fields. (REQ-3)
  * [ ] 1.2 Define audit detail fields. (REQ-4)
  * [ ] 1.3 Define supported filters. (REQ-6)
  * [ ] 1.4 Define status values. (REQ-10)
  * [ ] 1.5 Define severity values. (REQ-10)
  * [ ] 1.6 Define known action label mapping. (REQ-11)
  * [ ] 1.7 Define redaction rules. (REQ-8)
  * [ ] 1.8 Define audit-of-audit policy. (REQ-15)
  * [ ] 1.9 Document optional export policy. (REQ-14)

* [ ] 2. Add or update audit list API

  * [ ] 2.1 Add or verify `GET /admin/audit`. (REQ-3)
  * [ ] 2.2 Protect endpoint with owner auth. (REQ-2)
  * [ ] 2.3 Return events in reverse chronological order by default. (REQ-1, REQ-3)
  * [ ] 2.4 Return created time, actor, action, target, status, severity, request ID, and summary. (REQ-3)
  * [ ] 2.5 Support pagination. (REQ-5)
  * [ ] 2.6 Support safe legacy event fallbacks. (REQ-3, REQ-11)
  * [ ] 2.7 Apply server-side redaction. (REQ-8)
  * [ ] 2.8 Add API tests for owner, non-owner, unauthenticated, default sort, response shape, and redaction. (REQ-2, REQ-3, REQ-8, REQ-18)

* [ ] 3. Add audit list filters

  * [ ] 3.1 Add date range filter. (REQ-6)
  * [ ] 3.2 Add action filter. (REQ-6)
  * [ ] 3.3 Add target type filter. (REQ-6)
  * [ ] 3.4 Add actor filter where supported. (REQ-6)
  * [ ] 3.5 Add status filter. (REQ-6)
  * [ ] 3.6 Add severity filter. (REQ-6)
  * [ ] 3.7 Add request ID/correlation ID filters where supported. (REQ-6, REQ-7)
  * [ ] 3.8 Validate invalid filters and date ranges. (REQ-6)
  * [ ] 3.9 Add API tests for each supported filter and invalid filters. (REQ-6, REQ-7, REQ-18)

* [ ] 4. Add or update audit detail API

  * [ ] 4.1 Add or verify `GET /admin/audit/{audit_id}`. (REQ-4)
  * [ ] 4.2 Protect endpoint with owner auth. (REQ-2)
  * [ ] 4.3 Return overview fields. (REQ-4)
  * [ ] 4.4 Return actor and target fields. (REQ-4)
  * [ ] 4.5 Return request context. (REQ-12)
  * [ ] 4.6 Return safe metadata. (REQ-4, REQ-8)
  * [ ] 4.7 Return safe before/after changes. (REQ-9)
  * [ ] 4.8 Handle not-found event. (REQ-4, REQ-17)
  * [ ] 4.9 Add API tests for detail, not found, legacy event, redaction, and authorization. (REQ-2, REQ-4, REQ-8, REQ-18)

* [ ] 5. Implement server-side redaction

  * [ ] 5.1 Redact passwords. (REQ-8)
  * [ ] 5.2 Redact tokens, API keys, and credentials. (REQ-8)
  * [ ] 5.3 Redact signed URLs. (REQ-8)
  * [ ] 5.4 Redact prompts. (REQ-8)
  * [ ] 5.5 Redact source and translated text. (REQ-8)
  * [ ] 5.6 Redact private glossary definitions. (REQ-8)
  * [ ] 5.7 Redact private paths and storage credentials. (REQ-8)
  * [ ] 5.8 Add recursive redaction for metadata and changes JSON. (REQ-8, REQ-9)
  * [ ] 5.9 Add tests for all redaction categories. (REQ-8, REQ-18)

* [ ] 6. Implement safe before/after diff formatting

  * [ ] 6.1 Normalize change data into field/before/after rows. (REQ-9)
  * [ ] 6.2 Redact unsafe before/after values. (REQ-9)
  * [ ] 6.3 Handle missing change data. (REQ-9)
  * [ ] 6.4 Handle malformed change data. (REQ-9)
  * [ ] 6.5 Add tests for safe diff, redacted diff, missing diff, and malformed diff. (REQ-9, REQ-18)

* [ ] 7. Add audit summary support

  * [ ] 7.1 Add summary counts to list response or separate endpoint if useful. (REQ-13)
  * [ ] 7.2 Count total events in selected range. (REQ-13)
  * [ ] 7.3 Count failed/denied events. (REQ-13)
  * [ ] 7.4 Count critical events. (REQ-13)
  * [ ] 7.5 Include most recent event timestamp where available. (REQ-13)
  * [ ] 7.6 Ensure page-only counts are labeled if global range counts are unavailable. (REQ-13)
  * [ ] 7.7 Add tests for summary success and partial failure. (REQ-13, REQ-18)

* [ ] 8. Add optional audit export

  * [ ] 8.1 Decide whether audit export is in scope. (REQ-14)
  * [ ] 8.2 If in scope, add admin-only export endpoint. (REQ-14)
  * [ ] 8.3 Apply same filters as viewer. (REQ-14)
  * [ ] 8.4 Apply server-side redaction. (REQ-14)
  * [ ] 8.5 Enforce max rows/date range. (REQ-14)
  * [ ] 8.6 Generate audit event for export request. (REQ-14, REQ-15)
  * [ ] 8.7 Add tests for export authorization, redaction, row cap, and audit event. (REQ-14, REQ-18)

* [ ] 9. Add audit-of-audit behavior

  * [ ] 9.1 Decide whether detail views should be audited. (REQ-15)
  * [ ] 9.2 Add `admin.audit.detail_viewed` if policy requires it. (REQ-15)
  * [ ] 9.3 Add `admin.audit.export_requested` if export is implemented. (REQ-15)
  * [ ] 9.4 Avoid logging raw metadata payloads. (REQ-15)
  * [ ] 9.5 Add sampling/noise policy for list views if implemented. (REQ-15)
  * [ ] 9.6 Add tests for audit-of-audit events where implemented. (REQ-15, REQ-18)

* [ ] 10. Add frontend API client

  * [ ] 10.1 Add `listAuditEvents(params)`. (REQ-3)
  * [ ] 10.2 Add `getAuditEvent(eventId)`. (REQ-4)
  * [ ] 10.3 Add `exportAuditEvents(params)` if export is implemented. (REQ-14)
  * [ ] 10.4 Add types/interfaces for audit list/detail responses. (REQ-3, REQ-4)
  * [ ] 10.5 Add client-side defensive redaction for known unsafe keys. (REQ-8)
  * [ ] 10.6 Add API client tests/mocks according to frontend conventions. (REQ-18)

* [ ] 11. Add admin audit page route

  * [ ] 11.1 Register `/admin/audit`. (REQ-1)
  * [ ] 11.2 Add admin route guard. (REQ-2)
  * [ ] 11.3 Add admin navigation link if appropriate. (REQ-1)
  * [ ] 11.4 Add page header and description. (REQ-1)
  * [ ] 11.5 Add loading/error/empty states. (REQ-1, REQ-17)
  * [ ] 11.6 Add route tests for admin and non-admin behavior. (REQ-1, REQ-2, REQ-18)

* [ ] 12. Implement audit filters UI

  * [ ] 12.1 Add date range filter. (REQ-6)
  * [ ] 12.2 Add action filter. (REQ-6)
  * [ ] 12.3 Add target type filter. (REQ-6)
  * [ ] 12.4 Add actor filter where supported. (REQ-6)
  * [ ] 12.5 Add status filter. (REQ-6)
  * [ ] 12.6 Add severity filter. (REQ-6)
  * [ ] 12.7 Add request/correlation ID lookup where supported. (REQ-6, REQ-7)
  * [ ] 12.8 Add clear filters action. (REQ-6)
  * [ ] 12.9 Sync filters with query params where frontend convention supports it. (REQ-6)
  * [ ] 12.10 Add tests for filter changes, invalid filters, and clear filters. (REQ-6, REQ-7, REQ-18)

* [ ] 13. Implement audit table

  * [ ] 13.1 Render time column. (REQ-1)
  * [ ] 13.2 Render actor column. (REQ-3)
  * [ ] 13.3 Render action column with known label fallback. (REQ-11)
  * [ ] 13.4 Render target column. (REQ-3)
  * [ ] 13.5 Render status column. (REQ-10)
  * [ ] 13.6 Render severity column. (REQ-10)
  * [ ] 13.7 Render request ID column where available. (REQ-12)
  * [ ] 13.8 Render summary column. (REQ-3)
  * [ ] 13.9 Render view details action. (REQ-4)
  * [ ] 13.10 Add tests for table rendering and unknown/legacy events. (REQ-3, REQ-10, REQ-11, REQ-18)

* [ ] 14. Implement pagination

  * [ ] 14.1 Render pagination controls. (REQ-5)
  * [ ] 14.2 Request selected page. (REQ-5)
  * [ ] 14.3 Enforce max page size. (REQ-5)
  * [ ] 14.4 Reset page on filter changes. (REQ-5)
  * [ ] 14.5 Recover from invalid empty page. (REQ-5)
  * [ ] 14.6 Add pagination tests. (REQ-5, REQ-18)

* [ ] 15. Implement audit detail view

  * [ ] 15.1 Add detail drawer/modal/page. (REQ-4)
  * [ ] 15.2 Render overview. (REQ-4)
  * [ ] 15.3 Render actor section. (REQ-4)
  * [ ] 15.4 Render target section. (REQ-4)
  * [ ] 15.5 Render request context section. (REQ-12)
  * [ ] 15.6 Render metadata section with redaction. (REQ-4, REQ-8)
  * [ ] 15.7 Render before/after changes. (REQ-9)
  * [ ] 15.8 Render safe error details if present. (REQ-17)
  * [ ] 15.9 Add loading/error/not-found states. (REQ-4, REQ-17)
  * [ ] 15.10 Add tests for detail rendering, redaction, diffs, and error states. (REQ-4, REQ-8, REQ-9, REQ-18)

* [ ] 16. Implement summary cards

  * [ ] 16.1 Render total events count where available. (REQ-13)
  * [ ] 16.2 Render failed/denied count where available. (REQ-13)
  * [ ] 16.3 Render critical event count where available. (REQ-13)
  * [ ] 16.4 Render most recent event timestamp where available. (REQ-13)
  * [ ] 16.5 Handle summary load failure without breaking list. (REQ-13)
  * [ ] 16.6 Add tests for summary cards and unavailable state. (REQ-13, REQ-18)

* [ ] 17. Implement optional export UI

  * [ ] 17.1 Hide export action if backend export is not implemented. (REQ-14)
  * [ ] 17.2 Add export action if implemented. (REQ-14)
  * [ ] 17.3 Show row/date limit explanation. (REQ-14)
  * [ ] 17.4 Use current filters for export. (REQ-14)
  * [ ] 17.5 Show export success/failure states. (REQ-14)
  * [ ] 17.6 Add tests for hidden export or implemented export flow. (REQ-14, REQ-18)

* [ ] 18. Accessibility pass

  * [ ] 18.1 Ensure audit table has headers. (REQ-16)
  * [ ] 18.2 Ensure filters have labels. (REQ-16)
  * [ ] 18.3 Ensure status/severity do not rely only on color. (REQ-16)
  * [ ] 18.4 Ensure detail drawer/modal focus management. (REQ-16)
  * [ ] 18.5 Ensure pagination is keyboard accessible. (REQ-16)
  * [ ] 18.6 Ensure empty/error states are readable text. (REQ-16)
  * [ ] 18.7 Add accessibility tests where project tooling supports them. (REQ-16, REQ-18)

* [ ] 19. Error handling pass

  * [ ] 19.1 Add safe list load error state. (REQ-17)
  * [ ] 19.2 Add safe detail load error state. (REQ-17)
  * [ ] 19.3 Add unauthorized state. (REQ-17)
  * [ ] 19.4 Add forbidden state. (REQ-17)
  * [ ] 19.5 Add invalid filter guidance. (REQ-17)
  * [ ] 19.6 Ensure backend unsafe errors are not displayed. (REQ-17)
  * [ ] 19.7 Add tests for API failure states. (REQ-17, REQ-18)

* [ ] 20. Security review

  * [ ] 20.1 Verify route guard. (REQ-2)
  * [ ] 20.2 Verify API authorization. (REQ-2)
  * [ ] 20.3 Verify server-side redaction. (REQ-8)
  * [ ] 20.4 Verify frontend does not display unsafe fields. (REQ-8)
  * [ ] 20.5 Verify export redaction if export is implemented. (REQ-14)
  * [ ] 20.6 Verify audit-of-audit behavior if required. (REQ-15)
  * [ ] 20.7 Add missing security tests. (REQ-2, REQ-8, REQ-14, REQ-15, REQ-18)

* [ ] 21. Test coverage pass

  * [ ] 21.1 Test admin-only page access. (REQ-2, REQ-18)
  * [ ] 21.2 Test list API and UI rendering. (REQ-3, REQ-18)
  * [ ] 21.3 Test detail API and UI rendering. (REQ-4, REQ-18)
  * [ ] 21.4 Test pagination. (REQ-5, REQ-18)
  * [ ] 21.5 Test filters and search. (REQ-6, REQ-7, REQ-18)
  * [ ] 21.6 Test redaction. (REQ-8, REQ-18)
  * [ ] 21.7 Test before/after diffs. (REQ-9, REQ-18)
  * [ ] 21.8 Test status/severity labels. (REQ-10, REQ-18)
  * [ ] 21.9 Test unknown action fallback. (REQ-11, REQ-18)
  * [ ] 21.10 Test request context display. (REQ-12, REQ-18)
  * [ ] 21.11 Test summary cards. (REQ-13, REQ-18)
  * [ ] 21.12 Test export if implemented. (REQ-14, REQ-18)
  * [ ] 21.13 Test audit-of-audit if implemented. (REQ-15, REQ-18)
  * [ ] 21.14 Test accessibility and error states. (REQ-16, REQ-17, REQ-18)

* [ ] 22. Documentation

  * [ ] 22.1 Document audit viewer route. (REQ-1)
  * [ ] 22.2 Document admin permissions. (REQ-2)
  * [ ] 22.3 Document audit list/detail API fields. (REQ-3, REQ-4)
  * [ ] 22.4 Document filters and pagination. (REQ-5, REQ-6)
  * [ ] 22.5 Document redaction rules. (REQ-8)
  * [ ] 22.6 Document status/severity values. (REQ-10)
  * [ ] 22.7 Document supported event actions and unknown fallback. (REQ-11)
  * [ ] 22.8 Document optional export behavior. (REQ-14)
  * [ ] 22.9 Document audit-of-audit policy. (REQ-15)

* [ ] 23. Completion verification

  * [ ] 23.1 Log in as admin and open `/admin/audit`. (REQ-19)
  * [ ] 23.2 Verify audit events are visible in newest-first order. (REQ-1, REQ-19)
  * [ ] 23.3 Filter by action, date, and status and verify matching events. (REQ-6, REQ-19)
  * [ ] 23.4 Open event detail and verify actor/action/target/request context/metadata/changes. (REQ-4, REQ-19)
  * [ ] 23.5 Verify unsafe values are redacted. (REQ-8, REQ-19)
  * [ ] 23.6 Try non-admin access and verify blocked page/API access. (REQ-2, REQ-19)
  * [ ] 23.7 Verify unknown/legacy action renders safely. (REQ-11, REQ-19)
  * [ ] 23.8 Simulate audit API failure and verify safe recoverable error. (REQ-17, REQ-19)
  * [ ] 23.9 Verify audit-of-audit records are created if policy requires them. (REQ-15, REQ-19)
  * [ ] 23.10 Mark `admin-audit-log-viewer` complete only after admins can investigate sensitive actions safely and non-admins cannot access audit data.
