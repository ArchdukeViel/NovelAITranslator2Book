# Getting Started with Novel AI

This guide walks through the web-first setup for Novel AI: FastAPI backend, Next.js frontend, local storage, optional worker, and production-style deployment.

The commands are written for PowerShell on Windows because this workspace is currently on Windows. The same flow works on other platforms with equivalent shell syntax.

Current mode is single-owner / controlled-admin. The backend has scheduler-enabled admin-owned provider/model routing and baseline owner/admin security hardening. Database storage (Supabase PostgreSQL 16) and public user auth are implemented. Public contribution credentials, batch mode, billing, organizations, and multi-admin teams are not implemented.

## 1. What You Are Running

Local development uses separate processes:

```text
Next.js frontend  http://127.0.0.1:3000
FastAPI backend   http://127.0.0.1:8000
Local storage     storage/novel_library
Optional worker   novelaibook worker
```

In production style, Caddy or another reverse proxy serves one domain:

```text
/api/* -> FastAPI backend
/*     -> Next.js frontend
```

## 2. Prerequisites

Install:

- Python 3.13 or newer
- Node.js LTS with npm
- Git
- Docker Desktop, only if you want the production-like Compose run
- Gemini API key for primary real translation
- NVIDIA API key if you want the Gemma fallback provider

Check versions:

```powershell
py --version
node --version
npm --version
git --version
```

If `npm` is not recognized after installing Node.js, reopen PowerShell. If it still fails, temporarily add Node.js to the current shell:

```powershell
$env:Path = "C:\Program Files\nodejs;" + $env:Path
```

## 3. Install Backend

From the repository root:

```powershell
cd "C:\Akmal\Novel AI"

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[documents,gemini,dev,db,worker]"
```

Activate the virtual environment when working manually:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. Install Frontend

```powershell
cd "C:\Akmal\Novel AI\frontend"
npm install
```

The frontend stack is:

- Next.js App Router
- TypeScript
- Tailwind CSS
- shadcn/ui-style primitives
- TanStack Query
- Zustand

## 5. Configure Backend

Create `.env`:

```powershell
cd "C:\Akmal\Novel AI"
Copy-Item .env.example .env
```

Useful local values:

```env
NOVEL_LIBRARY_DIR=storage/novel_library
PROVIDER_DEFAULT=gemini
PROVIDER_GEMINI_API_KEY=your_gemini_key_here
NVIDIA_API_KEY=your_nvidia_key_here
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
NVIDIA_DEFAULT_MODEL=google/gemma-4-31b-it
TRANSLATION_TARGET_LANGUAGE=English
LOG_LEVEL=INFO
WEB_RATE_LIMITER_BACKEND=memory
DATABASE_URL=postgresql+psycopg://novelai:novelai@localhost:5432/novelai
REDIS_URL=redis://localhost:6379/0
```

Start PostgreSQL and Redis via Docker (required for the `db` extra):

```powershell
docker compose -f deploy/compose.yml up -d postgres redis
```

Run database migrations:

```powershell
.\.venv\Scripts\alembic -c backend/alembic.ini upgrade head
```

Optional Google OAuth for public login (disabled unless all three are set):

```env
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-google-client-secret
GOOGLE_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/api/auth/google/callback
PUBLIC_FRONTEND_URL=http://127.0.0.1:3000
```

Admin API protection is controlled by `WEB_API_KEY`.

- Leave it unset for local development without bearer auth.
- Set it in production.
- If set, add the same token in `/admin/settings`.

Provider API keys are runtime secrets. They should come from `.env` or the process environment, not committed files.

## 6. Configure Frontend

For local development, the frontend uses `/api` and proxies to the backend through `BACKEND_API_URL`.

`frontend/.env.local` is optional. If needed:

```env
NEXT_PUBLIC_API_BASE_URL=/api
BACKEND_API_URL=http://127.0.0.1:8000
```

## 7. Run Local Development

Terminal 1, backend:

```powershell
cd "C:\Akmal\Novel AI"
novelaibook web --reload
```

Terminal 2, frontend:

```powershell
cd "C:\Akmal\Novel AI\frontend"
npm run dev
```

Terminal 3, optional worker:

