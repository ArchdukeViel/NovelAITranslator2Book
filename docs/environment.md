# Novel AI — Environment Variables Reference

> **Comprehensive reference for all environment variables.**
> Source of truth: `backend/src/novelai/config/settings.py`
> Example files: `.env.example`, `deploy/.env.example`
> Last updated: 2026-07-12 — documentation reconciliation

---

## Table of Contents

1. [Overview](#overview)
2. [File Structure](#file-structure)
3. [Quick Start](#quick-start)
4. [Variable Reference by Category](#variable-reference-by-category)
   - [Runtime](#runtime)
   - [Storage](#storage)
   - [Web](#web)
   - [Provider / Model](#provider--model)
   - [Scraping](#scraping)
   - [Translation](#translation)
   - [Database](#database)
   - [Redis](#redis)
   - [Auth / Session](#auth--session)
   - [Email / SMTP](#email--smtp)
   - [Cache](#cache)
   - [Semantic Cache](#semantic-cache)
   - [LLM QA](#llm-qa)
   - [Docker Compose](#docker-compose)
5. [Environment Profiles](#environment-profiles)
6. [Security Notes](#security-notes)
7. [Docker Compose Integration](#docker-compose-integration)
8. [Supabase Setup](#supabase-setup)
9. [Troubleshooting](#troubleshooting)
10. [Migration from Previous Docs](#migration-from-previous-docs)

---

## Overview

Novel AI uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to load configuration from environment variables. All settings have sensible defaults — you only need to set the values that differ from the default.

### How Environment Variables Are Loaded

1. `AppSettings` in `backend/src/novelai/config/settings.py` defines every variable with a default
2. On startup, pydantic-settings reads from `.env` in the project root
3. Process environment variables override `.env` values
4. Docker Compose reads `deploy/.env` automatically

### Change Categories

Each variable in the reference below has a **Change?** column:

| Label | Meaning |
|-------|---------|
| **must change** | Required for any non-trivial use |
| **can leave default** | Sensible default, change only if needed |
| **rarely changed** | Advanced tuning |
| **enables feature** | Must be set to enable this feature |
| **profile-specific** | Only needed for specific deployment profiles |

---

## File Structure

| File | Location | Purpose | Tracked in Git? |
|------|----------|---------|-----------------|
| `.env` | root | Local development | No (`.gitignore` line 73) |
| `.env.example` | root | Template for local dev | Yes |
| `deploy/.env` | deploy/ | Docker Compose configuration | No (`.gitignore` line 74) |
| `deploy/.env.example` | deploy/ | Template for Docker | Yes |
| `deploy/.env.production.example` | deploy/ | Production-specific template | Yes |

> **Security note:** `.env` and `.env.*` (without `.example`) are gitignored. Only `.example` files are tracked in version control. Never commit real secrets.

---

## Quick Start

```yaml
# .env (root) — minimum required to run
ENV: development
SESSION_SECRET_KEY: <generate-with-python-secrets>
OWNER_BOOTSTRAP_SECRET: <set-a-value>
DATABASE_URL: postgresql+psycopg://novelai:novelai@localhost:5432/novelai
REDIS_URL: redis://localhost:6379/0
PROVIDER_DEFAULT: gemini
```

Generate required secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Variable Reference by Category

### Runtime

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `ENV` | `str` | `development` | No | **must change** in prod | Runtime environment. `production` enables HTTPS-only cookies and session secret fail-closed. | `production` |
| `LOG_LEVEL` | `str` | `INFO` | No | can leave default | Python log level. | `DEBUG` |

### Storage

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `NOVEL_LIBRARY_DIR` | `Path` | `./storage/novel_library` | No | can leave default | Root directory for runtime data (metadata, chapters, exports). | `/app/storage/novel_library` |
| `STORAGE_BACKEND` | `str` | `filesystem` | No | rarely changed | Backend type. `filesystem` (default) or `s3`. | `s3` |
| `S3_BUCKET` | `str` | `None` | If `STORAGE_BACKEND=s3` | enables feature | S3 bucket name. | `my-novelai-bucket` |
| `S3_REGION` | `str` | `us-east-1` | If `STORAGE_BACKEND=s3` | can leave default | S3 region. | `eu-west-1` |
| `S3_KEY_PREFIX` | `str` | `""` | No | can leave default | Optional key prefix (folder) for all S3 objects. | `novelai-prod/` |
| `S3_ENDPOINT` | `str` | `None` | No | **enables feature** | Custom S3-compatible endpoint URL (for example MinIO or Cloudflare R2). | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |

### Backups

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `BACKUP_ENABLED` | `bool` | `false` | Production | **must change** in prod | Enables the lightweight daily backup scheduler. | `true` |
| `BACKUP_SCHEDULE_CRON` | `str` | `0 2 * * *` | No | can leave default | Cron expression evaluated by the scheduler for object backups. | `0 2 * * *` |
| `BACKUP_TIMEZONE` | `str` | `UTC` | No | can leave default | IANA timezone used when evaluating the backup schedule. | `UTC` |
| `BACKUP_S3_ENABLED` | `bool` | `false` | With S3 production storage | **must change** in prod | Enables committed snapshots to an independent S3-compatible bucket. | `true` |
| `BACKUP_S3_ENDPOINT_URL` | `str` | `None` | With offsite snapshots | **must change** | Endpoint for the independent backup target. | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `BACKUP_S3_REGION` | `str` | `auto` | With offsite snapshots | can leave default for R2 | Backup-target region. | `auto` |
| `BACKUP_S3_BUCKET` | `str` | `None` | With offsite snapshots | **must change** | Independent backup bucket; must differ from `S3_BUCKET`. | `my-backup-bucket` |
| `BACKUP_S3_PREFIX` | `str` | `snapshots` | With offsite snapshots | can leave default | Non-root prefix containing committed snapshot directories. | `snapshots` |
| `BACKUP_S3_ACCESS_KEY_ID` | `SecretStr` | `None` | With offsite snapshots | **must change** | Target-scoped backup access key. | `<secret>` |
| `BACKUP_S3_SECRET_ACCESS_KEY` | `SecretStr` | `None` | With offsite snapshots | **must change** | Target-scoped backup secret key. | `<secret>` |
| `SNAPSHOT_SOURCE_S3_ACCESS_KEY_ID` | `SecretStr` | `None` | With offsite snapshots | **must change** | Dedicated read-only credential for the production bucket. | `<secret>` |
| `SNAPSHOT_SOURCE_S3_SECRET_ACCESS_KEY` | `SecretStr` | `None` | With offsite snapshots | **must change** | Dedicated read-only source secret. | `<secret>` |
| `SCHEDULED_JOB_LEASE_SECONDS` | `int` | `900` | No | tune for workload | Cross-instance lease duration; active jobs renew at one-third of this interval. | `900` |

### Managed PostgreSQL

The application reuses one engine per effective configuration. Direct and session modes use bounded SQLAlchemy pools; transaction mode uses `NullPool` and disables psycopg automatic prepared statements.

| Variable | Default | Description |
|---|---:|---|
| `DB_CONNECTION_MODE` | `direct` | `direct`, `session`, or `transaction`. |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | `5` / `5` | Permanent and burst connections per process; ignored in transaction mode. |
| `DB_CONNECTION_BUDGET` | `20` | Maximum combined admin and reader pool capacity accepted by production validation. |
| `DB_POOL_TIMEOUT_SECONDS` / `DB_POOL_RECYCLE_SECONDS` | `30` / `1800` | Checkout timeout and connection recycle interval. |
| `DB_CONNECT_TIMEOUT_SECONDS` | `10` | Network connection timeout. |
| `DB_SSL_MODE` | `prefer` | Production requires `require`, `verify-ca`, or `verify-full`. |
| `DB_STATEMENT_TIMEOUT_MS` | `120000` | Per-connection statement timeout. |
| `DB_LOCK_TIMEOUT_MS` | `10000` | Per-connection lock wait timeout. |
| `DB_IDLE_IN_TRANSACTION_TIMEOUT_MS` | `60000` | Terminates abandoned transactions. |

### Logical Database Recovery

`DATABASE_BACKUP_ENABLED=true` schedules a PostgreSQL 17 custom-format dump of the application-owned `public` schema. The dump stream is encrypted with chunked AES-256-GCM before it reaches disk and is committed under `DATABASE_BACKUP_S3_PREFIX` only after its manifest is written.

Required production values are `DATABASE_BACKUP_ENCRYPTION_KEY`, a non-root database prefix distinct from `BACKUP_S3_PREFIX`, the existing independent backup-bucket credentials, and working PostgreSQL 17 client tools. Operator alerts additionally require `OPERATOR_ALERT_EMAIL` and tested SMTP configuration.

Set `DATABASE_RESTORE_VERIFICATION_ENABLED=true` only with a dedicated clean database whose name contains `restore`. The leased monthly job downloads the newest committed manifest, decrypts to a short-lived local file, runs PostgreSQL 17 `pg_restore`, checks the Alembic head, public-table presence, and validated constraints, then deletes both temporary files.

### Web

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `WEB_HOST` | `str` | `127.0.0.1` | No | can leave default | Bind address. Use `0.0.0.0` in Docker. | `0.0.0.0` |
| `WEB_PORT` | `int` | `8000` | No | can leave default | Bind port. | `8000` |
| `WEB_API_KEY` | `SecretStr` | `None` | No | **recommended** in prod | Bearer token for admin API. | `a-long-random-token` |
| `WEB_CORS_ORIGINS` | `list[str]` | `[]` | No | **must change** with custom domain | CORS origins JSON array. Empty = same-origin (behind reverse proxy). | `["https://example.com"]` |
| `WEB_REQUEST_TIMEOUT_SECONDS` | `int` | `600` | No | can leave default | HTTP request timeout. | `120` |
| `WEB_RATE_LIMITER_BACKEND` | `str` | `memory` | No | **must change** for multi-instance | Rate limiter backend: `memory` (single-instance) or `redis` (multi-instance). | `redis` |
| `JOB_WORKER_ENABLED` | `bool` | `false` | No | can leave default | Enable in-process background activity worker. | `true` |
| `JOB_WORKER_POLL_SECONDS` | `float` | `2.0` | No | can leave default | Worker poll interval in seconds. | `3` |

### Provider / Model

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `PROVIDER_DEFAULT` | `str` | `gemini` | No | can leave default | Default translation provider. Use `dummy` for testing. | `gemini` |
| `PROVIDER_GEMINI_API_KEY` | `SecretStr` | `None` | If using Gemini | **must change** | Google AI Studio API key for Gemini. | `AIza...` |
| `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` | `SecretStr` | `None` | If storing API keys in DB | **must change** | Key for encrypting stored provider credentials. Generate with `secrets.token_urlsafe(32)`. | `aBcD...` |
| `PROVIDER_GEMINI_DEFAULT_MODEL` | `str` | `gemini-3.1-flash-lite` | No | can leave default | Default Gemini model for translation. | `gemini-3.1-flash-lite` |
| `PROVIDER_GEMINI_MODEL_FALLBACKS` | `list[str]` | `["gemma-4-31b-it"]` | No | can leave default | Gemini fallback model list. | `["gemma-4-31b-it"]` |

### Scraping

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `SCRAPE_DELAY_SECONDS` | `float` | `1.0` | No | can leave default | Minimum delay between HTTP requests to source sites (rate limiting). | `0.5` |

### Translation

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `TRANSLATION_CONCURRENCY` | `int` | `4` | No | can leave default | Pipeline concurrency level. | `8` |
| `TRANSLATION_CHAPTER_CONCURRENCY` | `int` | `1` | No | can leave default | Max parallel chapters per orchestrator run (1-32). | `4` |
| `TRANSLATION_TARGET_CHARS_PER_CHUNK` | `int` | `4500` | No | rarely changed | Target characters per chunk for translation. | `5000` |
| `TRANSLATION_HARD_MAX_CHARS_PER_CHUNK` | `int` | `7000` | No | rarely changed | Hard maximum characters per chunk. | `8000` |
| `TRANSLATION_CHUNK_OVERLAP_PARAGRAPHS` | `int` | `1` | No | rarely changed | Overlap between adjacent chunks in paragraphs. | `2` |
| `TRANSLATION_ALLOW_MULTI_CHAPTER_BUNDLES` | `bool` | `true` | No | rarely changed | Allow bundling multiple chapters into one translation request. | `false` |
| `TRANSLATION_MAX_CHAPTERS_PER_BUNDLE` | `int` | `3` | No | rarely changed | Max chapters per bundle (if bundling enabled). | `5` |
| `TRANSLATION_MAX_ATTEMPTS_PER_CHUNK` | `int` | `3` | No | can leave default | Max retry attempts per chunk on failure. | `5` |
| `TRANSLATION_METADATA_CHAPTER_TITLE_BATCH_SIZE` | `int` | `25` | No | rarely changed | Batch size for chapter title translation. | `50` |
| `TRANSLATION_ADAPTIVE_CHUNKING_ENABLED` | `bool` | `true` | No | rarely changed | Enable adaptive chunk size based on content. | `false` |
| `TRANSLATION_ADAPTIVE_SOFT_TARGET_CHARS` | `int` | `5800` | No | rarely changed | Soft target for adaptive chunking. | `6000` |
| `TRANSLATION_ADAPTIVE_HARD_MAX_CHARS` | `int` | `7000` | No | rarely changed | Hard max for adaptive chunking. | `8000` |
| `TRANSLATION_CONDITIONAL_OVERLAP_ENABLED` | `bool` | `true` | No | rarely changed | Enable conditional overlap between chunks. | `false` |
| `TRANSLATION_DEFAULT_OVERLAP_PARAGRAPHS` | `int` | `0` | No | rarely changed | Default overlap when conditional overlap is off. | `1` |
| `TRANSLATION_UNSAFE_BOUNDARY_OVERLAP_PARAGRAPHS` | `int` | `1` | No | rarely changed | Overlap at unsafe boundaries. | `2` |
| `TRANSLATION_BOUNDARY_CONTEXT_CHARS` | `int` | `160` | No | rarely changed | Context characters at chunk boundaries. | `200` |
| `TRANSLATION_DELTA_WINDOW_PADDING_PARAGRAPHS` | `int` | `1` | No | rarely changed | Padding paragraphs for delta retranslation window. | `2` |
| `TRANSLATION_DELTA_RETRANSLATION_ENABLED` | `bool` | `true` | No | rarely changed | Enable delta retranslation (only changed paragraphs). | `false` |
| `TRANSLATION_DELTA_REQUIRE_STRUCTURED_PARAGRAPH_MAP` | `bool` | `true` | No | rarely changed | Require paragraph map for delta retranslation. | `false` |
| `TRANSLATION_DELTA_FORCE_FULL_ON_UNSAFE` | `bool` | `true` | No | rarely changed | Fall back to full retranslation when delta is unsafe. | `false` |
| `TRANSLATION_SCHEDULER_POLICY` | `str` | `volume_first` | No | can leave default | Scheduler model selection policy. | `quality_first` |
| `TRANSLATION_MODEL_POLICY` | `list[dict]` | `[]` | No | can leave default | Custom model policy list. Items define provider_key, provider_model, priority_order, etc. | — |
| `COST_PER_TOKEN_USD` | `float` | `0.000002` | No | rarely changed | Estimated cost per token for usage tracking. | `0.000003` |
| `TRANSLATION_TARGET_LANGUAGE` | `str` | `English` | No | can leave default | Target language for translation. | `English` |
| `TRANSLATION_LOW_CONFIDENCE_ACTIVATION_THRESHOLD` | `float` | `0.55` | No | can leave default | Confidence threshold below which translations are not auto-activated. | `0.5` |

### Database

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `DATABASE_URL` | `str` | `None` | Yes (for DB-backed features) | **must change** | PostgreSQL connection string. Format: `postgresql+psycopg://user:password@host:port/dbname` | `postgresql+psycopg://novelai:novelai@localhost:5432/novelai` |

### Redis

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `REDIS_URL` | `str` | `None` | Yes (for redis rate limiter / RQ workers) | **must change** if used | Redis connection string. | `redis://localhost:6379/0` |

### Auth / Session

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `SESSION_SECRET_KEY` | `str` | `changeme-generate-a-real-secret-in-production` | Yes (production) | **must change** in prod | Key for signing HTTP-only session cookies. Generate with `secrets.token_hex(32)`. | `a1b2c3...` |
| `OWNER_BOOTSTRAP_SECRET` | `str` | `None` | Yes (until OAuth configured) | **must change** | Bootstrap secret for initial owner login. Never commit real value. | `a-strong-random-value` |
| `SESSION_MAX_AGE` | `int` | `28800` (8 hours) | No | can leave default | Session cookie max age in seconds. | `86400` |
| `GOOGLE_OAUTH_CLIENT_ID` | `str` | `None` | If using Google OAuth | **enables feature** | Google OAuth client ID. All three `GOOGLE_OAUTH_*` must be set. | `123456.apps.googleusercontent.com` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | `SecretStr` | `None` | If using Google OAuth | **enables feature** | Google OAuth client secret. | `GOCSPX-...` |
| `GOOGLE_OAUTH_REDIRECT_URI` | `str` | `None` | If using Google OAuth | **enables feature** | Must match Google Cloud Console redirect URI exactly. | `http://localhost:8000/api/auth/google/callback` |
| `PUBLIC_FRONTEND_URL` | `str` | `http://127.0.0.1:3000` | Yes (production) | **must change** in prod | Frontend base URL for post-OAuth redirect and email links. | `https://novelai.example.com` |
| `AUTH_EMAIL_DELIVERY_MODE` | `str` | `noop` | No | can leave default | Email delivery mode: `noop` (no email sent) or `smtp`. | `smtp` |

Each running deployment uses exactly one `GOOGLE_OAUTH_REDIRECT_URI`. A Google OAuth web client may register multiple authorized redirect URIs (for example local direct-backend, local Compose, and production), but the value selected in each environment must match one registered URI exactly. Do not copy a local HTTP callback into a deployed production environment; production uses the final HTTPS application origin.

### Email / SMTP

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `AUTH_PASSWORD_RESET_PATH` | `str` | `/password/reset` | No | can leave default | Frontend path for password reset. | `/reset` |
| `AUTH_EMAIL_VERIFICATION_PATH` | `str` | `/email/verify` | No | can leave default | Frontend path for email verification. | `/verify` |
| `SMTP_HOST` | `str` | `None` | If `AUTH_EMAIL_DELIVERY_MODE=smtp` | **must change** | SMTP server hostname. | `smtp.sendgrid.net` |
| `SMTP_PORT` | `int` | `587` | If `AUTH_EMAIL_DELIVERY_MODE=smtp` | can leave default | SMTP server port. | `465` |
| `SMTP_USERNAME` | `str` | `None` | If `AUTH_EMAIL_DELIVERY_MODE=smtp` | **must change** | SMTP authentication username. | `apikey` |
| `SMTP_PASSWORD` | `SecretStr` | `None` | If `AUTH_EMAIL_DELIVERY_MODE=smtp` | **must change** | SMTP authentication password. | `SG.xxxx` |
| `SMTP_FROM_EMAIL` | `str` | `None` | If `AUTH_EMAIL_DELIVERY_MODE=smtp` | **must change** | From address for outgoing emails. | `noreply@example.com` |
| `SMTP_FROM_NAME` | `str` | `Dokushodo` | No | can leave default | Display name for the From address. | `Novel AI` |
| `SMTP_STARTTLS` | `bool` | `true` | No | can leave default | Enable STARTTLS for SMTP. | `false` |
| `SMTP_USE_SSL` | `bool` | `false` | No | can leave default | Use SSL for SMTP (port 465). | `true` |
| `SMTP_TIMEOUT_SECONDS` | `float` | `10.0` | No | can leave default | SMTP connection timeout. | `15` |

### Cache

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `TRANSLATION_CACHE_ENABLED` | `bool` | `true` | No | can leave default | Enable translation cache (SHA-256 keyed, sharded file storage). | `false` |
| `TRANSLATION_CACHE_MAX_ENTRIES` | `int` | `100000` | No | rarely changed | Maximum cache entries before eviction. | `50000` |
| `TRANSLATION_CACHE_TTL_SECONDS` | `int` | `0` | No | can leave default | Cache TTL in seconds. `0` = no expiry. | `86400` |
| `USAGE_LOG_MAX_ENTRIES` | `int` | `10000` | No | rarely changed | Max usage log entries before rotation. | `5000` |

### Semantic Cache

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `SEMANTIC_CACHE_ENABLED` | `bool` | `false` | No | **enables feature** | Enable semantic cache (future feature, disabled by default). | `true` |
| `SEMANTIC_CACHE_SIMILARITY_THRESHOLD` | `float` | `0.85` | No | can leave default | Cosine similarity threshold for cache candidates (0.0-1.0). | `0.9` |
| `SEMANTIC_CACHE_CONTEXT_GUARD_ENABLED` | `bool` | `true` | No | can leave default | Enable context guard for semantic cache. | `false` |
| `SEMANTIC_CACHE_EMBEDDING_PROVIDER` | `str` | `gemini` | No | can leave default | Embedding provider for semantic cache. | `gemini` |
| `SEMANTIC_CACHE_EMBEDDING_MODEL` | `str` | `text-embedding-004` | No | can leave default | Embedding model for semantic cache. | `text-embedding-004` |

### LLM QA

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `LLM_QA_ENABLED` | `bool` | `false` | No | **enables feature** | Enable LLM QA (future feature, disabled by default). | `true` |
| `LLM_QA_PROVIDER` | `str` | `gemini` | No | can leave default | Provider for LLM QA. | `gemini` |
| `LLM_QA_MODEL` | `str` | `gemini-3.1-flash-lite` | No | can leave default | Model for LLM QA. | `gemini-3.1-flash-lite` |
| `LLM_QA_COST_TRACKING_ENABLED` | `bool` | `true` | No | can leave default | Enable cost tracking for LLM QA. | `false` |

### Docker Compose

| Variable | Type | Default | Required? | Change? | Description | Example |
|----------|------|---------|----------|---------|-------------|---------|
| `PUBLIC_HTTP_PORT` | `int` | `80` | No | can leave default | Public HTTP port for Caddy. | `8080` |
| `PUBLIC_HTTPS_PORT` | `int` | `443` | No | can leave default | Public HTTPS port for Caddy. | `443` |
| `SITE_DOMAIN` | `str` | — | No | can leave default | Public domain for Caddy TLS. | `novelai.example.com` |

The canonical Compose file does not provision the primary application database, so legacy `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `POSTGRES_HOST_PORT` placeholders are not used. Configure Supabase or another managed PostgreSQL service only through `DATABASE_URL` and the `DB_*` connection controls. The isolated `restore-db` service has fixed local role/database names and receives its separate password through `DATABASE_RESTORE_PASSWORD`.

---

## Environment Profiles

### Development (local)

```yaml
# .env or deploy/.env
ENV: development
PROVIDER_DEFAULT: gemini
WEB_RATE_LIMITER_BACKEND: memory
JOB_WORKER_ENABLED: false
DATABASE_URL: postgresql+psycopg://novelai:novelai@localhost:5432/novelai
REDIS_URL: redis://localhost:6379/0
SESSION_SECRET_KEY: <any-value-works-in-dev>
OWNER_BOOTSTRAP_SECRET: <any-value-works-in-dev>
PUBLIC_FRONTEND_URL: http://127.0.0.1:3000
AUTH_EMAIL_DELIVERY_MODE: noop
```

**Use case:** Local development without real provider or database.

### Staging (ngrok tunnel)

```yaml
# deploy/.env
ENV: development
PROVIDER_DEFAULT: gemini
PROVIDER_GEMINI_API_KEY: <real-key>
WEB_RATE_LIMITER_BACKEND: memory
JOB_WORKER_ENABLED: true
PUBLIC_FRONTEND_URL: https://your-tunnel.ngrok-free.dev
SESSION_SECRET_KEY: <strong-secret>
OWNER_BOOTSTRAP_SECRET: <strong-secret>
GOOGLE_OAUTH_CLIENT_ID: <your-client-id>
GOOGLE_OAUTH_CLIENT_SECRET: <your-client-secret>
GOOGLE_OAUTH_REDIRECT_URI: https://your-tunnel.ngrok-free.dev/api/auth/google/callback
```

**Use case:** Testing with real provider and OAuth via ngrok tunnel.

### Production

```yaml
# deploy/.env
ENV: production
PROVIDER_DEFAULT: gemini
PROVIDER_GEMINI_API_KEY: <real-key>
WEB_RATE_LIMITER_BACKEND: redis
JOB_WORKER_ENABLED: true
DATABASE_URL: <supabase-or-managed-postgres-url>
REDIS_URL: redis://redis:6379/0
SESSION_SECRET_KEY: <strong-random-secret>
OWNER_BOOTSTRAP_SECRET: <strong-random-secret>
PUBLIC_FRONTEND_URL: https://yourdomain.com
WEB_API_KEY: <long-random-admin-token>
```

**Use case:** Production deployment with Caddy reverse proxy, Supabase/managed Postgres, Redis rate limiter.

---

## Security Notes

### Secret Variables (Never Commit Real Values)

All of these are **SecretStr** or sensitive strings. Their actual values must never appear in version control:

| Variable | Why It's Secret | How To Generate |
|----------|----------------|-----------------|
| `SESSION_SECRET_KEY` | Signs session cookies; compromise allows session forgery | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `OWNER_BOOTSTRAP_SECRET` | Grants initial owner access before OAuth | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `PROVIDER_GEMINI_API_KEY` | Provider API key; compromise allows unauthorized API usage | Get from Google AI Studio |
| `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` | Encrypts stored provider credentials; loss requires re-encryption | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `WEB_API_KEY` | Bearer token for admin API | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `GOOGLE_OAUTH_CLIENT_SECRET` | OAuth client secret; compromise allows token forgery | Get from Google Cloud Console |
| `SMTP_PASSWORD` | Email password; compromise allows unauthorized email sending | Use app-specific password |
| `DATABASE_URL` | Contains database password in the connection string | Set via Supabase dashboard or your DB provider |

### .gitignore Coverage

The `.gitignore` file (root) already covers:

```
.env          # line 73 — local development .env
.env.*        # line 74 — all .env variants
!.env.example # line 75 — exception for example files
```

Run this to verify no secrets are tracked:

```bash
git ls-files | grep "\.env"
# Should only show: .env.example and deploy/.env.example (and similar)
```

### Rotation Guidance

- **`SESSION_SECRET_KEY`**: Rotate periodically. Rotating invalidates all existing sessions.
- **`PROVIDER_CREDENTIAL_ENCRYPTION_KEY`**: Rotate with care. Requires re-encrypting all stored credentials using the old key first.
- **Provider API keys**: Rotate per provider's guidance (typically every 90 days).
- **`DATABASE_URL`**: Rotate database passwords immediately if compromised.

---

## Docker Compose Integration

### File Relationships

```
deploy/compose.yml
  reads → deploy/.env (automatically)
  references → Dockerfile in deploy/
  depends on → redis, migrate services
```

### Variable Precedence (highest to lowest)

1. Environment variables passed to `docker compose run`
2. `deploy/.env` file
3. `compose.yml` defaults (in `${VAR:-default}` expressions)

### DATABASE_URL Resolution

The `compose.yml` does **not** provision a PostgreSQL service. An external database instance must be provided via `DATABASE_URL`.

- **If `DATABASE_URL` is set** in `deploy/.env` or process environment → all services use it
- **If `DATABASE_URL` is NOT set** → services fail to start (compose requires it)

To use Supabase or any managed PostgreSQL, add to `deploy/.env`:

```bash
DATABASE_URL=postgresql+psycopg://postgres:your-password@db.your-project.supabase.co:5432/postgres
```

To use a locally running PostgreSQL (not managed by Compose), set `DATABASE_URL` to point at it:

```bash
DATABASE_URL=postgresql+psycopg://novelai:novelai@host.docker.internal:5432/novelai
```

> **Note:** Compose only provisions Redis, Caddy, frontend, backend, reader, and the migration service. PostgreSQL must be provided externally.

---

## Supabase Setup

### Prerequisites

- A Supabase project at https://supabase.com
- Your project's database connection string

### Step 1: Get Your Connection String

1. Go to [Supabase Dashboard](https://supabase.com/dashboard/projects)
2. Select your project
3. Go to **Project Settings → Database**
4. Under **Connection string**, copy the **URI** mode string

The dashboard may display a `postgresql://` URI. Normalize its scheme to the project's psycopg v3 form before use:
```
postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

> Choose the direct or pooled endpoint shown by the current Supabase Connect panel. Connection modes and network support vary; do not infer pooling behavior from a port alone.

### Step 2: Configure `deploy/.env`

Add the Supabase URL:

```bash
# Replace values in brackets
DATABASE_URL=postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres
```

### Step 3: Run Migrations

```bash
cd deploy
docker compose run migrate
```

Or directly (from repo root):

```powershell
Set-Location backend
$env:DATABASE_URL = "postgresql+psycopg://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-REF].supabase.co:5432/postgres"
alembic -c alembic.ini upgrade head
```

### Step 4: Start Services

```bash
cd deploy
docker compose up
```

Supabase requires SSL. The backend uses `postgresql+psycopg://` driver which supports SSL by default. If you get SSL errors, add `?sslmode=require` to the connection string:

```
DATABASE_URL=postgresql+psycopg://postgres:password@db.project.supabase.co:5432/postgres?sslmode=require
```

### Step 5: Verify

```bash
docker compose logs backend
# Look for: "Engine created" or "Connected to database"
```

### Supabase-Specific Notes

- **SSL is required** — Supabase enforces it. The `postgresql+psycopg://` driver handles SSL automatically.
- **Connection mode** — Select direct, session-pooler, or transaction-pooler mode from the current Supabase Connect panel based on network reachability and workload. Verify prepared-statement compatibility before using transaction pooling.
- **IPv6** — Some Supabase projects may require IPv6 support on your Docker host.
- **Connection limits** — Limits depend on the project's current compute and pooler configuration. Check the project dashboard instead of relying on a fixed number.
- **Backups** — Availability, retention, and point-in-time recovery depend on the current project plan and configuration. Database backups are separate from object-store backups and must be verified independently.

---

## Troubleshooting

### Common Errors

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `SESSION_SECRET_KEY` is default | Production mode with default secret | Set `SESSION_SECRET_KEY` to a strong random value |
| `could not connect to server` | Database offline or wrong `DATABASE_URL` | Check database status and URL format |
| `Provider not configured` | `PROVIDER_DEFAULT` mismatch or missing API key | Check `PROVIDER_DEFAULT` and corresponding `PROVIDER_*_API_KEY` |
| `CORS error` in browser | `WEB_CORS_ORIGINS` mismatch | Set `WEB_CORS_ORIGINS=["https://yourdomain.com"]` |
| `Session not persisted` | `SESSION_SECRET_KEY` changed between restarts | Keep the same `SESSION_SECRET_KEY` across restarts |
| `Google OAuth error` | Redirect URI mismatch | Must match exactly between `.env` and Google Cloud Console |
| `SSL connection required` | Connecting to Supabase without SSL | Add `?sslmode=require` to `DATABASE_URL` |
| `.env not found` | Running from wrong directory | Run from project root; or set `PYTHONPATH` |

### Verification Commands

```bash
# Check all loaded settings
python -c "from novelai.config.settings import settings; print(settings.model_dump_json(indent=2))"

# Test database connection
python -c "
from sqlalchemy import create_engine
from novelai.config.settings import settings
engine = create_engine(settings.DATABASE_URL)
engine.connect()
print('Database connection OK')
"

# Check env vars are loaded correctly
python -c "from novelai.config.settings import settings; print(settings.ENV, settings.PROVIDER_DEFAULT, settings.LOG_LEVEL)"

# Verify .gitignore coverage
git ls-files | grep "\.env"
```

---

## Migration from Previous Docs

This document (`docs/environment.md`) is the **single source of truth** for all environment variables. It supersedes the scattered env var references in:

- `docs/guides/GETTING_STARTED.md` — env var sections now point here
- `docs/architecture/architecture.md` — mentions `.env` in security context
- `docs/reference/data-output-structure.md` — mentions provider keys

When adding new environment variables to the codebase, update this file along with `settings.py`.
