# requirements.md

# Requirements: Deployment Production Hardening

## Introduction

Production deployment must be safe, explicit, and observable. The system must validate production configuration, protect secrets, enforce secure headers/cookies/CORS/proxy rules, run migrations safely, configure workers/storage/backups correctly, and provide clear deployment, smoke-test, and rollback procedures.

## Requirement 1: Environment mode

### User story

As an operator, I want explicit environment modes so production behavior cannot accidentally use development settings.

### Acceptance criteria

1. WHEN `APP_ENV=production` THEN debug mode SHALL be disabled.
2. WHEN `APP_ENV=production` THEN production config validation SHALL run.
3. WHEN environment mode is missing THEN the app SHALL use a safe default or fail according to project policy.
4. WHEN environment mode is invalid THEN startup SHALL fail with a safe configuration error.
5. WHEN production mode is active THEN development-only endpoints/tools SHALL be disabled unless explicitly allowed.
6. WHEN tests run THEN environment mode behavior SHALL be covered.

## Requirement 2: Production configuration validation

### User story

As an operator, I want startup validation so dangerous production misconfiguration is caught before serving traffic.

### Acceptance criteria

1. WHEN production startup begins THEN required production variables SHALL be validated.
2. WHEN required config is missing THEN startup SHALL fail or report fatal readiness failure.
3. WHEN weak/default secrets are detected THEN startup SHALL fail in production.
4. WHEN insecure cookie settings are detected THEN startup SHALL fail in production.
5. WHEN wildcard credentialed CORS is detected THEN startup SHALL fail in production.
6. WHEN public site URL is missing or non-HTTPS THEN startup SHALL fail or warn according to policy.
7. WHEN storage/database/queue config is incomplete THEN startup SHALL fail or readiness SHALL be unhealthy.
8. WHEN validation produces warnings THEN they SHALL be visible in logs or admin health safely.

## Requirement 3: Secrets hardening

### User story

As an operator, I want production secrets protected from source control, frontend bundles, and logs.

### Acceptance criteria

1. WHEN production starts THEN required secrets SHALL not equal known defaults or placeholders.
2. WHEN frontend is built THEN backend-only secrets SHALL not be included in frontend bundle.
3. WHEN errors are logged THEN secrets SHALL be redacted.
4. WHEN config is displayed in admin health/status THEN secret values SHALL be omitted or redacted.
5. WHEN secret rotation is needed THEN documentation SHALL describe the rotation process.
6. WHEN tests inspect unsafe config/log paths THEN secrets SHALL not be exposed.
7. WHEN API/provider keys are missing for enabled features THEN startup or readiness SHALL report the issue safely.

## Requirement 4: TLS and trusted proxy handling

### User story

As an operator, I want TLS/proxy settings correct so URLs, cookies, and client IP handling are safe.

### Acceptance criteria

1. WHEN production public URL is configured THEN it SHALL use HTTPS.
2. WHEN app is behind a reverse proxy THEN trusted proxy settings SHALL be explicit.
3. WHEN forwarded headers are trusted THEN they SHALL be trusted only from configured proxy networks.
4. WHEN forwarded headers are not trusted THEN client-supplied forwarded headers SHALL be ignored.
5. WHEN secure cookies depend on HTTPS detection THEN proxy protocol handling SHALL be correct.
6. WHEN allowed hosts are configured THEN unknown host headers SHALL be rejected where supported.
7. WHEN tests run THEN trusted/untrusted forwarded header behavior SHALL be covered.

## Requirement 5: CORS and CSRF hardening

### User story

As a security-conscious operator, I want production cross-origin behavior restricted.

### Acceptance criteria

1. WHEN production CORS is enabled THEN allowed origins SHALL be explicit.
2. WHEN credentials are allowed THEN wildcard origins SHALL not be allowed.
3. WHEN admin APIs are called cross-origin THEN only approved origins SHALL be allowed.
4. WHEN cookie-auth write actions exist THEN CSRF protection SHALL be enabled or documented with an equivalent defense.
5. WHEN CSRF trusted origins are configured THEN they SHALL be explicit.
6. WHEN CORS/CSRF config is unsafe THEN production validation SHALL fail or warn according to severity.
7. WHEN tests run THEN allowed origin, blocked origin, and preflight behavior SHALL be covered.

