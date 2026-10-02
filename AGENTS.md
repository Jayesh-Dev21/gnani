# AGENTS.md — Audio Notes Platform (agent guide)

Task: upload audio → transcript (Gnani ASR) → LLM summary. Next.js frontend, FastAPI
backend, Postgres, object storage, background jobs. Must be reachable at a public URL.

## How To Work

**Do only the task stated in the prompt.** Nothing adjacent, nothing "while we're here". If a
prompt says fix the status transition, the deliverable is the status transition — not a refactor of
the module it lives in, not a new test, not a docs sweep. Adjacent problems get reported, not
fixed.

**Ask a lot of questions first.** Before writing code, resolve what the request actually means:
scope, where logic belongs, which of several designs is intended, what is explicitly out of scope.
Two wrong assumptions implemented quickly cost more than five questions. If a requirement is
ambiguous, ask — do not pick silently and mention the choice afterwards. If the answer is "it
doesn't matter", proceed and note the assumption in one line.

**Plan the whole thing, then build it in small units.** For anything past a trivial change:

1. Restate the goal and the acceptance criteria — what must be observably true when done.
2. Sketch the design end to end (data flow, module boundaries, failure paths) and get it
   confirmed.
3. Then implement one unit at a time, each one coherent and reviewable on its own, keeping the
   tree working between units. Stop at each boundary and check in rather than ploughing through
   the whole plan unasked.

If the plan turns out wrong mid-build, stop and say so instead of quietly improvising a
different design.

## How To Write

Every response follows the **`i-have-adhd`** skill
(`~/.config/opencode/skills/i-have-adhd/SKILL.md`) — read it if any rule below is unclear.

- **Lead with the next action**, not context. The first line must be something the reader can do.
- **Number multi-step work.** One bounded action per step. Fewest steps that still work.
- **End with one concrete next action**, doable in under two minutes.
- **Restate state every turn** — which unit, which step, what just landed. The reader cannot hold
  it in memory between messages. Use the todo tool for anything multi-step.
- **Concrete time estimates.** "About 20 minutes", not "a bit of work".
- **Cap visible lists at five items per group**, most relevant first. Group the rest.
- **Make finished work visible** — say what now works and how to see it, not a recap of edits.
- **Errors are stated flat**: cause and fix. Never "uh oh" or "there seems to be a problem".
- **No preamble, no recap, no closing pleasantries.** No "let me know if", no "hope this helps".
- **Suppress tangents.** Finish the asked task first; raise a second issue once, at the end, as its
  own question.

Keep the build/verify commands tight: `bun run build` ~40s, `docker compose up -d --build` ~3min
on a warm cache. Prefer `timeout 180` over multi-minute waits, and re-run rather than extend.

## Stack

- **Frontend**: Next.js 16 (App Router, Turbopack), React 19, TypeScript, Tailwind v4. Bun as
  package manager. `output: "standalone"` is set — the Dockerfile depends on it.
- **Backend**: FastAPI, Python 3.11, `uv` for deps/venv. No ORM wired yet — and it will be a
  Python ORM: Prisma and Drizzle are TypeScript tools and do not apply to a FastAPI backend.
- **Data**: PostgreSQL 16 (`audio_notes` db). Audio files on local disk under the app for now;
  a real bucket comes later behind the same interface.
- **Auth**: Better Auth, running in Next.js. FastAPI is a resource server that verifies
  Better Auth sessions — it never owns passwords or sessions.
- **Background work**: transcription runs as a job, not in the request. The queue is
  **Procrastinate on Postgres** (psycopg3, retries + task locks) with the worker as its own
  compose service running the same image. Not wired yet. No Redis, no Kafka.

## Dev Commands

```bash
docker compose up -d postgres backend   # postgres + backend only
docker compose up -d                   # adds the frontend, which also binds :3000
docker compose logs -f backend

cd app/frontend
bun dev                             # watch, serves :3000 (stop the compose frontend first)
bun run build                       # typecheck + production build
bun run lint                        # eslint
bun run start:standalone            # run the production build locally
bunx tsc --noEmit                   # typecheck only
bun run db:generate                 # regenerate Better Auth's Drizzle migration
bun run db:migrate                  # apply auth tables (needs Postgres up)

cd app/backend
uv sync                             # deps
uv run uvicorn src.main:app --reload --port 8000
uv run python -c "import src.main"  # import smoke check
```

