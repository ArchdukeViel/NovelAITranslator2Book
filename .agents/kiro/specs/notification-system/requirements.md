# requirements.md

# Requirements: Notification System

## Introduction

The application needs a notification system so users are informed when translations complete, fail, or require review. The system must support in-app notifications, user preferences, and optional email delivery if email infrastructure exists.

## Requirement 1: In-app notification creation

### User story

As a user, I want in-app notifications so I can see important translation updates inside the application.

### Acceptance criteria

1. WHEN a notification-worthy event occurs THEN the system SHALL create an in-app notification if the user’s preference allows it.
2. WHEN an in-app notification is created THEN it SHALL include recipient user, event type, title, body, severity, source reference, and created timestamp.
3. WHEN a notification is created THEN it SHALL default to unread.
4. WHEN a notification source has an action URL THEN the notification SHALL include a safe action URL.
5. WHEN notification creation fails THEN the originating translation job SHALL not be marked failed solely because notification creation failed after translation completion.
6. WHEN notification content is generated THEN it SHALL not include secrets, stack traces, raw provider errors, or full private text.
7. WHEN duplicate event delivery occurs THEN the system SHALL avoid creating duplicate notifications for the same dedupe key.

## Requirement 2: Translation completed notification

### User story

As a user, I want to be notified when my translation completes so I know the result is ready.

### Acceptance criteria

1. WHEN a translation activity successfully completes THEN the system SHALL create a `translation.completed` notification for the activity owner or initiating user.
2. WHEN a completed notification is created THEN its severity SHALL be `success` or equivalent.
3. WHEN a completed notification is created THEN it SHALL include a title indicating completion.
4. WHEN a completed notification is created THEN it SHOULD include a link to the activity, novel, chapter, or translated result.
5. WHEN the same completion event is processed more than once THEN the system SHALL not create duplicate completed notifications.
6. WHEN the user disabled completed notifications for a channel THEN that channel SHALL be skipped.
7. WHEN the completed translation belongs to private content THEN only authorized recipient users SHALL be notified.

## Requirement 3: Translation failed notification

### User story

As a user, I want to be notified when my translation fails so I can retry or inspect the problem.

### Acceptance criteria

1. WHEN a translation activity fails THEN the system SHALL create a `translation.failed` notification for the activity owner or initiating user.
2. WHEN a failed notification is created THEN its severity SHALL be `error` or equivalent.
3. WHEN a failed notification is created THEN it SHALL include a safe failure summary.
4. WHEN a failed notification is created THEN it SHALL include an action link to the activity detail or retry path when available.
5. WHEN failure details include stack traces or provider secrets THEN those details SHALL be redacted.
6. WHEN the same failure event is processed repeatedly due to retry loops THEN the system SHALL not spam duplicate notifications.
7. WHEN the user disabled failed notifications for a channel THEN that channel SHALL be skipped unless product policy marks it required.

## Requirement 4: Translation requires review notification

### User story

As a user, I want to be notified when a translation requires review so I can resolve quality or glossary issues.

### Acceptance criteria

1. WHEN a translation activity enters review-required state THEN the system SHALL create a `translation.requires_review` notification.
2. WHEN a review notification is created THEN its severity SHALL be `warning` or equivalent.
3. WHEN a review notification is created THEN it SHALL include a safe reason summary where available.
4. WHEN a review page or activity detail exists THEN the notification SHALL include an action URL.
5. WHEN review is required due to glossary conflicts THEN the notification MAY include a safe count or category summary.
6. WHEN review is required due to quality gate failure THEN the notification MAY include a safe quality warning category.
7. WHEN the same review-required event is processed more than once THEN the system SHALL avoid duplicate notifications.

## Requirement 5: Notification recipient resolution

### User story

As a maintainer, I want notifications sent only to the correct users so private activities are not leaked.

### Acceptance criteria