## Requirement 6: Cookie and session security

### User story

As a user, I want session cookies protected in production.

### Acceptance criteria

1. WHEN production mode is active THEN session cookies SHALL use `Secure`.
2. WHEN session cookies are used THEN they SHALL use `HttpOnly`.
3. WHEN SameSite policy is configured THEN it SHALL be explicit.
4. WHEN cross-site cookies are used THEN `SameSite=None` SHALL require `Secure`.
5. WHEN user is disabled THEN existing sessions SHALL be invalidated or blocked according to auth policy.
6. WHEN admin session is revoked THEN admin access SHALL stop.
7. WHEN tests run THEN cookie/security behavior SHALL be covered where practical.

## Requirement 7: Security headers

### User story

As an operator, I want baseline security headers in production.

### Acceptance criteria

1. WHEN production responses are served THEN `X-Content-Type-Options: nosniff` SHALL be present.
2. WHEN production responses are served THEN referrer policy SHALL be present.
3. WHEN production responses are served THEN frame embedding policy SHALL be present through `X-Frame-Options` or CSP `frame-ancestors`.
4. WHEN HTTPS is enforced THEN HSTS SHOULD be enabled according to deployment policy.
5. WHEN CSP is implemented THEN it SHALL not break public reader/admin core flows.
6. WHEN CSP is not fully enforced THEN report-only mode MAY be used with documentation.
7. WHEN tests inspect headers THEN required security headers SHALL be present.

## Requirement 8: Database migration safety

### User story

As an operator, I want migrations to run safely so deploys do not corrupt production data.

### Acceptance criteria

1. WHEN deploying production version THEN migrations SHALL be run intentionally before or during deployment according to documented process.
2. WHEN migration fails THEN deployment SHALL stop or readiness SHALL fail.
3. WHEN destructive migration exists THEN backup/approval SHALL be required according to policy.
4. WHEN app starts in production THEN it SHALL not run unsafe migrations concurrently from multiple web processes.
5. WHEN schema version is outdated THEN readiness SHALL be unhealthy or warning according to policy.
6. WHEN rollback requires schema considerations THEN documentation SHALL describe the safe rollback path.
7. WHEN tests or checks run THEN migration status validation SHALL be covered.

## Requirement 9: Worker, queue, and scheduler production roles

### User story

As an operator, I want web, worker, and scheduler processes configured clearly.

### Acceptance criteria

1. WHEN production deploys THEN process roles SHALL be documented.
2. WHEN queue-backed jobs are enabled THEN worker process SHALL be configured.
3. WHEN workers run THEN concurrency SHALL be bounded.
4. WHEN schedulers run THEN duplicate scheduler execution SHALL be prevented through locks or single scheduler role.
5. WHEN maintenance cron is enabled THEN it SHALL run intentionally in one safe context.
6. WHEN backup scheduler is enabled THEN it SHALL run intentionally in one safe context.
7. WHEN queue is unavailable THEN readiness or admin health SHALL report it.
8. WHEN worker heartbeat is stale THEN health/admin status SHALL report it.
9. WHEN tests run THEN worker/scheduler config validation SHALL be covered where practical.

## Requirement 10: Storage production hardening

### User story

As an operator, I want storage configured so private and public files are separated safely.

### Acceptance criteria

1. WHEN production storage is configured THEN private source/draft files SHALL not be publicly readable.
2. WHEN public reader projections are used THEN they SHALL be stored in public-safe paths only.
3. WHEN public assets are served THEN they SHALL not require exposing private storage credentials.
4. WHEN signed URLs are used THEN they SHALL be short-lived and not embedded in public metadata.
5. WHEN takedown is applied THEN public storage/projection access SHALL be invalidated or blocked.
6. WHEN storage config is incomplete THEN startup/readiness SHALL fail or warn according to severity.
7. WHEN tests/checks run THEN storage visibility assumptions SHALL be verified where practical.

## Requirement 11: Public cache safety

### User story

As an operator, I want production caching to improve performance without leaking private or removed content.

### Acceptance criteria

