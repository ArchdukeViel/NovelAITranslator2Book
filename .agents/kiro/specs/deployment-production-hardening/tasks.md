# tasks.md

# Tasks: Deployment Production Hardening

## Task List

* [ ] 0. Preflight production deployment review

  * [ ] 0.1 Inspect current environment/config loading.
  * [ ] 0.2 Inspect existing `.env.example`, docs, and deployment notes.
  * [ ] 0.3 Inspect auth/session/cookie configuration.
  * [ ] 0.4 Inspect CORS/CSRF/proxy configuration.
  * [ ] 0.5 Inspect database migration process.
  * [ ] 0.6 Inspect worker/queue/scheduler startup model.
  * [ ] 0.7 Inspect storage/public/private bucket configuration.
  * [ ] 0.8 Inspect backup/restore configuration.
  * [ ] 0.9 Inspect health/readiness endpoints.
  * [ ] 0.10 Inspect CI/CD or manual deployment flow.
  * [ ] 0.11 Inspect logging/redaction behavior.
  * [ ] 0.12 Inspect public reader cache and takedown invalidation paths.

* [ ] 1. Define production environment modes

  * [ ] 1.1 Add or verify `ENV` support. (REQ-1)
  * [ ] 1.2 Define valid environment values. (REQ-1)
  * [ ] 1.3 Disable debug behavior in production. (REQ-1)
  * [ ] 1.4 Disable development-only endpoints/tools in production. (REQ-1)
  * [ ] 1.5 Add tests for valid, invalid, missing, and production modes. (REQ-1, REQ-19)

* [ ] 2. Implement production config validator

  * [ ] 2.1 Add `ProductionConfigValidator` or equivalent. (REQ-2)
  * [ ] 2.2 Validate required production variables. (REQ-2)
  * [ ] 2.3 Validate weak/default secrets. (REQ-2, REQ-3)
  * [ ] 2.4 Validate secure cookie settings. (REQ-2, REQ-6)
  * [ ] 2.5 Validate CORS safety. (REQ-2, REQ-5)
  * [ ] 2.6 Validate public site URL. (REQ-2, REQ-4)
  * [ ] 2.7 Validate database/queue/storage config. (REQ-2)
  * [ ] 2.8 Validate backup/rate-limit config. (REQ-2, REQ-12)
  * [ ] 2.9 Return fatal/warning/info results. (REQ-2)
  * [ ] 2.10 Add tests for validation pass/fail cases. (REQ-2, REQ-19, REQ-20)

* [ ] 3. Harden secrets handling

  * [ ] 3.1 Inventory all required secrets. (REQ-3)
  * [ ] 3.2 Add known-default/placeholder secret rejection. (REQ-3)
  * [ ] 3.3 Ensure backend secrets are not exposed to frontend build. (REQ-3)
  * [ ] 3.4 Redact secrets from config/status/log output. (REQ-3, REQ-13)
  * [ ] 3.5 Document secret rotation procedure. (REQ-3, REQ-18)
  * [ ] 3.6 Add tests for default secret rejection and redaction. (REQ-3, REQ-19)

* [ ] 4. Harden TLS and proxy behavior

  * [ ] 4.1 Validate production public URL uses HTTPS. (REQ-4)
  * [ ] 4.2 Add trusted proxy CIDR config if missing. (REQ-4)
  * [ ] 4.3 Trust forwarded headers only from configured proxies. (REQ-4)
  * [ ] 4.4 Ignore spoofed forwarded headers from untrusted clients. (REQ-4)
  * [ ] 4.5 Configure allowed hosts if framework supports it. (REQ-4)
  * [ ] 4.6 Verify secure cookie/proxy protocol behavior. (REQ-4, REQ-6)
  * [ ] 4.7 Add tests for trusted/untrusted forwarded headers and host behavior. (REQ-4, REQ-19)

