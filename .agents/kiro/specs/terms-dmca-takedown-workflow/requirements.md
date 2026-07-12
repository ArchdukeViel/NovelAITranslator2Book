# requirements.md

# Requirements: Terms DMCA Takedown Workflow

## Introduction

The system needs an operational takedown workflow for public legal/DMCA requests. It must capture submissions, support admin review, apply public content restrictions, invalidate caches and sitemap entries, audit decisions, and avoid exposing private legal details.

## Requirement 1: Public takedown intake

### User story

As a rights holder or reporter, I want to submit a takedown request so the site can review allegedly infringing or problematic public content.

### Acceptance criteria

1. WHEN public takedown intake is enabled THEN a submission endpoint SHALL accept takedown requests.
2. WHEN a valid takedown request is submitted THEN the system SHALL create a takedown request record.
3. WHEN a request includes public URLs THEN the system SHALL store those URLs safely.
4. WHEN a URL maps to known content THEN the system SHOULD record the matched target.
5. WHEN a URL cannot be matched THEN the system SHALL still store the request for manual review.
6. WHEN submission succeeds THEN the submitter SHALL receive a safe confirmation response.
7. WHEN public intake is disabled THEN the endpoint SHALL return a safe unavailable response or hide the form.
8. WHEN tests run THEN valid and unmatched submissions SHALL be covered.

## Requirement 2: Intake validation

### User story

As an operator, I want takedown submissions validated so incomplete or abusive requests are controlled.

### Acceptance criteria

1. WHEN a takedown request is submitted THEN contact email SHALL be required.
2. WHEN a takedown request is submitted THEN description or reason SHALL be required.
3. WHEN a DMCA-like request is submitted THEN signature or typed name SHALL be required if configured.
4. WHEN a DMCA-like request is submitted THEN good-faith statement SHALL be required if configured.
5. WHEN a DMCA-like request is submitted THEN accuracy statement SHALL be required if configured.
6. WHEN too many URLs are submitted THEN the request SHALL be rejected or truncated according to policy.
7. WHEN submission exceeds body size or field length limits THEN it SHALL be rejected safely.
8. WHEN validation fails THEN the response SHALL show safe field/form errors.
9. WHEN tests run THEN required fields and size limits SHALL be covered.

## Requirement 3: Abuse protection for intake

### User story

As an operator, I want public takedown intake protected from spam and abuse.

### Acceptance criteria

1. WHEN takedown submissions exceed configured rate limits THEN the system SHALL reject or throttle them.
2. WHEN submission body exceeds configured size THEN the system SHALL reject it.
3. WHEN honeypot/spam checks are implemented THEN spam submissions SHALL be rejected or dropped according to policy.
4. WHEN attachments are not supported THEN the endpoint SHALL reject attachments.
5. WHEN attachments are supported THEN size/type restrictions SHALL apply.
6. WHEN abuse is detected THEN safe abuse logging SHOULD occur.
7. WHEN tests run THEN rate limit and size limit behavior SHALL be covered.

## Requirement 4: Takedown request data model

### User story

As an admin, I want takedown requests stored with enough information for review.

### Acceptance criteria

1. WHEN a request is stored THEN it SHALL have a unique ID.
2. WHEN a request is stored THEN it SHALL include request type.
3. WHEN a request is stored THEN it SHALL include status.
4. WHEN a request is stored THEN it SHALL include submitter contact details.
5. WHEN a request is stored THEN it SHALL include reported URLs or description.
6. WHEN a request is stored THEN it MAY include matched target type and target ID.
7. WHEN a request is stored THEN it SHALL include timestamps.
8. WHEN sensitive request fields are exposed through APIs THEN they SHALL be admin-only.
9. WHEN tests run THEN request persistence and defaults SHALL be covered.

## Requirement 5: Admin takedown list

### User story

As an admin, I want to view takedown requests so I can triage and review them.

### Acceptance criteria

