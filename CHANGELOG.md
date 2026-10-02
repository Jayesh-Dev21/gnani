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