* [ ] 5. Harden CORS and CSRF

  * [ ] 5.1 Replace wildcard production CORS with explicit origins. (REQ-5)
  * [ ] 5.2 Reject wildcard origins when credentials are enabled. (REQ-5)
  * [ ] 5.3 Restrict admin API origins. (REQ-5)
  * [ ] 5.4 Enable CSRF protection for cookie-auth write actions or document equivalent defense. (REQ-5)
  * [ ] 5.5 Add trusted CSRF origins config. (REQ-5)
  * [ ] 5.6 Add tests for allowed origin, blocked origin, preflight, and unsafe config. (REQ-5, REQ-19)

* [ ] 6. Harden cookies and sessions

  * [ ] 6.1 Ensure production cookies use `Secure`. (REQ-6)
  * [ ] 6.2 Ensure session cookies use `HttpOnly`. (REQ-6)
  * [ ] 6.3 Define explicit SameSite policy. (REQ-6)
  * [ ] 6.4 Validate `SameSite=None` requires Secure. (REQ-6)
  * [ ] 6.5 Verify disabled users cannot retain active access. (REQ-6)
  * [ ] 6.6 Verify admin session revocation. (REQ-6)
  * [ ] 6.7 Add tests for cookie flags and session invalidation where practical. (REQ-6, REQ-19)

* [ ] 7. Add security headers

  * [ ] 7.1 Add `X-Content-Type-Options: nosniff`. (REQ-7)
  * [ ] 7.2 Add referrer policy. (REQ-7)
  * [ ] 7.3 Add frame embedding protection. (REQ-7)
  * [ ] 7.4 Add HSTS when HTTPS policy is ready. (REQ-7)
  * [ ] 7.5 Add CSP or CSP report-only according to frontend compatibility. (REQ-7)
  * [ ] 7.6 Verify headers do not break public reader/admin flows. (REQ-7)
  * [ ] 7.7 Add header tests. (REQ-7, REQ-19, REQ-20)

* [ ] 8. Define production migration process

  * [ ] 8.1 Document migration command and timing. (REQ-8, REQ-18)
  * [ ] 8.2 Disable unsafe automatic multi-process migrations in production. (REQ-8)
  * [ ] 8.3 Add migration status check to readiness/admin health where possible. (REQ-8, REQ-14)
  * [ ] 8.4 Define destructive migration approval/backup requirement. (REQ-8)
  * [ ] 8.5 Document rollback considerations for migrations. (REQ-8, REQ-17)
  * [ ] 8.6 Add tests/checks for migration status validation where practical. (REQ-8, REQ-19)

* [ ] 9. Define production process roles

  * [ ] 9.1 Document web process role. (REQ-9)
  * [ ] 9.2 Document worker process role. (REQ-9)
  * [ ] 9.3 Document scheduler process role. (REQ-9)
  * [ ] 9.4 Document maintenance process/cron role. (REQ-9)
  * [ ] 9.5 Document backup scheduler role. (REQ-9)
  * [ ] 9.6 Add worker concurrency config. (REQ-9)
  * [ ] 9.7 Add scheduler lock validation. (REQ-9)
  * [ ] 9.8 Add health/admin status for queue and stale workers. (REQ-9, REQ-14)
  * [ ] 9.9 Add tests for process-role config validation where practical. (REQ-9, REQ-19)

* [ ] 10. Harden production storage config

  * [ ] 10.1 Validate object storage credentials. (REQ-10)
  * [ ] 10.2 Validate public base URL. (REQ-10)
  * [ ] 10.3 Verify private source/draft files are not publicly readable. (REQ-10)
  * [ ] 10.4 Verify public projections use public-safe paths. (REQ-10)
  * [ ] 10.5 Ensure signed URLs are not embedded in public metadata. (REQ-10)
  * [ ] 10.6 Ensure takedown can block public storage/projection access. (REQ-10)
  * [ ] 10.7 Add storage config validation tests/checks. (REQ-10, REQ-19)

