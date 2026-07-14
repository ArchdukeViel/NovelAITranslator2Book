# =============================================================================
# Stage 1: Builder — install deps into an isolated prefix
# =============================================================================
FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS builder

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
    pip install ".[documents,gemini,db,worker,auth]"

# Copy remaining backend artifacts (alembic, tests, sql) after deps are cached
COPY backend ./backend

# =============================================================================
# Stage 2: Runtime — lean image, no build tools
# =============================================================================
FROM python:3.13-slim@sha256:eb43ff125d8d58d7449dcba7d336c23bcac412f526d861db493b9994d8010280 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8001 \
    NOVEL_LIBRARY_DIR=/app/storage/novel_library

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libffi8 curl \
    && rm -rf /var/lib/apt/lists/* \
    && addgroup --system novelai \
    && adduser --system --ingroup novelai --no-create-home novelai

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/backend ./backend
COPY pyproject.toml readme.md ./

RUN mkdir -p /app/storage/novel_library \
    && chown -R novelai:novelai /app/storage

USER novelai

EXPOSE 8001

ENTRYPOINT ["novelai", "reader", "--host", "0.0.0.0", "--port", "8001"]