1. WHEN an admin opens the takedown admin page THEN requests SHALL be listed.
2. WHEN requests exist THEN they SHALL be shown in newest-first order by default.
3. WHEN no requests exist THEN an empty state SHALL be shown.
4. WHEN requests are loading THEN a loading state SHALL be shown.
5. WHEN loading fails THEN a safe error state SHALL be shown.
6. WHEN list renders THEN it SHALL show type, submitter, target, status, enforcement state, and submitted time where available.
7. WHEN non-admin attempts to view the list THEN access SHALL be blocked.

## Requirement 6: Admin takedown detail

### User story

As an admin, I want a detail view for each request so I can evaluate it.

### Acceptance criteria

1. WHEN an admin opens a takedown request detail THEN full admin-safe details SHALL be shown.
2. WHEN detail renders THEN it SHALL show request overview.
3. WHEN detail renders THEN it SHALL show submitter/claimant information.
4. WHEN detail renders THEN it SHALL show reported URLs and matched targets.
5. WHEN detail renders THEN it SHALL show statements/signature fields where available.
6. WHEN admin notes exist THEN they SHALL be visible only to admins.
7. WHEN detail load fails THEN a safe error state SHALL be shown.
8. WHEN non-admin attempts to view detail THEN access SHALL be blocked.

## Requirement 7: Admin workflow transitions

### User story

As an admin, I want clear status transitions so request handling is tracked.

### Acceptance criteria

1. WHEN a request is submitted THEN initial status SHALL be `submitted`.
2. WHEN an admin triages a request THEN status MAY change to `triaged`.
3. WHEN more information is needed THEN status MAY change to `needs_more_info`.
4. WHEN review begins THEN status MAY change to `under_review`.
5. WHEN a takedown is approved THEN status SHALL change to `accepted`.
6. WHEN a request is rejected THEN status SHALL change to `rejected`.
7. WHEN a request is withdrawn THEN status MAY change to `withdrawn`.
8. WHEN a counter-notice is received THEN status MAY change to `counter_notice_received`.
9. WHEN content is restored THEN status MAY change to `restored`.
10. WHEN workflow is complete THEN status MAY change to `closed`.
11. WHEN invalid transition is attempted THEN the system SHALL reject it safely.
12. WHEN status changes THEN audit logging SHALL occur.

## Requirement 8: Content enforcement state

### User story

As an operator, I want takedown decisions to affect public content availability.

### Acceptance criteria

1. WHEN takedown is not active THEN enforcement state SHALL be `none` or equivalent.
2. WHEN content is temporarily hidden THEN enforcement state SHALL be `temporarily_hidden`.
3. WHEN takedown is active THEN enforcement state SHALL be `takedown_active`.
4. WHEN content is restored THEN enforcement state SHALL be `restored` or cleared according to policy.
5. WHEN enforcement state is active THEN public reader SHALL not serve restricted content.
6. WHEN enforcement state is active THEN public APIs SHALL not return restricted content text.
7. WHEN enforcement state changes THEN audit logging SHALL occur.
8. WHEN tests run THEN each enforcement state SHALL be covered.

## Requirement 9: Public tombstone behavior

### User story

As a public reader, I should see a safe unavailable page when content has been taken down.

### Acceptance criteria

1. WHEN a public novel is under active takedown THEN public access SHALL return unavailable/tombstone behavior.
2. WHEN a public chapter is under active takedown THEN public access SHALL return unavailable/tombstone behavior.
3. WHEN a tombstone page is shown THEN it SHALL use a generic public-safe message.
4. WHEN configured status is 451 THEN active takedown SHALL return `451 Unavailable For Legal Reasons`.
5. WHEN configured status is 404 THEN active takedown SHALL return `404 Not Found`.
6. WHEN tombstone is shown THEN it SHALL not expose claimant details, admin notes, private metadata, or legal reasoning.
7. WHEN content is restored and still published THEN normal public access MAY resume.
8. WHEN tests run THEN public tombstone behavior SHALL be covered.

## Requirement 10: Public reader and API blocking

### User story

As an operator, I want taken-down content blocked consistently across public surfaces.

### Acceptance criteria

