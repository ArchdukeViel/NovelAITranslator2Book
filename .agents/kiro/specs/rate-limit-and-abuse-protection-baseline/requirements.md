# requirements.md

# Requirements: Rate Limit and Abuse Protection Baseline

## Introduction

The application needs baseline rate limiting and abuse protection for public, authenticated, and admin endpoints. The system must prevent obvious request flooding, form spam, brute-force attempts, and resource exhaustion while preserving legitimate reader and user flows.

## Requirement 1: Central rate-limit framework

### User story

As a maintainer, I want centralized rate limiting so endpoint protections are consistent and configurable.

### Acceptance criteria

1. WHEN rate limiting is enabled THEN requests SHALL be evaluated against a configured policy.
2. WHEN rate limiting is disabled THEN the limiter SHALL become no-op except for request size guards if separately enabled.
3. WHEN a route has a specific policy THEN that policy SHALL be applied.
4. WHEN a route has no specific policy THEN the default policy SHALL be applied where appropriate.
5. WHEN a request exceeds its limit THEN the system SHALL return `429 Too Many Requests`.
6. WHEN a request is allowed THEN it SHALL proceed normally.
7. WHEN rate-limit configuration is invalid THEN the system SHALL surface a startup/configuration error or fail safely.
8. WHEN rate-limit code fails unexpectedly THEN it SHALL follow configured fail-open/fail-closed behavior.

## Requirement 2: Rate-limit store

### User story

As an operator, I want rate-limit counters stored reliably so limits work across requests and instances.

### Acceptance criteria

1. WHEN a rate-limited request is evaluated THEN the system SHALL increment or check a counter in the configured store.
2. WHEN Redis or shared store is configured THEN limits SHALL work across application instances.
3. WHEN in-memory store is used THEN the system SHALL document that limits are per-process.
4. WHEN a counter window expires THEN old counts SHALL no longer affect new requests.
5. WHEN store access fails THEN the system SHALL apply configured failure behavior.
6. WHEN store keys are created THEN they SHALL not expose raw IP addresses, emails, tokens, or passwords.
7. WHEN tests run THEN store behavior SHALL be covered with fake or test store.

## Requirement 3: Rate-limit identity keys

### User story

As an operator, I want limits applied to the right identity so users are protected without unnecessary blocking.

### Acceptance criteria

1. WHEN a user is authenticated THEN user-based limits SHALL use authenticated user identity where appropriate.
2. WHEN a user is anonymous THEN limits SHALL use a privacy-safe IP/session/anonymous key.
3. WHEN IP address is used THEN it SHALL be hashed before storage/logging where practical.
4. WHEN account identifiers are used for auth protection THEN they SHALL be normalized and hashed.
5. WHEN a request comes through a proxy THEN the system SHALL only trust forwarded IP headers from trusted proxies.
6. WHEN rate-limit key is included in logs or store keys THEN it SHALL not reveal raw private identifiers.
7. WHEN key resolution fails THEN the system SHALL fall back to a conservative safe key or fail safely.

## Requirement 4: Public reader limits

### User story

As a reader, I want public reader pages to remain available while abusive high-volume traffic is controlled.

### Acceptance criteria

1. WHEN public reader requests are below configured limit THEN they SHALL be allowed.
2. WHEN public reader requests exceed configured limit THEN the system SHALL return `429`.
3. WHEN public reader limits are configured THEN they SHALL be generous enough for normal reading and browser navigation.
4. WHEN public reader fallback/snapshot endpoints exist THEN they SHALL be covered by public reader policy.
5. WHEN public reader request is rate-limited THEN response SHALL not expose internal limiter details.
6. WHEN rate-limit store fails for public read endpoints THEN behavior SHALL follow configured public read fail-open/fail-closed policy.
7. WHEN tests run THEN public reader allow and block behavior SHALL be covered.

## Requirement 5: Public search limits

### User story

As an operator, I want search endpoints protected because search can be expensive and scrape-prone.

### Acceptance criteria

1. WHEN search requests are below configured limit THEN they SHALL be allowed.
2. WHEN search requests exceed configured limit THEN the system SHALL return `429`.
3. WHEN search request includes page size THEN the system SHALL enforce maximum page size.
4. WHEN search request includes unsupported filters THEN they SHALL be rejected or ignored safely.
5. WHEN search request includes excessive pagination offset/page THEN it SHALL be rejected or capped.
6. WHEN search request is logged for abuse THEN raw query text SHALL not be logged by default.
7. WHEN tests run THEN search throttling, max page size, and unsafe logging behavior SHALL be covered.

