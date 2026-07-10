# tasks.md

# Tasks: Notification System

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect existing user model and ownership fields.
  * [ ] 0.2 Inspect activity model/status transitions.
  * [ ] 0.3 Inspect translation worker/orchestrator completion, failure, and review-required paths.
  * [ ] 0.4 Inspect existing email sender or notification infrastructure, if any.
  * [ ] 0.5 Inspect existing frontend auth layout/nav patterns.
  * [ ] 0.6 Inspect existing settings/preferences patterns.
  * [ ] 0.7 Inspect existing admin/user API authorization conventions.
  * [ ] 0.8 Inspect database migration/model conventions.
  * [ ] 0.9 Inspect existing tests for activity, users, frontend layout, and settings.

* [ ] 1. Define notification event contract

  * [ ] 1.1 Define required event types: `translation.completed`, `translation.failed`, `translation.requires_review`. (REQ-2, REQ-3, REQ-4)
  * [ ] 1.2 Define optional event types for future crawl/export/system notifications. (REQ-1)
  * [ ] 1.3 Define severity values: info, success, warning, error. (REQ-1)
  * [ ] 1.4 Define notification statuses: unread, read, archived, dismissed. (REQ-1, REQ-9)
  * [ ] 1.5 Define notification source fields: source type and source ID. (REQ-1)
  * [ ] 1.6 Define dedupe key format. (REQ-12)
  * [ ] 1.7 Define safe action URL rules. (REQ-14)
  * [ ] 1.8 Define content redaction rules. (REQ-14)

* [ ] 2. Add notification configuration

  * [ ] 2.1 Add notification system enabled flag if needed. (REQ-1)
  * [ ] 2.2 Add email notification enabled flag if email is in scope. (REQ-10)
  * [ ] 2.3 Add default preference config if needed. (REQ-6)
  * [ ] 2.4 Add notification retention days config. (REQ-15)
  * [ ] 2.5 Add archived/dismissed retention config. (REQ-15)
  * [ ] 2.6 Add delivery retention config if external delivery is implemented. (REQ-15)
  * [ ] 2.7 Validate notification config. (REQ-18)

* [ ] 3. Add notification database model

  * [ ] 3.1 Create `notifications` table/model. (REQ-1)
  * [ ] 3.2 Add user ID field. (REQ-1, REQ-14)
  * [ ] 3.3 Add event type, title, body, severity, and status fields. (REQ-1)
  * [ ] 3.4 Add read timestamp. (REQ-8, REQ-9)
  * [ ] 3.5 Add action URL. (REQ-1)
  * [ ] 3.6 Add source type and source ID. (REQ-1)
  * [ ] 3.7 Add dedupe key. (REQ-12)
  * [ ] 3.8 Add safe metadata JSON. (REQ-1, REQ-14)
  * [ ] 3.9 Add created, updated, and optional expiry timestamps. (REQ-1, REQ-15)
  * [ ] 3.10 Add unique constraint or index for user ID + dedupe key where appropriate. (REQ-12)
  * [ ] 3.11 Add indexes for user ID, status, created time, event type, and source. (REQ-7, REQ-8)
  * [ ] 3.12 Add migration tests or migration verification. (REQ-17)

* [ ] 4. Add notification preference model

  * [ ] 4.1 Choose preference storage table or existing user settings JSON. (REQ-6)
  * [ ] 4.2 Add user ID, channel, event type, and enabled fields. (REQ-6)
  * [ ] 4.3 Add unique key for user ID + channel + event type. (REQ-6)
  * [ ] 4.4 Add default preference resolver. (REQ-6)
  * [ ] 4.5 Add validation for supported event types and channels. (REQ-6)
  * [ ] 4.6 Add tests for defaults, updates, invalid event type, invalid channel, and user isolation. (REQ-6, REQ-17)

* [ ] 5. Add notification delivery model if email/external delivery is implemented

  * [ ] 5.1 Create `notification_deliveries` table/model. (REQ-10, REQ-11)
  * [ ] 5.2 Add notification ID, user ID, channel, status, and attempt count. (REQ-11)
  * [ ] 5.3 Add last attempt, delivered, and failed timestamps. (REQ-11)
  * [ ] 5.4 Add safe error category/message fields. (REQ-11)
  * [ ] 5.5 Add provider message ID if available and safe. (REQ-11)
  * [ ] 5.6 Add indexes for notification ID, user ID, channel, status, and created time. (REQ-11)
  * [ ] 5.7 Add tests for delivery record lifecycle. (REQ-10, REQ-11, REQ-17)

