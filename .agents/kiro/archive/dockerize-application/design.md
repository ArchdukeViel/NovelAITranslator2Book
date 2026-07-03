# Design: Dockerize Application

## Overview

Create multi-stage Dockerfiles for the backend and frontend, a Docker Compose configuration for the full stack (backend, frontend, PostgreSQL, Caddy), and development overrides. The existing `deploy/` directory structure is used.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `deploy/backend.Dockerfile` | Create/update — multi-stage Python image |
| `deploy/frontend.Dockerfile` | Create/update — multi-stage Next.js image |
| `deploy/compose.yml` | Update — full stack with healthchecks |
| `deploy/compose.dev.yml` | New — development overrides |
| `.dockerignore` | Update — exclude unnecessary files |
| `deploy/.env.example` | Update — all required variables |

### Files Not Touched

- Application source code — no changes
- `pyproject.toml` — no changes
- `next.config.mjs` — no changes (may add `output: "standalone"`)

## Component Design

### 1. Backend Dockerfile (`deploy/backend.Dockerfile`)

```dockerfile
# Stage 1: Builder
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.lock .
RUN pip install --no-cache-dir --user -r requirements.lock

# Install the package
COPY pyproject.toml .
COPY backend/src/ ./backend/src/
RUN pip install --no-cache-dir --user -e .


# Stage 2: Runtime
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application config and entrypoint
COPY pyproject.toml .
COPY alembic.ini .
COPY backend/src/ ./backend/src/
COPY backend/alembic/ ./backend/alembic/

RUN mkdir -p /app/storage /app/storage_backups

EXPOSE 8000

ENV STORAGE_PATH=/app/storage/novel_library
ENV STAGE=production

ENTRYPOINT ["novelai", "web", "--host", "0.0.0.0", "--port", "8000"]
```

### 2. Frontend Dockerfile (`deploy/frontend.Dockerfile`)

```dockerfile
# Stage 1: Builder
FROM node:20-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

ARG NEXT_PUBLIC_API_URL=http://backend:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build


# Stage 2: Runtime
FROM node:20-alpine AS runtime

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/next.config.mjs ./
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
```

### 3. Docker Compose (`deploy/compose.yml`)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME:-novelai}
      POSTGRES_USER: ${DB_USER:-novelai}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-novelai}
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-novelai}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - novelai-net
    restart: unless-stopped

  backend:
    build:
      context: ..
      dockerfile: deploy/backend.Dockerfile
    environment:
      DATABASE_URL: postgresql://${DB_USER:-novelai}:${DB_PASSWORD:-novelai}@db:5432/${DB_NAME:-novelai}
      JWT_SECRET_KEY: ${JWT_SECRET_KEY}
      STORAGE_PATH: /app/storage/novel_library
    volumes:
      - storage_data:/app/storage
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/public/catalog"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - novelai-net
    restart: unless-stopped

  frontend:
    build:
      context: ..
      dockerfile: deploy/frontend.Dockerfile
      args:
        NEXT_PUBLIC_API_URL: http://backend:8000
    depends_on:
      - backend
    networks:
      - novelai-net
    restart: unless-stopped

  caddy:
    image: caddy:2-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on:
      - backend
      - frontend
    networks:
      - novelai-net
    restart: unless-stopped

volumes:
  db_data:
  storage_data:
  caddy_data:

networks:
  novelai-net:
    driver: bridge
```

### 4. Development Override (`deploy/compose.dev.yml`)

```yaml
services:
  backend:
    volumes:
      - ../backend/src:/app/backend/src:ro
      - storage_data:/app/storage
    command: novelai web --host 0.0.0.0 --port 8000 --reload
    environment:
      STAGE: development

  frontend:
    volumes:
      - ../frontend:/app:ro
      - /app/node_modules
    command: npm run dev
    environment:
      NODE_ENV: development
```

Usage: `docker compose -f deploy/compose.yml -f deploy/compose.dev.yml up`

### 5. `.dockerignore`

```
__pycache__/
*.pyc
.venv/
env/
.git/
.hypothesis/
.ruff_cache/
.mypy_cache/
.pytest_cache/
node_modules/
.next/
frontend/
storage/
storage_backups/
novels/
tmp/
*.md
!readme.md
```

## Migration and Backward Compatibility

- Existing deployment scripts (`docker-compose-dev.ps1`) continue to work if the file paths remain.
- The existing `deploy/` directory structure is preserved.
- Docker images are additive; non-Docker development workflows are unaffected.

## Acceptance Criteria

1. `docker compose -f deploy/compose.yml up -d` starts all 4 services.
2. `docker compose ps` shows all services healthy.
3. `curl http://localhost:8000/api/public/catalog` returns a valid JSON response.
4. `curl http://localhost:3000` returns the frontend HTML.
5. `docker compose exec backend novelai create-user` creates a user.
6. Backend image is under 500 MB (`docker images` confirms).
7. `docker compose -f deploy/compose.yml -f deploy/compose.dev.yml up` enables hot-reload.