```powershell
cd "C:\Akmal\Novel AI"
novelaibook worker
```

Open:

```text
http://127.0.0.1:3000/admin
```

Health check:

```text
http://127.0.0.1:8000/api/health
```

## 8. Admin Workflow

Use the web UI for daily work:

1. `/admin/dashboard`: operational home, worker state, queue snapshot, and recent jobs.
2. `/admin/settings`: API token state, dummy API mode, and backend health.
3. `/admin/crawler`: queue source crawls, run direct scrapes, import documents, and inspect quick source health.
4. `/admin/translation`: queue translations, run direct translations, view progress, and download exports.
5. `/admin/activity`: inspect queued, running, paused, failed, completed, and cancelled crawler/translation activity.
6. `/admin/activity/[activityId]`: inspect activity payloads, errors, scheduler progress, and provider/model state.
7. `/admin/editor`: review source/translation text, create manual edit versions, and roll back active versions.
8. `/admin/requests`: inspect reader/admin novel requests.

Public reader routes:

```text
/                              — public catalog home
/novels/[slug]                  — novel detail
/novels/[slug]/chapter/[chapterId] — chapter reader
/account/history               — reading history (authenticated)
/account/requests              — novel/chapter requests (authenticated)
/account/contribute            — contribution (gated/unavailable)
```

Public users can log in with Google OAuth, save novels to their library, track reading progress, view reading history, rate/review novels, and submit novel/chapter requests. Contribution credentials remain gated and unavailable.

The reader stores theme, font size, and width preferences in the frontend state.

## 9. First Example Flow

1. Start backend and frontend.
2. Open `/admin/settings`.
3. Add a real API token, or click the dummy API button for UI-only testing.
4. Open `/admin/crawler`.
5. Select a source such as `syosetu_ncode`.
6. Enter the novel ID or URL required by the source adapter.
7. Queue metadata and chapter crawls.
8. Open `/admin/activity` and run a worker if activity remains pending.
9. Open `/admin/translation`.
10. Queue translation for a chapter range such as `1-3`.
11. Open `/admin/editor` to review and edit output.
12. Open the public reader route for the novel.
13. Export EPUB, HTML, or Markdown from the translation page when chapters are ready.

## 10. Production-Style Local Run

The production-like files are under `deploy/`:

```text
deploy/
  compose.yml
  Caddyfile
  backend.Dockerfile
  frontend.Dockerfile
  .env.production.example
```

Create production env:

```powershell
cd "C:\Akmal\Novel AI"
Copy-Item deploy\.env.production.example deploy\.env.production
notepad deploy\.env.production
```

Set at least:

```env
PUBLIC_HTTP_PORT=8080
PROVIDER_DEFAULT=gemini
PROVIDER_GEMINI_API_KEY=your_gemini_key_here
WEB_API_KEY=replace_with_a_long_random_admin_token
NOVEL_LIBRARY_DIR=storage/novel_library
```

Run:

```powershell
docker compose --env-file deploy\.env.production -f deploy\compose.yml up --build
```

Open:

```text
http://127.0.0.1:8080/admin
```

If `WEB_API_KEY` is set, add it in `/admin/settings` so browser requests include the bearer token.

## 11. Verification Commands

Backend:

```powershell
cd "C:\Akmal\Novel AI"
pytest --tb=short -q
pyright
```

Frontend:

```powershell
cd "C:\Akmal\Novel AI\frontend"
npm run typecheck
npm run build
```

Run a single API-focused test file:

```powershell
pytest --tb=short -q backend/tests/test_web_api.py
```

## 12. Troubleshooting

Port 8000 already in use:

```powershell
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
  Select-Object LocalAddress,LocalPort,State,OwningProcess
```

Stop the old process, or run the backend on another port if the launcher supports it.

Port 3000 already in use:

```powershell
cd frontend
npm run dev -- -p 3001
```

`npm` not recognized:

- Reinstall or repair Node.js LTS.
- Reopen PowerShell.
- Check `C:\Program Files\nodejs` is on `PATH`.

Unstyled frontend or broken hot reload:

```powershell
cd frontend
npm install
npm run dev
```

Then hard-refresh the browser. If the dev server was started before dependencies were installed, restart it.

API calls return `401`:

