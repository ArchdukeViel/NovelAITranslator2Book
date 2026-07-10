# design.md

# Design: Notification System

## Overview

`notification-system` adds user notifications for important translation and workflow events.

The system should notify users when translation jobs complete, fail, or require review. It should also support user notification preferences so users can control which events and delivery channels they receive.

This is a should-have operations/UX feature. It improves trust and reduces the need for users to repeatedly check activity status pages.

## Goals

* Add in-app notifications.
* Notify users when translations complete.
* Notify users when translations fail.
* Notify users when translations require review.
* Add user notification preferences.
* Support optional email delivery if email infrastructure exists.
* Store notification read/unread state.
* Avoid duplicate notification spam.
* Add tests for notification creation, delivery, preferences, and authorization.

## Non-goals

* No full marketing email system.
* No push notifications unless already supported.
* No SMS notifications.
* No complex notification campaign builder.
* No public announcement system.
* No admin support inbox.
* No real-time websocket requirement for V1, though the design should not block it later.

## Notification types

Recommended V1 notification event types:

```text id="m4eyb5"
translation.completed
translation.failed
translation.requires_review
crawl.completed
crawl.failed
export.completed
export.failed
system.maintenance
```

Required for this spec:

```text id="kmf2g9"
translation.completed
translation.failed
translation.requires_review
```

Optional useful events:

```text id="eoe7wq"
crawl.failed
export.completed
export.failed
backup.failed
scheduler.stale
```

Operational admin alerts can be added later or integrated with this system carefully.

## Delivery channels

Recommended V1 channels:

```text id="6llbup"
in_app
email
```

Required:

```text id="f7bkoc"
in_app
```

Optional:

```text id="j1qdrm"
email
```

Future channels:

```text id="z2nchq"
web_push
mobile_push
slack
discord
webhook
```

## Data model

### Notifications

Recommended table/model: `notifications`

Recommended fields:

```text id="t015iv"
id
user_id
event_type
title
body
severity
status
read_at
action_url
source_type
source_id
dedupe_key
metadata_json
created_at
updated_at
expires_at
```

Recommended severity values:

```text id="vh06tg"
info
success
warning
error
```

Recommended status values:

```text id="muwbgs"
unread
read
archived
dismissed
```

### Notification deliveries

If email or other external delivery is implemented, track delivery attempts separately.

Recommended table/model: `notification_deliveries`

Recommended fields:

```text id="sjmgi5"
id
notification_id
user_id
channel
status
attempt_count
last_attempt_at
delivered_at
failed_at
error_category
error_message
provider_message_id
created_at
updated_at
```

Recommended delivery statuses:

```text id="hwvcda"
pending
sent
failed
skipped_preferences
skipped_no_address
skipped_disabled
```

### Notification preferences

Recommended table/model: `notification_preferences`

Recommended fields:

```text id="4mifmt"
id
user_id
channel
event_type
enabled
created_at
updated_at
```

Alternative: store preferences as JSON on user profile if the project already uses profile settings.

Recommended default preferences:

```text id="pmwccn"
in_app translation.completed: enabled
in_app translation.failed: enabled
in_app translation.requires_review: enabled
email translation.completed: disabled by default
email translation.failed: enabled if verified email exists
email translation.requires_review: enabled if verified email exists
```

Use project-specific defaults if email policy already exists.

## Notification creation flow

High-level flow:

```text id="nsqhyp"
1. Translation pipeline emits domain event.
2. NotificationService receives event.
3. Service resolves recipient user.
4. Service checks preferences.
5. Service creates in-app notification if enabled.
6. Service enqueues email delivery if enabled and available.
7. Service records delivery state.
```

Recommended service components:

```text id="f3h4qp"
NotificationService
NotificationPreferenceService
NotificationDeliveryService
NotificationTemplateService
NotificationRepository
NotificationRouter
```

## Translation event integration

The translation worker/activity pipeline should call notification creation on important transitions.

### On translation completed

Trigger:

```text id="ks7rlv"
translation activity status changes to completed/succeeded
```

Notification:

```text id="i32bf9"
event_type: translation.completed
severity: success
title: Translation completed
action_url: activity detail or novel/chapter page
```

### On translation failed

Trigger:

```text id="v5lo6y"
translation activity status changes to failed
```

Notification:

```text id="17rjfj"
event_type: translation.failed
severity: error
title: Translation failed
action_url: activity detail page
```

Include safe error category, not raw stack trace.

### On translation requires review

Trigger examples:

```text id="c3ne8q"
quality gate requires review
glossary conflicts require review
manual review flag set
translation completed with review_required status
```

Notification:

```text id="krmixx"
event_type: translation.requires_review
severity: warning
title: Translation requires review
action_url: review or activity detail page
```

## Event source and ownership

Only notify users who are allowed to see the source activity.

Recommended recipient resolution:

```text id="04zrl5"
activity.owner_user_id
novel.owner_user_id
requesting_user_id
admin/operator for system alerts
```

For V1 translation notifications, use the user who initiated or owns the translation activity.

Never notify unrelated users about private novels or private activities.

## Dedupe policy

Avoid notification spam.

Recommended dedupe key:

```text id="0d2h0c"
{event_type}:{source_type}:{source_id}:{status_version}
```

Examples:

