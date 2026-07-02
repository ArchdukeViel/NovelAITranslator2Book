# Stage 1: Builder
FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --upgrade pip

COPY pyproject.toml readme.md ./
COPY backend ./backend

RUN python -m pip install --no-cache-dir ".[documents,gemini,db,worker,auth]"

# Stage 2: Runtime
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/backend ./backend
COPY pyproject.toml readme.md ./

ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8000
ENV NOVEL_LIBRARY_DIR=/app/storage/novel_library

RUN mkdir -p /app/storage

EXPOSE 8000

ENTRYPOINT ["novelai", "web", "--host", "0.0.0.0", "--port", "8000"]
