# Deployment Checklist

**Last reviewed**: 2026-06-15 (DEP1B fixes)
**Authority**: subordinate to `docs/architecture/architecture.md`

---

## 1. Required Production Environment Variables

See `.env.example` for full reference. Critical variables:

| Variable | Required | Notes |
|---|---|---|
| `ENV=production` | Yes | Enables `https_only` cookies, session secret fail-closed |
| `SESSION_SECRET_KEY` | **Yes** | Strong random secret; app refuses to start if default |
| `OWNER_BOOTSTRAP_SECRET` | Yes | Owner login secret; never commit real value |
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:***@host:5432/dbname` |
| `REDIS_URL` | Yes | `redis://host:6379/0` |
| `GOOGLE_OAUTH_CLIENT_ID` | For public login | Google Cloud Console |
| `GOOGLE_OAUTH_CLIENT_SECRET` | For public login | Google Cloud Console |
| `GOOGLE_OAUTH_REDIRECT_URI` | For public login | Must match Google Console exactly |
| `PUBLIC_FRONTEND_URL` | For public login and auth email links | Frontend origin for post-OAuth redirect, password reset, and email verification links |
| `AUTH_EMAIL_DELIVERY_MODE` | For auth email | `noop` by default; set `smtp` only after SMTP vars are configured |
| `WEB_CORS_ORIGINS` | If cross-origin | Empty list (default) for same-origin behind Caddy |
| `WEB_RATE_LIMITER_BACKEND` | Recommended | `redis` for multi-instance; `memory` for single |
| `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` | If using admin-managed provider keys | Strong secret used to decrypt DB-backed provider credentials; never commit the real value |
| `PROVIDER_GEMINI_API_KEY` | If using Gemini | Translation provider key |
| `NVIDIA_API_KEY` | If using NVIDIA fallback | Translation provider key |

---

## 2. Google OAuth Redirect URI Checklist

### Google Cloud Console

- [ ] Create OAuth 2.0 Client ID (Web application type)
- [ ] Add authorized redirect URIs:
  - Development: `http://127.0.0.1:8000/api/auth/google/callback`
  - Production: `https://yourdomain.com/api/auth/google/callback`
- [ ] URI must match `GOOGLE_OAUTH_REDIRECT_URI` exactly (scheme, host, port, path)

### Backend Environment

- [ ] `GOOGLE_OAUTH_CLIENT_ID` set
- [ ] `GOOGLE_OAUTH_CLIENT_SECRET` set
- [ ] `GOOGLE_OAUTH_REDIRECT_URI` set and matches Google Console
- [ ] `PUBLIC_FRONTEND_URL` set to frontend origin (e.g., `https://yourdomain.com`)

---

## 3. Auth Email / SMTP Checklist

Password reset and email verification use the backend auth email service.

### Safe Defaults

- [ ] `AUTH_EMAIL_DELIVERY_MODE=noop` unless SMTP is ready.
- [ ] In `noop` mode, password reset and verification tokens are created but no email is sent.
- [ ] `noop` mode does not require any SMTP variables and should not block app startup.
- [ ] Configure SMTP before enabling frontend password reset or email verification UI.

### SMTP Mode

Set `AUTH_EMAIL_DELIVERY_MODE=smtp` and configure:

| Variable | Required in `smtp` mode | Notes |
|---|---|---|
| `SMTP_HOST` | Yes | SMTP server hostname |
| `SMTP_PORT` | Yes | Usually `587` for STARTTLS or `465` for SSL |
| `SMTP_USERNAME` | Usually | SMTP username, if provider requires auth |
| `SMTP_PASSWORD` | Usually | SMTP password or app password; never commit real value |
| `SMTP_FROM_EMAIL` | Yes | Sender email address |
| `SMTP_FROM_NAME` | No | Defaults to `Dokushodo` |
| `SMTP_STARTTLS` | No | Defaults to `true`; use with port `587` |
| `SMTP_USE_SSL` | No | Defaults to `false`; use with port `465` when needed |
| `SMTP_TIMEOUT_SECONDS` | No | Defaults to `10` |
| `PUBLIC_FRONTEND_URL` | Yes | Base origin used in reset/verification links |
| `AUTH_PASSWORD_RESET_PATH` | No | Defaults to `/password/reset` |
| `AUTH_EMAIL_VERIFICATION_PATH` | No | Defaults to `/email/verify` |

