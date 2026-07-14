# =============================================================================
# Stage 1: deps — restore npm cache layer independently
# =============================================================================
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS deps

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --prefer-offline

# =============================================================================
# Stage 2: builder — compile Next.js standalone output
# =============================================================================
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS builder

WORKDIR /app/frontend
ENV NEXT_TELEMETRY_DISABLED=1

# Passed in from compose build args; falls back to the rewrite proxy path
ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}

COPY --from=deps /app/frontend/node_modules ./node_modules
COPY frontend ./
RUN --mount=type=cache,target=/root/.npm \
    npm run build

# =============================================================================
# Stage 3: runner — minimal production image
# =============================================================================
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS runner

WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --system nodejs && adduser --system --ingroup nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/frontend/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/frontend/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