1. WHEN public reader cache is enabled THEN only public published content SHALL be cacheable.
2. WHEN private/unpublished/preview content is requested THEN it SHALL not be publicly cached.
3. WHEN content is taken down THEN public caches SHALL be invalidated or bypassed.
4. WHEN glossary annotation settings change THEN affected public reader cache SHALL be invalidated or versioned.
5. WHEN public cache headers are emitted THEN they SHALL match publication safety policy.
6. WHEN cache config is unsafe THEN production validation SHALL warn or fail.
7. WHEN tests run THEN public/private cache behavior SHALL be covered where practical.

## Requirement 12: Backup and restore readiness

### User story

As an operator, I want backups configured and restorable before production launch.

### Acceptance criteria

1. WHEN production mode is active THEN backup configuration SHALL be validated.
2. WHEN scheduled backups are required THEN backup scheduler SHALL be enabled.
3. WHEN backup target is missing THEN readiness/admin health SHALL report unhealthy or warning according to policy.
4. WHEN backup retention is missing THEN safe default retention SHALL apply or validation SHALL fail.
5. WHEN backup encryption is required THEN encryption key SHALL be configured.
6. WHEN restore drill procedure is missing THEN deployment checklist SHALL flag it.
7. WHEN backup fails THEN admin health/status SHALL surface it safely.
8. WHEN tests/checks run THEN backup config validation SHALL be covered.

## Requirement 13: Observability and safe logging

### User story

As an operator, I want production issues diagnosable without exposing secrets or private content.

### Acceptance criteria

1. WHEN production logs are emitted THEN they SHOULD be structured.
2. WHEN requests are handled THEN request IDs SHALL be generated or propagated.
3. WHEN errors are logged THEN secrets/private content SHALL be redacted.
4. WHEN health checks run THEN they SHALL not log noisy secrets or payloads.
5. WHEN frontend error logging is enabled THEN logs SHALL be safe.
6. WHEN rate-limit/abuse logs are emitted THEN raw IPs/tokens/passwords SHALL not be logged.
7. WHEN tests inspect redaction paths THEN unsafe values SHALL not appear.

## Requirement 14: Health and readiness checks

### User story

As an operator, I want health endpoints that accurately reflect production readiness.

### Acceptance criteria

1. WHEN liveness is requested THEN it SHALL return lightweight process health.
2. WHEN readiness is requested THEN it SHALL check critical dependencies.
3. WHEN database is unavailable THEN readiness SHALL be unhealthy.
4. WHEN migrations are not current THEN readiness SHALL be unhealthy or degraded according to policy.
5. WHEN queue is required and unavailable THEN readiness SHALL be unhealthy or degraded.
6. WHEN storage is required and unavailable THEN readiness SHALL be unhealthy or degraded.
7. WHEN critical config is invalid THEN readiness SHALL be unhealthy.
8. WHEN admin health is requested by admin THEN detailed safe dependency status SHALL be shown.
9. WHEN tests run THEN health/readiness states SHALL be covered.

## Requirement 15: Production deployment gates

### User story

As a maintainer, I want deployment gates so broken builds are not promoted.

### Acceptance criteria

1. WHEN production deployment is attempted THEN tests SHALL pass.
2. WHEN production deployment is attempted THEN lint/type checks SHOULD pass according to project policy.
3. WHEN production deployment is attempted THEN build artifact SHALL be produced successfully.
4. WHEN production deployment is attempted THEN production config validation SHALL pass.
5. WHEN production deployment is attempted THEN migration validation SHALL pass or be explicitly approved.
6. WHEN production deployment is attempted THEN backup status SHALL be checked or exception documented.
7. WHEN deployment gate fails THEN deployment SHALL stop or require explicit override.
8. WHEN deployment override exists THEN it SHALL be documented and audited where practical.

## Requirement 16: Smoke tests

### User story

As an operator, I want a production smoke-test checklist so deploys can be verified quickly.

### Acceptance criteria

