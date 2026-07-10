# tasks.md

# Tasks: Rate Limit and Abuse Protection Baseline

## Task List

* [ ] 0. Preflight review

  * [ ] 0.1 Inspect backend middleware/dependency injection stack.
  * [ ] 0.2 Inspect routing conventions and route template availability.
  * [ ] 0.3 Inspect auth endpoints: login, register, password reset.
  * [ ] 0.4 Inspect public reader and public search endpoints.
  * [ ] 0.5 Inspect analytics ingestion endpoint if implemented.
  * [ ] 0.6 Inspect contact/support/report form endpoints.
  * [ ] 0.7 Inspect export creation/download endpoints.
  * [ ] 0.8 Inspect translation/crawl/import job creation endpoints.
  * [ ] 0.9 Inspect admin API route patterns.
  * [ ] 0.10 Inspect Redis/cache/database availability for shared limiter store.
  * [ ] 0.11 Inspect trusted proxy/deployment config.
  * [ ] 0.12 Inspect existing tests for middleware, auth, reader, search, export, and jobs.

* [ ] 1. Define rate-limit policy model

  * [ ] 1.1 Define policy key. (REQ-1)
  * [ ] 1.2 Define window seconds. (REQ-1)
  * [ ] 1.3 Define max requests. (REQ-1)
  * [ ] 1.4 Define burst behavior if token bucket is used. (REQ-1)
  * [ ] 1.5 Define per-endpoint policy mapping. (REQ-1)
  * [ ] 1.6 Define fail-open/fail-closed behavior. (REQ-14)
  * [ ] 1.7 Define response headers policy. (REQ-13)
  * [ ] 1.8 Define safe logging fields. (REQ-17)

* [ ] 2. Add configuration

  * [ ] 2.1 Add `RATE_LIMIT_ENABLED`. (REQ-1)
  * [ ] 2.2 Add limiter store config. (REQ-2)
  * [ ] 2.3 Add default window and max request config. (REQ-1)
  * [ ] 2.4 Add endpoint-specific policy config. (REQ-4 through REQ-11)
  * [ ] 2.5 Add hash salt secret config. (REQ-3)
  * [ ] 2.6 Add fail-open/fail-closed config. (REQ-14)
  * [ ] 2.7 Add trusted proxy config. (REQ-15)
  * [ ] 2.8 Add allowlist config. (REQ-16)
  * [ ] 2.9 Add request body size config. (REQ-12)
  * [ ] 2.10 Validate config at startup. (REQ-1)

* [ ] 3. Implement rate-limit store abstraction

  * [ ] 3.1 Define store interface for increment/check. (REQ-2)
  * [ ] 3.2 Implement Redis-backed store if Redis exists. (REQ-2)
  * [ ] 3.3 Implement in-memory store for development/tests. (REQ-2)
  * [ ] 3.4 Add counter expiration behavior. (REQ-2)
  * [ ] 3.5 Ensure store keys do not contain raw private identifiers. (REQ-2, REQ-3)
  * [ ] 3.6 Add tests for increment, expiry, over-limit, and store failure. (REQ-2, REQ-19)

* [ ] 4. Implement rate-limit key resolver

  * [ ] 4.1 Resolve authenticated user key. (REQ-3)
  * [ ] 4.2 Resolve anonymous/session key where available. (REQ-3)
  * [ ] 4.3 Resolve IP hash key. (REQ-3)
  * [ ] 4.4 Normalize and hash account identifiers for auth endpoints. (REQ-8)
  * [ ] 4.5 Add trusted proxy handling. (REQ-15)
  * [ ] 4.6 Normalize IPv6 addresses. (REQ-15)
  * [ ] 4.7 Avoid raw IP/user/email in logs or keys. (REQ-3, REQ-17)
  * [ ] 4.8 Add tests for authenticated, anonymous, IP hash, account hash, proxy, and spoofed header behavior. (REQ-3, REQ-8, REQ-15, REQ-19)

* [ ] 5. Implement policy registry

  * [ ] 5.1 Add default policy. (REQ-1)
  * [ ] 5.2 Add public reader policy. (REQ-4)
  * [ ] 5.3 Add public search policy. (REQ-5)
  * [ ] 5.4 Add analytics ingestion policy. (REQ-6)
  * [ ] 5.5 Add contact/support/report form policy. (REQ-7)
  * [ ] 5.6 Add auth login/register/password reset policies. (REQ-8)
  * [ ] 5.7 Add export create/download policies. (REQ-9)
  * [ ] 5.8 Add translation/crawl/import job policies. (REQ-10)
  * [ ] 5.9 Add admin API policy. (REQ-11)
  * [ ] 5.10 Add tests for route-to-policy selection. (REQ-1, REQ-19)

