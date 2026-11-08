# ==============================================================================
# PharmaPredict AI — Next.js Frontend Multi-Stage Production Dockerfile
# Hardened non-root alpine container for pharmaceutical enterprise deployments.
# ==============================================================================

# 1. Base stage: Node.js 20 LTS Alpine with package manager
FROM node:20-alpine AS base
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@12.3.4 --activate
ENV NEXT_TELEMETRY_DISABLED=1

# 2. Dependencies stage: Install node_modules
FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile --prod=false

# 3. Builder stage: Build Next.js application with standalone bundle
FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_OUTPUT_STANDALONE=true
ENV NODE_ENV=production
RUN pnpm run build

# 4. Production Runner stage: Minimal, secure, non-root execution
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root system user and group
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy public assets and built standalone server
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

# Container health probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]

