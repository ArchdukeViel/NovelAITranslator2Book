# =============================================================================
# Stage 1: deps — restore npm cache layer independently
# =============================================================================
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS deps

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# =============================================================================
# Stage 2: builder — compile Next.js standalone output
# =============================================================================
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS builder

WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1

# Passed in from compose build args; falls back to the rewrite proxy path
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

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
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS runner

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