* [ ] 6. Implement rate-limit middleware/dependency

  * [ ] 6.1 Add middleware or route dependency. (REQ-1)
  * [ ] 6.2 Match request to route template. (REQ-1)
  * [ ] 6.3 Resolve policy. (REQ-1)
  * [ ] 6.4 Resolve identity key. (REQ-3)
  * [ ] 6.5 Check/increment limiter store. (REQ-2)
  * [ ] 6.6 Allow request under limit. (REQ-1)
  * [ ] 6.7 Return `429` over limit. (REQ-13)
  * [ ] 6.8 Add `Retry-After` where possible. (REQ-13)
  * [ ] 6.9 Add optional rate-limit headers. (REQ-13)
  * [ ] 6.10 Add tests for allow, block, response body, headers, and policy matching. (REQ-1, REQ-13, REQ-19)

* [ ] 7. Add request body size guards

  * [ ] 7.1 Add global max body size guard where framework supports it. (REQ-12)
  * [ ] 7.2 Add analytics ingestion body size limit. (REQ-6, REQ-12)
  * [ ] 7.3 Add contact/support form body size limit. (REQ-7, REQ-12)
  * [ ] 7.4 Add export/job creation payload size limit. (REQ-9, REQ-10, REQ-12)
  * [ ] 7.5 Return safe `413` or validation response. (REQ-12)
  * [ ] 7.6 Ensure rejected body is not echoed/logged. (REQ-12, REQ-17)
  * [ ] 7.7 Add tests for each size limit. (REQ-12, REQ-19)

* [ ] 8. Protect public reader endpoints

  * [ ] 8.1 Apply public reader policy to novel list/detail pages. (REQ-4)
  * [ ] 8.2 Apply public reader policy to chapter pages. (REQ-4)
  * [ ] 8.3 Apply policy to reader fallback/snapshot endpoints if present. (REQ-4)
  * [ ] 8.4 Verify normal reading flow stays below limits. (REQ-4)
  * [ ] 8.5 Add tests for under-limit and over-limit public reader requests. (REQ-4, REQ-19)

* [ ] 9. Protect public search endpoints

  * [ ] 9.1 Apply public search rate-limit policy. (REQ-5)
  * [ ] 9.2 Enforce max page size. (REQ-5)
  * [ ] 9.3 Enforce max offset/page depth if applicable. (REQ-5)
  * [ ] 9.4 Reject or ignore unsupported filters safely. (REQ-5)
  * [ ] 9.5 Ensure raw search queries are not logged in abuse logs. (REQ-5, REQ-17)
  * [ ] 9.6 Add tests for throttling, max page size, max offset, unsupported filters, and safe logging. (REQ-5, REQ-19)

* [ ] 10. Protect analytics ingestion

  * [ ] 10.1 Apply analytics ingestion rate-limit policy. (REQ-6)
  * [ ] 10.2 Enforce max events per request. (REQ-6)
  * [ ] 10.3 Enforce request body size. (REQ-6, REQ-12)
  * [ ] 10.4 Ensure analytics validation still applies. (REQ-6)
  * [ ] 10.5 Ensure rate-limit failure does not affect core app behavior. (REQ-6)
  * [ ] 10.6 Add tests for over-limit, too many events, body too large, and valid ingestion. (REQ-6, REQ-19)

* [ ] 11. Protect contact/support/report forms

  * [ ] 11.1 Apply form submission policy. (REQ-7)
  * [ ] 11.2 Enforce form body size. (REQ-7, REQ-12)
  * [ ] 11.3 Add honeypot validation if in scope. (REQ-7)
  * [ ] 11.4 Log safe spam/rate-limit events. (REQ-7, REQ-17)
  * [ ] 11.5 Return safe response when limited. (REQ-7, REQ-13)
  * [ ] 11.6 Add tests for under-limit, over-limit, body too large, honeypot if implemented, and safe logs. (REQ-7, REQ-19)

