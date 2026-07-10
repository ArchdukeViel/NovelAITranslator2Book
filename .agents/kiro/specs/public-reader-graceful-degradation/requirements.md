# requirements.md

# Requirements: Public Reader Graceful Degradation

## Introduction

The public reader should degrade gracefully when dependencies flicker. When database/catalog, storage, object storage, or optional reader features fail temporarily, the application should either serve a safe cached public snapshot or return a public-safe temporary unavailable response. It must never bypass publication, privacy, or takedown rules.

## Requirement 1: Normal reader behavior preservation

### User story

As a reader, I want normal chapter loading to behave the same when dependencies are healthy.

### Acceptance criteria

1. WHEN public reader dependencies are healthy THEN the chapter response SHALL match existing successful behavior except for additive safe metadata if implemented.
2. WHEN a published chapter is requested THEN the system SHALL perform existing publication checks.
3. WHEN a public novel detail page is requested THEN the system SHALL preserve existing availability behavior.
4. WHEN no dependency failure occurs THEN fallback logic SHALL not change the returned content.
5. WHEN existing reader response schemas are used THEN this feature SHALL not remove or rename existing fields.
6. WHEN existing reader tests run THEN normal-path behavior SHALL continue passing.

## Requirement 2: Dependency timeout handling

### User story

As a reader, I want the public reader to respond quickly instead of hanging when a dependency is slow.

### Acceptance criteria

1. WHEN catalog lookup exceeds configured timeout THEN the system SHALL treat it as a dependency timeout.
2. WHEN chapter storage read exceeds configured timeout THEN the system SHALL treat it as a dependency timeout.
3. WHEN object storage read exceeds configured timeout THEN the system SHALL treat it as a dependency timeout.
4. WHEN public snapshot read exceeds configured timeout THEN the system SHALL return a safe unavailable response if no other fallback is available.
5. WHEN optional feature lookup exceeds configured timeout THEN the system SHALL return the core reader response without that optional feature.
6. WHEN total public reader timeout is exceeded THEN the system SHALL fail safely with a public-safe response.
7. WHEN a timeout occurs THEN the system SHALL log a safe diagnostic event.

## Requirement 3: Circuit breaker behavior

### User story

As an operator, I want repeated dependency failures to open a circuit so the public reader can fail fast or use fallback instead of repeatedly waiting on broken services.

### Acceptance criteria

1. WHEN a protected dependency fails repeatedly beyond threshold THEN its circuit breaker SHALL open.
2. WHEN a circuit breaker is open THEN calls to that dependency SHALL fail fast or skip to fallback.
3. WHEN recovery interval passes THEN the circuit breaker SHALL enter half-open state.
4. WHEN a half-open probe succeeds THEN the circuit breaker SHALL close.
5. WHEN a half-open probe fails THEN the circuit breaker SHALL reopen.
6. WHEN a circuit breaker changes state THEN the system SHALL log a safe event.
7. WHEN circuit breaker state is used for fallback decisions THEN the reader response SHALL remain public-safe.
8. WHEN circuit breakers are disabled by config THEN dependency calls SHALL proceed without breaker state.

## Requirement 4: Safe public snapshot fallback

### User story

As a reader, I want the chapter to remain readable during temporary outages when a safe public snapshot exists.

### Acceptance criteria

1. WHEN primary reader dependencies fail and a safe public snapshot exists THEN the system SHALL serve the snapshot as fallback.
2. WHEN a snapshot is served as fallback THEN the response SHALL indicate degraded/fallback state through safe metadata or headers.
3. WHEN a snapshot is served as fallback THEN the content SHALL be from public projection/snapshot storage, not raw private storage.
4. WHEN snapshot fallback is disabled by configuration THEN the system SHALL not serve snapshots.
5. WHEN no safe snapshot exists THEN the system SHALL return a public-safe unavailable response.
6. WHEN snapshot read fails THEN the system SHALL return a public-safe unavailable response.
7. WHEN fallback is served THEN the system SHALL log a safe fallback event.
8. WHEN fallback is served THEN existing reader clients SHALL still be able to render the response.

## Requirement 5: Snapshot freshness

### User story

As an operator, I want fallback snapshots to respect freshness policy so the reader does not serve content that is too stale.

### Acceptance criteria