1. WHEN a translation event occurs THEN the system SHALL resolve the recipient from the activity owner, initiating user, or existing ownership model.
2. WHEN no valid recipient exists THEN the system SHALL skip user notification and log a safe warning.
3. WHEN the source activity is private THEN the system SHALL notify only users authorized to view it.
4. WHEN the source novel/chapter is private THEN the notification SHALL not be sent to unrelated users.
5. WHEN admin/system alerts are added later THEN they SHALL use separate recipient rules.
6. WHEN recipient resolution fails THEN the original translation status SHALL not be corrupted.

## Requirement 6: Notification preferences

### User story

As a user, I want to control notification preferences so I receive only the channels and events I want.

### Acceptance criteria

1. WHEN a user views notification preferences THEN the system SHALL return preferences for supported event types and channels.
2. WHEN a user updates notification preferences THEN the system SHALL persist the changes.
3. WHEN preferences are updated THEN they SHALL apply to future notifications.
4. WHEN a preference disables a channel for an event THEN that channel SHALL be skipped for future matching notifications.
5. WHEN no explicit preference exists THEN the system SHALL use default notification preferences.
6. WHEN a user updates preferences THEN they SHALL only update their own preferences.
7. WHEN invalid event type or channel is submitted THEN the system SHALL return validation error.
8. WHEN in-app notifications are required by product policy THEN the system MAY prevent disabling required in-app events.

## Requirement 7: Notification list API

### User story

As a user, I want to list my notifications so I can review recent updates.

### Acceptance criteria

1. WHEN an authenticated user requests notifications THEN the system SHALL return only that user’s notifications.
2. WHEN an unauthenticated user requests notifications THEN the system SHALL return `401 Unauthorized`.
3. WHEN a user requests notifications THEN the response SHALL support pagination.
4. WHEN a user filters by status THEN the system SHALL return matching notifications.
5. WHEN a user filters by event type THEN the system SHALL return matching notifications.
6. WHEN notifications are returned THEN they SHALL include title, body, severity, status, action URL, event type, and created timestamp.
7. WHEN notifications are returned THEN they SHALL not expose secrets, stack traces, or private content beyond what the user is authorized to see.
8. WHEN no notifications exist THEN the system SHALL return an empty list.

## Requirement 8: Unread count

### User story

As a user, I want to see my unread notification count so I know when something needs attention.

### Acceptance criteria

1. WHEN an authenticated user requests unread count THEN the system SHALL return the number of unread notifications for that user.
2. WHEN no unread notifications exist THEN the system SHALL return zero.
3. WHEN a notification is marked read THEN unread count SHALL decrease.
4. WHEN a new unread notification is created THEN unread count SHALL increase.
5. WHEN an unauthenticated user requests unread count THEN the system SHALL return `401 Unauthorized`.
6. WHEN unread count is returned THEN it SHALL count only the current user’s notifications.

## Requirement 9: Read, unread, and archive actions

### User story

As a user, I want to mark notifications as read or archive them so I can manage my notification list.

### Acceptance criteria

1. WHEN a user marks one of their notifications as read THEN the system SHALL set read status and read timestamp.
2. WHEN a user marks all notifications as read THEN the system SHALL mark all of that user’s unread notifications as read.
3. WHEN a user archives or dismisses a notification THEN the system SHALL remove it from the default active list.
4. WHEN a user tries to modify another user’s notification THEN the system SHALL return `404` or `403` according to project convention.
5. WHEN a notification is already read THEN marking it read SHALL be safe and idempotent.
6. WHEN a notification is archived THEN unread count SHALL not include it.
7. WHEN an unauthenticated user attempts a notification action THEN the system SHALL return `401 Unauthorized`.

## Requirement 10: Optional email delivery

### User story

As a user, I want optional email notifications for important translation events so I can be notified outside the app.

### Acceptance criteria