* [ ] 12. Protect auth endpoints

  * [ ] 12.1 Apply login IP-based limit. (REQ-8)
  * [ ] 12.2 Apply login account-identifier limit. (REQ-8)
  * [ ] 12.3 Apply registration limit. (REQ-8)
  * [ ] 12.4 Apply password reset limit. (REQ-8)
  * [ ] 12.5 Hash account identifiers in limiter keys. (REQ-8)
  * [ ] 12.6 Ensure rate-limited auth response does not reveal account existence. (REQ-8)
  * [ ] 12.7 Ensure bypass does not skip auth protection unless explicitly configured. (REQ-8, REQ-16)
  * [ ] 12.8 Add tests for login brute force, account hash, register, password reset, and account-existence safety. (REQ-8, REQ-19)

* [ ] 13. Protect export endpoints

  * [ ] 13.1 Apply export creation policy. (REQ-9)
  * [ ] 13.2 Apply export download policy if needed. (REQ-9)
  * [ ] 13.3 Enforce export request body size. (REQ-9, REQ-12)
  * [ ] 13.4 Ensure over-limit export creation enqueues no job. (REQ-9)
  * [ ] 13.5 Integrate with duplicate running export policy where available. (REQ-9)
  * [ ] 13.6 Add tests for create allowed, create blocked, no job enqueued, download limit, and size limit. (REQ-9, REQ-19)

* [ ] 14. Protect translation/crawl/import job endpoints

  * [ ] 14.1 Apply translation job creation policy. (REQ-10)
  * [ ] 14.2 Apply crawl/import/add-novel policy. (REQ-10)
  * [ ] 14.3 Enforce request body size. (REQ-10, REQ-12)
  * [ ] 14.4 Add optional queue-depth acceptance guard. (REQ-10)
  * [ ] 14.5 Ensure over-limit job creation enqueues no job. (REQ-10)
  * [ ] 14.6 Integrate with duplicate job policy where available. (REQ-10)
  * [ ] 14.7 Add tests for translation/crawl allowed, blocked, queue depth guard, no job enqueued, and duplicate behavior. (REQ-10, REQ-19)

* [ ] 15. Protect admin APIs

  * [ ] 15.1 Apply admin API policy. (REQ-11)
  * [ ] 15.2 Ensure auth/authorization runs correctly with rate limiting. (REQ-11)
  * [ ] 15.3 Add optional emergency bypass if required. (REQ-11, REQ-16)
  * [ ] 15.4 Audit/log bypass usage if implemented. (REQ-11, REQ-16)
  * [ ] 15.5 Add tests for admin under-limit, over-limit, non-admin behavior, and bypass if implemented. (REQ-11, REQ-16, REQ-19)

* [ ] 16. Implement store failure behavior

  * [ ] 16.1 Add failure policy for public read endpoints. (REQ-14)
  * [ ] 16.2 Add failure policy for auth endpoints. (REQ-14)
  * [ ] 16.3 Add failure policy for job-creation endpoints. (REQ-14)
  * [ ] 16.4 Add failure policy for admin endpoints. (REQ-14)
  * [ ] 16.5 Log safe warning when store fails. (REQ-14, REQ-17)
  * [ ] 16.6 Add tests for fail-open and fail-closed modes. (REQ-14, REQ-19)

* [ ] 17. Implement allowlist/bypass controls

  * [ ] 17.1 Add explicit allowlist config parser. (REQ-16)
  * [ ] 17.2 Support selected internal health-check bypass if needed. (REQ-16)
  * [ ] 17.3 Prevent auth brute-force bypass by default. (REQ-16)
  * [ ] 17.4 Log safe bypass events. (REQ-16, REQ-17)
  * [ ] 17.5 Validate invalid bypass config. (REQ-16)
  * [ ] 17.6 Add tests for allowlisted, non-allowlisted, invalid config, and auth no-bypass behavior. (REQ-16, REQ-19)

* [ ] 18. Add abuse logging

  * [ ] 18.1 Log `abuse.rate_limited`. (REQ-17)
  * [ ] 18.2 Log `abuse.request_too_large`. (REQ-17)
  * [ ] 18.3 Log optional suspicious pattern events if implemented. (REQ-17)
  * [ ] 18.4 Include route template and policy key. (REQ-17)
  * [ ] 18.5 Include hashed actor/session/IP identity where safe. (REQ-17)
  * [ ] 18.6 Exclude passwords, tokens, raw request bodies, raw IPs, raw query strings, and private content. (REQ-17)
  * [ ] 18.7 Add log sampling/rate-limiting where practical. (REQ-17)
  * [ ] 18.8 Add safe logging tests where project conventions support them. (REQ-17, REQ-19)