* [ ] 6. Implement notification repository

  * [ ] 6.1 Add create notification method. (REQ-1)
  * [ ] 6.2 Add idempotent create-by-dedupe-key method. (REQ-12)
  * [ ] 6.3 Add list notifications by user with pagination and filters. (REQ-7)
  * [ ] 6.4 Add unread count by user. (REQ-8)
  * [ ] 6.5 Add mark single notification read. (REQ-9)
  * [ ] 6.6 Add mark all notifications read for user. (REQ-9)
  * [ ] 6.7 Add archive/dismiss notification. (REQ-9)
  * [ ] 6.8 Add cleanup method for expired notifications. (REQ-15)
  * [ ] 6.9 Add repository tests for create, dedupe, list, unread count, read, read-all, archive, and cleanup. (REQ-1, REQ-7, REQ-8, REQ-9, REQ-12, REQ-15, REQ-17)

* [ ] 7. Implement notification preference service

  * [ ] 7.1 Add get preferences for current user. (REQ-6)
  * [ ] 7.2 Add update preferences for current user. (REQ-6)
  * [ ] 7.3 Add default preference merge behavior. (REQ-6)
  * [ ] 7.4 Add channel-enabled check. (REQ-6)
  * [ ] 7.5 Add required in-app event enforcement if product policy requires it. (REQ-6)
  * [ ] 7.6 Add tests for get, update, defaults, disabled channel, and required in-app behavior. (REQ-6, REQ-17)

* [ ] 8. Implement notification service

  * [ ] 8.1 Add create event notification method. (REQ-1)
  * [ ] 8.2 Resolve recipient user from source activity. (REQ-5)
  * [ ] 8.3 Check in-app preferences before creating in-app notification. (REQ-6)
  * [ ] 8.4 Generate safe title/body/action URL. (REQ-1, REQ-14)
  * [ ] 8.5 Apply dedupe key. (REQ-12)
  * [ ] 8.6 Create in-app notification. (REQ-1)
  * [ ] 8.7 Queue or create email delivery if enabled and allowed. (REQ-10, REQ-11)
  * [ ] 8.8 Log safe skipped events for no recipient or disabled preference. (REQ-5, REQ-16)
  * [ ] 8.9 Ensure service failure does not corrupt source activity state. (REQ-1, REQ-13)
  * [ ] 8.10 Add service tests for creation, preferences, dedupe, recipient failure, and failure isolation. (REQ-1, REQ-5, REQ-6, REQ-12, REQ-13, REQ-17)

* [ ] 9. Add notification templates

  * [ ] 9.1 Add in-app template for translation completed. (REQ-2)
  * [ ] 9.2 Add in-app template for translation failed. (REQ-3)
  * [ ] 9.3 Add in-app template for translation requires review. (REQ-4)
  * [ ] 9.4 Add safe failure summary formatter. (REQ-3, REQ-14)
  * [ ] 9.5 Add safe review reason formatter. (REQ-4, REQ-14)
  * [ ] 9.6 Add email templates if email delivery is implemented. (REQ-10)
  * [ ] 9.7 Add tests for template output and redaction. (REQ-2, REQ-3, REQ-4, REQ-10, REQ-14, REQ-17)

* [ ] 10. Wire translation completed event

  * [ ] 10.1 Locate successful translation activity status transition. (REQ-2)
  * [ ] 10.2 Call notification service on completion. (REQ-2)
  * [ ] 10.3 Include activity source reference. (REQ-2)
  * [ ] 10.4 Include safe action URL. (REQ-2)
  * [ ] 10.5 Add dedupe key. (REQ-12)
  * [ ] 10.6 Add tests for completed notification creation and duplicate completion processing. (REQ-2, REQ-12, REQ-17)

* [ ] 11. Wire translation failed event

  * [ ] 11.1 Locate failed translation activity status transition. (REQ-3)
  * [ ] 11.2 Call notification service on failure. (REQ-3)
  * [ ] 11.3 Include safe failure category/summary. (REQ-3, REQ-14)
  * [ ] 11.4 Include activity action URL or retry URL if available. (REQ-3)
  * [ ] 11.5 Add dedupe key to prevent retry spam. (REQ-12)
  * [ ] 11.6 Add tests for failed notification creation, redaction, and duplicate failure processing. (REQ-3, REQ-12, REQ-14, REQ-17)

* [ ] 12. Wire translation requires-review event

  * [ ] 12.1 Locate review-required state or quality gate outcome. (REQ-4)
  * [ ] 12.2 Call notification service when review is required. (REQ-4)
  * [ ] 12.3 Include safe review reason summary. (REQ-4)
  * [ ] 12.4 Include glossary conflict count or quality warning category if available and safe. (REQ-4)
  * [ ] 12.5 Include review/action URL if available. (REQ-4)
  * [ ] 12.6 Add dedupe key. (REQ-12)
  * [ ] 12.7 Add tests for review-required notification, safe reason formatting, and dedupe. (REQ-4, REQ-12, REQ-17)