### Security Notes

- [ ] Password reset and email verification links contain bearer tokens.
- [ ] Do not log reset/verification URLs, request bodies, or email bodies.
- [ ] Do not log `SMTP_PASSWORD`.
- [ ] Use provider app passwords or restricted SMTP credentials where available.
- [ ] Missing SMTP config in `smtp` mode returns a safe delivery failure; auth endpoints still return generic responses to avoid account enumeration.
- [ ] Invalid `AUTH_EMAIL_DELIVERY_MODE` fails clearly during mailer construction.

---

## 4. HTTPS / Caddy / Reverse Proxy Checklist

### Production (HTTPS)

- [ ] Use `deploy/Caddyfile.example` as template (copy to `deploy/Caddyfile`)
- [ ] Replace `{$SITE_DOMAIN:yourdomain.com}` with actual domain or set `SITE_DOMAIN` env var
- [ ] DNS A/AAAA records point to server
- [ ] Port 443 exposed in `deploy/compose.yml` (already configured)
- [ ] Caddy auto-provisions Let's Encrypt certificate on first request

### Local Development (HTTP)

- [ ] Default `deploy/Caddyfile` uses `:80` — works for local Docker usage
- [ ] Port 80 exposed in `deploy/compose.yml` (already configured)

### Caddy Routing

- [ ] `/api/*` → `backend:8000`
- [ ] Everything else → `frontend:3000`

---

## 5. Session Cookie / CSRF Checklist

### Session Security

- [ ] `ENV=production` → `https_only=True` for session cookies
- [ ] `SESSION_SECRET_KEY` is strong random secret (not default)
- [ ] Cookies are HTTP-only, SameSite=Lax

### CSRF Protection

- [ ] Token endpoint: `GET /api/auth/csrf`
- [ ] Header: `X-CSRF-Token`
- [ ] Frontend auto-fetches and sends token on mutations
- [ ] All cookie-auth mutations require CSRF validation

### CORS

- [ ] Same-origin behind Caddy: `WEB_CORS_ORIGINS=[]` (default, recommended)
- [ ] Cross-origin: set `WEB_CORS_ORIGINS=["https://frontend.example.com"]`
- [ ] CORS allows credentials and `X-CSRF-Token` header

---

## 6. Database Migration Checklist

### PostgreSQL

- [ ] PostgreSQL 16 running and accessible
- [ ] `DATABASE_URL` set with correct connection string
- [ ] Alembic migrations applied

### Migration Commands

```bash
# From repository root
cd backend
alembic upgrade head
alembic current  # Verify current revision
```

**Current schema**: `bb48b53baff5_initial_schema`

---

## 7. Redis / Worker Checklist

### Redis

- [ ] Redis 7 running and accessible
- [ ] `REDIS_URL` set (e.g., `redis://redis:6379/0`)
- [ ] `WEB_RATE_LIMITER_BACKEND=redis` set for multi-instance production deployments

### Background Worker

Choose one:

**Option A**: In-process worker (single instance)
```bash
# Set in .env
JOB_WORKER_ENABLED=true
```

**Option B**: Separate worker process (recommended for scaling)
```bash
novelaibook worker
```

---

## 8. Service Startup Order (Docker Compose)

1. `postgres` — PostgreSQL (health check required)
2. `redis` — Redis (health check required)
3. `migrate` — Runs `alembic upgrade head` automatically (depends on `postgres` health)
4. `backend` — FastAPI (depends on `migrate` completion, `postgres`, and `redis`)
5. `frontend` — Next.js
6. `caddy` — Reverse proxy (depends on backend, frontend)

### Quick Start

