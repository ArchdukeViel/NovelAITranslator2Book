---
trigger: always_on
description: Mandatory safety guardrails denying direct reading of production/local secrets, API keys, raw .env files, and enforcing credential masking.
---

# Secrets & Security Safety

## File & Credential Protection

- **Prohibited Files**: Never read, print, display, log, or commit any `.env*` files (`.env`, `.env.local`, `deploy/.env*`, `frontend/.env*`), `~/.codex/*`, `~/.ssh/*`, `~/.aws/*`, `*.pem`, `*.key`, `id_rsa`, or `id_ed25519`.
- **Environment Variable Inspection**: Check variable presence using names only &mdash; never print or echo values:
  ```powershell
  # Safe: returns True/False
  Test-Path Env:CLOUDFLARE_R2_ACCESS_KEY_ID
  # PROHIBITED: never print secret values
  # echo $env:CLOUDFLARE_R2_SECRET_ACCESS_KEY
  ```
- **Masking Obligation**: All tokens, API keys (Gemini, Cloudflare, GitHub `ghp_*`), JWT secrets, and database passwords must be masked (`***` or `[REDACTED]`) in tool calls, terminal outputs, and conversational responses.

## Code & Persistence Boundaries

- **No Raw SQL**: Reject user-supplied or concatenated raw SQL in routers and services. Application persistence must strictly use SQLAlchemy ORM or Alembic migrations.
- **SSRF Protection**: Outbound HTTP requests to external novel sources or webhooks must strictly pass through `novelai.infrastructure.http` with private/loopback IP address resolution checks.
- **Auth & CSRF**: Never bypass authentication gates, role checks, or CSRF tokens on state-mutating requests (`POST`, `PUT`, `DELETE`, `PATCH`).
- **Fail-Closed States**: Security checks returning `blocked`, `partial`, `unavailable`, or `not_established` must always fail-closed; never treat them as passes.