1. WHEN a snapshot is newer than configured max age THEN it SHALL be eligible for fallback.
2. WHEN a snapshot is older than configured max age and stale fallback is disabled THEN it SHALL NOT be served.
3. WHEN a snapshot is older than configured max age and stale fallback is allowed THEN it MAY be served with degraded metadata.
4. WHEN snapshot generated time is missing or invalid THEN the snapshot SHALL be treated as unsafe or stale.
5. WHEN a stale snapshot is served THEN the response SHALL indicate degraded/stale state safely.
6. WHEN freshness policy changes THEN tests SHALL cover allowed and disallowed stale behavior.

## Requirement 6: Publication and takedown safety

### User story

As an operator, I want fallback behavior to never expose unpublished, private, or removed content.

### Acceptance criteria

1. WHEN a chapter is unpublished THEN fallback SHALL NOT serve it.
2. WHEN a novel is unpublished THEN fallback SHALL NOT serve its chapters.
3. WHEN a takedown tombstone or revocation exists THEN fallback SHALL NOT serve the affected content.
4. WHEN publication state cannot be verified and no public projection guarantee exists THEN fallback SHALL NOT serve the content.
5. WHEN fallback snapshot was not generated by the public publication/projection pipeline THEN it SHALL NOT be served.
6. WHEN an unpublish/takedown event occurs THEN public snapshots SHALL be deleted, tombstoned, or otherwise blocked from fallback.
7. WHEN fallback safety checks fail THEN the system SHALL return unavailable or not-found according to existing public behavior.
8. WHEN fallback is served THEN it SHALL not include private/admin-only metadata.

## Requirement 7: Optional feature degradation

### User story

As a reader, I want optional reader features to fail without breaking the core chapter.

### Acceptance criteria

1. WHEN glossary annotation lookup fails THEN the system SHALL return the chapter with empty annotations or omitted optional data according to response contract.
2. WHEN optional reader metadata lookup fails THEN the system SHALL return the core reader response if safe.
3. WHEN optional feature timeout occurs THEN the system SHALL not fail the whole chapter response.
4. WHEN optional feature failure occurs THEN the system SHALL log a safe warning.
5. WHEN optional feature data is unavailable THEN the response SHALL remain schema-compatible.
6. WHEN optional feature failure occurs THEN public responses SHALL not expose stack traces or internal errors.

## Requirement 8: Public unavailable response

### User story

As a reader, I want a clear and safe response when the reader cannot serve content.

### Acceptance criteria

1. WHEN primary dependencies fail and no safe fallback exists THEN the system SHALL return `503 Service Unavailable` or the project-standard temporary unavailable response.
2. WHEN unavailable response is returned THEN it SHALL include a public-safe message.
3. WHEN unavailable response is returned THEN it SHALL not expose internal dependency names unless explicitly allowed.
4. WHEN unavailable response is returned THEN it SHALL not expose stack traces, storage paths, database errors, credentials, or raw exception messages.
5. WHEN unavailable response is returned THEN it SHOULD avoid long-lived caching.
6. WHEN unavailable response is returned for a known unpublished/takedown case THEN existing not-found/unavailable semantics SHALL be preserved.

## Requirement 9: Response metadata and headers

### User story

As a frontend developer, I want safe metadata indicating degraded or fallback state so the UI can display a temporary notice later.

### Acceptance criteria

1. WHEN normal response is returned THEN degraded/fallback metadata SHALL be false or absent according to response contract.
2. WHEN fallback snapshot is served THEN the response SHALL include safe degraded/fallback indicator.
3. WHEN a stale snapshot is served THEN the response SHALL include safe stale indicator or snapshot generated time.
4. WHEN optional features fail but core content succeeds THEN the response MAY include safe degraded metadata.
5. WHEN metadata is included THEN it SHALL not expose internal hostnames, credentials, storage paths, or stack traces.
6. WHEN response headers are used instead of body metadata THEN they SHALL be safe and documented.
7. WHEN old clients ignore metadata THEN reader rendering SHALL still work.

## Requirement 10: Cache compatibility

### User story

As an operator, I want degradation behavior to work with existing reader caches without resurrecting removed content.

### Acceptance criteria

1. WHEN public reader cache exists THEN fallback behavior SHALL respect its invalidation rules.
2. WHEN content is unpublished THEN cached fallback content SHALL be invalidated, deleted, or blocked by tombstone.
3. WHEN content is taken down THEN cached fallback content SHALL be invalidated, deleted, or blocked by tombstone.
4. WHEN a fallback response is cached THEN it SHALL be cached only according to safe fallback cache policy.
5. WHEN a 503 unavailable response is returned THEN it SHALL not be cached for a long duration.
6. WHEN cache entries are stale and not allowed by policy THEN they SHALL not be served.
7. WHEN cache lookup fails THEN the system SHALL fail safely.

