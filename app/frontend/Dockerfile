FROM oven/bun:1.3.5 AS deps

WORKDIR /srv

COPY package.json bun.lock ./

RUN bun install --frozen-lockfile

# One-shot stage for applying Better Auth's Drizzle migrations. The runtime image
# is node-only (standalone output), so drizzle-kit needs its own stage.
FROM oven/bun:1.3.5 AS migrate

WORKDIR /srv

COPY --from=deps /srv/node_modules ./node_modules
COPY package.json drizzle.config.ts ./
COPY lib/db ./lib/db
COPY drizzle ./drizzle

CMD ["bun", "run", "db:migrate"]

FROM node:22-bookworm-slim AS builder

WORKDIR /srv

ENV NEXT_TELEMETRY_DISABLED=1

# Build arg from docker-compose (falls back to localhost for local builds).
# Must be mapped into ENV: a bare ARG is invisible to `next build`, which reads
# process.env, so without this line every image bakes in localhost and browsers
# outside the build host fail with "NetworkError when attempting to fetch resource".
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY --from=deps /srv/node_modules ./node_modules
COPY . .

RUN node node_modules/next/dist/bin/next build

FROM node:22-alpine AS runtime

WORKDIR /srv

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

RUN addgroup --gid 1001 --system app \
    && adduser --uid 1001 --system --ingroup app --shell /usr/sbin/nologin nextjs

COPY --from=builder --chown=nextjs:app /srv/public ./public
COPY --from=builder --chown=nextjs:app /srv/.next/standalone ./
COPY --from=builder --chown=nextjs:app /srv/.next/static ./.next/static

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]