Env lives in two places, both gitignored, both from `.env.example`: the repo-root `.env` is read
by `docker compose`, and `app/frontend/.env.local` is read by `bun dev`. `BETTER_AUTH_SECRET` must
be a real secret — compose refuses to start without it.

**Before every commit**: `bun run build` (frontend, includes tsc) + `bun run lint`, and the
backend must import cleanly. Testing is explicitly out of scope for now — no test scaffolding,
no new test files.

## Architecture

### Layout

```
app/frontend/app/        routes (App Router). /architecture is a required page.
app/frontend/lib/        api client, auth helpers, types. No logic in components.
app/backend/src/main.py  app assembly + /health. Thin, nothing else.
app/backend/src/modules/<name>/router.py    one folder per feature
app/backend/src/modules/<name>/service.py   the actual logic
app/backend/src/modules/<name>/schemas.py   pydantic in/out models
app/backend/src/db/       db session + schema, once it exists
```

- **Router order matters** in `main.py`: include feature routers before catch-all/`/` routes.
- Routers stay thin: parse input, call one service function, map result/exception to a status.
  No business logic, no `httpx` calls, no SQL.
- Feature code goes in its module. A `services/` grab-bag at the root is where things rot.

### Frontend

- Server components by default. `"use client"` only for interaction (upload, polling, forms).
- All backend calls go through one client in `lib/api.ts`. No `fetch("http://localhost:8000")`
  scattered in components. It attaches the Better Auth session token and the base URL from
  `NEXT_PUBLIC_API_URL`.
- Uploads stream to the backend; **never** through a Next.js server action (body size limits,
  and it would block the request).
- The saved-transcript list is a client-side `localStorage` store behind `useSessions()` in
  `lib/notes.ts` (`useSyncExternalStore`, no effect-driven state). It is a placeholder: unit 2
  swaps the store's internals for `GET /api/notes` and the UI does not change.
- Plain white, no colour: hairlines, uppercase micro-labels, mono metadata. That is the brief,
  not laziness — don't add gradients, shadows or accent colours.
- Light and dark are the same design with different tokens. Every colour is a CSS variable
  (`--paper`, `--ink`, `--muted`, `--rule`) that flips under `[data-theme="dark"]`; `lib/theme.ts`
  owns the toggle and persistence. Never hard-code a hex value in a component, or it will not
  survive the theme flip. Default follows the OS; the user's choice wins once toggled.

### API surface

```
GET    /health                liveness only, no auth, no dependency checks
POST   /api/notes             multipart: file, language_code?, title?   -> 201 Note
GET    /api/notes             -> 200 [NoteSummary]   (bare array, ?limit, newest first)
GET    /api/notes/{id}        -> 200 Note            (the endpoint the client polls)
GET    /api/notes/{id}/audio  -> 200/206 audio       Range requests, for playback
PATCH  /api/notes/{id}        -> 200 Note            rename (title only)
DELETE /api/notes/{id}        -> 204                 also deletes the audio object
POST   /api/notes/{id}/retry  -> 202 Note (queued)   409 unless the note is `failed`
```

`Note`: `id, title, status, filename, content_type, size_bytes, duration_seconds, language_code,
transcript, summary, error, audio_url, created_at, updated_at`. `error` is `null | {code, message}`.
`NoteSummary` (list items) drops `transcript`/`summary` so the list stays cheap. Every route except
`/health` is user-scoped; `404` covers both unknown and not-yours.

### Upload → transcript flow

1. `POST /api/notes` (multipart) → backend validates the file, stores it under a generated key,
   inserts a `notes` row with status `queued`, returns `201` with the note. Nothing waits on ASR.
2. A worker picks up `queued` notes, writes `transcribing` **before** starting, runs the Gnani
   Batch STT flow below, writes the transcript, then writes `ready`.
3. The client polls `GET /api/notes/{id}` (or `GET /api/notes` for the list view) and renders from
   the `status` field. Polling is the source of progress truth — no websockets, no SSE.

