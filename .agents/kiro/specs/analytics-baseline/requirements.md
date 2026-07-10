# requirements.md

# Requirements: Analytics Baseline

## Introduction

The application needs a privacy-safe analytics baseline to understand product usage. It should track reader engagement, novel/chapter views, exports, searches, and feature interactions without collecting sensitive content or creating a surveillance system.

## Requirement 1: Analytics event model

### User story

As a maintainer, I want a standard analytics event model so product usage can be recorded consistently.

### Acceptance criteria

1. WHEN an analytics event is recorded THEN it SHALL include an allowed event name.
2. WHEN an analytics event is recorded THEN it SHALL include event timestamp.
3. WHEN an analytics event is recorded THEN it MAY include safe actor/session identifiers.
4. WHEN an analytics event is recorded THEN it MAY include safe source references such as novel ID or chapter ID.
5. WHEN an analytics event is recorded THEN metadata SHALL be JSON-compatible.
6. WHEN an analytics event includes unknown unsafe fields THEN they SHALL be dropped or rejected.
7. WHEN event recording fails THEN the original user action SHALL not fail solely due to analytics failure.

## Requirement 2: Allowed event names and schemas

### User story

As an operator, I want only approved analytics events accepted so arbitrary or sensitive data is not stored.

### Acceptance criteria

1. WHEN an event is submitted THEN the system SHALL validate its event name against an allowlist.
2. WHEN an event name is not allowed THEN the event SHALL be rejected or dropped.
3. WHEN event metadata is submitted THEN it SHALL be validated against the event schema where practical.
4. WHEN metadata includes unsupported keys THEN unsupported keys SHALL be dropped or rejected.
5. WHEN metadata values exceed size limits THEN values SHALL be truncated or rejected.
6. WHEN events are stored THEN they SHALL use stable event names.
7. WHEN new event types are added THEN tests SHALL cover validation and privacy rules.

## Requirement 3: Public novel and chapter view tracking

### User story

As an operator, I want to know which public novels and chapters are being viewed so I can understand reader engagement.

### Acceptance criteria

1. WHEN a public novel page is viewed THEN the system SHOULD record `public_novel.view`.
2. WHEN a public chapter page is viewed THEN the system SHOULD record `public_chapter.view`.
3. WHEN a public chapter view is recorded THEN it MAY include safe novel and chapter IDs.
4. WHEN public reader view events are recorded THEN they SHALL not include full chapter text.
5. WHEN public reader view events are recorded THEN they SHALL not include raw query strings or signed URLs.
6. WHEN a reader is anonymous THEN the event MAY use a privacy-safe anonymous/session identifier.
7. WHEN view tracking fails THEN public reader rendering SHALL still work.

## Requirement 4: Reader engagement tracking

### User story

As an operator, I want coarse reader engagement data so I can understand whether chapters are being read without collecting detailed behavior.

### Acceptance criteria

1. WHEN a reader moves to the next chapter THEN the system MAY record `reader.chapter_next`.
2. WHEN a reader moves to the previous chapter THEN the system MAY record `reader.chapter_previous`.
3. WHEN progress milestones are tracked THEN they SHALL use coarse milestones only.
4. WHEN progress milestones are tracked THEN they SHALL not record every scroll event.
5. WHEN progress milestone metadata is recorded THEN it SHALL not include selected text or chapter content.
6. WHEN engagement tracking is disabled THEN reader functionality SHALL remain unchanged.

## Requirement 5: Search analytics

### User story

As an operator, I want to understand search usage without storing raw private queries.

### Acceptance criteria

1. WHEN a search is performed THEN the system SHOULD record `search.performed`.
2. WHEN search analytics are recorded THEN they SHALL include safe search scope where available.
3. WHEN search analytics are recorded THEN they SHOULD include result count bucket.
4. WHEN search analytics are recorded THEN they MAY include filter count or sort key.
5. WHEN search analytics are recorded THEN raw query text SHALL NOT be stored by default.
6. WHEN raw query storage is disabled THEN the system SHALL drop or omit query text.
7. WHEN search analytics recording fails THEN search behavior SHALL still work.

## Requirement 6: Export analytics

### User story

As an operator, I want to understand export usage so I can see which formats are used and whether exports are downloaded.

### Acceptance criteria

1. WHEN an export is requested THEN the system SHOULD record `export.requested`.
2. WHEN an export artifact is downloaded THEN the system SHOULD record `export.downloaded`.
3. WHEN an export fails and failure analytics are enabled THEN the system MAY record `export.failed`.
4. WHEN export analytics are recorded THEN they MAY include safe format, status, and freshness status.
5. WHEN export analytics are recorded THEN they SHALL not include raw artifact paths.
6. WHEN export analytics are recorded THEN they SHALL not include signed URLs or credentials.
7. WHEN export analytics recording fails THEN export behavior SHALL still work.

## Requirement 7: Glossary annotation interaction analytics