* [ ] 19. Add optional admin rate-limit status

  * [ ] 19.1 Add `GET /admin/rate-limits/status` if admin ops routes exist. (REQ-18)
  * [ ] 19.2 Protect endpoint with admin auth. (REQ-18)
  * [ ] 19.3 Return enabled state. (REQ-18)
  * [ ] 19.4 Return policy keys and limits. (REQ-18)
  * [ ] 19.5 Return safe store health if available. (REQ-18)
  * [ ] 19.6 Return aggregate recent limited counts if available. (REQ-18)
  * [ ] 19.7 Ensure no raw IPs/emails/tokens/bodies in response. (REQ-18)
  * [ ] 19.8 Add tests for admin, non-admin, unauthenticated, and response safety. (REQ-18, REQ-19)

* [ ] 20. Backend test coverage pass

  * [ ] 20.1 Test default policy allow/block. (REQ-1, REQ-19)
  * [ ] 20.2 Test store increment/expiry/failure. (REQ-2, REQ-19)
  * [ ] 20.3 Test authenticated and anonymous key resolution. (REQ-3, REQ-19)
  * [ ] 20.4 Test public reader policy. (REQ-4, REQ-19)
  * [ ] 20.5 Test search policy. (REQ-5, REQ-19)
  * [ ] 20.6 Test analytics ingestion policy. (REQ-6, REQ-19)
  * [ ] 20.7 Test contact/support form policy. (REQ-7, REQ-19)
  * [ ] 20.8 Test auth endpoint policy. (REQ-8, REQ-19)
  * [ ] 20.9 Test export policy. (REQ-9, REQ-19)
  * [ ] 20.10 Test translation/crawl/import policy. (REQ-10, REQ-19)
  * [ ] 20.11 Test admin API policy. (REQ-11, REQ-19)
  * [ ] 20.12 Test request size limits. (REQ-12, REQ-19)
  * [ ] 20.13 Test response format. (REQ-13, REQ-19)
  * [ ] 20.14 Test store failure behavior. (REQ-14, REQ-19)
  * [ ] 20.15 Test trusted proxy behavior. (REQ-15, REQ-19)
  * [ ] 20.16 Test allowlist behavior. (REQ-16, REQ-19)
  * [ ] 20.17 Test safe abuse logging. (REQ-17, REQ-19)
  * [ ] 20.18 Test admin status if implemented. (REQ-18, REQ-19)

* [ ] 21. Documentation

  * [ ] 21.1 Document rate-limit config keys. (REQ-1)
  * [ ] 21.2 Document limiter store options. (REQ-2)
  * [ ] 21.3 Document identity key resolution and privacy behavior. (REQ-3)
  * [ ] 21.4 Document endpoint policies. (REQ-4 through REQ-11)
  * [ ] 21.5 Document request size limits. (REQ-12)
  * [ ] 21.6 Document 429 response format. (REQ-13)
  * [ ] 21.7 Document store failure policy. (REQ-14)
  * [ ] 21.8 Document trusted proxy config. (REQ-15)
  * [ ] 21.9 Document allowlist/bypass behavior. (REQ-16)
  * [ ] 21.10 Document abuse logging safety rules. (REQ-17)

* [ ] 22. Completion verification

  * [ ] 22.1 Send repeated public search requests until limit is exceeded. (REQ-20)
  * [ ] 22.2 Verify public search returns `429`. (REQ-20)
  * [ ] 22.3 Send repeated analytics ingestion requests until limit is exceeded. (REQ-20)
  * [ ] 22.4 Verify analytics ingestion is limited according to policy. (REQ-20)
  * [ ] 22.5 Send repeated login attempts and verify auth rate limit without account-existence leak. (REQ-8, REQ-20)
  * [ ] 22.6 Send repeated export creation requests and verify no extra jobs are queued after limit. (REQ-9, REQ-20)
  * [ ] 22.7 Send repeated translation/crawl job requests and verify no extra jobs are queued after limit. (REQ-10, REQ-20)
  * [ ] 22.8 Submit oversized request body and verify safe rejection. (REQ-12, REQ-20)
  * [ ] 22.9 Verify normal public reader navigation below limit is not blocked. (REQ-4, REQ-20)
  * [ ] 22.10 Inspect abuse logs and verify no raw IPs, tokens, passwords, request bodies, or private text appear. (REQ-17, REQ-20)
  * [ ] 22.11 Simulate limiter store failure and verify behavior matches config. (REQ-14, REQ-20)
  * [ ] 22.12 Mark `rate-limit-and-abuse-protection-baseline` complete only after high-risk endpoints are protected and legitimate reader flows still work.