**Status values are a closed set**: `queued | transcribing | ready | failed`. `summarising` is not
in the set yet — it arrives with the LLM step, and until then `summary` is always `null`. Never
fake a summary; an empty summary is honest, an invented one is not. Every state transition is
written to the DB before the work starts, so a crashed worker leaves a truthful state rather than a
stuck spinner.

### Gnani ASR (source of truth: <https://docs.gnani.ai/api/STTBatch/Introduction>)

Use **Batch STT**, not `POST /stt/v3`: the synchronous endpoint caps audio at 60s (ideal 30s) and
this app must take a 2-minute recording. Batch takes up to 4 hours per file. The documented
sequence, in order:

```
1. CREATE    POST /stt/v3/batch/jobs              -> 201 job_id, status CREATED
2. START     POST /stt/v3/batch/jobs/{job_id}/start -> 202 status STARTING
3. WAIT      GET  /stt/v3/batch/jobs/{job_id}     poll >= 10s until a terminal status
                                                    (STARTING -> QUEUED -> IN_PROGRESS -> COMPLETED)
4. FILES     GET  /stt/v3/batch/jobs/{job_id}/files -> transcript_url per completed file
5. DOWNLOAD  GET  <transcript_url>                 -> JSON with full_transcript + segments
```

Non-negotiables that follow from those docs: auth is the `X-API-Key-ID` header on every call;
`config` requires `model: "gnani-prisma-v2.5"` and `language_code`; creating a job does **not**
start it (`/start` is required or the job sits in `CREATED` forever); `full_transcript` is not on
the status or files response — only behind `transcript_url`; `transcript_url` expires after 1 hour;
poll no tighter than 10s (30s for big jobs) or we get `429`; terminal statuses include
`PARTIAL_FAILURE`, `START_FAILED` and `CANCELLED`, not just `COMPLETED`/`FAILED`; ITN is not
supported on Batch (so `format=transcribe` equivalents do not apply); diarization is available with
`num_speakers` max 2. Webhooks exist but are explicitly best-effort — polling stays the truth.

`language_code` must be one of `bn-IN, en-IN, hi-IN, kn-IN, ml-IN, mr-IN, ta-IN, te-IN`, or up to
three comma-separated codes for per-file identification (first is the fallback). `gu-IN` and
`pa-IN` are Batch-unsupported — reject them at upload rather than failing the job later.

### Long audio and file transfer

- **No chunking.** Batch STT has no duration cap worth worrying about, so we send whole files.
- **File transfer to Gnani differs by environment, deliberately.** Batch accepts audio two ways:
  direct `multipart` upload (10 MB per file) or a `cloud_storage` source it fetches over HTTP (no
  byte limit). With storage on local disk there is no URL Gnani can reach, so **dev uses the
  multipart path** — which is fine for the 2-minute recordings this task targets. Once a real
  bucket exists, prod switches to `source.type: "cloud_storage"` with a signed URL. One code path
  per environment behind the storage interface, not one compromise path for both.

### Failure handling

The user must always be able to tell what happened. Concretely:

- `failed` rows store `error_code` and `error_message`. The UI shows the message, not a generic
  "something went wrong".
- ASR timeouts are bounded per attempt with retries + backoff; after the last attempt the note
  goes to `failed` rather than hanging. No infinite `queued`, and no note left in `transcribing`.
- A Gnani job that ends `FAILED`/`START_FAILED`/`PARTIAL_FAILURE` is surfaced as our `failed` with
  the reason translated into something a user can act on.
- Worker crashes mid-note are recoverable: a note stuck in a non-terminal state past a timeout is
  reset to `queued` on worker start.
- Storage and DB errors surface as `5xx` with a real message in logs and a generic-but-honest
  message to the client. Never swallow an exception into a `200`.

### Auth (Better Auth in Next, verified by FastAPI)

- Better Auth owns signup/login/session and its own tables (generated by the Better Auth CLI —
  never hand-edit them, and never edit them behind its back).