## Requirement 6: Analytics ingestion protection

### User story

As an operator, I want analytics ingestion protected from spam and storage exhaustion.

### Acceptance criteria

1. WHEN analytics ingestion is below configured limit THEN events SHALL be accepted according to analytics validation.
2. WHEN analytics ingestion exceeds configured limit THEN the endpoint SHALL return `429` or safely drop according to policy.
3. WHEN analytics ingestion request contains too many events THEN it SHALL be rejected or truncated according to policy.
4. WHEN analytics ingestion request body is too large THEN it SHALL be rejected.
5. WHEN analytics ingestion metadata is oversized THEN it SHALL be rejected or sanitized by analytics validation.
6. WHEN analytics ingestion is rate-limited THEN core app behavior SHALL remain unaffected.
7. WHEN tests run THEN ingestion rate limit, batch size, and request size behavior SHALL be covered.

## Requirement 7: Contact/support/report form protection

### User story

As an operator, I want support forms protected from spam.

### Acceptance criteria

1. WHEN a contact/support/report form submission is below configured limit THEN it SHALL be accepted according to normal validation.
2. WHEN submissions exceed configured limit THEN the system SHALL return `429`.
3. WHEN form body exceeds configured size THEN the system SHALL return `413` or validation error according to project policy.
4. WHEN honeypot field is implemented and filled THEN submission SHALL be rejected or silently dropped according to policy.
5. WHEN form spam is detected THEN the system SHALL log a safe abuse event.
6. WHEN form is rate-limited THEN response SHALL not reveal internal spam scoring details.
7. WHEN tests run THEN form rate limit and size limit behavior SHALL be covered.

## Requirement 8: Auth endpoint protection

### User story

As a user, I want login and account endpoints protected from brute-force attempts.

### Acceptance criteria

1. WHEN login attempts exceed configured IP-based limit THEN login SHALL be rate-limited.
2. WHEN login attempts exceed configured account-identifier limit THEN login SHALL be rate-limited.
3. WHEN password reset requests exceed configured limit THEN requests SHALL be rate-limited.
4. WHEN registration attempts exceed configured limit THEN registration SHALL be rate-limited.
5. WHEN auth requests are rate-limited THEN response SHALL not reveal whether an account exists.
6. WHEN account identifiers are used in limiter keys THEN they SHALL be hashed.
7. WHEN trusted admin or allowlisted IP exists THEN auth brute-force protection SHALL not be bypassed by default unless explicitly configured.
8. WHEN tests run THEN login, password reset, and registration protection SHALL be covered.

## Requirement 9: Export protection

### User story

As an operator, I want export generation protected because exports can consume CPU, memory, and storage.

### Acceptance criteria

1. WHEN export creation requests are below configured limit THEN they SHALL be accepted according to existing export validation.
2. WHEN export creation requests exceed configured limit THEN they SHALL return `429`.
3. WHEN export downloads exceed configured limit THEN they MAY be rate-limited according to configured policy.
4. WHEN an export job for the same target/format is already running THEN the system SHOULD dedupe, reject, or return existing job according to existing job policy.
5. WHEN export request payload is too large THEN it SHALL be rejected.
6. WHEN export is rate-limited THEN no export job SHALL be enqueued.
7. WHEN tests run THEN export create/download limit behavior SHALL be covered.

## Requirement 10: Translation/crawl/import job protection

### User story

As an operator, I want job creation endpoints protected so users cannot flood workers and queues.

### Acceptance criteria

1. WHEN translation job creation is below configured limit THEN it SHALL be accepted according to normal validation.
2. WHEN translation job creation exceeds configured limit THEN it SHALL return `429`.
3. WHEN crawl/import/add-novel job creation is below configured limit THEN it SHALL be accepted according to normal validation.
4. WHEN crawl/import/add-novel job creation exceeds configured limit THEN it SHALL return `429`.
5. WHEN queue depth exceeds configured acceptance threshold THEN job creation MAY be rejected with a safe busy/limited response.
6. WHEN duplicate job exists for the same target THEN the system SHOULD dedupe or reject according to job policy.
7. WHEN rate-limited THEN no job SHALL be enqueued.
8. WHEN tests run THEN translation and crawl/import job limit behavior SHALL be covered.

