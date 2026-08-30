# =============================================================================
# Stage 1: deps — restore npm cache layer independently
# =============================================================================
FROM node:26.8.1-alpine@sha256:2d984a15c9b54fd0aeb608b8e0d0d83529eb34d2966db27a1fb4f1edc3d298a3 AS deps

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# =============================================================================
# Stage 2: builder — compile Next.js standalone output
# =============================================================================
FROM node:26.8.1-alpine@sha256:2d984a15c9b54fd0aeb608b8e0d0d83529eb34d2966db27a1fb4f1edc3d298a3 AS builder

WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1

# Passed in from compose build args; falls back to the rewrite proxy path
ARG NEXT_PUBLIC_API_BASE_URL=/api
ARG NEXT_PUBLIC_API_URL=
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend ./
# The .next/cache mount keeps the Next.js webpack/compiled cache across
# rebuilds of the same BuildKit daemon (local compose dev/CI retries),
# so unchanged modules do not recompile from scratch.
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=cache,target=/app/frontend/.next/cache \
    npm run build

# =============================================================================
# Stage 3: runner — minimal production image
# =============================================================================
FROM node:26.8.1-alpine@sha256:2d984a15c9b54fd0aeb608b8e0d0d83529eb34d2966db27a1fb4f1edc3d298a3 AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system nodejs && adduser --system --ingroup nodejs nextjs

# The standalone server has no runtime package-manager dependency. Removing
# npm, npx, Corepack, and their package trees keeps the production image
# limited to the Node runtime and the compiled application.
RUN rm -rf \
    /usr/local/lib/node_modules/npm \
    /usr/local/lib/node_modules/corepack \
    /usr/local/bin/npm \
    /usr/local/bin/npx \
    /usr/local/bin/corepack \
    /usr/local/bin/yarn \
    /usr/local/bin/yarnpkg

COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./frontend/.next/static
COPY --from=builder --chown=nextjs:nodejs /app/frontend/public ./frontend/public

USER nextjs

EXPOSE 3000

CMD ["node", "frontend/server.js"]
