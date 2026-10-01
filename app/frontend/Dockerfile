FROM oven/bun:1.3.5 AS deps

WORKDIR /srv

COPY package.json bun.lock ./

RUN bun install --frozen-lockfile

FROM node:22-bookworm-slim AS builder

WORKDIR /srv

ENV NEXT_TELEMETRY_DISABLED=1 \
    NEXT_PUBLIC_API_URL=http://localhost:8000

ARG NEXT_PUBLIC_API_URL

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