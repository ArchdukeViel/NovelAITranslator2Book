# =============================================================================
# Stage 1: Builder — install deps into an isolated prefix
# =============================================================================
FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS builder

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
    pip install ".[documents,gemini,db,worker,auth,s3]"

# Copy remaining backend artifacts (alembic, sql) after deps are cached — src already present
COPY backend/alembic.ini ./backend/alembic.ini
COPY backend/alembic ./backend/alembic
COPY backend/sql ./backend/sql

# =============================================================================
# Stage 2: Runtime — lean image, no build tools
# =============================================================================
FROM python:3.14.6-slim@sha256:7bec7ddcddeff7975d6ba9b4be7dd6f6b2f55e7491539145e2978f7f97ce9144 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8000 \
    NOVEL_LIBRARY_DIR=/app/storage/novel_library

WORKDIR /app

# Keep the runtime client above the CVE-2026-6473 fix level. The exact
# PGDG version is available for the Debian 13 image used by this release.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi8 curl ca-certificates gnupg \
    && install -d /usr/share/postgresql-common/pgdg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
       | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg \
    && . /etc/os-release \
    && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
       > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-18=18.6-1.pgdg13+2 \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system novelai \
    && adduser --system --ingroup novelai --no-create-home novelai

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/backend ./backend
COPY pyproject.toml readme.md ./

RUN mkdir -p /app/storage/novel_library \
    && chown -R novelai:novelai /app/storage

USER novelai

EXPOSE 8000

CMD ["novelai", "web", "--host", "0.0.0.0", "--port", "8000"]