## Requirement 11: Admin API protection

### User story

As an operator, I want admin APIs protected from accidental or malicious high-volume calls without blocking legitimate admin use.

### Acceptance criteria

1. WHEN admin API requests are below configured limit THEN they SHALL be allowed.
2. WHEN admin API requests exceed configured limit THEN they SHALL return `429`.
3. WHEN admin APIs are rate-limited THEN they SHALL still require normal admin authorization.
4. WHEN admin requests are logged for rate limits THEN logs SHALL be safe and avoid sensitive payloads.
5. WHEN an emergency bypass exists THEN it SHALL be explicitly configured and audited.
6. WHEN tests run THEN admin API limit and authorization interaction SHALL be covered.

## Requirement 12: Request body size limits

### User story

As an operator, I want request size limits so large payloads cannot exhaust memory or storage.

### Acceptance criteria

1. WHEN a request body exceeds the configured global maximum THEN the system SHALL reject it.
2. WHEN an endpoint has a stricter body size limit THEN that endpoint limit SHALL apply.
3. WHEN analytics ingestion body is too large THEN it SHALL be rejected.
4. WHEN contact/support form body is too large THEN it SHALL be rejected.
5. WHEN export/job creation payload is too large THEN it SHALL be rejected.
6. WHEN request body is rejected due to size THEN the system SHALL return `413 Payload Too Large` or project-standard equivalent.
7. WHEN body size error is returned THEN it SHALL not echo the body.
8. WHEN tests run THEN body size limits SHALL be covered.

## Requirement 13: Rate-limited response format

### User story

As an API client, I want clear safe responses when I am rate-limited.

### Acceptance criteria

1. WHEN a request is rate-limited THEN response SHALL use HTTP `429`.
2. WHEN a request is rate-limited THEN response body SHALL include a safe error code such as `rate_limited`.
3. WHEN a request is rate-limited THEN response body SHALL include a generic safe message.
4. WHEN retry time is known THEN response SHOULD include `Retry-After`.
5. WHEN rate-limit headers are enabled THEN response MAY include safe limit/remaining/reset headers.
6. WHEN a request is rate-limited THEN response SHALL not include internal store keys.
7. WHEN a request is rate-limited THEN response SHALL not include raw IP, user ID, or account identifier.
8. WHEN tests run THEN response format SHALL be covered.

## Requirement 14: Store failure behavior

### User story

As an operator, I want predictable behavior when the rate-limit store is unavailable.

### Acceptance criteria

1. WHEN limiter store fails for public read endpoints THEN behavior SHALL follow configured public-read failure policy.
2. WHEN limiter store fails for auth endpoints THEN the system SHALL fail closed or use conservative fallback according to config.
3. WHEN limiter store fails for job-creation endpoints THEN the system SHALL fail closed or use conservative fallback according to config.
4. WHEN limiter store fails for admin endpoints THEN the system SHALL fail closed or use conservative fallback according to config.
5. WHEN limiter store failure occurs THEN the system SHALL log a safe warning.
6. WHEN store failure is user-facing THEN response SHALL be safe and not expose backend details.
7. WHEN tests run THEN fail-open and fail-closed behavior SHALL be covered.

## Requirement 15: Trusted proxy handling

### User story

As an operator, I want correct client identity behind proxies so rate limits cannot be bypassed with spoofed headers.

### Acceptance criteria

1. WHEN trusted proxy handling is disabled THEN the system SHALL ignore forwarded IP headers.
2. WHEN trusted proxy handling is enabled THEN forwarded IP headers SHALL be trusted only from configured proxy networks.
3. WHEN a request comes from an untrusted source THEN client-supplied forwarded headers SHALL not control rate-limit identity.
4. WHEN IPv6 addresses are used THEN identity normalization SHALL be stable.
5. WHEN IP identity is stored/logged THEN it SHALL be hashed where practical.
6. WHEN tests run THEN trusted, untrusted, and spoofed forwarded header behavior SHALL be covered.

## Requirement 16: Allowlist and bypass controls

### User story

As an operator, I want explicit allowlists for trusted internal services without accidentally bypassing sensitive protections.

### Acceptance criteria

