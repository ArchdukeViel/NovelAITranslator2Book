# design.md

# Design: Rate Limit and Abuse Protection Baseline

## Overview

`rate-limit-and-abuse-protection-baseline` adds a baseline abuse-protection layer for public and authenticated API surfaces.

The app has several endpoints that can be abused:

```text id="gy6h2k"
public reader pages
public search
analytics ingestion
contact/support/error report forms
auth login/register/password flows
export generation and download
crawl/import/add-novel workflows
translation job creation
admin APIs
```

This spec adds centralized rate limiting, request size limits, safe abuse logging, and endpoint-specific policies. The goal is to prevent obvious abuse and resource exhaustion without blocking legitimate readers.

## Goals

* Add centralized rate-limit middleware or dependency.
* Add endpoint-specific rate-limit policies.
* Protect public reader and public search.
* Protect analytics ingestion.
* Protect contact/support/report forms.
* Protect auth endpoints.
* Protect export generation.
* Protect crawl/import/translation job creation.
* Add request body size limits where needed.
* Add safe structured abuse logs.
* Add admin visibility for rate-limit configuration/status where useful.
* Add tests for throttling, identity keys, bypass rules, and safety.

## Non-goals

* No full WAF implementation.
* No CAPTCHA requirement unless already available.
* No bot-detection fingerprinting.
* No third-party anti-abuse vendor integration.
* No DDoS mitigation replacement for infrastructure/CDN.
* No per-user surveillance dashboard.
* No blocking search engines through this layer; crawler rules belong to SEO/robots and infrastructure.
* No complete fraud/risk scoring engine.

## Threat model

Baseline protection should address:

```text id="1r0pm3"
high-volume public page requests
public search scraping
analytics ingestion spam
contact/support spam
brute-force login attempts
registration abuse
export generation abuse
translation job spam
crawl/import abuse
large request bodies
repeated failing requests
admin endpoint probing
```

This is not enough for large-scale DDoS. Deployment should still use infrastructure protections where available.

## Architecture

Recommended components:

```text id="wphd3f"
RateLimitConfig
RateLimitPolicyRegistry
RateLimitMiddleware
RateLimitKeyResolver
RateLimitStore
AbuseEventLogger
RequestSizeGuard
AdminRateLimitStatusService
```

High-level request flow:

```text id="8w1cx6"
1. Request enters middleware.
2. Route is matched to a rate-limit policy.
3. Key resolver builds a privacy-safe rate-limit key.
4. Rate-limit store increments usage for the window.
5. If under limit, request continues.
6. If over limit, response returns 429 with safe error.
7. Abuse event is logged safely.
```

## Rate-limit algorithms

Recommended V1 algorithm:

```text id="crmp4h"
fixed window or sliding window counter
```

Better but optional:

```text id="fb0eqz"
token bucket
sliding window log
leaky bucket
```

Recommended store options:

```text id="d4hnsu"
Redis for multi-instance deployments
database for simple deployments
in-memory for single-node development only
```

Production should avoid in-memory-only limits if multiple app instances exist.

## Identity keys

Recommended key priority:

```text id="9noxff"
authenticated user ID
API key/client ID if supported
session ID hash
IP hash
anonymous ID/session ID hash
route policy key
```

Privacy rules:

```text id="zihuxd"
do not store raw IP addresses when avoidable
hash IP/session identifiers
salt hashes with deployment secret
do not expose rate-limit keys in public responses
```

For authenticated endpoints, prefer user ID over IP so users behind shared networks are not unfairly blocked.

For unauthenticated endpoints, use IP hash and optional anonymous/session ID.

## Global limits

Add a coarse global protection layer.

Recommended config:

```text id="2r2am3"
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORE=redis
RATE_LIMIT_DEFAULT_WINDOW_SECONDS=60
RATE_LIMIT_DEFAULT_MAX_REQUESTS=120
RATE_LIMIT_IP_HASH_SALT_SECRET=...
RATE_LIMIT_FAIL_OPEN=false
```

Recommended default policy:

```text id="smxstn"
120 requests per minute per identity for normal API routes
```

Adjust based on app traffic.

## Endpoint-specific policies

Recommended baseline policies:

```text id="u3bn8r"
public_reader: 300/minute
public_search: 30/minute
analytics_ingestion: 60/minute and max events/request
contact_forms: 5/hour
auth_login: 10/15 minutes
auth_register: 5/hour
password_reset: 5/hour
export_create: 10/hour
export_download: 120/hour
translation_create: 20/hour
crawl_import_create: 20/hour
admin_api: 300/minute
```

These are starting points. Make them configurable.

## Public reader policy

Public reader pages should be generous enough for normal reading.

Recommended:

```text id="3i8c12"
public novel/chapter reads: high limit
public assets/static files: handled by CDN/static layer if possible
public reader fallback/snapshot endpoints: same public reader policy
```

Avoid blocking legitimate users who read quickly or use browser prefetch.

## Public search policy

Search can be expensive and scrape-prone.

Recommended protections:

```text id="wumx89"
rate limit search requests
minimum query length if applicable
max page size
max result offset/page
request timeout
drop unsupported filters
```