* [ ] 13. Implement email delivery if in scope

  * [ ] 13.1 Inspect existing email sender. (REQ-10)
  * [ ] 13.2 Add email channel availability check. (REQ-10)
  * [ ] 13.3 Check user email and verification state where applicable. (REQ-10)
  * [ ] 13.4 Create delivery record when email is queued. (REQ-11)
  * [ ] 13.5 Send or enqueue email using existing worker/queue. (REQ-10, REQ-11)
  * [ ] 13.6 Mark delivery sent on success. (REQ-10, REQ-11)
  * [ ] 13.7 Mark delivery failed on failure. (REQ-10, REQ-11)
  * [ ] 13.8 Record skipped statuses for disabled preference or missing address. (REQ-10, REQ-11)
  * [ ] 13.9 Ensure in-app notification remains even when email fails. (REQ-10)
  * [ ] 13.10 Add tests with fake email sender for sent, failed, skipped preference, skipped missing address, and unverified email. (REQ-10, REQ-11, REQ-17)

* [ ] 14. Add notification API routes

  * [ ] 14.1 Add `GET /notifications`. (REQ-7)
  * [ ] 14.2 Add `GET /notifications/unread-count`. (REQ-8)
  * [ ] 14.3 Add `POST /notifications/{notification_id}/read`. (REQ-9)
  * [ ] 14.4 Add `POST /notifications/read-all`. (REQ-9)
  * [ ] 14.5 Add `POST /notifications/{notification_id}/archive` or dismiss equivalent. (REQ-9)
  * [ ] 14.6 Protect all routes with authenticated user auth. (REQ-7, REQ-8, REQ-9, REQ-14)
  * [ ] 14.7 Ensure users cannot access or mutate other users’ notifications. (REQ-7, REQ-9, REQ-14)
  * [ ] 14.8 Add API tests for list, filters, unread count, read, read-all, archive, unauthenticated, and cross-user access. (REQ-7, REQ-8, REQ-9, REQ-14, REQ-17)

* [ ] 15. Add notification preferences API routes

  * [ ] 15.1 Add `GET /notification-preferences`. (REQ-6)
  * [ ] 15.2 Add `PUT /notification-preferences`. (REQ-6)
  * [ ] 15.3 Protect preference routes with authenticated user auth. (REQ-6, REQ-14)
  * [ ] 15.4 Validate event types and channels. (REQ-6)
  * [ ] 15.5 Return default merged preferences. (REQ-6)
  * [ ] 15.6 Prevent cross-user preference access. (REQ-6, REQ-14)
  * [ ] 15.7 Add API tests for get, update, invalid input, unauthenticated, and user isolation. (REQ-6, REQ-14, REQ-17)

* [ ] 16. Add frontend notification UI

  * [ ] 16.1 Add notification API client methods. (REQ-13)
  * [ ] 16.2 Add notification entry point or bell for authenticated layout. (REQ-13)
  * [ ] 16.3 Add unread count badge. (REQ-8, REQ-13)
  * [ ] 16.4 Add notification list/dropdown/page. (REQ-7, REQ-13)
  * [ ] 16.5 Render severity, title, body, created time, and action URL. (REQ-7, REQ-13)
  * [ ] 16.6 Add mark-as-read action. (REQ-9, REQ-13)
  * [ ] 16.7 Add mark-all-as-read action. (REQ-9, REQ-13)
  * [ ] 16.8 Add archive/dismiss action if implemented. (REQ-9, REQ-13)
  * [ ] 16.9 Hide notification UI for unauthenticated public pages. (REQ-13)
  * [ ] 16.10 Add frontend tests for list rendering, unread count, mark read, read all, action links, and error states. (REQ-13, REQ-17)

* [ ] 17. Add frontend preferences UI

  * [ ] 17.1 Add notification preferences page/section. (REQ-6, REQ-13)
  * [ ] 17.2 Render supported event types. (REQ-6, REQ-13)
  * [ ] 17.3 Render supported channels. (REQ-6, REQ-13)
  * [ ] 17.4 Disable unavailable channels such as email when email is not configured. (REQ-10, REQ-13)
  * [ ] 17.5 Save preference changes. (REQ-6, REQ-13)
  * [ ] 17.6 Show success/error state. (REQ-13)
  * [ ] 17.7 Add frontend tests for preferences load, update, unavailable email, validation, and error states. (REQ-6, REQ-13, REQ-17)

* [ ] 18. Add retention cleanup hook

  * [ ] 18.1 Add notification cleanup repository method. (REQ-15)
  * [ ] 18.2 Add delivery cleanup repository method if deliveries exist. (REQ-15)
  * [ ] 18.3 Preserve recent unread notifications. (REQ-15)
  * [ ] 18.4 Make cleanup callable from `maintenance-cron`. (REQ-15)
  * [ ] 18.5 Add tests for cleanup eligibility and preservation. (REQ-15, REQ-17)