1. WHEN a taken-down chapter is requested through public chapter API THEN chapter text SHALL not be returned.
2. WHEN a taken-down novel is requested through public novel API THEN restricted content SHALL not be returned.
3. WHEN public search/discovery includes content under active takedown THEN it SHALL exclude that content.
4. WHEN public reader fallback/snapshot exists THEN it SHALL not serve taken-down content.
5. WHEN glossary annotations exist for taken-down content THEN they SHALL not be returned publicly.
6. WHEN analytics/SEO routes request taken-down content THEN they SHALL not expose content details.
7. WHEN tests run THEN all public access paths SHALL be covered.

## Requirement 11: Cache invalidation

### User story

As an operator, I want takedown enforcement to purge cached public content.

### Acceptance criteria

1. WHEN takedown is applied THEN public reader cache SHALL be invalidated or bypassed.
2. WHEN takedown is applied THEN public projection cache SHALL be invalidated where applicable.
3. WHEN takedown is applied THEN public API cache SHALL be invalidated.
4. WHEN takedown is applied THEN sitemap cache SHALL be invalidated.
5. WHEN takedown is applied THEN SEO metadata cache SHALL be invalidated.
6. WHEN takedown is restored THEN affected caches SHALL be invalidated or rebuilt.
7. WHEN cache invalidation fails THEN the system SHALL fail the action or log a critical warning according to policy.
8. WHEN tests run THEN stale cache exposure after takedown SHALL be covered.

## Requirement 12: Sitemap and SEO exclusion

### User story

As an operator, I want taken-down content removed from discovery surfaces.

### Acceptance criteria

1. WHEN content is under active takedown THEN it SHALL be excluded from sitemap.
2. WHEN content is under active takedown THEN it SHALL be noindex if a public page is shown.
3. WHEN content is under active takedown THEN Open Graph/Twitter metadata SHALL not expose private content.
4. WHEN content is restored and published THEN it MAY become eligible for sitemap again.
5. WHEN content is restored but unpublished/private THEN it SHALL remain excluded.
6. WHEN tests run THEN sitemap exclusion and noindex behavior SHALL be covered.

## Requirement 13: Export/download blocking

### User story

As an operator, I want exports for taken-down content unavailable publicly.

### Acceptance criteria

1. WHEN a novel is under active takedown THEN public export/download access SHALL be disabled.
2. WHEN a chapter-specific export is under active takedown THEN public export/download access SHALL be disabled.
3. WHEN export access is disabled THEN response SHALL be safe and generic.
4. WHEN admin views export metadata THEN admin access MAY remain available according to policy.
5. WHEN takedown is restored THEN export access MAY resume only if content is still published and policy allows.
6. WHEN tests run THEN public export/download blocking SHALL be covered.

## Requirement 14: Notifications

### User story

As an operator, I want relevant parties notified when takedown requests are submitted or decided.

### Acceptance criteria

1. WHEN a takedown request is submitted THEN admins SHOULD receive a notification if notification system exists.
2. WHEN a submitter provides email and email delivery exists THEN submitter MAY receive confirmation.
3. WHEN takedown is accepted/applied THEN content owner MAY be notified if owner model exists.
4. WHEN takedown is rejected THEN submitter MAY be notified according to policy.
5. WHEN notification is sent THEN it SHALL not include private admin notes.
6. WHEN notification fails THEN takedown workflow SHALL still persist the decision.
7. WHEN tests run THEN notification behavior SHALL be covered where implemented.

## Requirement 15: Audit logging

### User story

As a security-conscious operator, I want takedown workflow actions audited.

### Acceptance criteria

1. WHEN takedown request is submitted THEN an audit event SHALL be recorded.
2. WHEN admin changes request status THEN an audit event SHALL be recorded.
3. WHEN admin applies takedown enforcement THEN an audit event SHALL be recorded.
4. WHEN admin restores content THEN an audit event SHALL be recorded.
5. WHEN admin rejects a request THEN an audit event SHALL be recorded.
6. WHEN counter-notice is recorded THEN an audit event SHALL be recorded.
7. WHEN audit event is recorded THEN it SHALL include safe request/target/status fields.
8. WHEN audit event is recorded THEN it SHALL not include full legal request body, private text, prompts, secrets, or sensitive claimant details unless policy allows.
9. WHEN tests run THEN audit events SHALL be covered.