1. WHEN email delivery is enabled and user preference allows it THEN the system SHALL create or enqueue email delivery for supported events.
2. WHEN email delivery is disabled globally THEN no email deliveries SHALL be sent.
3. WHEN a user disables email for an event THEN email delivery SHALL be skipped for that event.
4. WHEN email verification exists and the user email is unverified THEN email delivery SHALL be skipped unless product policy allows it.
5. WHEN email delivery succeeds THEN the delivery status SHALL be recorded as sent.
6. WHEN email delivery fails THEN the delivery status SHALL be recorded as failed with safe error category.
7. WHEN email delivery fails THEN the in-app notification SHALL remain available.
8. WHEN email content is generated THEN it SHALL not include raw stack traces, provider secrets, or full private content.
9. WHEN email infrastructure does not exist THEN email preferences SHALL be hidden, disabled, or marked unavailable.

## Requirement 11: Notification delivery tracking

### User story

As an operator, I want delivery attempts tracked so failed email or future channels can be diagnosed.

### Acceptance criteria

1. WHEN an external channel delivery is queued THEN the system SHALL create a delivery record.
2. WHEN delivery succeeds THEN the system SHALL record delivered timestamp.
3. WHEN delivery fails THEN the system SHALL record failed timestamp and safe error category.
4. WHEN delivery is skipped due to preferences THEN the system SHOULD record skipped status or log a safe event.
5. WHEN delivery is skipped due to missing email/address THEN the system SHOULD record skipped status or log a safe event.
6. WHEN delivery is retried THEN attempt count SHALL increase.
7. WHEN delivery records are exposed through any admin/operator API later THEN secrets SHALL be redacted.

## Requirement 12: Notification deduplication

### User story

As a user, I want to avoid duplicate notifications when jobs retry or events are processed more than once.

### Acceptance criteria

1. WHEN the same event with the same dedupe key is processed more than once THEN the system SHALL create at most one active notification.
2. WHEN a translation job is retried but the activity state has not changed THEN the system SHALL not create duplicate failure notifications.
3. WHEN a new activity run occurs THEN it MAY create a new notification with a different dedupe key.
4. WHEN an event changes from failed to completed after retry THEN the system MAY create a completion notification because the event type changed.
5. WHEN dedupe key conflicts occur concurrently THEN the system SHALL avoid duplicate rows using database or service-level protection.
6. WHEN dedupe skips a duplicate THEN the system SHOULD log a safe debug event.

## Requirement 13: Frontend notification UI

### User story

As a user, I want to view and manage notifications in the frontend.

### Acceptance criteria

1. WHEN a logged-in user opens the app THEN the UI SHOULD show a notification entry point.
2. WHEN unread notifications exist THEN the UI SHOULD show unread count.
3. WHEN a user opens notifications THEN the UI SHALL display notification list items.
4. WHEN a notification has an action URL THEN the UI SHALL allow navigation to it.
5. WHEN a user marks a notification as read THEN the UI SHALL update read state.
6. WHEN a user marks all as read THEN the UI SHALL update unread count.
7. WHEN a user opens preferences THEN the UI SHALL show supported events and channels.
8. WHEN a user updates preferences THEN the UI SHALL save changes and show success or error state.
9. WHEN notification APIs fail THEN the UI SHALL show safe error states.
10. WHEN a non-authenticated visitor is using public pages THEN notification UI SHALL not require or expose private notifications.

## Requirement 14: Security and privacy

### User story

As a user, I want notification data protected so private translation activity is not leaked.

### Acceptance criteria

1. WHEN notifications are queried THEN users SHALL see only their own notifications.
2. WHEN notification preferences are queried or updated THEN users SHALL access only their own preferences.
3. WHEN notification action URLs are used THEN the destination SHALL still enforce authorization.
4. WHEN notifications are stored THEN they SHALL not contain secrets, provider API keys, tokens, or raw stack traces.
5. WHEN failed translation notifications are created THEN raw provider errors SHALL be summarized and redacted.
6. WHEN email notifications are sent THEN they SHALL not include more private data than the user is authorized to receive.
7. WHEN logs include notification events THEN logs SHALL not include full private message bodies if avoidable.
8. WHEN admin users exist THEN they SHALL not automatically gain access to user notification inboxes unless a separate admin feature allows it.