1. WHEN deployment completes THEN public reader smoke test SHALL be run.
2. WHEN deployment completes THEN login/auth smoke test SHALL be run.
3. WHEN deployment completes THEN admin health smoke test SHALL be run.
4. WHEN deployment completes THEN queue/worker smoke test SHOULD be run.
5. WHEN deployment completes THEN storage read/write smoke test SHOULD be run.
6. WHEN deployment completes THEN backup status SHALL be checked.
7. WHEN deployment completes THEN sitemap/robots SHALL be checked if public reader is enabled.
8. WHEN smoke test fails THEN rollback or mitigation procedure SHALL be followed.

## Requirement 17: Rollback and kill switches

### User story

As an operator, I want rollback and feature kill switches so production incidents can be mitigated.

### Acceptance criteria

1. WHEN deployment causes incident THEN rollback procedure SHALL be documented.
2. WHEN migration is not backward-compatible THEN rollback notes SHALL describe limitations.
3. WHEN public reader must be disabled THEN a kill switch or operational procedure SHALL exist.
4. WHEN glossary annotations cause incident THEN they SHALL be disableable.
5. WHEN analytics or optional scripts cause incident THEN they SHALL be disableable.
6. WHEN schedulers/workers cause incident THEN they SHALL be pausable.
7. WHEN exports cause incident THEN export creation SHALL be disableable.
8. WHEN takedown enforcement or cache issue occurs THEN cache invalidation procedure SHALL exist.
9. WHEN kill switch is used THEN action SHOULD be audited or logged safely.

## Requirement 18: Documentation

### User story

As an operator, I want production deployment documentation so setup and incidents are repeatable.

### Acceptance criteria

1. WHEN docs are updated THEN they SHALL list required production environment variables.
2. WHEN docs are updated THEN they SHALL describe deployment steps.
3. WHEN docs are updated THEN they SHALL describe migration steps.
4. WHEN docs are updated THEN they SHALL describe worker/scheduler process roles.
5. WHEN docs are updated THEN they SHALL describe backup/restore procedure.
6. WHEN docs are updated THEN they SHALL describe health check URLs.
7. WHEN docs are updated THEN they SHALL describe rollback procedure.
8. WHEN docs are updated THEN they SHALL describe secret rotation.
9. WHEN docs are updated THEN they SHALL describe public cache invalidation.
10. WHEN docs are updated THEN they SHALL describe smoke-test checklist.

## Requirement 19: Test coverage

### User story

As a maintainer, I want tests/checks for production hardening so unsafe config does not regress.

### Acceptance criteria

1. WHEN tests run THEN they SHALL cover production config validation.
2. WHEN tests run THEN they SHALL cover weak/default secret rejection.
3. WHEN tests run THEN they SHALL cover CORS validation.
4. WHEN tests run THEN they SHALL cover secure cookie validation.
5. WHEN tests run THEN they SHALL cover trusted proxy behavior.
6. WHEN tests run THEN they SHALL cover security headers.
7. WHEN tests run THEN they SHALL cover readiness dependency states.
8. WHEN tests run THEN they SHALL cover migration status checks where practical.
9. WHEN tests run THEN they SHALL cover storage config validation where practical.
10. WHEN tests run THEN they SHALL cover backup config validation where practical.
11. WHEN tests run THEN they SHALL cover safe logging/redaction paths.

## Requirement 20: Completion verification

### User story

As an operator, I want a clear verification path so production hardening is complete only when deployment safety is proven.

### Acceptance criteria

1. WHEN production-like config is missing a required secret THEN startup validation SHALL fail.
2. WHEN wildcard credentialed CORS is configured THEN validation SHALL fail.
3. WHEN insecure cookies are configured in production THEN validation SHALL fail.
4. WHEN public site URL is non-HTTPS in production THEN validation SHALL fail or warn according to policy.
5. WHEN readiness is checked with healthy dependencies THEN it SHALL pass.
6. WHEN readiness is checked with missing database/queue/storage dependency THEN it SHALL fail or degrade according to policy.
7. WHEN security headers are inspected THEN required headers SHALL be present.
8. WHEN smoke tests run in staging/prod-like environment THEN public reader, auth, admin health, worker, storage, backups, sitemap, and robots checks SHALL pass where enabled.
9. WHEN rollback docs are reviewed THEN operator can identify how to revert app, pause workers, run/rollback migrations, invalidate cache, and disable features.