## Requirement 16: Redaction and privacy

### User story

As an operator, I want legal request details protected from public exposure.

### Acceptance criteria

1. WHEN public response is returned THEN it SHALL not include submitter private contact details.
2. WHEN public response is returned THEN it SHALL not include claimant private details.
3. WHEN public response is returned THEN it SHALL not include admin notes.
4. WHEN public response is returned THEN it SHALL not include internal target IDs unless already public-safe.
5. WHEN admin APIs return request details THEN only admins SHALL access them.
6. WHEN logs are emitted THEN sensitive request fields SHALL be redacted or omitted.
7. WHEN tests provide sensitive request data THEN it SHALL not appear in public responses or unsafe logs.

## Requirement 17: Admin authorization

### User story

As an operator, I want only admins to review and act on takedown requests.

### Acceptance criteria

1. WHEN unauthenticated user calls admin takedown APIs THEN response SHALL be `401`.
2. WHEN non-admin calls admin takedown APIs THEN response SHALL be `403`.
3. WHEN admin calls admin takedown APIs THEN access SHALL be allowed.
4. WHEN scoped permissions exist THEN takedown review SHALL require appropriate permission.
5. WHEN admin action is attempted by unauthorized user THEN no state change SHALL occur.
6. WHEN tests run THEN admin authorization SHALL be covered for list, detail, and actions.

## Requirement 18: Retention and cleanup

### User story

As an operator, I want takedown records retained according to legal policy.

### Acceptance criteria

1. WHEN takedown retention is configured THEN records SHALL be eligible for cleanup only after retention period.
2. WHEN retention is not configured THEN the system SHALL use a safe long-retention default.
3. WHEN cleanup exists THEN it SHALL not delete active takedown enforcement states.
4. WHEN cleanup exists THEN it SHALL preserve required audit history according to audit policy.
5. WHEN records are archived or deleted THEN public enforcement behavior SHALL remain correct.
6. WHEN tests run THEN retention behavior SHALL be covered if implemented.

## Requirement 19: Test coverage

### User story

As a maintainer, I want tests for the takedown workflow so public restriction behavior does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover public intake validation.
2. WHEN tests run THEN they SHALL cover public intake abuse protections.
3. WHEN tests run THEN they SHALL cover admin list/detail authorization.
4. WHEN tests run THEN they SHALL cover workflow status transitions.
5. WHEN tests run THEN they SHALL cover apply takedown.
6. WHEN tests run THEN they SHALL cover restore content.
7. WHEN tests run THEN they SHALL cover public reader/API blocking.
8. WHEN tests run THEN they SHALL cover cache invalidation.
9. WHEN tests run THEN they SHALL cover sitemap/SEO exclusion.
10. WHEN tests run THEN they SHALL cover export/download blocking.
11. WHEN tests run THEN they SHALL cover notifications where implemented.
12. WHEN tests run THEN they SHALL cover audit logging.
13. WHEN tests run THEN they SHALL cover redaction and privacy.

## Requirement 20: Completion verification

### User story

As an operator, I want a clear verification path so takedown workflow is complete only when public content can be removed safely.

### Acceptance criteria

1. WHEN a public takedown request is submitted THEN admin can see it in takedown queue.
2. WHEN admin accepts and applies takedown to a public chapter THEN public chapter text SHALL no longer be served.
3. WHEN public route is requested after takedown THEN generic tombstone/unavailable behavior SHALL be returned.
4. WHEN sitemap is requested after takedown THEN taken-down URL SHALL be absent.
5. WHEN SEO metadata is inspected after takedown THEN page SHALL be noindex or unavailable.
6. WHEN cached public reader response existed before takedown THEN it SHALL not continue serving content after takedown.
7. WHEN public export/download is requested after takedown THEN it SHALL be disabled.
8. WHEN admin restores content and content is still published THEN public access MAY resume.
9. WHEN audit logs are inspected THEN takedown actions SHALL be recorded safely.
10. WHEN public responses/logs are inspected THEN private legal details SHALL not be exposed.