- FastAPI accepts **only** Better Auth-issued sessions. It verifies the JWT signature against
  Better Auth's JWKS, caches the keys, and rejects anything unknown. It has no password hashing,
  no session table, no login endpoint. If you find yourself adding one, the design has drifted.
- Every DB query in FastAPI is scoped by the verified user id. A user id that arrives in a
  request body is ignored — identity comes from the token only.
- `ENABLE_DEV_AUTH=true` + `X-DEV-USER` header is a **local-dev-only** bypass. It must be
  impossible to enable in production: refuse to start if it is set while `ENV=production`.

## Conventions (would miss without being told)

- **DB migrations are generated, never hand-edited.** Change the schema definition, run the
  generator, commit the migration + snapshots. Editing or deleting an applied migration corrupts
  the chain for everyone. Resetting a dev database means dropping the volume, never rewriting
  history. Backend: SQLAlchemy 2.0 async + Alembic. Auth tables are Better Auth's, generated by
  its CLI into `app/frontend/drizzle/` — same rule, different generator.
- **Audio files live in the bucket, never in the repo or the DB.** DB stores the object key,
  size, duration, mime type. Local disk only as a dev-mode fallback behind the same interface:
  `app/backend/src/storage.py` is the **only** module allowed to build a filesystem path. Before
  production it becomes object storage with short-lived signed URLs, and the browser's `src`
  changes from `/api/notes/{id}/audio` to the signed URL. Nothing else moves.
- **Long audio**: do not add chunking. Batch STT takes whole files up to 4 hours; chunking would
  only add mid-word splice artefacts. The 10 MB per-file cap applies to Gnani's direct multipart
  path in dev, not to cloud-storage source in prod.
- **`/health` is liveness only.** It must not touch Postgres, the bucket, or Gnani — a dependency
  blip should not make Docker restart a healthy API. Readiness is a separate concern; if you add
  dependency checks, they go on a `/ready` route.
- **Env vars** are read through one settings module and validated at startup (`pydantic-settings`
  is already installed). Fail fast on missing config rather than `KeyError` at request time.
- **Errors**: `{ "error": "human readable message" }`. Success payloads carry the resource
  directly. Don't invent a second envelope halfway through.

## Deploy

- `docker compose up -d --build` on a VPS / Render / Railway / Fly. The compose stack is the
  deployable unit — if it only works with extra host commands, the compose file is wrong.
- **TLS is an infra assumption.** The app does not reject HTTP at the application layer;
  termination belongs at the reverse proxy (Caddy/nginx/Cloudflare). All external endpoints must
  be served over HTTPS in production.
- Storage in dev = local disk; in prod = a real bucket. Configured by env, same interface.

## Code Quality Mindset

Every change should be judged against: **is there a way to make this dramatically simpler by
restructuring, rather than polishing?**

- **Delete over rearrange.** Near-identical methods collapse into one parameterised method. A
  file in the wrong place gets moved — don't add a forwarding layer. Dead route files get
  `git rm`'d.
- **Structural simplification over local cleanup.** Don't just rename variables when a layer or
  abstraction should be eliminated. Goal: fewer concepts for the next reader.
- **Be suspicious of growth.** Files crossing ~1k lines, a function past ~210 lines, a new
  boolean flag on an existing function, duplicated branching in adjacent files — these are design
  problems, not style nits. Decompose or collapse; don't add another conditional.
- **Every abstraction earns its keep.** Thin pass-through wrappers and generic handlers that hide
  simple data shapes make the code harder to read. Prefer the direct call.
- **Push logic to its canonical home.** Token handling lives in the auth client, HTTP lives in
  `lib/api.ts`, transcription logic lives in its module. Not scattered, not duplicated.
- **Layer discipline.** Components don't call `fetch` or read env directly. Routers don't do
  business logic. Services don't wrap other services — they're the canonical implementation.
- **Parallelise what's obviously independent.** Sequential awaits on unrelated work are a design
  smell, not just a perf issue.

## Changelog

- `CHANGELOG.md` is updated for every major feature, refactor, or UX change. Not for typo/bump-only
  commits.
- Format: entries prefixed with the commit hash, grouped under `###` category headers, new version
  header per release. Example: `- **abc1234**: Short description of the change`.