* [ ] 11. Harden public cache safety

  * [ ] 11.1 Review public reader cache headers. (REQ-11)
  * [ ] 11.2 Ensure only published public content is cacheable. (REQ-11)
  * [ ] 11.3 Prevent caching private/unpublished/preview responses. (REQ-11)
  * [ ] 11.4 Verify takedown cache invalidation/bypass. (REQ-11)
  * [ ] 11.5 Verify glossary annotation setting cache invalidation/versioning. (REQ-11)
  * [ ] 11.6 Validate cache config in production validator where possible. (REQ-11)
  * [ ] 11.7 Add public/private cache behavior tests. (REQ-11, REQ-19)

* [ ] 12. Validate backup and restore readiness

  * [ ] 12.1 Validate backup enabled/disabled production policy. (REQ-12)
  * [ ] 12.2 Validate backup target config. (REQ-12)
  * [ ] 12.3 Validate backup retention config. (REQ-12)
  * [ ] 12.4 Validate backup encryption config if required. (REQ-12)
  * [ ] 12.5 Surface backup status in admin health/status. (REQ-12, REQ-14)
  * [ ] 12.6 Document restore drill procedure. (REQ-12, REQ-18)
  * [ ] 12.7 Add backup config validation tests/checks. (REQ-12, REQ-19)

* [ ] 13. Harden observability and logging

  * [ ] 13.1 Ensure request IDs are generated/propagated. (REQ-13)
  * [ ] 13.2 Ensure production logs are structured where practical. (REQ-13)
  * [ ] 13.3 Redact secrets/private content from backend logs. (REQ-13)
  * [ ] 13.4 Redact unsafe values from frontend error logs. (REQ-13)
  * [ ] 13.5 Redact raw IPs/tokens/passwords from abuse logs. (REQ-13)
  * [ ] 13.6 Add tests for redaction paths where practical. (REQ-13, REQ-19)

* [ ] 14. Verify health and readiness

  * [ ] 14.1 Verify `/health/live` is lightweight. (REQ-14)
  * [ ] 14.2 Verify `/health/ready` checks critical dependencies. (REQ-14)
  * [ ] 14.3 Add database readiness failure behavior. (REQ-14)
  * [ ] 14.4 Add migration status readiness behavior. (REQ-14)
  * [ ] 14.5 Add queue readiness behavior. (REQ-14)
  * [ ] 14.6 Add storage readiness behavior. (REQ-14)
  * [ ] 14.7 Add critical config readiness behavior. (REQ-14)
  * [ ] 14.8 Verify admin health exposes safe details. (REQ-14)
  * [ ] 14.9 Add health/readiness tests. (REQ-14, REQ-19, REQ-20)

* [ ] 15. Add deployment gates

  * [ ] 15.1 Require tests before production deploy. (REQ-15)
  * [ ] 15.2 Require lint/type checks according to project policy. (REQ-15)
  * [ ] 15.3 Require successful production build artifact. (REQ-15)
  * [ ] 15.4 Require production config validation. (REQ-15)
  * [ ] 15.5 Require migration validation/approval. (REQ-15)
  * [ ] 15.6 Require backup status check or documented exception. (REQ-15)
  * [ ] 15.7 Document override policy. (REQ-15)
  * [ ] 15.8 Add CI/manual checklist updates. (REQ-15, REQ-18)

* [ ] 16. Add production smoke-test checklist

  * [ ] 16.1 Add public reader smoke test. (REQ-16)
  * [ ] 16.2 Add login/auth smoke test. (REQ-16)
  * [ ] 16.3 Add admin health smoke test. (REQ-16)
  * [ ] 16.4 Add queue/worker smoke test. (REQ-16)
  * [ ] 16.5 Add storage read/write smoke test. (REQ-16)
  * [ ] 16.6 Add backup status smoke test. (REQ-16)
  * [ ] 16.7 Add sitemap/robots smoke test. (REQ-16)
  * [ ] 16.8 Document failure response/rollback trigger. (REQ-16, REQ-17)

