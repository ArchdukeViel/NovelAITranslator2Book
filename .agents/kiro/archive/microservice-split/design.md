# Design: Microservice Split

## Overview

Separate the public reader API from the owner admin API into two FastAPI applications within the same repository. Share database, storage, and common code via a `novelai-core` package. Use Caddy as a reverse proxy. Support a `DEPLOY_MODE=monolith` fallback for backward compatibility.

## Architecture

### Affected Files

| File | Change type |
|---|---|
| `backend/src/novelai/main.py` | Refactor — support `DEPLOY_MODE` to load only relevant routers |
| `backend/src/novelai/main_reader.py` | New — FastAPI app for public reader service |
| `backend/src/novelai/main_admin.py` | New — FastAPI app for admin service |
| `backend/src/novelai/common/` | New — shared models, schemas, utilities |
| `deploy/compose.yml` | Update — add reader service, rename backend to admin |
| `deploy/reader.Dockerfile` | New — Dockerfile for reader service |
| `deploy/admin.Dockerfile` | New (rename of backend.Dockerfile) — Dockerfile for admin service |
| `deploy/Caddyfile` | Update — dual-service routing |
| `.github/workflows/ci.yml` | Update — dual build and test |

### Service Boundaries

| Endpoint group | Service | Auth |
|---|---|---|
| `GET /api/public/catalog` | Reader | None |
| `GET /api/public/novels/{slug}` | Reader | None |
| `GET /api/public/novels/{slug}/chapters/{id}` | Reader | None |
| `POST /api/admin/novels` | Admin | Owner |
| `POST /api/admin/novels/{id}/scrape` | Admin | Owner |
| `POST /api/admin/novels/{id}/translate` | Admin | Owner |
| `POST /api/admin/novels/{id}/glossary` | Admin | Owner |
| `GET /api/admin/novels/{id}` | Admin | Owner |
| `GET /api/admin/health/errors` | Admin | Owner |

### Files Not Touched

- Frontend — no change (frontend already calls the correct endpoints)
- DB models — shared via `novelai-core`
- Alembic migrations — shared
- Pipeline stages — no change
- Source adapters — no change

## Component Design

### 1. Shared `novelai-core` Package

Create `backend/src/novelai_core/` with `setup.py` or `pyproject.toml`:

```
novelai_core/
  __init__.py
  models/            # SQLAlchemy models (Novel, Chapter, User, etc.)
  schemas/           # Pydantic response/request models
  storage/           # StorageService (shared filesystem access)
  db/                # DB engine, session helpers
```

Both services install `novelai-core` as a dependency:

```bash
pip install -e ./backend/src/novelai_core
```

### 2. Service Entry Points

**`main_reader.py`** — Public reader service on port 8001:

```python
from fastapi import FastAPI
from novelai_core.db.engine import engine

app = FastAPI(title="NovelAI Reader", version="1.0.0")

@app.on_event("startup")
async def startup():
    # Read-only DB connection
    pass

@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()

# Register only public routers
from novelai.api.routers.public import router as public_router
app.include_router(public_router, prefix="/api/public")
```

**`main_admin.py`** — Admin service on port 8000:

```python
from fastapi import FastAPI
from novelai_core.db.engine import engine

app = FastAPI(title="NovelAI Admin", version="1.0.0")

# Register admin routers
from novelai.api.routers.library import router as library_router
from novelai.api.routers.operations import router as operations_router
from novelai.api.routers.admin import router as admin_router
from novelai.api.routers.health import router as health_router

app.include_router(library_router, prefix="/api/admin")
app.include_router(operations_router)
app.include_router(admin_router, prefix="/api/admin")
app.include_router(health_router, prefix="/api/admin")
```

**`main.py`** — Monolith (default, backward compatible):

```python
app = FastAPI(title="NovelAI")
app.include_router(public_router, prefix="/api/public")
app.include_router(library_router, prefix="/api/admin")
# ... all other routers
```

### 3. Caddyfile Routing

```
reader.novelai.localhost {
    reverse_proxy reader:8001 {
        health_uri /api/public/health
        health_interval 10s
    }
    rate_limit {
        zone dynamic 10r/s
    }
}

admin.novelai.localhost {
    reverse_proxy admin:8000 {
        health_uri /api/admin/health
        health_interval 10s
    }
    rate_limit {
        zone dynamic 5r/s
    }
}
```

### 4. Docker Compose (`compose.yml`)

```yaml
services:
  admin:
    build:
      context: ..
      dockerfile: deploy/admin.Dockerfile
    ports:
      - "8000:8000"
    env_file: .env
    volumes:
      - ../storage:/app/storage

  reader:
    build:
      context: ..
      dockerfile: deploy/reader.Dockerfile
    ports:
      - "8001:8001"
    env_file: .env
    volumes:
      - ../storage:/app/storage (read-only ideally)

  caddy:
    image: caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
```

### 5. `DEPLOY_MODE` Support

In the CLI entry point (`novelaibook web`):

```python
def main():
    deploy_mode = os.environ.get("DEPLOY_MODE", "monolith")
    if deploy_mode == "split":
        import uvicorn
        import multiprocessing
        p1 = multiprocessing.Process(target=run_admin)
        p2 = multiprocessing.Process(target=run_reader)
        p1.start()
        p2.start()
        p1.join()
        p2.join()
    else:
        run_monolith()
```

## Migration and Backward Compatibility

- `DEPLOY_MODE=monolith` preserves the exact current behavior.
- Existing Docker Compose configuration still works (single service).
- No API contract changes. All existing endpoints remain at the same paths.
- Alembic migrations remain in a single location and are applied once.
- The split is opt-in: operators can deploy as monolith or split based on their needs.

## Acceptance Criteria

1. With `DEPLOY_MODE=monolith`, all existing functionality works identically.
2. With `DEPLOY_MODE=split`, public endpoints are served by `main_reader.py` on port 8001 and admin endpoints by `main_admin.py` on port 8000.
3. Caddy correctly routes `/api/public/*` to the reader service and `/api/admin/*` to the admin service.
4. Both services can start independently and share the same database and storage.
5. CI builds and tests both services.
6. Rate limits apply independently to each service.