```bash
# 1. Copy environment files
cp .env.example .env
cp frontend/.env.example frontend/.env
# Edit .env with production values

# 2. Configure Caddyfile for production
cp deploy/Caddyfile.example deploy/Caddyfile
# Edit with your domain

# 3. Start services (migrations run automatically via the `migrate` service)
docker compose --env-file .env -f deploy/compose.yml up -d

# 4. Verify
curl http://localhost/api/health
# Should return: {"status":"ok"}
```

### Compose Env File Rule

Run Docker Compose from the repository root and pass the root `.env` explicitly:

```bash
docker compose --env-file .env -f deploy/compose.yml ...
```

In this repository, plain `docker compose -f deploy/compose.yml ...` may not
load the root `.env` reliably. This matters for
`PROVIDER_CREDENTIAL_ENCRYPTION_KEY`: encrypted DB-backed provider credentials
cannot hydrate unless Docker receives the same key that encrypted them.

Never commit `.env`. Never rotate `PROVIDER_CREDENTIAL_ENCRYPTION_KEY` without
re-encrypting or recreating the DB-backed provider credentials that depend on
it.

Windows PowerShell helper:

```powershell
.\scripts\docker-compose-dev.ps1 up -d postgres redis backend
.\scripts\docker-compose-dev.ps1 run --rm migrate
.\scripts\docker-compose-dev.ps1 logs -f backend
.\scripts\docker-compose-dev.ps1 stop backend
```

If you need to run migrations manually (e.g., for troubleshooting):
```bash
docker compose --env-file .env -f deploy/compose.yml run --rm migrate
```

Common Docker commands:

```bash
# Start PostgreSQL, Redis, and backend
docker compose --env-file .env -f deploy/compose.yml up -d postgres redis backend

# Run migrations
docker compose --env-file .env -f deploy/compose.yml run --rm migrate

# Rebuild backend and migration images
docker compose --env-file .env -f deploy/compose.yml build backend migrate

# Recreate backend after config changes
docker compose --env-file .env -f deploy/compose.yml up -d backend

# Health check
curl http://localhost:8000/api/health

# Stop backend without deleting volumes
docker compose --env-file .env -f deploy/compose.yml stop backend

# View backend logs
docker compose --env-file .env -f deploy/compose.yml logs -f backend
```

---

## 9. Health Check Commands

```bash
# Backend
curl http://localhost/api/health
# Expected: {"status":"ok"}

# Frontend (public catalog)
curl http://localhost/

# Admin UI
curl http://localhost/admin

# OAuth (if configured)
curl http://localhost/api/auth/me
# Expected: {"user_id":null,"email":null,"role":"guest","is_authenticated":false,"is_owner":false}
```

---

## 10. Smoke Test Checklist

### Public User Flow

- [ ] Browse public catalog (`GET /`)
- [ ] View novel detail (`GET /novel/{slug}`)
- [ ] Read chapter (`GET /novel/{slug}/chapter/{id}`)
- [ ] Login with Google OAuth (`GET /api/auth/google/start`)
- [ ] Add novel to library
- [ ] Track reading progress
- [ ] View reading history
- [ ] Submit review/rating
- [ ] Submit novel request
- [ ] Logout

### Admin Flow

- [ ] Login with owner bootstrap secret (`POST /api/auth/login`)
- [ ] View admin dashboard (`GET /admin`)
- [ ] Create crawl job
- [ ] Create translation job
- [ ] Edit chapter
- [ ] Export novel

---

## 11. Rollback Checklist

### Quick Rollback

```bash
# Stop services
docker-compose down

# Revert to previous image (if using tags)
docker-compose pull
docker-compose up -d

# Rollback database (if needed)
cd backend && alembic downgrade -1
```

### Data Safety

- [ ] PostgreSQL volume persisted (`postgres_data`)
- [ ] Redis volume persisted (`redis_data`)
- [ ] Storage volume mounted (`../storage/novel_library:/app/storage/novel_library`)

---

## 12. Known Limitations

### Current State

- **No separate worker service in Compose** — use in-process worker or run manually
- **No worker health endpoint** — worker runs without dedicated health check

### Future Improvements

- Add separate `worker` service to `deploy/compose.yml`
- Add `/api/worker/health` endpoint
- Add monitoring/alerting for worker failures