### User story

As an operator, I want to know whether glossary annotations are being used without storing glossary definitions or matched terms.

### Acceptance criteria

1. WHEN a glossary annotation is opened and analytics are enabled THEN the frontend MAY record `glossary_annotation.opened`.
2. WHEN glossary annotation analytics are recorded THEN they SHALL not include source term.
3. WHEN glossary annotation analytics are recorded THEN they SHALL not include display term.
4. WHEN glossary annotation analytics are recorded THEN they SHALL not include definition.
5. WHEN glossary annotation analytics are recorded THEN they MAY include safe match type or annotation count bucket.
6. WHEN glossary annotation analytics are disabled THEN annotation rendering SHALL still work.

## Requirement 8: Notification interaction analytics

### User story

As an operator, I want basic notification interaction counts so I can understand notification usefulness.

### Acceptance criteria

1. WHEN a notification is opened and analytics are enabled THEN the system MAY record `notification.opened`.
2. WHEN a notification action is clicked and analytics are enabled THEN the system MAY record `notification.action_clicked`.
3. WHEN notification analytics are recorded THEN they MAY include event type, severity, and channel.
4. WHEN notification analytics are recorded THEN they SHALL not include notification body text.
5. WHEN notification analytics fail THEN notification behavior SHALL still work.

## Requirement 9: Analytics ingestion endpoint

### User story

As a frontend developer, I want a safe analytics ingestion endpoint so the frontend can record approved events.

### Acceptance criteria

1. WHEN analytics ingestion is enabled THEN the backend SHALL expose a controlled ingestion endpoint.
2. WHEN the ingestion endpoint receives events THEN it SHALL validate event names.
3. WHEN the ingestion endpoint receives metadata THEN it SHALL sanitize metadata.
4. WHEN a request includes too many events THEN the endpoint SHALL reject or truncate according to policy.
5. WHEN a request body is too large THEN the endpoint SHALL reject it.
6. WHEN public ingestion is abused THEN rate limits SHALL apply.
7. WHEN ingestion succeeds THEN the endpoint SHALL return a success response.
8. WHEN ingestion fails validation THEN the endpoint SHALL return a safe validation response or drop invalid events according to policy.

## Requirement 10: Server-side analytics recording

### User story

As a maintainer, I want server-side analytics for trusted events so key actions are recorded consistently.

### Acceptance criteria

1. WHEN export request is handled server-side THEN the server SHOULD record export analytics.
2. WHEN export download is handled server-side THEN the server SHOULD record download analytics.
3. WHEN account signup completes and signup analytics are enabled THEN the server MAY record signup analytics.
4. WHEN notification action is handled server-side THEN the server MAY record notification analytics.
5. WHEN server-side analytics recording fails THEN the primary action SHALL still complete according to normal behavior.
6. WHEN server-side analytics are recorded THEN privacy rules SHALL still apply.

## Requirement 11: Admin analytics summary API

### User story

As an admin, I want analytics summaries so I can understand product usage trends.

### Acceptance criteria

1. WHEN an admin requests analytics summary THEN the system SHALL return aggregate product usage data.
2. WHEN an unauthenticated user requests analytics summary THEN the system SHALL return `401 Unauthorized`.
3. WHEN a non-admin requests analytics summary THEN the system SHALL return `403 Forbidden`.
4. WHEN summary is returned THEN it SHALL include requested window and generated timestamp.
5. WHEN reader view events exist THEN summary SHOULD include novel/chapter view counts.
6. WHEN export events exist THEN summary SHOULD include export request/download counts.
7. WHEN search events exist THEN summary SHOULD include search counts.
8. WHEN glossary/notification events exist THEN summary MAY include aggregate feature usage.
9. WHEN summary is returned THEN it SHALL not include raw user-level clickstreams.
10. WHEN summary generation fails for one group THEN the API SHOULD return available groups where practical.

## Requirement 12: Optional admin analytics dashboard

### User story

As an admin, I want a simple analytics dashboard so I can view product usage without raw queries.

### Acceptance criteria

1. WHEN dashboard is in scope THEN `/admin/analytics` or equivalent route SHALL be added.
2. WHEN an admin opens the dashboard THEN it SHALL show reader view totals.
3. WHEN an admin opens the dashboard THEN it SHALL show export usage totals.
4. WHEN an admin opens the dashboard THEN it SHALL show search usage totals.
5. WHEN top novel analytics are available THEN the dashboard MAY show top novels by views.
6. WHEN feature interaction analytics are available THEN the dashboard MAY show glossary/notification usage.
7. WHEN non-admin opens the dashboard THEN access SHALL be blocked.
8. WHEN analytics API fails THEN the dashboard SHALL show a safe error or partial state.

## Requirement 13: Privacy guardrails

### User story

As a privacy-conscious operator, I want analytics to avoid collecting sensitive content or overly personal identifiers.

