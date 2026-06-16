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
| `PUBLIC_FRONTEND_URL` | For public login | Frontend origin for post-OAuth redirect |
| `WEB_CORS_ORIGINS` | If cross-origin | Empty list (default) for same-origin behind Caddy |
| `WEB_RATE_LIMITER_BACKEND` | Recommended | `redis` for multi-instance; `memory` for single |
| `PROVIDER_GEMINI_API_KEY` | If using Gemini | Translation provider key |
| `PROVIDER_OPENAI_API_KEY` | If using OpenAI | Translation provider key |

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

## 3. HTTPS / Caddy / Reverse Proxy Checklist

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

## 4. Session Cookie / CSRF Checklist

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

## 5. Database Migration Checklist

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

## 6. Redis / Worker Checklist

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

## 7. Service Startup Order (Docker Compose)

1. `postgres` — PostgreSQL (health check required)
2. `redis` — Redis (health check required)
3. **Run migrations manually**: `docker-compose exec backend alembic upgrade head`
4. `backend` — FastAPI (depends on postgres, redis)
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

# 3. Start services
docker-compose up -d

# 4. Run migrations
docker-compose exec backend alembic upgrade head

# 5. Verify
curl http://localhost/api/health
# Should return: {"status":"ok"}
```

---

## 8. Health Check Commands

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

## 9. Smoke Test Checklist

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

## 10. Rollback Checklist

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

## 11. Known Limitations

### Current State (DEP1B)

- **No automated migration runner** — migrations must be run manually after starting backend
- **No separate worker service in Compose** — use in-process worker or run manually
- **No worker health endpoint** — worker runs without dedicated health check

### Future Improvements

- Add init container or entrypoint script for automatic migrations
- Add separate `worker` service to `deploy/compose.yml`
- Add `/api/worker/health` endpoint
- Add monitoring/alerting for worker failures