* [ ] 17. Document rollback and kill switches

  * [ ] 17.1 Document app version rollback. (REQ-17)
  * [ ] 17.2 Document migration rollback limitations. (REQ-17)
  * [ ] 17.3 Document how to pause workers. (REQ-17)
  * [ ] 17.4 Document how to pause schedulers. (REQ-17)
  * [ ] 17.5 Document public reader kill switch/procedure. (REQ-17)
  * [ ] 17.6 Document glossary annotation kill switch. (REQ-17)
  * [ ] 17.7 Document analytics disable switch. (REQ-17)
  * [ ] 17.8 Document export disable switch. (REQ-17)
  * [ ] 17.9 Document public cache invalidation procedure. (REQ-17)
  * [ ] 17.10 Add audit/logging for kill-switch use where practical. (REQ-17)

* [ ] 18. Update production documentation

  * [ ] 18.1 Document required production env vars. (REQ-18)
  * [ ] 18.2 Document deployment steps. (REQ-18)
  * [ ] 18.3 Document migration steps. (REQ-18)
  * [ ] 18.4 Document worker/scheduler roles. (REQ-18)
  * [ ] 18.5 Document backup/restore procedure. (REQ-18)
  * [ ] 18.6 Document health check URLs. (REQ-18)
  * [ ] 18.7 Document rollback procedure. (REQ-18)
  * [ ] 18.8 Document secret rotation. (REQ-18)
  * [ ] 18.9 Document cache invalidation. (REQ-18)
  * [ ] 18.10 Document smoke-test checklist. (REQ-18)

* [ ] 19. Test coverage pass

  * [ ] 19.1 Test production config validation. (REQ-19)
  * [ ] 19.2 Test weak/default secret rejection. (REQ-19)
  * [ ] 19.3 Test CORS validation. (REQ-19)
  * [ ] 19.4 Test secure cookie validation. (REQ-19)
  * [ ] 19.5 Test trusted proxy behavior. (REQ-19)
  * [ ] 19.6 Test security headers. (REQ-19)
  * [ ] 19.7 Test readiness dependency states. (REQ-19)
  * [ ] 19.8 Test migration status check where practical. (REQ-19)
  * [ ] 19.9 Test storage config validation where practical. (REQ-19)
  * [ ] 19.10 Test backup config validation where practical. (REQ-19)
  * [ ] 19.11 Test safe logging/redaction. (REQ-19)

* [ ] 20. Staging/prod-like verification

  * [ ] 20.1 Run startup with missing secret and verify validation fails. (REQ-20)
  * [ ] 20.2 Run startup with wildcard credentialed CORS and verify validation fails. (REQ-20)
  * [ ] 20.3 Run startup with insecure production cookie config and verify validation fails. (REQ-20)
  * [ ] 20.4 Run startup with non-HTTPS production public URL and verify fail/warn policy. (REQ-20)
  * [ ] 20.5 Run readiness with healthy dependencies and verify pass. (REQ-20)
  * [ ] 20.6 Run readiness with missing database/queue/storage and verify fail/degraded behavior. (REQ-20)
  * [ ] 20.7 Inspect production-like security headers. (REQ-20)
  * [ ] 20.8 Run smoke tests for public reader, auth, admin health, worker, storage, backup, sitemap, and robots where enabled. (REQ-16, REQ-20)
  * [ ] 20.9 Review rollback docs and confirm app rollback, worker pause, migration notes, cache invalidation, and kill switches are clear. (REQ-17, REQ-20)
  * [ ] 20.10 Mark `deployment-production-hardening` complete only after production-like deployment fails unsafe config, passes healthy readiness, emits security headers, and has documented deploy/rollback procedures.