### Acceptance criteria

1. WHEN analytics events are recorded THEN they SHALL not include full source text.
2. WHEN analytics events are recorded THEN they SHALL not include full translated text.
3. WHEN analytics events are recorded THEN they SHALL not include raw prompts.
4. WHEN analytics events are recorded THEN they SHALL not include glossary definitions.
5. WHEN analytics events are recorded THEN they SHALL not include notification body text.
6. WHEN analytics events are recorded THEN they SHALL not include raw signed URLs.
7. WHEN analytics events are recorded THEN they SHALL not include credentials, API keys, or tokens.
8. WHEN analytics events are recorded THEN they SHALL not include full IP addresses by default.
9. WHEN analytics events are recorded THEN they SHALL not use browser fingerprinting.
10. WHEN analytics output is shown to admins THEN it SHALL prefer aggregate views over per-user histories.

## Requirement 14: Retention and cleanup

### User story

As an operator, I want analytics events to expire so product usage data does not accumulate forever.

### Acceptance criteria

1. WHEN analytics retention is configured THEN events older than retention SHALL be eligible for cleanup.
2. WHEN maintenance cron exists THEN analytics cleanup SHALL integrate with it.
3. WHEN cleanup runs THEN it SHALL delete or aggregate old analytics according to policy.
4. WHEN cleanup runs in dry-run mode THEN it SHALL report eligible analytics records without deleting them.
5. WHEN analytics are deleted THEN core application data SHALL not be affected.
6. WHEN retention config is missing THEN the system SHALL use a safe default.
7. WHEN tests run THEN retention cleanup behavior SHALL be covered.

## Requirement 15: Analytics disable controls

### User story

As an operator, I want to disable analytics if needed for privacy, compliance, or debugging.

### Acceptance criteria

1. WHEN analytics are globally disabled THEN new analytics events SHALL not be stored.
2. WHEN public ingestion is disabled THEN the ingestion endpoint SHALL reject or ignore frontend events safely.
3. WHEN analytics are disabled THEN reader, search, export, and notification behavior SHALL remain unchanged.
4. WHEN analytics are disabled THEN admin summary SHALL indicate analytics disabled or show empty data safely.
5. WHEN analytics config changes THEN future tracking SHALL respect the new config.
6. WHEN analytics are disabled THEN frontend tracking client SHALL become no-op where practical.

## Requirement 16: Failure isolation

### User story

As a user, I want analytics failures to never break normal application flows.

### Acceptance criteria

1. WHEN analytics recording fails during reader view THEN reader page SHALL still render.
2. WHEN analytics recording fails during search THEN search SHALL still work.
3. WHEN analytics recording fails during export request THEN export SHALL still work according to normal behavior.
4. WHEN analytics recording fails during notification action THEN notification behavior SHALL still work.
5. WHEN analytics storage is unavailable THEN events MAY be dropped or queued according to config.
6. WHEN analytics failure is logged THEN logs SHALL be safe and avoid spam.

## Requirement 17: Test coverage

### User story

As a maintainer, I want tests for analytics recording and privacy so the baseline remains safe.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover analytics event recording.
2. WHEN tests run THEN they SHALL cover event name validation.
3. WHEN tests run THEN they SHALL cover metadata sanitization.
4. WHEN tests run THEN they SHALL cover public ingestion validation and rate limits where practical.
5. WHEN tests run THEN they SHALL cover reader view tracking.
6. WHEN tests run THEN they SHALL cover export analytics.
7. WHEN tests run THEN they SHALL cover search analytics without raw query storage.
8. WHEN tests run THEN they SHALL cover glossary annotation analytics without term/definition storage where implemented.
9. WHEN tests run THEN they SHALL cover admin summary authorization.
10. WHEN tests run THEN they SHALL cover admin summary aggregation.
11. WHEN tests run THEN they SHALL cover retention cleanup.
12. WHEN tests run THEN they SHALL cover analytics disabled behavior.
13. WHEN tests run THEN they SHALL cover failure isolation.

## Requirement 18: Completion verification

### User story

As an operator, I want a clear verification path so analytics baseline is complete only when useful aggregate data is recorded safely.

### Acceptance criteria

1. WHEN a public novel page is viewed THEN a safe novel view event SHALL be recorded.
2. WHEN a public chapter page is viewed THEN a safe chapter view event SHALL be recorded.
3. WHEN a search is performed THEN a safe search event SHALL be recorded without raw query text.
4. WHEN an export is requested/downloaded THEN safe export events SHALL be recorded.
5. WHEN admin summary is requested by admin THEN aggregate counts SHALL be visible.
6. WHEN admin summary is requested by non-admin THEN access SHALL be blocked.
7. WHEN analytics event payloads are inspected THEN they SHALL not include private content, prompts, definitions, signed URLs, or secrets.
8. WHEN analytics are disabled THEN events SHALL not be stored and app behavior SHALL continue.
