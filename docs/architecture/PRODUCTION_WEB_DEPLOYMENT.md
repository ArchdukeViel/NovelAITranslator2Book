# Production Web Deployment

Production-style deployment keeps the public/admin frontend and backend API as separate processes behind one domain.

```text
https://yourdomain.com/          -> Next.js frontend
https://yourdomain.com/admin     -> Next.js admin workspace
https://yourdomain.com/novel/... -> Next.js public reader
https://yourdomain.com/api/...   -> FastAPI backend
```

## Local Development

Run the backend:

```powershell
novelaibook web
```

Run the frontend:

```powershell
cd frontend
npm install
npm run dev
```

The frontend defaults to `NEXT_PUBLIC_API_BASE_URL=/api`. In local split development, set:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000/api
```

## Backend API

FastAPI now exposes the same router at both:

- `/novels/...` for backward compatibility
- `/api/novels/...` for production reverse-proxy routing

Health check:

```text
GET /api/health
```

## Frontend Structure

```text
frontend/
  app/
    (public)/
      novel/[slug]/
      novel/[slug]/chapter/[chapterId]/
    (admin)/
      admin/dashboard/
      admin/crawler/
      admin/translation/
      admin/requests/
      admin/editor/
      admin/settings/
  components/
  lib/
  server/
```

## Reverse Proxy

Use the example Caddy config at `deploy/Caddyfile.example`.

For a public WTR-style deployment, run:

- Next.js frontend on `127.0.0.1:3000`
- FastAPI backend on `127.0.0.1:8000`
- Durable runtime storage mounted at `storage/novel_library` or configured with `NOVEL_LIBRARY_DIR`
- Caddy/Nginx/Cloudflare routing `/api/*` to FastAPI and everything else to Next.js

## Later Hardening

- Move durable state from JSON files to PostgreSQL.
- Move jobs to Redis/RQ, Celery, or Dramatiq.
- Run crawler/translator workers separately from the API process.
- Put source images/assets behind object storage and a CDN.
- Require `WEB_API_KEY` and HTTPS for admin endpoints.