## Requirement 15: Retention and cleanup compatibility

### User story

As an operator, I want old notifications cleaned up eventually so the notification store does not grow forever.

### Acceptance criteria

1. WHEN notification retention is configured THEN old notifications SHALL be eligible for cleanup after retention period.
2. WHEN archived/dismissed retention is configured THEN archived/dismissed notifications MAY be cleaned sooner.
3. WHEN delivery record retention is configured THEN old delivery records SHALL be eligible for cleanup.
4. WHEN cleanup is implemented in maintenance cron THEN notification cleanup SHALL be callable from that system.
5. WHEN active unread notifications are recent THEN cleanup SHALL preserve them.
6. WHEN cleanup deletes notifications THEN it SHALL not delete source activity records.
7. WHEN cleanup is not implemented in this spec THEN retention hooks or follow-up documentation SHALL exist.

## Requirement 16: Observability

### User story

As an operator, I want safe logs for notification creation and delivery so problems can be diagnosed.

### Acceptance criteria

1. WHEN a notification is created THEN the system SHOULD log a safe creation event.
2. WHEN a notification is skipped due to preferences THEN the system SHOULD log a safe skipped event.
3. WHEN external delivery is queued THEN the system SHOULD log a safe queued event.
4. WHEN external delivery succeeds THEN the system SHOULD log a safe delivered event.
5. WHEN external delivery fails THEN the system SHALL log a safe failure event.
6. WHEN preferences are updated THEN the system SHOULD log a safe update event.
7. WHEN logs are emitted THEN they SHALL not include secrets, raw provider errors, full private text, or raw email provider responses.

## Requirement 17: Test coverage

### User story

As a maintainer, I want notification tests so users reliably receive important translation updates.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover notification model/repository behavior.
2. WHEN tests run THEN they SHALL cover translation completed notification.
3. WHEN tests run THEN they SHALL cover translation failed notification.
4. WHEN tests run THEN they SHALL cover translation requires-review notification.
5. WHEN tests run THEN they SHALL cover recipient resolution.
6. WHEN tests run THEN they SHALL cover deduplication.
7. WHEN tests run THEN they SHALL cover preferences and default preferences.
8. WHEN tests run THEN they SHALL cover notification list authorization.
9. WHEN tests run THEN they SHALL cover unread count.
10. WHEN tests run THEN they SHALL cover mark read, mark all read, and archive/dismiss.
11. WHEN email delivery is implemented THEN tests SHALL cover queued, sent, failed, and skipped delivery.
12. WHEN frontend UI is implemented THEN tests SHALL cover notification list and preferences rendering.
13. WHEN tests run THEN they SHALL cover security/redaction rules where practical.
14. WHEN tests run THEN they SHALL cover notification creation failure isolation.

## Requirement 18: Completion verification

### User story

As a maintainer, I want a clear verification path so notification system is only complete when translation events create user-visible notifications.

### Acceptance criteria

1. WHEN a translation completes in staging THEN the initiating user SHALL receive an in-app completed notification.
2. WHEN a translation fails in staging THEN the initiating user SHALL receive an in-app failed notification.
3. WHEN a translation requires review in staging THEN the initiating user SHALL receive an in-app review notification.
4. WHEN the user disables a notification event/channel THEN future matching notifications SHALL respect that preference.
5. WHEN duplicate event processing is simulated THEN duplicate notifications SHALL not be created.
6. WHEN a user lists notifications THEN only their notifications SHALL be returned.
7. WHEN unread count is requested THEN it SHALL match unread notifications.
8. WHEN email is enabled THEN email delivery SHALL be sent or recorded according to preference.
9. WHEN email is disabled or unavailable THEN in-app notifications SHALL still work.