* [ ] 19. Add observability logs

  * [ ] 19.1 Log notification created event. (REQ-16)
  * [ ] 19.2 Log skipped due to preferences. (REQ-16)
  * [ ] 19.3 Log delivery queued. (REQ-16)
  * [ ] 19.4 Log delivery sent. (REQ-16)
  * [ ] 19.5 Log delivery failed. (REQ-16)
  * [ ] 19.6 Log preferences updated. (REQ-16)
  * [ ] 19.7 Redact secrets, provider errors, and private text from logs. (REQ-16)
  * [ ] 19.8 Add log tests only where project conventions support them. (REQ-16, REQ-17)

* [ ] 20. Security and privacy review

  * [ ] 20.1 Verify users can only list their own notifications. (REQ-14)
  * [ ] 20.2 Verify users can only mutate their own notifications. (REQ-14)
  * [ ] 20.3 Verify users can only manage their own preferences. (REQ-14)
  * [ ] 20.4 Verify action URLs still enforce authorization. (REQ-14)
  * [ ] 20.5 Verify notification content excludes secrets and stack traces. (REQ-14)
  * [ ] 20.6 Verify failed notification summaries redact provider details. (REQ-3, REQ-14)
  * [ ] 20.7 Verify email templates avoid unsafe private content. (REQ-10, REQ-14)
  * [ ] 20.8 Add missing security tests. (REQ-14, REQ-17)

* [ ] 21. Backend test coverage pass

  * [ ] 21.1 Add model/repository tests. (REQ-17)
  * [ ] 21.2 Add completed notification tests. (REQ-2, REQ-17)
  * [ ] 21.3 Add failed notification tests. (REQ-3, REQ-17)
  * [ ] 21.4 Add requires-review notification tests. (REQ-4, REQ-17)
  * [ ] 21.5 Add recipient resolution tests. (REQ-5, REQ-17)
  * [ ] 21.6 Add preference/default tests. (REQ-6, REQ-17)
  * [ ] 21.7 Add notification list API tests. (REQ-7, REQ-17)
  * [ ] 21.8 Add unread count tests. (REQ-8, REQ-17)
  * [ ] 21.9 Add read/read-all/archive tests. (REQ-9, REQ-17)
  * [ ] 21.10 Add email delivery tests if implemented. (REQ-10, REQ-11, REQ-17)
  * [ ] 21.11 Add dedupe/concurrency tests. (REQ-12, REQ-17)
  * [ ] 21.12 Add security/redaction tests. (REQ-14, REQ-17)
  * [ ] 21.13 Add failure isolation tests. (REQ-1, REQ-13, REQ-17)

* [ ] 22. Documentation

  * [ ] 22.1 Document notification event types. (REQ-1)
  * [ ] 22.2 Document default notification preferences. (REQ-6)
  * [ ] 22.3 Document notification API endpoints. (REQ-7, REQ-8, REQ-9)
  * [ ] 22.4 Document preferences API endpoints. (REQ-6)
  * [ ] 22.5 Document email delivery behavior if implemented. (REQ-10, REQ-11)
  * [ ] 22.6 Document dedupe behavior. (REQ-12)
  * [ ] 22.7 Document retention/maintenance integration. (REQ-15)
  * [ ] 22.8 Document security/privacy rules. (REQ-14)

* [ ] 23. Completion verification

  * [ ] 23.1 Run a successful translation and verify completed notification is created. (REQ-2, REQ-18)
  * [ ] 23.2 Run a failed translation and verify failed notification is created. (REQ-3, REQ-18)
  * [ ] 23.3 Trigger review-required translation and verify review notification is created. (REQ-4, REQ-18)
  * [ ] 23.4 Verify unread count updates after notifications are created. (REQ-8, REQ-18)
  * [ ] 23.5 Mark notification read and verify unread count updates. (REQ-9, REQ-18)
  * [ ] 23.6 Disable completed notification preference and verify future completed notifications respect it. (REQ-6, REQ-18)
  * [ ] 23.7 Process duplicate event and verify duplicate notification is not created. (REQ-12, REQ-18)
  * [ ] 23.8 Verify user cannot read another user’s notifications. (REQ-14, REQ-18)
  * [ ] 23.9 Verify notification content does not include stack traces or secrets. (REQ-14, REQ-18)
  * [ ] 23.10 If email is enabled, verify delivery status is recorded. (REQ-10, REQ-18)
  * [ ] 23.11 If email is disabled, verify in-app notifications still work. (REQ-10, REQ-18)
  * [ ] 23.12 Mark `notification-system` complete only after translation events create user-visible notifications and preferences are respected.