Do not store raw query strings in abuse logs unless approved.

## Analytics ingestion policy

Analytics ingestion is public-write and needs strict validation.

Protections:

```text id="hizzwb"
rate limit by IP/session hash
max events per request
max body size
event allowlist
metadata size limit
drop unknown fields
```

This complements `analytics-baseline`.

## Contact/support/report forms

Forms are spam-prone.

Protections:

```text id="sb1dmp"
low rate limit per identity
body size limit
honeypot field optional
minimum submit interval optional
email/domain blocklist optional
safe spam category logging
```

CAPTCHA can be added later if needed.

## Auth endpoint protection

Auth endpoints need stricter policy.

Recommended:

```text id="k62s05"
login attempts limited by IP hash and account identifier hash
register limited by IP hash
password reset limited by IP hash and account identifier hash
```

Do not reveal whether an account exists.

Use existing auth security conventions if present.

## Export/crawl/translation protection

Resource-creating actions need strict limits.

Recommended:

```text id="7u6b7l"
export creation limited per authenticated user
translation job creation limited per authenticated user
crawl/import/add-novel limited per authenticated user
admin users may have higher limits but not unlimited by default
queue depth guard before accepting jobs
```

If a job is already running for the same target, dedupe or reject according to existing job policy.

## Request size limits

Recommended request body limits:

```text id="wfyx6q"
analytics ingestion: small batch limit
contact/support forms: modest text limit
auth forms: small limit
export/create request: small config limit
translation/crawl create request: bounded URL/list/config size
admin uploads/imports: explicit configured limit
```

Return safe `413 Payload Too Large` for oversized requests.

## Response behavior

For rate-limited requests:

```http id="t8rj24"
HTTP 429 Too Many Requests
```

Recommended body:

```json id="i161xl"
{
  "error": {
    "code": "rate_limited",
    "message": "Too many requests. Please try again later."
  }
}
```

Recommended headers:

```text id="xgwcuy"
Retry-After
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
```

Headers are optional if project avoids exposing limits publicly. `Retry-After` is useful.

Do not expose internal keys or store details.

## Fail-open vs fail-closed

If the rate-limit store fails:

Recommended policy:

```text id="b9knw6"
public read endpoints -> fail open with safe log
auth/write/job creation endpoints -> fail closed or conservative local fallback
admin endpoints -> fail closed or conservative local fallback
```

Config:

```text id="tp5525"
RATE_LIMIT_FAIL_OPEN=false
RATE_LIMIT_PUBLIC_READ_FAIL_OPEN=true
```

Production should avoid accepting unlimited expensive writes if limiter store is down.

## Allowlist and bypass

Optional allowlists:

```text id="3l7a9q"
internal health checks
trusted reverse proxy
admin emergency bypass
known safe uptime monitor
```

Rules:

```text id="u7a75p"
allowlists must be configured explicitly
bypass must not apply to auth brute-force protection by default
bypass usage should be logged safely
do not trust arbitrary client-supplied IP headers unless proxy config is trusted
```

## Reverse proxy IP handling

If deployed behind a proxy/CDN:

```text id="a7ox6u"
trust forwarded IP headers only from configured trusted proxies
otherwise use direct remote address
normalize IPv6
hash IP before storage/logging
```

Config:

```text id="cmjix9"
TRUSTED_PROXY_CIDRS=...
RATE_LIMIT_TRUST_X_FORWARDED_FOR=false
```

## Abuse logging

Recommended event:

```text id="h7ahgi"
abuse.rate_limited
abuse.request_too_large
abuse.suspicious_pattern
```

Safe fields:

```text id="0gwpxj"
route_template
policy_key
actor_type
actor_id_hash
ip_hash
status_code
limit
window_seconds
retry_after_seconds
```

Do not log:

```text id="rfxd41"
raw IP
password
auth tokens
request body
raw search query
full URL with query string
private text
```

## Admin visibility

Optional endpoint:

```http id="l96du6"
GET /admin/rate-limits/status
```

Recommended response:

```json id="qeufja"
{
  "enabled": true,
  "store": "redis",
  "policies": [
    {
      "key": "public_search",
      "window_seconds": 60,
      "max_requests": 30
    }
  ],
  "recent_rate_limited_count": 42
}
```

Admin-only. Do not expose raw IPs or user private data.

## Testing strategy

Tests should cover:

```text id="cywq7x"
default rate limit allows requests below threshold
rate limit returns 429 above threshold
Retry-After behavior
per-route policy selection
authenticated user key
anonymous/IP hash key
login dual key behavior
request size limits
analytics ingestion limits
contact form limits
export/translation job creation limits
limiter store failure behavior
trusted proxy IP handling
allowlist behavior
safe abuse logging
admin status authorization
```

## Rollout plan

1. Inspect routing/middleware stack.
2. Add config and policy registry.
3. Add limiter store abstraction.
4. Add key resolver.
5. Add middleware/dependency.
6. Add endpoint-specific policies.
7. Add request size guards.
8. Add abuse logs.
9. Add optional admin status.
10. Add tests.
11. Start with permissive limits in staging.
12. Tighten write-heavy endpoints first.
13. Verify legitimate reader flows are not blocked.