- `WEB_API_KEY` is set on the backend.
- Add the same value in `/admin/settings`.
- For local no-auth development, unset `WEB_API_KEY` and restart the backend.

No real translation output:

- Check provider keys in `.env`.
- Check `PROVIDER_DEFAULT`.
- Use dummy provider only for UI and workflow testing.

---

## 13. Production Deployment Appendix

### Required Production Environment Variables

See `.env.example` for full reference.

| Variable | Required | Notes |
|---|---|---|
| `ENV=production` | Yes | Enables `https_only` cookies, session secret fail-closed |
| `SESSION_SECRET_KEY` | **Yes** | Strong random secret; app refuses to start if default |
| `OWNER_BOOTSTRAP_SECRET` | Yes | Owner login secret; never commit real value |
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:***@host:5432/dbname` |
| `REDIS_URL` | Yes | `redis://host:6379/0` |
| `PROVIDER_GEMINI_API_KEY` | If using Gemini | Translation provider key |
| `WEB_API_KEY` | Recommended | Bearer token for admin API |

### Google OAuth Setup

**Google Cloud Console**: Create OAuth 2.0 Client ID (Web application). Add redirect URIs:
- Dev: `http://127.0.0.1:8000/api/auth/google/callback`
- Prod: `https://yourdomain.com/api/auth/google/callback`

URI must match `GOOGLE_OAUTH_REDIRECT_URI` exactly.

### Auth Email Modes

| Mode | What happens |
|---|---|
| `AUTH_EMAIL_DELIVERY_MODE=noop` (default) | Tokens created but no email sent. Safe for dev. |
| `AUTH_EMAIL_DELIVERY_MODE=smtp` | Real email. Requires SMTP_HOST, SMTP_PORT, SMTP_FROM_EMAIL. |

### Session & CSRF

- `ENV=production` → session cookies are HTTPS-only
- `SESSION_SECRET_KEY` must be strong and secret
- CSRF: `GET /api/auth/csrf` → token, send as `X-CSRF-Token` header on mutations
- `WEB_CORS_ORIGINS=[]` (default) for same-origin behind Caddy

### Database Migrations

```bash
cd backend
alembic upgrade head
alembic current   # verify current revision: bb48b53baff5_initial_schema
```

### Service Startup Order (Docker Compose)

```text
postgres → redis → migrate → backend → frontend → caddy
```

The `migrate` service runs `alembic upgrade head` automatically.

### Quick Production Start

```bash
cp .env.example .env
# Edit .env with production values
cp deploy/Caddyfile.example deploy/Caddyfile
# Edit Caddyfile with your domain
docker compose --env-file .env -f deploy/compose.yml up -d
```

### Health Checks

```bash
curl http://localhost/api/health
# Expected: {"status":"ok"}
curl http://localhost/
curl http://localhost/api/auth/me
# Expected: {"user_id":null,"email":null,"role":"guest","is_authenticated":false,"is_owner":false}
```

### Smoke Test Checklist

**Public flow**: Browse catalog → novel detail → read chapter → login (Google OAuth) → add to library → track progress → review → logout.

**Admin flow**: Login → dashboard → create crawl → create translation → edit chapter → export.

### Rollback

```bash
docker compose down
docker compose pull      # revert to previous image
docker compose up -d
# Database: cd backend && alembic downgrade -1
```

### Known Limitations

- No separate worker service in Compose — use in-process worker or run manually
- No worker health endpoint

Docker command missing:

- Install Docker Desktop.
- Reopen PowerShell after installation.
- Make sure Docker Desktop is running before Compose.

## 13. Storage Location

Runtime files are written under:

```text
storage/novel_library
```

This includes novel metadata, chapter bundles, translation versions, edit history, jobs, requests, usage logs, assets, and exports.
Scheduler state, provider request records, chunk output records, fetch cache entries, and other runtime traceability records are also stored under this runtime root.

See [../reference/data-output-structure.md](../reference/data-output-structure.md) for the file-level reference.

## 14. Next Reading

- [../architecture/architecture.md](../architecture/architecture.md)
- [../reference/data-output-structure.md](../reference/data-output-structure.md)
- [../reference/python-commands.md](../reference/python-commands.md)