## Requirement 11: Admin/operator status

### User story

As an admin, I want visibility into public reader degradation so I can diagnose outages.

### Acceptance criteria

1. WHEN admin resilience status is implemented THEN it SHALL be admin-only.
2. WHEN admin resilience status is requested by admin THEN it SHALL show circuit breaker states.
3. WHEN admin resilience status is requested by admin THEN it SHOULD show recent fallback and unavailable counts.
4. WHEN admin resilience status is requested by admin THEN it SHOULD show last safe error category.
5. WHEN public users request admin resilience status THEN access SHALL be denied.
6. WHEN admin status includes error details THEN they SHALL be redacted.
7. WHEN no admin endpoint is implemented THEN a service method SHALL still expose status for future health/metrics integration.

## Requirement 12: Observability

### User story

As an operator, I want logs for fallback and degradation events so outages can be investigated.

### Acceptance criteria

1. WHEN a public reader dependency fails THEN the system SHALL log a safe degradation event.
2. WHEN fallback snapshot is served THEN the system SHALL log a safe fallback event.
3. WHEN fallback is unavailable THEN the system SHALL log a safe unavailable event.
4. WHEN a circuit breaker opens, half-opens, or closes THEN the system SHALL log a safe circuit event.
5. WHEN optional feature failure is ignored THEN the system SHALL log a safe optional-feature failure event.
6. WHEN logs include content identifiers THEN they SHALL use public-safe IDs or redacted values.
7. WHEN logs include errors THEN they SHALL not include full chapter text, private metadata, credentials, or stack traces in user-visible responses.

## Requirement 13: Security and privacy

### User story

As an operator, I want graceful degradation to be safe because fallback systems can accidentally bypass normal checks.

### Acceptance criteria

1. WHEN fallback is used THEN it SHALL never serve private raw storage content.
2. WHEN fallback is used THEN it SHALL never serve unpublished content.
3. WHEN fallback is used THEN it SHALL never serve takedown-blocked content.
4. WHEN fallback is used THEN it SHALL never include admin notes or private glossary data.
5. WHEN fallback errors occur THEN public responses SHALL never expose secrets.
6. WHEN circuit breaker or dependency state is exposed publicly THEN it SHALL be limited to safe degraded/unavailable indicators.
7. WHEN fallback safety cannot be established THEN the system SHALL prefer unavailable over serving content.

## Requirement 14: Test coverage

### User story

As a maintainer, I want tests proving public reader degradation is safe and reliable.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover normal reader response unchanged.
2. WHEN tests run THEN they SHALL cover catalog/database timeout.
3. WHEN tests run THEN they SHALL cover storage/object-storage failure.
4. WHEN tests run THEN they SHALL cover safe snapshot fallback.
5. WHEN tests run THEN they SHALL cover no-snapshot unavailable response.
6. WHEN tests run THEN they SHALL cover stale snapshot allowed and disallowed behavior.
7. WHEN tests run THEN they SHALL cover unpublished content not served by fallback.
8. WHEN tests run THEN they SHALL cover takedown/tombstone blocking fallback.
9. WHEN tests run THEN they SHALL cover optional feature failure.
10. WHEN tests run THEN they SHALL cover circuit breaker open, half-open, and close behavior.
11. WHEN tests run THEN they SHALL cover public error redaction.
12. WHEN tests run THEN they SHALL cover cache invalidation compatibility where practical.
13. WHEN admin status endpoint is implemented THEN tests SHALL cover authorization and redaction.

## Requirement 15: Completion verification

### User story

As an operator, I want a clear verification path so graceful degradation is only complete when safe fallback works.

### Acceptance criteria

1. WHEN primary reader storage is failed in staging and a safe snapshot exists THEN the public reader SHALL serve fallback.
2. WHEN primary reader storage is failed in staging and no snapshot exists THEN the public reader SHALL return safe unavailable response.
3. WHEN catalog lookup fails and publication state cannot be safely verified THEN fallback SHALL not serve unsafe content.
4. WHEN content is unpublished or tombstoned THEN fallback SHALL not serve it.
5. WHEN optional annotation lookup fails THEN the chapter SHALL still load.
6. WHEN repeated failures occur THEN circuit breaker SHALL open.
7. WHEN dependency recovers THEN circuit breaker SHALL close after successful probe.
8. WHEN public responses are inspected THEN they SHALL not expose internal errors or secrets.