1. WHEN an allowlisted internal health check calls the app THEN it MAY bypass selected limits.
2. WHEN an allowlist entry is configured THEN it SHALL be explicit.
3. WHEN bypass is used THEN the system SHOULD log a safe bypass event.
4. WHEN bypass is enabled THEN auth brute-force protection SHALL not be bypassed unless explicitly configured.
5. WHEN a bypass config is invalid THEN the system SHALL reject it or fail safely.
6. WHEN tests run THEN allowlist and non-allowlist behavior SHALL be covered.

## Requirement 17: Abuse logging

### User story

As an operator, I want safe logs for abuse events so issues can be diagnosed.

### Acceptance criteria

1. WHEN a request is rate-limited THEN the system SHALL log a safe abuse event.
2. WHEN a request body is too large THEN the system SHOULD log a safe abuse event.
3. WHEN suspicious repeated invalid requests are detected THEN the system MAY log a safe abuse event.
4. WHEN abuse event is logged THEN it SHALL include route template and policy key.
5. WHEN abuse event is logged THEN it MAY include actor/session/IP hash.
6. WHEN abuse event is logged THEN it SHALL not include passwords, tokens, raw request bodies, raw IP addresses, raw query strings, or private content.
7. WHEN abuse logs are high-volume THEN they SHOULD be rate-limited or sampled where practical.
8. WHEN tests run THEN safe logging behavior SHALL be covered where project test conventions support it.

## Requirement 18: Admin status visibility

### User story

As an admin, I want basic visibility into rate-limit configuration and recent limiting so I can diagnose issues.

### Acceptance criteria

1. WHEN admin status endpoint is implemented THEN it SHALL require admin authorization.
2. WHEN admin requests rate-limit status THEN it SHALL show whether rate limiting is enabled.
3. WHEN admin requests rate-limit status THEN it SHALL show configured policy keys and limits.
4. WHEN recent rate-limited counts are available THEN status SHOULD include aggregate counts.
5. WHEN store status is available THEN status SHOULD include safe store health.
6. WHEN non-admin requests status THEN access SHALL be blocked.
7. WHEN status is returned THEN it SHALL not expose raw IPs, emails, tokens, or request bodies.

## Requirement 19: Test coverage

### User story

As a maintainer, I want tests for rate limits and abuse protection so endpoint protections do not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover default policy allow and block behavior.
2. WHEN tests run THEN they SHALL cover endpoint-specific policies.
3. WHEN tests run THEN they SHALL cover authenticated user keys.
4. WHEN tests run THEN they SHALL cover anonymous/IP-hash keys.
5. WHEN tests run THEN they SHALL cover auth endpoint brute-force keys.
6. WHEN tests run THEN they SHALL cover request body size limits.
7. WHEN tests run THEN they SHALL cover analytics ingestion protection.
8. WHEN tests run THEN they SHALL cover contact form protection.
9. WHEN tests run THEN they SHALL cover export/job creation protection.
10. WHEN tests run THEN they SHALL cover store failure behavior.
11. WHEN tests run THEN they SHALL cover trusted proxy behavior.
12. WHEN tests run THEN they SHALL cover allowlist behavior.
13. WHEN tests run THEN they SHALL cover response format.
14. WHEN tests run THEN they SHALL cover safe abuse logging.
15. WHEN admin status endpoint is implemented THEN tests SHALL cover authorization and response safety.

## Requirement 20: Completion verification

### User story

As an operator, I want a clear verification path so abuse protection is complete only when high-risk endpoints are protected safely.

### Acceptance criteria

1. WHEN repeated public search requests exceed the limit THEN requests SHALL return `429`.
2. WHEN repeated analytics ingestion requests exceed the limit THEN requests SHALL return `429` or be dropped according to policy.
3. WHEN repeated login attempts exceed the limit THEN login SHALL be rate-limited without revealing account existence.
4. WHEN repeated export creation requests exceed the limit THEN no extra export jobs SHALL be queued.
5. WHEN repeated translation/crawl job requests exceed the limit THEN no extra jobs SHALL be queued.
6. WHEN a request body exceeds endpoint limit THEN request SHALL be rejected safely.
7. WHEN legitimate public reader navigation occurs below limits THEN it SHALL not be blocked.
8. WHEN abuse logs are inspected THEN they SHALL not contain raw IPs, tokens, passwords, request bodies, or private text.
9. WHEN rate-limit store failure is simulated THEN behavior SHALL match configured fail-open/fail-closed policy.
