# Changelog

## 0.1.0

### Infrastructure

- **f364284**: Project scaffolding — shared root `.gitignore`, backend Dockerfile (uv, non-root,
  `HEALTHCHECK` on `/health`), frontend Dockerfile (Next standalone output on a Node runtime),
  and a `docker compose` stack wiring postgres → backend → frontend.
- **f364284**: `GET /health` on the FastAPI backend.

### Documentation

- **0f54b3d**: `AGENTS.md` — agent guide covering stack, dev commands, architecture, the API
  surface, the Gnani Batch STT flow and conventions for this repo.

### API

- **35245e2**: Stub note routes — `POST /api/notes`, `GET /api/notes`, `GET /api/notes/{id}`,
  `DELETE /api/notes/{id}`, `POST /api/notes/{id}/retry`. Placeholder responses only: no
  persistence, no auth, no storage. Exists so the frontend can be built against the final
  response shapes.
### Security

- Notes are now owned by a user. FastAPI verifies the Better Auth session JWT against the
  published JWKS (`X-Anonymous` style header guessing is no longer possible), scopes every query
  by the verified user id, and returns `404` for another user's note or audio.
- The saved-transcript list moved out of `localStorage` and into Postgres. Two accounts on one
  machine no longer share transcripts.

### API

- Real persistence: `notes` table via SQLAlchemy 2.0 async and an Alembic migration, with
  `user_id`, status, transcript, summary and error columns.
- Added `PATCH /api/notes/{id}` for renaming, user-scoped `GET /api/notes`, and range streaming
  for `GET /api/notes/{id}/audio`.
- Better Auth gains the `jwt` plugin plus its `jwks` table, and `BETTER_AUTH_TRUSTED_ORIGINS` so
  `127.0.0.1` and LAN origins are accepted like `localhost`.
- CORS origins, dev-auth guard (`ENABLE_DEV_AUTH` refuses to start under `ENV=production`),
  audio fetched with the session token so the player can use it.

### UI

- Theme toggle is now a sun/moon icon instead of LIGHT/DARK text.
- "New recording" opens an empty dashboard: transcript area cleared, composer back in the tray.
- The bottom tray doubles as the playback bar once a transcript is open — the upload controls are
  useless there, so the tray shows the note title, status and the audio player instead.

### UI

- The audio player blends into the page: transparent background, no grey box, tabular mono
  timecodes in both themes.
- `/architecture` rewritten to describe what is actually built: Better Auth with JWT verification
  through JWKS, per-user scoping and 404-instead-of-403, Postgres persistence, local-disk storage
  behind one module, the queue decision, and an explicit section on what is still stubbed.

### UI

- Replaced the native audio element with a custom player: play/pause, seek and volume sliders,
  tabular mono timecode. Chromium paints its own control panel and will not blend it with the
  page, so the controls are ours now and follow the theme in both light and dark.

### UI

- The volume slider is hidden until you hover the volume region (or tab into it), so the tray
  shows just the speaker icon at rest. Tailwind gates `hover:` behind `@media (hover: hover)`,
  which is why the expansion only appears on pointer devices.

### Configuration

- `GNANI_API_KEY` (required), `GNANI_MODEL` and `STT_REST_TIMEOUT_SECONDS` placeholders in
  `.env.example`; the backend refuses to start when the key is blank.
- `app/backend/.env.example` documents every backend setting, including the `AUTH_JWKS_URL` that
  must point at the `frontend` service inside compose and the audience that must match
  `BETTER_AUTH_URL`.
- Compose gained a `migrate` service so Better Auth's tables are applied automatically, and the
  backend derives the asyncpg driver from the shared `DATABASE_URL`.

### Fixes

- The `migrate` compose service ran the frontend's runtime image, which is node-only
  (standalone output) and has no `bun` or `drizzle-kit`. It now builds from a dedicated `migrate`
  stage carrying bun, `node_modules`, `drizzle.config.ts`, the schema and the migration folder, so
  `docker compose up -d` applies Better Auth's tables on a clean machine instead of failing with
  `Cannot find module '/srv/bun'`.

### Features

- Transcription now runs as a queued job instead of inside the upload request.
  `POST /api/notes` writes a `queued` note and returns; a `worker` service
  (same image, `python -m src.worker`) claims it, writes `transcribing`, runs
  Gnani, then writes `ready` or `failed`. Procrastinate on Postgres is the queue,
  so there is no second service to operate. Queue schema is installed by the
  backend's start command, migrations stay in Alembic.
- Gnani integration in `src/modules/transcription/gnani.py`: try the synchronous
  `POST /stt/v3` endpoint, escalate to Batch STT when Gnani reports the audio is
  over its 60 second cap, then poll at 30s, list completed files and download
  `full_transcript`. A 429 from polling, `/start`, or the file listing is waited
  out rather than reported as a failure, and a reattached job found in `CREATED`
  is started, since creating a job does not start it.
- No automatic retries, because a retry after a crash would re-send audio Gnani
  has already billed. Instead every attempt takes a lease on the note
  (`attempt_id`, `lease_expires_at`) and records the provider job it created
  (`provider_job_id`, `provider_submitted_at`). On worker start, notes with an
  expired lease go back to `queued` and are re-deferred with the provider job id
  intact, so the next attempt resumes the same Gnani job instead of paying twice.
  `POST /api/notes/{id}/retry` now accepts a `queued` note too, which is the only
  way to rescue a note whose job died before it was claimed.
- The UI polls the note list every 3 seconds while any note is `queued` or
  `transcribing`, re-reads the open note when its status changes, shows what each
  in-flight state means, and offers Retry on a failed note with the provider's own
  message instead of an error code.