```text id="vlwuyf"
translation.completed:activity:activity_123:v1
translation.failed:activity:activity_123:v1
translation.requires_review:activity:activity_123:v1
```

Rules:

```text id="2y7nf3"
same dedupe key should not create duplicate active notifications
retries should not create duplicate failure notifications
state changes may create new notifications if event type changes
manual re-run may use a new activity ID or status version
```

## In-app notification API

Recommended endpoints:

```http id="dwmvbb"
GET /notifications
GET /notifications/unread-count
POST /notifications/{notification_id}/read
POST /notifications/read-all
POST /notifications/{notification_id}/archive
GET /notification-preferences
PUT /notification-preferences
```

If the project uses `/api/...`, use that convention.

### List notifications

Query params:

```text id="pxj2qt"
status?: unread|read|archived
event_type?: string
page?: number
page_size?: number
```

Response:

```json id="vwyw4e"
{
  "items": [
    {
      "id": "notif_123",
      "event_type": "translation.completed",
      "title": "Translation completed",
      "body": "Your translation for Chapter 12 is ready.",
      "severity": "success",
      "status": "unread",
      "action_url": "/activities/activity_123",
      "created_at": "2026-07-10T00:00:00Z"
    }
  ],
  "page": 1,
  "page_size": 25,
  "total": 1
}
```

## Frontend design

Recommended UI elements:

```text id="9tcivm"
notification bell
unread count badge
notification dropdown or page
mark as read
mark all as read
notification preferences page
```

Minimum V1 UI:

```text id="ae2udw"
notification list/page
unread count
mark as read
preferences form
```

Notification display should include:

```text id="xlwimt"
title
message/body
severity
created time
action link
read/unread state
```

## Email delivery

If email infrastructure exists, email notifications should use templates.

Recommended templates:

```text id="xd7wy9"
translation_completed_email
translation_failed_email
translation_requires_review_email
```

Rules:

```text id="91cg3j"
send only if user preference allows email
send only if user has verified email when verification exists
do not include raw private text unless user already owns it and policy allows
do not include full stack traces
include action link to app
record delivery status
retry transient failures if existing job queue supports it
```

If email infrastructure does not exist, keep email preferences hidden or disabled and implement only in-app notifications.

## Preferences

Users should be able to control notification preferences.

Recommended preference matrix:

```text id="vgzeex"
event type x channel -> enabled/disabled
```

Example:

```json id="2v88mw"
{
  "preferences": [
    {
      "event_type": "translation.completed",
      "channel": "in_app",
      "enabled": true
    },
    {
      "event_type": "translation.completed",
      "channel": "email",
      "enabled": false
    }
  ]
}
```

Rules:

```text id="rg0qrr"
in-app critical failure notifications may be required and not disableable if product policy requires
email should be user-controlled
preferences update should apply to future notifications
existing notifications should not be deleted when preferences change
```

## Security and privacy

Rules:

```text id="qtag98"
users can only read their own notifications
users can only update their own notification preferences
admin cannot read user notifications unless a separate admin support feature exists
notifications must not include secrets
notifications must not include raw provider errors or stack traces
email notifications must not include private content beyond safe summaries
action URLs must be authorization-protected
```

## Retention

Notifications should not live forever.

Recommended config:

```text id="wrhbv4"
NOTIFICATION_RETENTION_DAYS=180
NOTIFICATION_ARCHIVED_RETENTION_DAYS=90
NOTIFICATION_DELIVERY_RETENTION_DAYS=180
```

Cleanup can be implemented in `maintenance-cron`.

For this spec, provide repository cleanup methods or document integration.

## Observability

Log safe notification events:

```text id="3bd44c"
notification.created
notification.skipped_preferences
notification.delivery_queued
notification.delivery_sent
notification.delivery_failed
notification.marked_read
notification.preferences_updated
```

Safe fields:

```text id="rzq6f0"
notification_id
user_id hash or internal ID if allowed in admin logs
event_type
channel
source_type
source_id
delivery_status
error_category
```

Do not log full message bodies if they may include private content.

## Error handling

Expected behavior:

```text id="onxszq"
notification creation fails -> log safe error; do not fail completed translation if translation already succeeded
preference lookup fails -> use safe default or skip external delivery according to policy
email delivery fails -> mark delivery failed; keep in-app notification
duplicate event -> return existing notification or skip duplicate
invalid preference update -> return validation error
```

## Testing strategy

Tests should cover:

```text id="7jxb2z"
create translation completed notification
create translation failed notification
create requires review notification
dedupe prevents duplicates
preferences skip disabled channel
in-app notification list only returns current user's notifications
unread count
mark read
mark all read
archive/dismiss
email delivery queued/sent/failed if implemented
safe error body for failed translations
notification creation failure does not fail translation
preferences API authorization
frontend notification list/preference rendering if UI implemented
```

## Rollout plan

1. Inspect activity/translation status transitions.
2. Add notification models and migrations.
3. Add notification service and repository.
4. Add preference model/service.
5. Wire translation completion/failure/review events.
6. Add in-app notification API.
7. Add frontend notification UI.
8. Add optional email delivery.
9. Add tests.
10. Verify:

    * completed translation creates notification.
    * failed translation creates notification.
    * review-required translation creates notification.
    * preferences are respected.
    * users cannot read other users’ notifications.
