# =============================================================================
# Stage 1: Builder — install deps into an isolated prefix
# =============================================================================
FROM python:3.14.7-slim@sha256:cae66f2ef0ec51a9891263eeee7f987dacf0a9879e8aa9353d5606e0530619a5 AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed to install — tests/alembic/sql excluded for cache efficiency
COPY pyproject.toml readme.md ./
COPY backend/src ./backend/src
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[gemini,db,worker,auth]"

# Copy remaining backend artifacts (alembic, sql) after deps are cached — src already present
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/alembic ./backend/alembic
COPY backend/sql ./backend/sql

# =============================================================================
# Stage 2: Runtime — lean image, no build tools
# =============================================================================
FROM python:3.14.7-slim@sha256:cae66f2ef0ec51a9891263eeee7f987dacf0a9879e8aa9353d5606e0530619a5 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8001 \
    RUNTIME_DIR=/app/data/runtime

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi8 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system novelai \
    && adduser --system --ingroup novelai --no-create-home novelai

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/backend ./backend
COPY pyproject.toml readme.md ./

RUN mkdir -p /app/data/runtime \
    && chown -R novelai:novelai /app/data

USER novelai

EXPOSE 8001

ENTRYPOINT ["novelai", "reader", "--host", "0.0.0.0", "--port", "8001"]
